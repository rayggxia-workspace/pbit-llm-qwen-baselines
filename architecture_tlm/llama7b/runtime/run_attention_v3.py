"""Run explicit Attention scenarios without overwriting historical results."""
import argparse
import copy
import csv
import gzip
import json
from pathlib import Path
from run_local_shared_v2 import configs
from system_decode import ROOT
from attention_tlm_v3 import AttentionLocalDecode,AttentionDigitalDecode,MODES


def configuration():
    cases,evidence,shape=configs()
    cfg=next(c for n,c in cases if n=='new_A8_per_tile')
    cfg['attention_v3']=json.loads((ROOT/'configs/attention_v3.json').read_text(encoding='utf-8'))
    return cfg,evidence,shape


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=ROOT/'results/attention_v3')
    p.add_argument('--contexts',type=int,nargs='+',default=[2048,8192])
    p.add_argument('--modes',choices=MODES,nargs='+',default=list(MODES))
    p.add_argument('--variants',choices=['fixed_sc_exact','dual_sc_sz','digital_bf16'],nargs='+',default=['fixed_sc_exact'])
    p.add_argument('--tokens',type=int,default=2)
    p.add_argument('--samples',type=int,default=512)
    p.add_argument('--small',action='store_true')
    p.add_argument('--trace',type=Path)
    p.add_argument('--calibration',type=Path)
    p.add_argument('--summary-initialization',choices=['cold_build','prefill_prebuilt'],default='cold_build')
    p.add_argument('--bridge',type=Path)
    p.add_argument('--dramsys-config',type=Path,default=ROOT/'dramsys/ddr4_2ch_NoPowerDown.json')
    args=p.parse_args()
    if args.output.exists() and any(args.output.iterdir()):raise SystemExit('Output must be empty; choose --output to preserve previous runs')
    args.output.mkdir(parents=True,exist_ok=True)
    base,evidence,shape=configuration()
    if args.small:shape.update(num_hidden_layers=1,vocab_size=1024)
    rows=[]
    for length in args.contexts:
        for variant in args.variants:
            for mode in args.modes:
                cfg=copy.deepcopy(base);cfg.update(context_tokens=length,decode_tokens=args.tokens)
                a=cfg['attention_v3'];a.update(mode=mode,samples=args.samples,summary_initialization=args.summary_initialization)
                if args.trace:a['trace_file']=str(args.trace.resolve())
                if args.calibration:a['calibration_file']=str(args.calibration.resolve())
                else:
                    candidate=ROOT/f'configs/attention_max4_c{length}.json'
                    if candidate.exists():a['calibration_file']=str(candidate.resolve())
                key=f'{variant}_{mode}_c{length}'
                if args.bridge:
                    cfg['external_memory'].update(backend='dramsys',bridge_executable=str(args.bridge.resolve()),
                        configuration=str(args.dramsys_config.resolve()),max_pending=32,
                        output_prefix=str((args.output/(key+'_dram')).resolve()))
                cls=AttentionDigitalDecode if variant=='digital_bf16' else AttentionLocalDecode
                model=cls(cfg,variant,evidence,shape)
                try:result=model.run()
                finally:
                    if hasattr(model.ext,'close'):model.ext.close()
                events=result['attention_v3'].pop('events')
                with gzip.open(args.output/(key+'.transactions.jsonl.gz'),'wt',encoding='utf-8') as f:
                    for event in events:f.write(json.dumps(event)+'\n')
                result['attention_v3']['transactions_file']=key+'.transactions.jsonl.gz'
                result['actual_shape']=shape;result['small']=args.small
                (args.output/(key+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
                row=dict(variant=variant,mode=mode,context=length,**result['metrics'],
                    selected_QK_fraction=result['actions']['ATT_selected_QK_tokens']/result['actions']['ATT_possible_QK_tokens'],
                    rng_words=result['actions'].get('ATT_random_words',0),
                    ising_attempts=result['actions'].get('ATT_ising_attempts',0),
                    v_dram_bytes=result['traffic'].get('attention_V_gather_physical_bytes',0),
                    source=result['attention_v3']['trace']['kind'])
                rows.append(row)
                print(key,json.dumps({k:row[k] for k in ('mean_TPOT_ms','attention_ms_per_token','scenario_mJ_per_token')}),flush=True)
    with (args.output/'summary.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    report=['Attention v3：事务一致性验证场景（不是芯片实测或 Qwen PPL）','',
        '默认为合成高斯 logits；真实校准参数只能校准筛选器，不能把合成 logits 变成真实工作负载。',
        '所有方案保留完整24层 FFN、投影、残差、输出；--small 例外。',
        '默认简化 Link 外存，只有提供 --bridge 时才调用 DRAMSys。',
        '筛选默认计入首个 decode 的摘要冷建立；预热后结果见逐 token 时间。','',
        '方案 | 上下文 | 整机 ms/token | Attention核心 ms/token | 整机 mJ/token | Attention直接 mJ/token | 保留QK比例']
    for r in rows:report.append(f"{r['mode']} / {r['variant']} | {r['context']} | {r['mean_TPOT_ms']:.4f} | {r['attention_ms_per_token']:.4f} | {r['scenario_mJ_per_token']:.4f} | {r['attention_direct_mJ_per_token']:.4f} | {r['selected_QK_fraction']:.3f}")
    report+=['','Attention核心不含 Q/K/V/O 投影。Attention直接能量不含共享闲置及共享根种子；',
        'DRAMSys 下 DRAMPower 无分请求归因，查看整机能量；不得将此列当完整 Attention 能耗。',
        'Ising 为串行数字随机选点更新的明确映射，不能代表原论文并行物理 p-bit 网络。',
        '本次没有新的全模型质量验证。源文件、配置、逐行采样统计和事务日志保存在同目录。']
    (args.output/'RESULTS_ZH.txt').write_text('\n'.join(report)+'\n',encoding='utf-8')


if __name__=='__main__':main()
