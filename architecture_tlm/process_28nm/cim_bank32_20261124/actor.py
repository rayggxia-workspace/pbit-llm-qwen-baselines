"""Single-zone actor with explicit capture, FIFO retirement and clock contracts."""
from collections import Counter, deque
from architecture_tlm.unified_v6.shared_memory import Signal, align_time
from alignment import cycles, tile_identity, transfer


def program(self, core, layer, mode, out, k):
    assert self.cim_states[core]=='free' and not self.cim_compute_busy[core]
    blocks=self.model['hidden' if mode=='GU' else 'ffn']//64
    tile=tile_identity(self,layer,mode,out,k,blocks)
    self.cim_tiles[core]=tile; self.cim_states[core]='loading'
    self.cim_rng_ready[core]=self.rng_assignments.request(tile,core)
    spans=self._weight_spans(layer,mode,out,k)
    assert sum(n for _,n in spans)==8192
    self.alignment_events.emit('weight_load_begin',tile,core,bytes=8192,resource='CIM')
    yield from self.h.fetch('CIM_core'+str(core),spans[0][0],8192,
        self.cim_weight[core],0,'GU_weights' if mode=='GU' else 'down_weights',spans=spans)
    self.cim_states[core]='ready'
    self.alignment_events.emit('weight_ready',tile,core,bytes=8192,resource='CIM')


def prefetch_gu(self,layer):
    tiles,_,_=self._tiles('GU')
    def one(core):
        out,k=tiles[core]
        yield from program(self,core,layer,'GU',out,k)
        self.common_prefetched.add((layer,core,out,k))
    yield from self._parallel([one(i) for i in range(min(self.common_cores,len(tiles)))])


