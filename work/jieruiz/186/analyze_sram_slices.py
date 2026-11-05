import argparse,hashlib,json,statistics
from pathlib import Path
B=Path('C:/Users/86134/Documents/a_P_BIT');R=B/'tmp/ffn-local-pipeline-issue186-20261025';D=R/'architecture_tlm/sliced_sram_20261027';W=R/'work/jieruiz/186'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def put(p,s):p.write_text(s,encoding='utf-8',newline='\n')
p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');args=p.parse_args()
rows=[];pending=[]
for folder,indices in [('results',[0,1,2]),('results_bf16fix',[3,4,5]),('results_accept',[2,5])]:
 for i in indices:
  q=D/f'{folder}/case_{i}/RESULT_SUMMARY.json'
  if not q.exists():pending.append(str(q.relative_to(R)));continue
  r=read(q);mf=read(q.with_name('MANIFEST.json'));assert mf['status']=='completed' and sha(q)==mf['files']['RESULT_SUMMARY.json']['sha256']
  c=r['case'];policy=('beats_accept' if folder=='results_accept' else ['legacy','descriptor','beats_cycle_end'][i%3])
  x=dict(algorithm=c['ffn'],policy=policy,elapsed_ms=r['metrics']['TPOT_ms'],phase_ns=r['phase_ns'],SRAM_bytes=sum(v for k,v in r['SRAM']['traffic'].items() if k.endswith('physical_bytes')),
    summary_path=q.relative_to(R).as_posix(),summary_sha256=sha(q),execution=r['execution_commit'],config_sha256=read(q.with_name('EXECUTION.json'))['config_sha256'],raw_result_sha256=r['raw_result_sha256'],wall_seconds=r['wall_seconds'])
  if 'sliced' in r['SRAM']:
   m=r['SRAM']['sliced'];links=sum(m['link_bytes'].values());banks=sum(m['per_bank_word_operations'].values())
   assert links==x['SRAM_bytes'] and banks*16==links
   x['extra_FIFO_bytes']=m['additional_payload_buffer_bytes'];x['aggregate_link_GBs']=m['aggregate_link_GBs']
   x['link_average_utilization']=sum(v for k,v in r['resource_busy_ns'].items() if k.startswith('sram_link:'))/(r['metrics']['elapsed_ns']*m['clusters'])
   x['bank_average_utilization']=banks*m['bank_period_ns']/(r['metrics']['elapsed_ns']*r['SRAM']['banks'])
   assert x['link_average_utilization']<=1+1e-9 and x['bank_average_utilization']<=1+1e-9
  else:x['extra_FIFO_bytes']=0
  rows.append((x,r))
ignore={'dram_background_ns','digital_idle_ns','sc_idle_ns','control_interconnect_ns','uncalibrated_HBM_system_ns','rng_calibrated_endpoint_energy_pJ'}
checks=[]
for kind in ('sc','bf16'):
 pairs=[(x,r) for x,r in rows if x['algorithm']==kind]
 if not pairs:continue
 base=next(r for x,r in pairs if x['policy']=='legacy');base_x=next(x for x,r in pairs if x['policy']=='legacy')
 for x,r in pairs:
  assert {k:v for k,v in base['actions'].items() if k not in ignore}=={k:v for k,v in r['actions'].items() if k not in ignore},x['policy']
  for k in ('SRAM','DRAM'):assert base[k]['traffic']==r[k]['traffic'],(kind,k,x['policy'])
  for k in ('attention_activity','FFN_activity'):assert base[k]==r[k],(kind,k,x['policy'])
  assert base['random_interface']['frame_output_sha256']==r['random_interface']['frame_output_sha256']
  assert base['config']['core_hz']==r['config']['core_hz']==500000000
  assert base['SRAM']['configured_bytes']==r['SRAM']['configured_bytes']==8*1024**2
  assert base['SRAM']['banks']==r['SRAM']['banks']==512
  x['time_change_percent']=(x['elapsed_ms']/base_x['elapsed_ms']-1)*100
  x['FFN_ms']=sum(v for k,v in r['phase_ns'].items() if k=='FFN' or k.startswith('FFN_') or k in ('ffn_output_conversion','ffn_residual'))/1e6
  x['lm_head_ms']=r['phase_ns'].get('lm_head_and_argmax',0)/1e6
  x['non_lm_head_ms']=x['elapsed_ms']-x['lm_head_ms']
  checks.append(dict(algorithm=kind,policy=x['policy'],same_arithmetic=True,same_physical_memory_bytes=True,same_FFN_and_attention_work=True,same_actual_random_output=True))
