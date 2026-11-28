"""Session controller: finite services, persistent KV, no numerical inference.

The event queue/Signal/delay/run are reused from unified_v6.shared_memory.
Sampling addresses are an explicit synthetic fixture; they never imply PPL.
"""
from collections import Counter, OrderedDict
from math import ceil
import random
from .session_program import compile_plan
from .session_services import Pool, SRAM, DMA, Engine, parallel


class Simulator:
    def __init__(self, core, clock_MHz, hw=None):
        self.core = core
        hw=hw or {}
        native=hw.get('dma_backend')=='beat_analytic'
        self.h = core.SharedMemory(core.AnalyticDRAM(latency_ns=hw.get('dram_latency_ns',30),bandwidth_GBs=hw.get('dram_GBs',136.4606)),
            credit=256 if native else 1,response_bytes=16384 if native else 64,
            issue_per_cycle=16,issue_period_ns=1000/clock_MHz,response_buffered=False,
            memory_config=dict(capacity=65536 if native else 4096,banks=16 if native else 1),return_banks=16 if native else 1)
        self.period = 1000/clock_MHz
        self.h.common_period_ns=self.period
        self.active = 0; self.completed = 0

    @property
    def now(self):
        return self.h.now

    def signal(self):
        return self.core.Signal()

    def edge(self, time):
        return self.core.align_time(time, self.period)

    def delay(self, ns):
        yield from self.h.delay(max(0, ns))

    def spawn(self, gen):
        self.active += 1
        def advance():
            while True:
                try:
                    event = next(gen)
                except StopIteration:
                    self.active -= 1; self.completed += 1; return
                if event():
                    continue
                assert hasattr(event, 'subscribe'), 'event notification required'
                event.subscribe(lambda: self.h.later(self.now, advance))
                return
        self.h.later(self.now, advance)

    def run(self, gen):
        self.spawn(gen)
        self.h.run(lambda: self.active == 0)
        assert self.active == 0 and not self.h.events


class Space:
    def __init__(self):
        self.top = 0; self.regions = {}

    def alloc(self, name, size):
        assert size > 0 and name not in self.regions
        address = ceil(self.top/8192)*8192
        self.regions[name] = dict(address=address, bytes=size)
        self.top = address + size
        return address

    def check(self, address, size):
        assert any(r['address'] <= address and address+size <= r['address']+r['bytes']
                   for r in self.regions.values()), ('DRAM extent violation',address,size)