def common_stage(self,layer,mode):
    service=self.p28_cim_binding['FFN_core']['modes'][mode]
    cfg=self.alignment; e=self.alignment_events; result=self.result_slots
    tiles,outs,blocks=self._tiles(mode); tasks=deque(enumerate(tiles)); n=len(tiles)
    h=self.h; ready={}; retire=deque(); expected=[0]*outs; occupied=set()
    state_slots=min(self.output_batch,outs) if mode=='GU' else outs
    owners=[None]*state_slots; input_key=[None]*self.common_cores
    completed=[0]; changed=[Signal()]; stats=Counter(); ports=self.state_port_free
    started=h.now; coverage=set(); previous_commit=[-1]*outs
    def state_slot(out): return out%state_slots
    def notify():
        prior=changed[0]; changed[0]=Signal(); prior.set()
    def loader(core):
        while tasks:
            ix,(out,k)=tasks.popleft(); key=(layer,core,out,k)
            if mode=='GU' and key in self.common_prefetched:
                self.common_prefetched.remove(key); stats['prefetch_hits']+=1
            else:
                yield from program(self,core,layer,mode,out,k)
            tile=self.cim_tiles[core]
            if mode=='GU':
                yield from transfer(self,self.vector,65536+(out*blocks+k)*2,2,False,
                    'GU_weight_scale_metadata',tile,core)
            else:
                base=65536+2*(self.model['ffn']//64)*(self.model['hidden']//64)
                for plane in range(2):
                    yield from transfer(self,self.vector,base+(2*out+plane)*blocks+k,1,False,
                        'Wd_weight_scale_metadata',tile,core)
            free=Signal(); ready[core]=(ix,out,k,free,tile)
            stats['peak_resident_ready_tiles']=max(stats['peak_resident_ready_tiles'],len(ready)); notify()
            yield free
    def worker(core):
        while completed[0]<n:
            row=ready.get(core)
            why=('drain' if stats['dispatched_frames']==n else 'weight_ready')
            if row:
                _,out,k,_,_=row
                if not result.available(core): why='result_slot'
                elif k!=expected[out]: why='crossK_dependency'
                elif out in occupied: why='output_busy'
                elif owners[state_slot(out)] not in (None,out): why='state_owner'
                else: why=None
            if why:
                t=h.now; yield changed[0]; elapsed=h.now-t
                stats['wait_'+why+'_core_ns']+=elapsed; e.wait(why,elapsed); continue
            ix,out,k,free,tile=ready.pop(core); occupied.add(out)
            assert self.cim_states[core]=='ready' and not self.cim_compute_busy[core]
            self.cim_states[core]='computing'; self.cim_compute_busy[core]=True
            cell=state_slot(out)
            if owners[cell] is None:
                assert k==0; owners[cell]=out
                e.emit('state_owner_acquire',tile,core,resource='wide_state',state_slot=cell)
                stats['peak_owned_state_groups']=max(stats['peak_owned_state_groups'],sum(v is not None for v in owners))
            slot=result.reserve(core,tile); stats['dispatched_frames']+=1; notify()
            key=(getattr(self,'alignment_command',0),layer,mode,k)
            if input_key[core]!=key:
                offset,size=(k*80,80) if mode=='GU' else (8192+k*128,128)
                t=h.now
                yield from transfer(self,self.vector,offset,size,False,
                    'GU_x_codes' if mode=='GU' else 'NL_gu_codes',tile,core)
                if mode=='Wd':
                    yield from transfer(self,self.vector,65536+self.cross_gu_scale+k,1,False,
                        'NL_gu_scale',tile,core)
                stats['input_load_core_ns']+=h.now-t; stats['input_cache_loads']+=1; input_key[core]=key
                e.emit('input_cache_fill',tile,core,bytes=size,resource='core_input_cache')
            else:
                stats['input_cache_hits']+=1; e.emit('input_cache_hit',tile,core,resource='core_input_cache')
            if not self.cim_rng_ready[core]():
                t=h.now; yield self.cim_rng_ready[core]; e.wait('rng_assignment',h.now-t)
            samples=service['samples']; rcfg=cfg['result']
            capture=(rcfg['columns']+rcfg['capture_lanes']-1)//rcfg['capture_lanes']
            drain=service['frame_cycles']-samples-rcfg['capture_cycles_in_original_frame']
            assert drain>=0
            begin=h.now; e.emit('command_accept',tile,core,resource='FFN_core')
            yield from cycles(self,samples,'common_'+mode+'_core')
            e.emit('sample_last',tile,core,resource='FFN_core',samples=samples)
            if drain: yield from cycles(self,drain,'common_'+mode+'_core')
            e.emit('result_valid',tile,core,resource='FFN_core',slot=slot)
            yield from cycles(self,capture,'common_'+mode+'_core')
            result.capture(core,slot)
            stats['sample_core_ns']+=h.now-begin; stats['sample_frames']+=1
            self.kernel_active['GU_frames' if mode=='GU' else 'Wd_M128_frames']+=1
            self.actions['GU_logical_R8_ports' if mode=='GU' else 'NL_logical_R8_ports']+=64*samples*(1 if mode=='GU' else 3)
            self.actions['common_R8_words']+=samples*(1 if mode=='GU' else 3)
            self.actions['SC_equivalent_MAC']+=8192
            assert ix not in coverage; coverage.add(ix)
            self.cim_compute_busy[core]=False; self.cim_states[core]='free'
            e.emit('cim_release',tile,core,resource='CIM',slot=slot)
            retire.append((core,slot,out,k,tile)); stats['peak_captured_results']=max(stats['peak_captured_results'],len(retire))
            free.set(); notify()
    def state_worker(port):
        stall=cfg['state']['test_initial_stall_cycles']
        if stall: yield from cycles(self,stall,'test_state_consumer_stall')
        while completed[0]<n:
            if not retire: yield changed[0]; continue
            core,slot,out,k,tile=retire.popleft(); offset=state_slot(out)*1024
            assert owners[state_slot(out)]==out and previous_commit[out]==k-1
            assert result.read(core,slot)==tile
            if k+1==blocks:
                t=h.now; yield lambda:not self.p28_staging_busy
                e.wait('encoder_resource',h.now-t); self.p28_staging_busy=True
            if k:
                yield from transfer(self,self.common_state,offset,1024,False,'common_'+mode+'_state_read',tile,core)
            p=cfg['period_ns']; begin=max(align_time(h.now,p),ports[port])
            beats=cfg['state']['packet_beats']; ii=cfg['state']['beat_II_cycles']; latency=cfg['state']['beat_latency_cycles']
            ports[port]=begin+beats*ii*p
            if begin>h.now:
                t=h.now; yield from h.delay(begin-h.now); e.wait('state_port',h.now-t)
            for beat in range(beats):
                e.emit('result_beat_accept',tile,core,resource='state_port%d'%port,slot=slot,
                    beat=beat,values=cfg['state']['lanes'],wire_bits=cfg['result']['state_input_bits'])
                yield from cycles(self,ii,'common_state32_port')
            result.release(core,slot); notify()
            if latency>ii: yield from cycles(self,latency-ii,'common_state32_tail')
            e.emit('state_update_valid',tile,core,resource='state_port%d'%port)
            self.actions['common_state32_vectors']+=beats; self.actions['crossK_updates']+=128
            if k+1<blocks:
                yield from transfer(self,self.common_state,offset,1024,True,'common_'+mode+'_state_write',tile,core)
            else:
                t=h.now; e.emit('encode_begin',tile,core,resource='shared_encoder')
                yield from self.p28_finish_output(self,mode)
                assert h.now-t==(cfg['encoding']['vector_codec_cycles']+(cfg['encoding']['GU_scale_cycles'] if mode=='GU' else 0))*p
                e.emit('encode_end',tile,core,resource='shared_encoder')
                if mode=='GU':
                    yield from transfer(self,self.vector,8192+out*128,128,True,'GU_quantized_output',tile,core)
                    yield from transfer(self,self.vector,65536+self.cross_gu_scale+out,1,True,'GU_scale_output',tile,core)
                else:
                    yield from transfer(self,self.vector,out*256,256,True,'FFN_BF16_output',tile,core)
                self.p28_staging_busy=False
            previous_commit[out]=k; expected[out]=k+1; occupied.remove(out)
            e.emit('state_commit',tile,core,resource='wide_state',last_K=k+1==blocks)
            if k+1==blocks:
                owners[state_slot(out)]=None
                e.emit('state_owner_release',tile,core,resource='wide_state',state_slot=state_slot(out))
            completed[0]+=1; notify()
    e.emit('stage_begin',resource='FFN_'+mode,layer=layer,mode=mode,command=getattr(self,'alignment_command',0))
    yield from self._parallel([loader(i) for i in range(min(self.common_cores,n))]
        +[worker(i) for i in range(self.common_cores)]+[state_worker(i) for i in range(self.state_ports)])
    assert len(coverage)==completed[0]==n and not ready and not retire and not occupied
    assert all(k==blocks for k in expected) and not self.common_prefetched
    assert not any(self.cim_compute_busy) and all(v=='free' for v in self.cim_states)
    assert self.result_slots.report()['live_slots']==0
    e.emit('stage_done',resource='FFN_'+mode,layer=layer,mode=mode,command=getattr(self,'alignment_command',0))
    elapsed=h.now-started
    self.common_stats.append(dict(layer=layer,mode=mode,state_slots=state_slots,
        state_capacity_bytes=self.common_state.size,output_batch=self.output_batch,frames=n,
        output_groups=outs,Kblocks=blocks,physical_common_cores=self.common_cores,elapsed_ns=elapsed,
        core_sampling_utilization=stats['sample_core_ns']/(self.common_cores*elapsed),
        frame_cycles=service['frame_cycles'],samples_per_frame=service['samples'],
        frame_service_ns=service['frame_ns'],
        effective_frame_cycles=service['frame_cycles']-cfg['result']['capture_cycles_in_original_frame']
            +(cfg['result']['columns']+cfg['result']['capture_lanes']-1)//cfg['result']['capture_lanes'],
        profile_sha256=self.p28_binding_sha,**dict(stats)))
