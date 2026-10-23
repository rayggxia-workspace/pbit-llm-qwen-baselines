"""Online adapter for the unchanged Issue95 native RNG protocol.

The kernel invokes the original RandomNetwork once per active source edge.
Idle intervals use the already verified EventNetwork fast-forward, preserving
age, seed transport, epochs, warmup and locked-reseed deferral. There is one
bounded command/request slot and an explicit one-cycle response-copy pipeline.
No host RNG draw substitutes for a native endpoint response.
"""
from collections import deque

from .contracts import Buffer,Clock,Operation,Resource
from architecture_tlm.random_service.model import SeedWords
from architecture_tlm.unified_v6.rng_integrated import EventNetwork,FastEndpoint


def resources():
    clock=Clock('core',10000)
    return [Resource('rng_submit',clock,1,capacity=1),Resource('rng_delivery',clock,1,capacity=1)]


def buffers(prefix):
    return [Buffer(prefix+'.rng_slot',1,initial=1,unit='native transaction credit')]


class NativeRandomService:
    def __init__(self,kernel,prefix,kinds,seed=0,seed_interval=100,seed_startup=10,
                 reseed_cycles=100000000,hold_cycles=0,operation_ids=None):
        if not kinds or type(hold_cycles) is not int or hold_cycles<0:
            raise ValueError('native endpoints and nonnegative hold cycles required')
        self.kernel,self.prefix=kernel,prefix
        self.clock=Clock('core',10000)
        self.network=EventNetwork({name:FastEndpoint(kind,reseed_cycles) for name,kind in kinds.items()},
            SeedWords('fixture',seed_interval,seed_startup,fixture_seed=seed,
                      provenance='explicit deterministic seed-bus fixture; not physical entropy'),clock_ns=10)
        self.pending=deque()
        self.active=None
        self.hold_cycles=hold_cycles
        self.receipts=[]
        self.operation_ids=operation_ids if operation_ids is not None else []
        self.process_name=prefix+'.native_rng'
        kernel.register_clock_process(self.process_name,self.clock,self._tick)

    def _add(self,suffix,resource,**kwargs):
        ident=self.prefix+'.'+suffix
        self.kernel.add(Operation(ident,resource,**kwargs))
        self.operation_ids.append(ident)
        return ident

    def _submit(self,label,transaction,deps,callback):
        done_id=self.prefix+'.'+label+'.done'
        submit_id=self.prefix+'.'+label+'.submit'
        transaction.update(label=label,done_id=done_id,submit_id=submit_id,callback=callback,
                           phase='request',submit_ps=None,wait_edges=0,hold_left=self.hold_cycles)
        def enqueued(k,op):
            transaction['submit_ps']=k.now_ps
            self.pending.append(transaction)
            if len(self.pending)+(self.active is not None)>1:
                raise AssertionError('native request slot overflow')
            k.wake_clock_process(self.process_name)
        self._add(label+'.submit','rng_submit',deps=tuple(deps),
                  inputs={self.prefix+'.rng_slot':1},on_complete=enqueued,
                  actions={'native_rng_request' if transaction['kind']=='frame' else 'native_rng_command':1})
        return done_id

    def frame(self,label,requests,deps,callback):
        if not requests or set(requests)-set(self.network.ports):
            raise ValueError('frame needs known endpoint names')
        normalized={}
        for name,thresholds in requests.items():
            q=list(thresholds)
            if len(q)!=self.network.ports[name].profile['lanes'] or any(type(v) is not int or not 0<=v<=256 for v in q):
                raise ValueError('native q/256 width/endpoint violation')
            normalized[name]=q
        return self._submit(label,dict(kind='frame',requests=normalized),deps,callback)

    def command(self,label,port,command,deps,callback=None):
        if port not in self.network.ports or command not in (1,2,3):
            raise ValueError('SAVE/RESTORE/RELEASE requires a known endpoint')
        return self._submit(label,dict(kind='command',port=port,command=command),deps,callback)

    def _finish(self,tx,response):
        response.update(submit_ps=tx['submit_ps'],native_complete_ps=self.kernel.now_ps,
                        wait_edges=tx['wait_edges'],kind=tx['kind'])
        receipt={key:value for key,value in response.items() if key not in ('words','bits')}
        receipt['label']=tx['label']
        self.receipts.append(receipt)
        def delivered(k,op):
            response['delivery_ps']=k.now_ps
            if tx['callback']: tx['callback'](response,op.id)
        self._add(tx['label']+'.done','rng_delivery',deps=(tx['submit_id'],),
                  outputs={self.prefix+'.rng_slot':1},on_complete=delivered,
                  actions={'native_response_copy':1},
                  metadata={'native_valid_ps':response.get('valid_ps'),
                            'native_complete_ps':response['native_complete_ps'],
                            'bridge':'one-cycle registered copy; born next edge after native consume'})
        self.active=None

    def _tick(self,kernel):
        target=kernel.now_ps//self.clock.period_ps
        if self.network.cycle>target:
            raise AssertionError('native source clock advanced into the future')
        self.network.advance_to(target)
        if self.active is None:
            if not self.pending: return False
            self.active=self.pending.popleft()
        tx=self.active
        tx['wait_edges']+=1
        if tx['kind']=='command':
            result=self.network.tick(commands={tx['port']:tx['command']})
            if result[tx['port']]['command_accepted']:
                self._finish(tx,dict(command=tx['command'],epoch=result[tx['port']]['epoch']))
        elif tx['phase']=='request':
            names=list(tx['requests'])
            ready=all(self.network.ports[name].signals(False,self.network.ingress[name].valid)['req_ready'] for name in names)
            result=self.network.tick(tx['requests'] if ready else {},readies={name:False for name in names})
            if ready:
                if not all(result[name]['accepted'] for name in names):
                    raise AssertionError('native full-wave atomic acceptance failed')
                tx['response']=dict(words={name:result[name]['words'] for name in names},
                                    bits={name:result[name]['bits'] for name in names},
                                    epochs={name:result[name]['epoch'] for name in names},
                                    valid_ps=kernel.now_ps)
                tx['phase']='response'
        else:
            names=list(tx['requests'])
            ready=tx['hold_left']==0
            result=self.network.tick(readies={name:ready for name in names})
            if not ready:
                tx['hold_left']-=1
                for name in names:
                    if result[name]['words']!=tx['response']['words'][name] or result[name]['bits']!=tx['response']['bits'][name]:
                        raise AssertionError('native output changed under backpressure')
            elif all(result[name]['consumed'] for name in names):
                self._finish(tx,tx['response'])
            else: raise AssertionError('native registered response was lost')
        return self.active is not None or bool(self.pending)

    def report(self,now_ps=None):
        if self.active is not None or self.pending:
            raise RuntimeError('report requested before native transactions drained')
        target=(self.kernel.now_ps if now_ps is None else now_ps)//self.clock.period_ps
        if self.network.cycle<=target:
            self.network.advance_to(target+1)
        report=self.network.report()
        report.update(adapter='cycle_v1 native clock process; Issue95 Endpoint/RandomNetwork via EventNetwork/FastEndpoint',
            independent_IID=False,physical_entropy=False,physical_timing_characterized=False,
            transaction_queue_capacity=1,response_hold_cycles=self.hold_cycles,
            response_bridge='explicit rng_submit/rng_delivery resources; one-cycle registered stages with no same-edge forwarding',
            receipts=self.receipts,jumped_idle_edges=self.network.jumped_edges)
        return report
