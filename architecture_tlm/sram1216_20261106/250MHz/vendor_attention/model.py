"""Opt-in250MHz Attention resource model; unified250MHz memory and DMA service."""
import re,math
from types import MethodType
from collections import deque
from .ordinary_pool import install as ordinary_install
from . import qk_layout as qk
from .pv_stream import sampled_small

def config(name):
 m=re.fullmatch(r'm(\d+)_v([124])_s([1248])_n([1248])_t(big|micro4)_r(8|16|32)',name)
 if not m:raise ValueError(name)
 lanes,pv,sam,norm,transpose,red=m.groups()
 return dict(lanes=int(lanes),pv=int(pv),sampler=int(sam),norm=int(norm),transpose=transpose,reduction=int(red))

class ServicePool:
 def __init__(self,model,slots,name):
  self.model=model;self.slots=slots;self.name=name;self.active=set();self.waiters=deque();self.rows=[]
 def acquire(self,g,kind):
  t=object();self.waiters.append(t);start=self.model.h.now
  yield lambda:self.waiters[0] is t and len(self.active)<self.slots
  self.waiters.popleft();assert g not in self.active;self.active.add(g)
  row=dict(group=g,kind=kind,wait_ns=self.model.h.now-start,start_ns=self.model.h.now,active=len(self.active));self.rows.append(row);return row
 def release(self,g,row):
  assert g in self.active;self.active.remove(g);row['end_ns']=self.model.h.now

def transpose_micro4(model,g):
 """Four128B8x8 staging tiles. Existing16B/1RW banks, explicit writes.

 Each slot is released only after all its eight16B destination stores retire.
 No dynamic payload array in the simulator; fixed transpose wiring is separately
 priced. XOR destination mapping is the same as the large-buffer control.
 """
 from architecture_tlm.unified_v6.shared_memory import Signal
 h=model.h;r=model.att[g];jobs=[(token8,d0) for token8 in range(8) for d0 in range(0,128,8)]
 state=dict(next=0,live=0,done=0);done=Signal()
 audit=dict(group=g,max_tiles=0,bytes_read=0,bytes_written=0,start_ns=h.now)
 model.resource_audit['transpose'].append(audit)
 def pump():
  while state['live']<4 and state['next']<len(jobs):
   token8,d0=jobs[state['next']];state['next']+=1;state['live']+=1;audit['max_tiles']=max(audit['max_tiles'],state['live'])
   tile=dict(read=0,written=0)
   def arrived(tile=tile,token8=token8,d0=d0):
    tile['read']+=1
    if tile['read']!=8:return
    def written():
     tile['written']+=1
     if tile['written']==8:
      state['live']-=1;state['done']+=1
      if state['done']==len(jobs):done.set()
      else:pump()
    for col in range(8):
     h.mem.submit(r,16384+qk.word16_address(d0+col,token8)*16,16,True,'selected_K_transpose_write',written)
     audit['bytes_written']+=16
   for row in range(8):
    h.mem.submit(r,(token8*8+row)*256+d0*2,16,False,'selected_K_transpose_read',arrived)
    audit['bytes_read']+=16
 pump();yield done
 assert state['live']==0 and audit['bytes_read']==audit['bytes_written']==16384
 audit['end_ns']=h.now
 model.actions['selected_K_reorder_read_bytes']+=16384;model.actions['selected_K_reorder_write_bytes']+=16384

def screen(self,layer,g):
 h=self.h;r=self.att[g];period=self.compute_period_ns
 yield from self._append(layer,g,True)
 yield from h.transfer(self.vector,196608+g*6144+5120,1024,False,'query_feature_scan')
 lease=yield from self.top_pool.acquire(g,'feature')
 yield from qk.local_delay(self,164*period,'feature_topk_macro');self.top_pool.release(g,lease)
 row=self.extra_input['rows'][(layer%3)*8+g]
 yield from qk.coarse(self,layer,g,row['dimensions'])
 yield from h.transfer(r,32768,16384,True,'coarse_scores')
 lease=yield from self.norm_pool.acquire(g,'normalize')
 for k in range(3):yield from h.transfer(r,32768,16384,False,'coarse_score_pass'+str(k+1))
 yield from qk.local_delay(self,1730*period,'SparQ_normalize_macro');self.norm_pool.release(g,lease)
 lease=yield from self.top_pool.acquire(g,'tokens')
 yield from qk.local_delay(self,815*period,'token_topk_macro');self.top_pool.release(g,lease)
 yield from qk.selected(self,layer,g,row['candidates'])
 yield from h.transfer(r,16384,2048,True,'selected_scores')

def install(model,name):
 from .unified_clock import install_clock
 install_clock(model)
 c=config(name);lanes=c['lanes'];kp=8 if lanes==640 else 4
 ordinary_install(model,lanes,kp,True,4)
 def reduction(outputs,leaves=8,adders=c['reduction']):
  cycles=0
  while leaves>1:cycles+=math.ceil(outputs*(leaves//2)/adders)+3;leaves=(leaves+1)//2
  return cycles
 model.reduction_cycles=reduction;model.compute_period_ns=4;model.pv_lanes=c['pv'];model.pool_phase=None
 model.qk_pool=qk.Pool(model,lanes);model.norm_pool=ServicePool(model,c['norm'],'norm');model.top_pool=ServicePool(model,c['norm'],'top');model.sampler_pool=ServicePool(model,c['sampler'],'sampler')
 model.transpose_call=transpose_micro4 if c['transpose']=='micro4' else qk.transpose
 model.resource_audit=dict(PV=[],QK_words=[],QK_leases=model.qk_pool.rows,pool_switches=0,transpose=[],norm=model.norm_pool.rows,top=model.top_pool.rows,sampler=model.sampler_pool.rows)
 model.resource_contract=dict(case=name,configuration=c,compute_MHz=250,SRAM_MHz=250,ordinary_FMA_lanes=lanes,K_parallel=kp,FP32_reduction_adders=c['reduction'],PV_ADD_lanes=32*c['pv'],PV_state_bytes=16384,PV_staging_bytes=2048,QK_transpose_staging_bytes=8*(512 if c['transpose']=='micro4' else 2048),QK_stream_buffers_bytes=1024,QK_shared_groups=model.qk_pool.slots,independent_QK_lanes=0,sampler_cores=c['sampler'],screen_top_cores=c['norm'],screen_norm_cores=c['norm'],whole_token=False,new_PPA=False,default_changed=False)
 model.ordinary_pool_contract.update(SRAM_period_ns=4,FP32_reduction_adders=c['reduction'],independent_QK_lanes=0,QK_reuse_implemented=True)
 model.digital_contract['FP32_reduction_adders']=c['reduction']
 model.compact_screen=MethodType(screen,model);model.attention_group=MethodType(sampled_small,model)
 model.attention_adapter_contract.update(QK_source='shared_ordinary',QK_lanes=min(8,model.qk_pool.slots)*64,sample_ADD_lanes=32*c['pv'])
 parent=model.phase
 def phase(self,name,generators,layer):
  pools=(self.qk_pool,self.norm_pool,self.top_pool,self.sampler_pool)
  assert self.pool_phase is None and all(not p.active and not p.waiters for p in pools)
  self.pool_phase=name
  try:
   if name in ('attention','O'):
    # Mode ownership uses two unified250MHz cycles.
    parent('pool_mode_switch',[self.h.delay(8)],layer);self.resource_audit['pool_switches']+=1
   return parent(name,generators,layer)
  finally:
   assert all(not p.active and not p.waiters for p in pools);self.pool_phase=None
 model.phase=MethodType(phase,model)
 return model