class Session:
    def __init__(self, core, model, hw, prompt, generated, rows=4, seed=17):
        self.model, self.hw, self.seed = model, hw, seed
        self.plan = compile_plan(model, hw, prompt, generated, rows)
        self.sim = Simulator(core, hw['clock_MHz'], hw); s = self.sim
        self.sram = SRAM(s, hw); self.dma = DMA(s, self.sram, hw)
        self.vector = Engine(s, 'vector', 1)
        self.digital = Engine(s, 'digital', 1)
        self.state = Engine(s, 'fp24_state', hw['state_workers'])
        self.sampler = Engine(s, 'winner_hold', hw['sampler_units'])
        self.pv = Engine(s, 'PV', model.q_heads)
        self.pcim = Pool(s, hw['cores'], 'pcim')
        self.states = Pool(s, hw['state_slots'], 'fp24_state_slots')
        self.commands = Pool(s, hw['command_slots'], 'engine_command_window')
        self.events = []; self.count = Counter(); self.phase = 'init'
        self.space = Space(); m = model; capacity = prompt + generated - 1
        self.weights = {}
        for layer in range(m.layers):
            for mode, n, k in [('QKV',(m.q_heads+2*m.kv_heads)*m.head_dim,m.hidden),
                                ('O',m.hidden,m.q_heads*m.head_dim),
                                ('GU',2*m.ffn,m.hidden), ('WD',m.hidden,m.ffn)]:
                tile = 128 if mode in ('GU','WD') else 64
                self.weights[layer,mode] = self.space.alloc(f'W/{layer}/{mode}', ceil(n/tile)*ceil(k/64)*8192)
        self.head = self.space.alloc('head_and_tied_embedding',ceil(m.vocab/64)*ceil(m.hidden/64)*8192)
        self.norm_weights = [self.space.alloc(f'norm/{layer}',m.hidden*4+m.head_dim*4) for layer in range(m.layers)]
        self.final_gamma = self.space.alloc('final_gamma',m.hidden*2)
        self.rope_table = self.space.alloc('rope_table',capacity*m.head_dim*4)
        self.metadata = {}
        for layer in range(m.layers):
            for mode,n,k in [('GU',m.ffn//64,m.hidden//64),('WD',m.hidden//128,m.ffn//64)]:
                self.metadata[layer,mode] = self.space.alloc(f'scale/{layer}/{mode}',n*k*2)
        self.kv = {}
        for layer in range(m.layers):
            for kind in ['K','V']:
                self.kv[layer,kind] = self.space.alloc(f'{kind}/{layer}',capacity*m.kv_heads*m.head_dim*2)
        self.kv_len = [0]*m.layers
        self.activations = [self.space.alloc(f'activation/{i}',prompt*m.hidden*3) for i in range(2)]
        # Full intermediate tensors have finite, reused DRAM backing.
        widths = {'norm':m.hidden, 'qkv':(m.q_heads+2*m.kv_heads)*m.head_dim,
                  'attn':m.q_heads*m.head_dim, 'projection':m.hidden}
        self.work = {name:self.space.alloc(name,prompt*width*3) for name,width in widths.items()}
        self.scratch = hw['front_bytes']-32768
        self.gu_base = 0
        self.x_base = self.plan['gu_record_bytes_per_row']*self.plan['prefill_rows']
        self.wd_base=ceil((self.x_base+self.plan['prefill_rows']*(m.hidden//64)*81)/64)*64
        self.state_base = hw['front_bytes']-hw['state_slots']*384
        self.timestamps = []; self.layers = []; self.frame_counts = Counter(); self.head_intervals=[]
        self.kv_audit = []; self.actions = Counter(); self.cim_busy = [False]*hw['cores']

    def emit(self, name, **values):
        if len(self.events) < 2000:
            self.events.append(dict(time_ns=self.sim.now, phase=self.phase, event=name, **values))
        self.count[name] += 1

    def issue(self, name):
        slot = yield from self.commands.acquire()
        yield from self.sim.delay(self.sim.period*self.hw['command_issue_cycles'])
        self.emit('command', op=name)
        self.commands.release(slot)

    def load(self, address, size, offset, tag, region='front'):
        self.space.check(address,size)
        yield from self.dma.transfer(address,size,region,offset,False,self.phase+'/'+tag)

    def store(self, address, size, offset, tag, region='front'):
        self.space.check(address,size)
        yield from self.sram.transfer(region,offset,size,True,tag+'_produce')
        yield from self.dma.transfer(address,size,region,offset,True,self.phase+'/'+tag)

    def elementwise(self, name, src, dst, values, operations=1, second_offset=None):
        yield from self.issue(name)
        block = 2048
        for begin in range(0,values,block):
            n = min(block,values-begin)
            yield from self.load(src+begin*3,n*3,self.scratch,name+'_input')
            yield from self.sram.transfer('front',self.scratch,n*3,False,name+'_consume')
            if second_offset is not None:
                yield from self.sram.transfer('front',second_offset+begin*3,n*3,False,name+'_skip_consume')
            yield from self.vector.execute(ceil(n*operations/self.hw['vector_lanes'])+2,name,n)
            yield from self.store(dst+begin*3,n*3,self.scratch+8192,name+'_output')

    def norm(self, name, src, dst, rows, width, gamma):
        """RMSNorm: whole-row reduction before scaling; one finite cached row."""
        yield from self.issue(name)
        yield from self.load(gamma,width*2,16384,name+'_gamma')
        for row in range(rows):
            yield from self.load(src+row*width*3,width*3,0,name+'_row')
            yield from self.sram.transfer('front',0,width*3,False,name+'_sumsq_read')
            yield from self.vector.execute(ceil(width*2/self.hw['vector_lanes'])+2,name+'_SUMSQ',width)
            yield from self.vector.execute(ceil(__import__('math').log2(width))+2,name+'_REDUCE_RSQRT',1)
            yield from self.sram.transfer('front',0,width*3,False,name+'_scale_read')
            yield from self.sram.transfer('front',16384,width*2,False,name+'_gamma_read')
            yield from self.vector.execute(ceil(width*3/self.hw['vector_lanes'])+2,name+'_SCALE',width)
            yield from self.store(dst+row*width*3,width*3,self.scratch+8192,name+'_output')

    def digital_matrix(self, name, weights, src, dst, rows, k, n, stream=False):
        yield from self.issue(name)
        # FP24 external values; native arithmetic remains BF16 x BF16 / FP32.
        yield from self.load(src,rows*k*3,0,name+'_input')
        yield from self.vector.execute(ceil(rows*k/self.hw['vector_lanes'])+2,'FP24_TO_BF16',rows*k)
        for out in range(ceil(n/64)):
            valid = min(64,n-out*64); blocks = ceil(k/64)
            loaded = {}; free = [self.sim.signal(),self.sim.signal()]
            free[0].set(); free[1].set()
            def loader():
                for kb in range(blocks):
                    yield free[kb%2]
                    free[kb%2] = self.sim.signal()
                    ready = self.sim.signal(); loaded[kb] = ready
                    yield from self.load(weights+(out*blocks+kb)*8192,8192,self.scratch+(kb%2)*8192,name+'_weight')
                    ready.set()
            self.sim.spawn(loader())
            for kb in range(blocks):
                # loader is started in this event cycle, before this delay ends.
                while kb not in loaded:
                    yield from self.sim.delay(self.sim.period)
                yield loaded[kb]
                yield from self.sram.transfer('front',self.scratch+(kb%2)*8192,8192,False,name+'_weight_use')
                for row in range(rows):
                    yield from self.sram.transfer('front',(row*k+kb*64)*3,min(64,k-kb*64)*3,False,name+'_operand')
                macs = rows*valid*min(64,k-kb*64)
                yield from self.digital.execute(ceil(macs/self.hw['fma_lanes'])+self.hw['fma_feedback_cycles'],name,macs)
                free[kb%2].set()
            if stream:
                yield from self.vector.execute(ceil(valid/self.hw['vector_lanes'])+2,'ARGMAX',valid)
                self.actions['head_streamed_logits'] += valid
            else:
                yield from self.vector.execute(ceil(rows*valid/self.hw['vector_lanes'])+2,'FP32_TO_FP24',rows*valid)
                for row in range(rows):
                    yield from self.store(dst+(row*n+out*64)*3,valid*3,self.scratch+24576,name+'_output')

    def pcim_matrix(self, layer, mode, rows):
        m = self.model; k = m.hidden if mode == 'GU' else m.ffn
        groups = m.ffn//64 if mode == 'GU' else m.hidden//128
        blocks = k//64; samples = self.hw['gu_samples'] if mode == 'GU' else self.hw['wd_samples']
        iterator = iter(range(groups)); workers = min(self.hw['cores'],self.hw['state_slots']//rows)
        assert workers > 0
        yield from self.issue(mode)
        metadata_bytes=groups*blocks*2
        yield from self.load(self.metadata[layer,mode],metadata_bytes,self.scratch,mode+'_weight_scales')
        def worker():
            core = yield from self.pcim.acquire()
            slots = [None]*rows
            for row in range(rows):
                slots[row] = yield from self.states.acquire()
            result_slots = Pool(self.sim,2,'result_slots')
            for out in iterator:
                for kb in range(blocks):
                    assert not self.cim_busy[core]
                    yield from self.load(self.weights[layer,mode]+(out*blocks+kb)*8192,
                                         8192,0,mode+'_weights',region='cim:'+str(core))
                    self.actions['CIM_read_equivalent_words'] += 512
                    yield from self.sram.transfer('front',self.scratch+(out*blocks+kb)*2,2,False,mode+'_weight_scale')
                    commits = []
                    self.cim_busy[core] = True
                    for row in range(rows):
                        rs = yield from result_slots.acquire()
                        offset = self.x_base+(row*blocks+kb)*80 if mode == 'GU' else (row*(m.ffn//64)+kb)*288
                        size = 80 if mode == 'GU' else 288
                        yield from self.sram.transfer('front',offset,size,False,mode+'_code')
                        if mode == 'GU':
                            scale_offset=self.x_base+rows*blocks*80+row*blocks+kb
                            yield from self.sram.transfer('front',scale_offset,1,False,'GU_x_shared_exponent')
                        yield from self.sim.delay((samples+self.hw['pcim_row_overhead_cycles'])*self.sim.period)
                        self.frame_counts[self.phase+'/'+mode] += 1
                        self.actions['local_count_values'] += 128
                        self.actions['rng_words'] += samples*(1 if mode=='GU' else 3)
                        done = self.sim.signal(); commits.append(done)
                        def commit(row=row,rs=rs,done=done,kb=kb,out=out):
                            state_worker = yield from self.state.pool.acquire()
                            state_begin=self.sim.now
                            yield from self.sim.delay(4*self.sim.period)
                            result_slots.release(rs) # four-beat capture complete
                            address = self.state_base+slots[row]*384
                            if kb:
                                yield from self.sram.transfer('front',address,384,False,'FP24_state_read')
                                yield from self.sim.delay(4*self.sim.period)
                            yield from self.sim.delay(9*self.sim.period)
                            if kb+1 < blocks:
                                yield from self.sram.transfer('front',address,384,True,'FP24_state_write')
                            elif mode == 'GU':
                                yield from self.vector.execute(15,'GU_P8_S_S2_SIGMOID',128)
                                yield from self.sram.transfer('front',(row*(m.ffn//64)+out)*288,288,True,'GU_event_record')
                            else:
                                yield from self.vector.execute(ceil(128/self.hw['vector_lanes'])+2,'WD_FP24_output',128)
                                yield from self.sram.transfer('front',self.wd_base+(row*m.hidden+out*128)*3,384,True,'WD_FP24_output_write')
                            self.state.actions['count_to_fp24'] += 128
                            self.state.actions['fp24_add'] += 128
                            self.state.busy_ns += self.sim.now-state_begin
                            self.state.pool.release(state_worker); done.set()
                        self.sim.spawn(commit())
                    self.cim_busy[core] = False # all rows captured locally; state drain may overlap load
                    for done in commits:
                        yield done
                    assert result_slots.used == 0
                self.emit('state_group_complete',mode=mode,output_group=out,rows=rows)
            for slot in slots:
                self.states.release(slot)
            self.pcim.release(core)
        yield from parallel(self.sim,[worker() for _ in range(workers)])
        assert self.states.used == 0 and self.pcim.used == 0

    def append_kv(self, layer, start, rows):
        m = self.model
        assert self.kv_len[layer] == start, 'prefill/decode KV gap or duplicate'
        width=(m.q_heads+2*m.kv_heads)*m.head_dim
        for row in range(rows):
            for kind in ['K','V']:
                values=m.kv_heads*m.head_dim
                source=(row*width+m.q_heads*m.head_dim+(values if kind=='V' else 0))*3
                yield from self.load(self.work['qkv']+source,values*3,0,'KV_source_'+kind,region='attention')
                yield from self.vector.execute(ceil(values/self.hw['vector_lanes'])+2,'FP24_TO_BF16_KV',values)
                address=self.kv[layer,kind]+(start+row)*values*2
                yield from self.store(address,values*2,0,'KV_append_'+kind,region='attention')
        self.kv_len[layer] += rows
        self.kv_audit.append(dict(phase=self.phase,layer=layer,begin=start,end=start+rows))

    def attention(self, layer, start, rows):
        m=self.model; qpg=m.q_heads//m.kv_heads
        yield from self.issue('P_ATTENTION')
        for row in range(rows):
            length=start+row+1
            assert length<=self.kv_len[layer]
            def group_job(group):
                region='attention:'+str(group%8)
                rng=random.Random(self.seed+layer*1000003+(start+row)*997+group)
                qaddr=self.work['qkv']+(row*(m.q_heads+2*m.kv_heads)+group*qpg)*m.head_dim*3
                yield from self.load(qaddr,qpg*m.head_dim*3,28672,'attention_Q',region)
                dims=set()
                for _ in range(qpg):
                    dims.update(rng.sample(range(m.head_dim),min(self.hw['screen_r'],m.head_dim)))
                self.actions['coarse_feature_dimensions']+=len(dims)
                for sector in sorted(set(i*2//64 for i in dims)):
                    for begin in range(0,length,self.hw['sg_segments']):
                        spans=[(self.kv[layer,'K']+(i*m.kv_heads+group)*m.head_dim*2+sector*64,64)
                               for i in range(begin,min(length,begin+self.hw['sg_segments']))]
                        for address,size in spans:
                            self.space.check(address,size)
                        yield from self.dma.transfer(spans[0][0],sum(n for _,n in spans),region,24576,
                            False,self.phase+'/coarse_K_sector',spans=spans)
                macs=qpg*length*min(self.hw['screen_r'],m.head_dim)
                self.actions['coarse_QK_MAC']+=macs
                yield from self.digital.execute(ceil(macs/self.hw['fma_lanes'])+4,'SparQ_coarse',macs)
                candidates=sorted(rng.sample(range(length),min(length,self.hw['candidates'])))
                for index in candidates:
                    address=self.kv[layer,'K']+(index*m.kv_heads+group)*m.head_dim*2
                    yield from self.load(address,m.head_dim*2,24576,'selected_K',region)
                    yield from self.sram.transfer(region,24576,m.head_dim*2,False,'selected_K_use')
                macs=qpg*len(candidates)*m.head_dim
                yield from self.digital.execute(ceil(macs/self.hw['fma_lanes'])+4,'selected_QK',macs)
                yield from self.vector.execute(ceil(length/self.hw['vector_lanes'])+self.hw['topk_cycles'],'SparQ_selection',length)
                yield from self.sram.transfer(region,32768,qpg*len(candidates),True,'P8_threshold_write')
                cache=OrderedDict(); changed=[self.sim.signal()]
                def notify():
                    old=changed[0];changed[0]=self.sim.signal();old.set()
                def head_job(head):
                    indices=[rng.choice(candidates) for _ in range(self.hw['pv_samples'])]
                    fifo=[]; credit=Pool(self.sim,self.hw.get('sample_fifo',8),'sample_fifo')
                    available=[self.sim.signal()]
                    def produce():
                        unit=yield from self.sampler.pool.acquire(); begin=self.sim.now
                        yield from self.sram.transfer(region,32768+head*len(candidates),len(candidates),False,'P8_sampler_input')
                        yield from self.sim.delay(self.hw['sampler_setup_cycles']*self.sim.period)
                        for index in indices:
                            ticket=yield from credit.acquire()
                            yield from self.sim.delay(self.sim.period)
                            fifo.append((index,ticket))
                            old=available[0];available[0]=self.sim.signal();old.set()
                            self.actions['attention_pbit_draws_requested']+=len(candidates)
                        self.sampler.busy_ns+=self.sim.now-begin
                        self.sampler.actions['winner_hold_query']+=1
                        self.sampler.pool.release(unit)
                    self.sim.spawn(produce())
                    for _ in indices:
                        while not fifo:
                            yield available[0]
                        index,ticket=fifo.pop(0);credit.release(ticket)
                        if index in cache:
                            entry=cache[index];entry['refs']+=1;cache.move_to_end(index)
                            self.actions['V_cache_hits']+=1
                            yield entry['ready']
                        else:
                            while len(cache)>=self.hw['v_cache_vectors']:
                                victim=next((i for i,e in cache.items() if e['refs']==0 and e['ready']()),None)
                                if victim is not None:
                                    slot=cache.pop(victim)['slot'];break
                                yield changed[0]
                            else:
                                slot=len(cache)
                            entry=dict(slot=slot,refs=1,ready=self.sim.signal())
                            cache[index]=entry
                            address=self.kv[layer,'V']+(index*m.kv_heads+group)*m.head_dim*2
                            yield from self.load(address,m.head_dim*2,slot*m.head_dim*2,'sampled_V',region)
                            self.actions['unique_V_fetches']+=1;entry['ready'].set();notify()
                        yield from self.sram.transfer(region,entry['slot']*m.head_dim*2,m.head_dim*2,False,'PV_cached_V')
                        yield from self.pv.execute(ceil(m.head_dim/self.hw['pv_add_lanes'])+self.hw['pv_feedback_cycles'],'PV_add',m.head_dim)
                        entry['refs']-=1;notify();self.actions['V_samples']+=1
                    self.actions['peak_sample_fifo']=max(self.actions['peak_sample_fifo'],credit.peak)
                yield from parallel(self.sim,[head_job(head) for head in range(qpg)])
                self.actions['causal_queries']+=qpg
            # Eight physical KV workspaces; additional model KV heads use waves.
            for first in range(0,m.kv_heads,8):
                yield from parallel(self.sim,[group_job(g) for g in range(first,min(first+8,m.kv_heads))])
            workspace_start=start if self.phase=='prefill' else 0
            output=self.work['attn']+(workspace_start+row)*m.q_heads*m.head_dim*3
            n=m.q_heads*m.head_dim*3
            yield from self.vector.execute(ceil(n/3/self.hw['vector_lanes'])+2,'PV_SCALE_FP32_TO_FP24',n//3)
            for begin in range(0,n,8192):
                yield from self.store(output+begin,min(8192,n-begin),0,'attention_output',region='attention')

    def decoder(self, layer, start, rows, src, dst):
        m=self.model; begin=self.sim.now; H=m.hidden; width=(m.q_heads+2*m.kv_heads)*m.head_dim
        yield from self.norm('ATTN_NORM',src,self.work['norm'],rows,H,self.norm_weights[layer])
        yield from self.digital_matrix('QKV',self.weights[layer,'QKV'],self.work['norm'],self.work['qkv'],rows,H,width)
        if m.qk_norm:
            for row in range(rows):
                for head in range(m.q_heads+m.kv_heads):
                    address=self.work['qkv']+(row*width+head*m.head_dim)*3
                    gamma=self.norm_weights[layer]+H*4+(m.head_dim*2 if head>=m.q_heads else 0)
                    yield from self.norm('QK_NORM',address,address,1,m.head_dim,gamma)
        yield from self.load(self.rope_table+start*m.head_dim*4,rows*m.head_dim*4,0,'rope_parameters')
        for row in range(rows):
            address=self.work['qkv']+row*width*3
            yield from self.elementwise('ROPE',address,address,(m.q_heads+m.kv_heads)*m.head_dim,4)
        yield from self.append_kv(layer,start,rows)
        yield from self.attention(layer,start,rows)
        workspace_start=start if self.phase=='prefill' else 0
        yield from self.digital_matrix('O',self.weights[layer,'O'],self.work['attn']+workspace_start*m.q_heads*m.head_dim*3,self.work['projection'],rows,m.q_heads*m.head_dim,H)
        # Residual has two real inputs, counted explicitly.
        yield from self.load(src,rows*H*3,0,'attention_residual_skip')
        yield from self.elementwise('ATTN_RESIDUAL',self.work['projection'],self.work['norm'],rows*H,second_offset=0)
        yield from self.norm('FFN_NORM',self.work['norm'],self.work['projection'],rows,H,self.norm_weights[layer]+H*2)
        yield from self.load(self.work['projection'],rows*H*3,0,'X_encode_source')
        yield from self.sram.transfer('front',0,rows*H*3,False,'X_encode_read')
        yield from self.vector.execute(ceil(rows*H/self.hw['vector_lanes'])+6,'X_P8_GROUP64',rows*H)
        yield from self.sram.transfer('front',self.x_base,rows*(H//64)*80,True,'X_P8_codes')
        yield from self.sram.transfer('front',self.x_base+rows*(H//64)*80,rows*(H//64),True,'X_shared_exponents')
        yield from self.pcim_matrix(layer,'GU',rows)
        yield from self.pcim_matrix(layer,'WD',rows)
        yield from self.load(self.work['norm'],rows*H*3,0,'FFN_residual_skip')
        for first in range(0,rows*H,2048):
            values=min(2048,rows*H-first)
            yield from self.sram.transfer('front',first*3,values*3,False,'FFN_residual_skip_read')
            yield from self.sram.transfer('front',self.wd_base+first*3,values*3,False,'WD_output_consume')
            yield from self.vector.execute(ceil(values/self.hw['vector_lanes'])+2,'FFN_RESIDUAL',values)
            yield from self.store(dst+first*3,values*3,self.scratch,'layer_output')
        self.layers.append(dict(phase=self.phase,layer=layer,token_begin=start,rows=rows,
                                begin_ns=begin,end_ns=self.sim.now))

    def embedding(self, position, tokens, dst):
        m=self.model
        for row,token in enumerate(tokens):
            assert 0 <= token < m.vocab
            for kb in range(m.hidden//64):
                address=self.head+((token//64)*(m.hidden//64)+kb)*8192+(token%64)*128
                yield from self.load(address,128,kb*128,'embedding')
            yield from self.vector.execute(ceil(m.hidden/self.hw['vector_lanes'])+2,'BF16_TO_FP24_embedding',m.hidden)
            yield from self.store(dst+row*m.hidden*3,m.hidden*3,self.scratch,'embedding_output')
        self.emit('embedding_complete',position=position,rows=len(tokens))

    def readout(self, src, output_index):
        m=self.model
        begin=self.sim.now
        yield from self.norm('FINAL_NORM',src,self.work['norm'],1,m.hidden,self.final_gamma)
        # Streaming logits use a bounded output scratch, never a vocabulary tensor.
        yield from self.digital_matrix('LM_HEAD',self.head,self.work['norm'],None,1,m.hidden,m.vocab,stream=True)
        self.head_intervals.append(dict(begin_ns=begin,end_ns=self.sim.now))
        self.timestamps.append(self.sim.now)
        self.emit('token_emitted',output_index=output_index,kv_length=self.kv_len[0])

    def execute(self):
        m=self.model; L=self.plan['prompt']; R=self.plan['prefill_rows']
        self.phase='prefill'
        for start in range(0,L,R):
            rows=min(R,L-start)
            yield from self.embedding(start,[(17+i)%m.vocab for i in range(start,start+rows)],self.activations[0]+start*m.hidden*3)
        for layer in range(m.layers):
            src,dst=self.activations[layer%2],self.activations[(layer+1)%2]
            for start in range(0,L,R):
                rows=min(R,L-start)
                yield from self.decoder(layer,start,rows,src+start*m.hidden*3,dst+start*m.hidden*3)
        assert self.kv_len == [L]*m.layers
        self.phase='first_token'
        yield from self.readout(self.activations[m.layers%2]+(L-1)*m.hidden*3,0)
        for output_index in range(1,self.plan['generated']):
            self.phase='decode'
            position=L+output_index-1
            yield from self.embedding(position,[output_index%m.vocab],self.activations[0])
            for layer in range(m.layers):
                yield from self.decoder(layer,position,1,self.activations[layer%2],self.activations[(layer+1)%2])
            yield from self.readout(self.activations[m.layers%2],output_index)
        self.phase='done'; self.emit('session_complete')

    def report(self):
        m=self.model; expected=m.layers*(self.plan['prompt']+self.plan['generated']-1)
        gu=expected*(m.ffn//64)*(m.hidden//64)
        wd=expected*(m.hidden//128)*(m.ffn//64)
        assert sum(n for k,n in self.frame_counts.items() if k.endswith('/GU'))==gu
        assert sum(n for k,n in self.frame_counts.items() if k.endswith('/WD'))==wd
        assert self.kv_len==[self.plan['prompt']+self.plan['generated']-1]*m.layers
        assert self.pcim.used==self.states.used==self.dma.slots.used==0 and not any(self.cim_busy)
        assert self.actions['head_streamed_logits']==m.vocab*self.plan['generated']
        expected_kv=2*expected*m.kv_heads*m.head_dim*2
        actual_kv=sum(v.get('write_logical_bytes',0) for k,v in self.dma.by_tag.items() if '/KV_append_' in k)
        assert expected_kv==actual_kv
        dram=sum(self.dma.count[k] for k in ['read_physical_bytes','write_physical_bytes'])
        sram=self.sram.count
        if self.sram.beat is not None:
            sram=self.sram.beat.count
        known=((sram['read_words']+self.actions['CIM_read_equivalent_words'])*self.hw['sram_read_pJ']+sram['write_words']*self.hw['sram_write_pJ'])/1e9
        return dict(status='COMPLETED_CONTROLLER_TLM_MACRO_MEMORY',plan=self.plan,
            elapsed_ms=self.sim.now/1e6,first_token_ms=self.timestamps[0]/1e6,
            final_norm_head_ms=sum(x['end_ns']-x['begin_ns'] for x in self.head_intervals)/1e6,
            elapsed_without_final_norm_head_ms=(self.sim.now-sum(x['end_ns']-x['begin_ns'] for x in self.head_intervals))/1e6,
            inter_token_ms=[(b-a)/1e6 for a,b in zip(self.timestamps,self.timestamps[1:])],
            output_times_ms=[t/1e6 for t in self.timestamps],layers=self.layers,frames=dict(self.frame_counts),
            actions=dict(self.actions),events=self.events,kv_lengths=self.kv_len,kv_audit=self.kv_audit,
            external_allocations=self.space.regions,external_capacity_bytes=self.space.top,
            SRAM=dict(counts=dict(sram),by_tag={k:dict(v) for k,v in self.sram.by_tag.items()},
                      dynamic_mJ_known=known,capacity_bytes=self.hw['front_bytes']+self.hw['attention_bytes']+8192*self.hw['cores']),
            DMA=dict(counts=dict(self.dma.count),by_tag={k:dict(v) for k,v in self.dma.by_tag.items()},
                     peak_8KiB_credits=self.dma.slots.peak,credit_limit=self.dma.slots.count,address_digest=self.dma.address_digest),
            request_backend_counts=dict(self.sim.h.count) if self.hw.get('dma_backend')=='beat_analytic' else None,
            state_peak_slots=self.states.peak,engines={x.name:dict(busy_ns=x.busy_ns,actions=dict(x.actions)) for x in [self.vector,self.digital,self.state,self.sampler,self.pv]},
            DRAM_transfer_mJ=dram*8*self.hw['dram_pJ_per_bit']/1e9,
            total_energy_mJ=None,total_area_mm2=None,
            memory_backend=dict(SRAM=self.hw.get('sram_backend','burst'),DMA=self.hw.get('dma_backend','burst'),
                                DRAM='analytic bandwidth/latency,not Ramulator'),
            scope='Full shape/control/traffic; macro DRAM and burst-calendar SRAM; synthetic Attention addresses; no numerical PPL or new RTL/PPA',
            pending=['native LPDDR replay','exact Attention trace binding','FP24 worker and23bit PPA','fine bank arbitration cross-check'])
