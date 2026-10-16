"""Full decode comparison for screened compact Ising sampler contracts."""
import argparse
import copy
import csv
import gzip
import json
from pathlib import Path
from run_attention_v3 import configuration
from system_decode import ROOT
from screen_ising_tlm_v4 import ScreenIsingLocal,ScreenIsingDigital


def setup(selection='fixed_budget',context=2048,tokens=1):
    cfg,evidence,shape=configuration();cfg.update(context_tokens=context,decode_tokens=tokens)
    cfg['screen_ising_v4']=json.loads((ROOT/'configs/screen_ising_v4.json').read_text(encoding='utf-8'))
    cfg['screen_ising_v4']['selection']=selection
    if selection=='variable':cfg['screen_ising_v4']['candidate_capacity']=context+tokens-1
    calibration=ROOT/f'configs/attention_max4_c{context}.json'
    if calibration.exists():cfg['attention_v3']['calibration_file']=str(calibration.resolve())
    return cfg,evidence,shape


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'results/screen_ising_v4_20261016')
    p.add_argument('--contexts',type=int,nargs='+',default=[2048,8192])
    p.add_argument('--selections',choices=['fixed_budget','variable'],nargs='+',default=['fixed_budget','variable'])
    p.add_argument('--tokens',type=int,default=1);p.add_argument('--samples',type=int,default=512)
    p.add_argument('--budget-blocks',type=int,default=8);p.add_argument('--capacity',type=int)
    p.add_argument('--small',action='store_true')
    p.add_argument('--variant',choices=['fixed_sc_exact','dual_sc_sz','digital_bf16'],default='fixed_sc_exact')
    p.add_argument('--trace',type=Path);p.add_argument('--ising-sample-trace',type=Path)
    p.add_argument('--macro-config',type=Path,help='JSON replacement of the ising macro configuration')
    p.add_argument('--prebuilt-summary',action='store_true')
    p.add_argument('--memory-cost-profile',type=Path,help='CACTI cost-only override; preserves service timing and local Q-hold assumptions')
    p.add_argument('--bridge',type=Path)
    p.add_argument('--dramsys-config',type=Path,default=ROOT/'dramsys/ddr4_2ch_NoPowerDown.json')
    args=p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):raise SystemExit('Choose an empty --output directory')
    args.output.mkdir(parents=True,exist_ok=True);table=[]
    for context in args.contexts:
        for selection in args.selections:
            cfg,evidence,shape=setup(selection,context,args.tokens);v=cfg['screen_ising_v4']
            if args.memory_cost_profile:
                from cacti_memory import apply_cost_profile
                apply_cost_profile(cfg,json.loads(args.memory_cost_profile.read_text(encoding='utf-8')))
            v.update(samples=args.samples,budget_blocks=args.budget_blocks)
            if selection=='fixed_budget':v['candidate_capacity']=args.budget_blocks*64
            if args.capacity is not None:v['candidate_capacity']=args.capacity
            if args.macro_config:v['ising']=json.loads(args.macro_config.read_text(encoding='utf-8'))
            if args.ising_sample_trace:v['ising'].update(numerical_source='sample_trace',sample_trace_file=str(args.ising_sample_trace.resolve()))
            if args.trace:cfg['attention_v3']['trace_file']=str(args.trace.resolve())
            if args.prebuilt_summary:cfg['attention_v3']['summary_initialization']='prefill_prebuilt'
            if args.small:shape.update(num_hidden_layers=1,vocab_size=1024)
            key=f'{selection}_c{context}'
            if args.bridge:
                cfg['external_memory'].update(backend='dramsys',bridge_executable=str(args.bridge.resolve()),
                    configuration=str(args.dramsys_config.resolve()),max_pending=32,
                    output_prefix=str((args.output/(key+'_dram')).resolve()))
            cls=ScreenIsingDigital if args.variant=='digital_bf16' else ScreenIsingLocal
            model=cls(cfg,args.variant,evidence,shape)
            try:d=model.run()
            finally:
                if hasattr(model.ext,'close'):model.ext.close()
            events=d['attention_v4'].pop('events')
            with gzip.open(args.output/(key+'.transactions.jsonl.gz'),'wt',encoding='utf-8',compresslevel=1) as f:
                for ev in events:f.write(json.dumps(ev,separators=(',',':'))+'\n')
            d['attention_v4']['transactions_file']=key+'.transactions.jsonl.gz'
            d.update(actual_shape=shape,small=args.small)
            (args.output/(key+'.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            r=dict(selection=selection,context=context,capacity=v['candidate_capacity'],
                mean_valid_candidates=sum(r['selected_tokens'] for r in d['attention_v4']['rows'])/len(d['attention_v4']['rows']),
                **{k:d['metrics'][k] for k in ('mean_TPOT_ms','scenario_mJ_per_token','attention_ms_per_token',
                    'ising_active_ms_per_token','ising_mJ_per_token','parameterized_area_mm2')})
            table.append(r);print(json.dumps(r),flush=True)
    with (args.output/'summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(table[0]));w.writeheader();w.writerows(table)
    lines=['筛选 → 紧凑 QK → Ising 宏模块 → V 稀疏累加：场景结果','',
        '合成 logits＋理想 IID 模块输出；宏参数是示例值，不能作为真实 PPL 或芯片能效结论。',
        '完整模型默认24层、固定权重随机FFN、单token decode；筛选摘要默认冷建立。',
        '固定方案8块×64=512槽；可变方案为最坏情况配置到上下文大小。两者保留比例不同。','',
        '策略 | 上下文 | 配置槽数 | 平均有效候选 | 整机ms/token | Attention ms/token | Ising忙碌ms/token | 整机mJ/token']
    for r in table:lines.append(f"{r['selection']} | {r['context']} | {r['capacity']} | {r['mean_valid_candidates']:.2f} | {r['mean_TPOT_ms']:.4f} | {r['attention_ms_per_token']:.4f} | {r['ising_active_ms_per_token']:.4f} | {r['scenario_mJ_per_token']:.4f}")
    lines+=['','Ising内部随机源/反馈/编码器已经包含在模块功耗，不额外计PRNG；外部随机源只服务筛选。',
        'Ising直接输出局部索引，不再准确Softmax/CDF后第二次采样。各头、各层串行复用一个宏模块。',
        '默认Link外存；--bridge才是DRAMSys。未测定的预热、采样周期、功耗、面积均可替换。']
    (args.output/'RESULTS_ZH.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')


if __name__=='__main__':main()
