"""Derive readable comparisons from SHA-verified, sealed result summaries."""
import hashlib,json
from pathlib import Path
HERE=Path(__file__).resolve().parent

def read_results():
 rows={}
 for folder in sorted((HERE/'results').glob('case_*')):
  mf=json.loads((folder/'MANIFEST.json').read_text(encoding='utf-8'))
  assert mf['status']=='completed'
  path=folder/'RESULT_SUMMARY.json'
  assert hashlib.sha256(path.read_bytes()).hexdigest()==mf['files'][path.name]['sha256']
  r=json.loads(path.read_text(encoding='utf-8'));r['result_path']=path.relative_to(HERE).as_posix()
  r['ffn_ms']=sum(v for k,v in r['phase_ns'].items() if k.startswith(('FFN_','ffn_')))/1e6
  rows[r['case']['name']]=r
 return rows

def main():
 rows=read_results();names=['full_old','full_dual_shared','full_dual_bypass']
 out=['# 封存结果自动汇总','', '单位：ms；合成事务时序，无模型精度或实测芯片性能含义。','',
      '## 完整36层decode（含词表输出层）','', '| 方案 | 整机/token | FFN总计 | Attention core | QKV/O投影 | 词表输出 |','|---|---:|---:|---:|---:|---:|']
 for n in names:
  if n not in rows:continue
  r=rows[n];p=r['phase_ns'];out.append(f"| {n} | {r['metrics']['TPOT_ms']:.4f} | {r['ffn_ms']:.4f} | {p['attention_core']/1e6:.4f} | {(p['QKV_projection']+p['O_projection'])/1e6:.4f} | {p['lm_head_and_argmax']/1e6:.4f} |")
 out+=['','## 单层因果扫描','', '下列只比较FFN相位；不把单层总时间当完整模型时间。非FFN算子不随FFN新调度改变；SRAM翻倍实验会同时影响其他算子，所以不能拿其整机变化归因于FFN。','',
       '| 方案 | FFN/层 | 相对双缓冲shared变化 |','|---|---:|---:|']
 ref=rows.get('layer_dual_shared',{}).get('ffn_ms')
 for n,r in rows.items():
  if not n.startswith('layer_'):continue
  ratio='N/A' if ref is None else f"{(r['ffn_ms']/ref-1)*100:+.2f}%"
  out.append(f"| {n} | {r['ffn_ms']:.6f} | {ratio} |")
 # Three primary configurations change schedules/storage only.
 for keys in [['full_old','full_dual_shared','full_dual_bypass'],['layer_old','layer_serial_new','layer_dual_shared','layer_dual_bypass']]:
  present=[rows[n] for n in keys if n in rows]
  if not present:continue
  a=present[0]
  for b in present[1:]:
   assert a['attention_activity']==b['attention_activity']
   assert a['FFN_activity']==b['FFN_activity']
   for k in ['SC_W8_magnitude_AND','SC_signed_temporal_accumulate','SC_coefficient16_restore','SC_bucket_shift_reduce']:
    assert a['actions'][k]==b['actions'][k],k
   for k in ['weights_logical_bytes','weight_scales_logical_bytes','weights_physical_bytes','weight_scales_physical_bytes']:
    assert a['DRAM']['traffic'][k]==b['DRAM']['traffic'][k],k
 if all(n in rows for n in names):
  a,b,c=[rows[n] for n in names]
  assert a['SRAM']['traffic']==b['SRAM']['traffic']
  expected=2*(b['FFN_contract']['local_pipeline']['counts']['weight_load_bytes']+b['FFN_contract']['local_pipeline']['counts']['coefficient_load_bytes'])
  actual=sum(b['SRAM']['traffic'][x]-c['SRAM']['traffic'][x] for x in ['read_logical_bytes','write_logical_bytes'])
  assert actual==expected
  out+=['','## 守恒检查','', '通过：相同FFN有效工作/采样计数、外存权重与系数字节、Attention事件；shared双缓冲与旧版SRAM字节完全相同；bypass只减对应FFN权重/系数shared写入+读取。',
        f'- bypass减少shared逻辑访问：{actual/1024**3:.6f} GiB/token。',
        f"- SRAM内部动态能量模型（不含其他电路）: {a['energy_J']['SRAM_internal']*1000:.6f} → {b['energy_J']['SRAM_internal']*1000:.6f} → {c['energy_J']['SRAM_internal']*1000:.6f} mJ/token。"]
 out+=['','## 逐项证据','']
 for n,r in rows.items():out.append(f"- [{n}]({r['result_path']})；执行提交 `{r['execution_commit']}`。")
 (HERE/'RESULTS_ZH.md').write_text('\n'.join(out)+'\n',encoding='utf-8',newline='\n')
 print(json.dumps(dict(completed=len(rows),full_completed=sum(n in rows for n in names),conservation='passed for available paired cases')))
if __name__=='__main__':main()
