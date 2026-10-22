"""Build a standalone read-only architecture view from existing model traces."""
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from architecture_tlm.random_service.model import Endpoint, SeedIngress


def trace(kind, scene):
    interval = 12 if scene == 'reseed' else 6 if scene == 'replay' else 0
    p = Endpoint(kind, interval)
    g = SeedIngress(p.profile['state_bits'])
    rng = random.Random(95)
    rows = []
    phase, number = 0, 0
    original, replay = [], []
    for c in range(38 if scene in ('reseed', 'replay') else 24):
        reset = c != 0
        req, cmd = True, 0
        sink = not (scene == 'stall' and 15 <= c <= 18)
        warm_before = p.warm
        if scene == 'replay':
            req = False
            if phase == 0:
                cmd = 1
            elif phase in (1, 3):
                req = True
            elif phase == 2:
                cmd = 2
            elif phase == 4:
                cmd = 3
            else:
                req = True
        pre = p.signals(sink, g.valid, cmd)
        result = p.tick(req, [128]*p.profile['lanes'], sink, g.valid, g.packet, cmd, reset)
        ingress = g.tick(pre['seed_req'], pre['seed_ready'], True, rng.getrandbits(32), True, reset)
        if scene == 'replay':
            if result['command_accepted']:
                phase += 1
                number = 0
            elif result['accepted'] and phase in (1, 3):
                (original if phase == 1 else replay).append(p.words)
                number += 1
                if number == 3:
                    phase += 1
        if not reset:
            event, explain = 'reset', '复位清空状态；本拍所有握手事件均无效。'
        elif result['seed_accepted']:
            event, explain = 'seed', '完整非零种子装载；epoch加1，age清零。Bivium之后还需5拍预热。'
        elif warm_before:
            event, explain = 'warm', '推进PRNG状态用于预热，丢弃输出；不记为有效随机响应。'
        elif result['command_accepted']:
            event = 'command'
            explain = {1:'SAVE：保存当前状态并锁定epoch，周期换种随后可以延期。',
                       2:'RESTORE：恢复保存状态，允许重放同一流；这不是获取新种子。',
                       3:'RELEASE：解除锁定，若已到期，后续开始重播种。'}[cmd]
        elif result['accepted']:
            event, explain = 'update', '成功接收请求，推进状态并保存响应；本拍可能同时消费上一帧。'
        elif ingress['accepted']:
            event, explain = 'bus', '接收一个合格32bit种子字。必须等整包完成后才能装载PRNG。'
        elif p.valid and not sink:
            event, explain = 'hold', '下游不接收；输出响应和PRNG状态保持，不把保持周期算成新样本。'
        elif pre['seed_req']:
            event, explain = 'wait', '端点需要新种子；完整包和安全装载条件未同时具备，不接受新请求。'
        else:
            event, explain = 'idle', '没有新生成事件；消费旧响应或等待控制命令的安全边界。'
        rows.append(dict(event=event, explain=explain, req=int(req), ready=int(pre['req_ready']),
            accepted=result['accepted'], consumed=result['consumed'], bus=ingress['accepted'],
            seed=result['seed_accepted'], valid=p.valid, epoch=p.epoch, age=p.age,
            warm=p.warm, locked=p.locked, word=p.words[0], bit=bool(p.bits[0]), command=cmd,
            sink=sink, state=hex(p.state), updates=p.counts['prng_updates'],
            warmups=p.counts['warmup_updates'], beats=g.counts['bus_beats'],
            loads=p.counts['seed_loads'], deferred=p.counts['reseed_deferred_cycles']))
    if scene == 'replay':
        assert len(original) == len(replay) == 3 and original == replay
        assert p.counts['reseed_deferred_cycles'] > 0
    if scene == 'reseed':
        assert p.counts['seed_loads'] >= 2
    if scene == 'stall':
        assert p.counts['output_stall_cycles'] == 4
    return rows


def main():
    folder = ROOT/'architecture_tlm/random_service'
    payload = dict(source_commit='970260e21ebcf98822b9cf47b643fb8360a31e2f',
        model_sha256=hashlib.sha256((folder/'model.py').read_bytes()).hexdigest(),
        notes=dict(boot='启动示例：上游始终提供合格字，下游始终接收；仅启动播种。',
                   stall='反压示例：第15～18沿下游rsp_ready=0，其余周期接收；仅启动播种。',
                   reseed='加速换种示例：RESEED_CYCLES=12，便于观察包接收、装载与预热。生产默认仍为1亿拍。',
                   replay='锁定示例：RESEED_CYCLES=6；SAVE后取3帧、RESTORE再取3帧、RELEASE。两段输出已在导出时核对相同。'),
        traces={kind:{scene:trace(kind,scene) for scene in ('boot','stall','reseed','replay')}
                for kind in ('lfsr32','lfsr32_shared64','bivium')})
    template = (folder/'architecture-view.template.html').read_text(encoding='utf-8')
    assert template.count('/*TRACE_DATA*/null') == 1
    html = template.replace('/*TRACE_DATA*/null', json.dumps(payload, ensure_ascii=False, separators=(',',':')))
    out = folder/'architecture-view.html'
    out.write_text(html, encoding='utf-8', newline='\n')
    delivery = ROOT.parent.parent/'远端上传/rng_architecture_20261022.html'
    delivery.write_bytes(out.read_bytes())
    receipt = dict(source_commit=payload['source_commit'], model_sha256=payload['model_sha256'],
                   trace_cases=12, trace_edges=sum(len(rows) for k in payload['traces'].values() for rows in k.values()),
                   exact_model_traces=True, replay_checked_for_all_backends=True,
                   path=str(delivery), bytes=out.stat().st_size, sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
                   numerical_model_modified=False, ppa_run=False)
    (ROOT/'work/rayggxia/95/ARCHITECTURE_VIEW.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(receipt,ensure_ascii=True,indent=2))


if __name__ == '__main__':
    main()
