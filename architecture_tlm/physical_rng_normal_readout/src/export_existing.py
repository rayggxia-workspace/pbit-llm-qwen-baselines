"""Export existing Spectre voltages and diagnostic bits, without resimulation."""
import argparse,csv,hashlib,json,shutil,tarfile,tempfile
from pathlib import Path
import engine as e
import run_characterization as parser
import long_metrics as m

EXPECTED='c02d6ad9e148b143b906c6b3f87c151c9ce8e05e53fe26683dfaf29d4404134c'
SEEDS=[32003,32009,32027]

def export(archive,out,expected=EXPECTED):
    if e.digest(archive)!=expected:raise ValueError('Original archive SHA mismatch')
    out.mkdir(parents=True,exist_ok=False)
    reports=[]
    names={'38380128_pilot/precision500_base_seed{}/raw/tranNoise.tran.tran'.format(s):s for s in SEEDS}
    with tempfile.TemporaryDirectory(dir=str(out),prefix='reading-') as temp:
        path=Path(temp)/'one.tran'
        with tarfile.open(str(archive),'r|gz') as tar:
            for member in tar:
                if member.name not in names:continue
                if not member.isfile():raise ValueError('Expected regular PSF file')
                seed=names[member.name]
                with tar.extractfile(member) as source,path.open('wb') as dest:shutil.copyfileobj(source,dest,1024*1024)
                source_sha=e.digest(path);rows=[]
                for j,r in enumerate(parser.checked_trace(path,.022,1e-7,['out','bit'])):
                    rel=j-20000
                    if 0<=rel<200000 and rel%10==0:
                        level='LOW' if r['bit']<=.16+1e-12 else 'HIGH' if r['bit']>=.64-1e-12 else 'MID'
                        rows.append(dict(sample_index=rel//10,time_s=r['time'],core_V=r['out'],
                            ideal_0p6V_bit=int(r['out']>.6),old_comparator_V=r['bit'],
                            old_threshold_bit=int(r['bit']>.4),old_level=level,old_level_valid=int(level!='MID')))
                path.unlink()
                if len(rows)!=20000:raise ValueError('Expected exactly20000 samples')
                if any(abs(r['time_s']-(.002+i*1e-6))>1e-12 for i,r in enumerate(rows)):raise ValueError('Timestamp grid mismatch')
                with (out/('seed{}_samples.csv'.format(seed))).open('w',encoding='utf-8',newline='') as f:
                    w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
                ideal=[r['ideal_0p6V_bit'] for r in rows];old=[r['old_threshold_bit'] for r in rows]
                for name,bits in [('ideal_0p6V',ideal),('old_comparator_threshold',old)]:
                    with (out/('seed{}_{}.txt'.format(seed,name))).open('w',encoding='ascii',newline='\n') as f:
                        for bit in bits:f.write(str(bit)+'\n')
                reports.append(dict(seed=seed,samples=20000,interval_s=1e-6,start_s=.002,last_s=rows[-1]['time_s'],
                    source_member=member.name,source_member_sha256=source_sha,
                    ideal=dict(p1=sum(ideal)/20000.,acf={str(k):m.lagged(ideal,k) for k in [1,2,5,10,20,50]}),
                    old_comparator=dict(p1=sum(old)/20000.,midrail=sum(not r['old_level_valid'] for r in rows),
                        acf={str(k):m.lagged(old,k) for k in [1,2,5,10,20,50]})))
    if sorted(r['seed'] for r in reports)!=SEEDS:raise ValueError('Missing/duplicate source seed')
    result=dict(status='EXPORTED_EXISTING_DIAGNOSTIC_SAMPLES_NOT_ENTROPY_QUALIFIED',
        source_job=38380128,source_archive=str(archive),source_archive_sha256=expected,
        source_simulation_commit='f1f93c608b39886ece3484421e9873bbc80d7b30',
        source_manifest_sha256='4d5e031fdc4907fedb25825cdf12f9f651cf3e9b2ad9ba34acd62d8b2246499c',
        export_code_sha256=e.digest(Path(__file__)),seeds=sorted(reports,key=lambda r:r['seed']),
        sampling_policy='Fixed first effective point, every10saved100ns points, no phase or seed selection',
        threshold_policy='Ideal core>0.600000V is software readout only; old physical comparator>0.4V includes allMID flags',
        noisefmin_Hz=500,noisefmax_Hz=1e8,maxstep_s=2.5e-9,core_already_loaded_by_old_comparator=True,
        physical_entropy_certified=False,new_simulation=False)
    e.write_json(out/'SUMMARY.json',result)
    readme='''每seed20000次1us对齐采样 / 2026-10-25 / Issue184

seed32003/32009/32027各一份CSV，两份单列0/1文本。每份文本20000行。
CSV同时含时间、核心电压、理想0.6V阈值bit、旧比较器电压/0.4V阈值bit和有效电平标记。
时间从2ms开始，到21.999ms止；三个seed分别保留，不拼接。

ideal_0p6V.txt是对真实Spectre核心电压作的软件理想读出，不是另一个已实现比较器。
核心原本连接旧比较器；不能把该波形改称完全裸核心。
old_comparator_threshold.txt是真实旧比较器电压的阈值判决，包含MID，不代表全部可用数字位。
有效低<=0.16V、高>=0.64V，其他为MID；CSV标记保留，不删除/挑选相位。

这是原38380128三条20ms有效/500Hz波形的派生导出，不是新仿真、10Hz长漂移或熵验收。
精确原归档/网表/配置/代码来源及各seed统计见SUMMARY.json；逐文件SHA见manifest.json。
1us间隔下理想读出有2万样本，并不证明它们完全独立；多lag、偏置与真实读出仍需验证。
'''
    with (out/'README_ZH.txt').open('w',encoding='utf-8',newline='\n') as stream:stream.write(readme)
    manifest={p.name:dict(bytes=p.stat().st_size,sha256=e.digest(p)) for p in sorted(out.iterdir()) if p.is_file()}
    e.write_json(out/'manifest.json',manifest)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--archive',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();r=export(a.archive,a.out)
    print(json.dumps(dict(out=str(a.out),seeds=[dict(seed=s['seed'],samples=s['samples'],ideal_P1=s['ideal']['p1'],old_MID=s['old_comparator']['midrail']) for s in r['seeds']]),ensure_ascii=False))