result=dict(status='partial' if pending else 'completed',rows=[x for x,r in rows],pending=pending,checks=checks,
    scope='one real-shaped Qwen3-4B decoder layer plus full151936 vocabulary; not36layer TPOT, no PPL/PPA',
    negative_results_preserved='cycle_end and original BF16 pre-run configuration failures retained',default_model_changed=False)
if pending and not args.partial:raise ValueError('incomplete matrix '+str(pending))
put(D/'COMPARISON.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n')
table=['# 分簇共享SRAM调度：实际对照','',result['scope'],'',
 '**总容量/带宽、算术和物理访存不变；beat方案额外16KiB FIFO明确计为未校准硬件成本。**','',
 '| 存储调度 | SC非词表部分 ms | SC含完整词表 ms | BF16非词表部分 ms | BF16含完整词表 ms |','|---|---:|---:|---:|---:|']
labels={'legacy':'旧全局fabric/描述符锁','descriptor':'分slice，bank仍整描述符','beats_cycle_end':'逐beat，写FIFO保留至周期末','beats_accept':'逐beat，写入接受即返credit'}
for policy,label in labels.items():
 values=[]
 for kind in ('sc','bf16'):
  x=next((x for x,r in rows if x['algorithm']==kind and x['policy']==policy),None)
  values.extend([f"{x['non_lm_head_ms']:.6f}",f"{x['elapsed_ms']:.6f}"] if x else ['待完成','待完成'])
 table.append('| '+label+' | '+' | '.join(values)+' |')
table+=['',f"已封存{len(rows)}/8项；未收齐时不能声明最终结果。主验证逐配置保持算术、SRAM/DRAM物理字节、FFN/Attention工作与实际RNG输出SHA相同。正号是变慢。没有把单层＋词表乘36当作整机时间。",'',
 '## 如何解释','',
 '仅拆全局锁仍可能无收益：同一长流仍会访问大部分bank，且阶段依赖、唯一DMA actor和既有算子供数顺序未改变。细化模型还显式计入包、bank时钟对齐和有限buffer；旧模型不是统一的悲观上界。','',
 'cycle_end策略让写入payload等待整个bank周期才返credit；accept在SRAM接收沿后返credit，bank端口仍独占完整12.5ns。二者作为硬件协议对照保留，而非改掉旧结果。具体收益以完整表为准。','',
 '新模型限定带宽在每个bank、端点与slice共享读写链路上，保持4×128GB/s总预算512GB/s，不能把每簇都当512GB/s。16KiB FIFO/互连/CDC功耗尚未校准，不能将旧2.52W直接套为新结构能耗。','',
 '参考/结构/限制见README_ZH.md；COMPARISON.json含执行提交、配置/原结果SHA与机器检查。原执行3169的BF16三项配置前失败，3175仅补这三项；旧SC健康项未重跑。accept执行3178是新协议比较。无新GPU质量/RTL/PT，全模型时序仍旧入口。','']
put(D/'RESULTS_ZH.md','\n'.join(table))
put(W/'SRAM_SLICE_COMPARISON_VALIDATION.json',json.dumps(dict(status=result['status'],completed=len(rows),pending=pending,checks=checks,new_tests=13,regression_tests=45,full_model_claim=False,new_PPA=False),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(dict(completed=len(rows),pending=len(pending),rows=[{k:v for k,v in x.items() if k in ('algorithm','policy','elapsed_ms','time_change_percent','FFN_ms','lm_head_ms')} for x,r in rows]),ensure_ascii=True))
