from pathlib import Path,PurePosixPath
import json,hashlib,tarfile,zipfile,math,re,io,csv
A=Path(__file__).resolve().parent;ROOT=A.parent.parent;W=ROOT/'tmp/pr55-review-round10-20261024'
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
out={'downloads':[],'records':[],'packages':[],'windows':[]}
for f in load(ROOT/'project_archives/remote_job_audit_20261024/DOWNLOAD_INDEX.json')['files']:
    p=Path(f['local']);b=p.read_bytes();assert len(b)==f['bytes'] and sha(b)==f['sha256'],str(p)
    out['downloads'].append({'path':str(p),'sha256':sha(b)})
checked={}
for id in ['digital-ppa8-20261024-audit','counter-38372030-power-recovery','cim-20261024-recovery']:
    rec=load(W/'digital_circuit_simulation_registry/records'/f'{id}.json')
    members=0
    for a in rec['artifacts']:
        p=Path(a['path']);b=p.read_bytes();assert sha(b)==a['sha256'],str(p)
        if a.get('bytes') is not None:assert len(b)==a['bytes']
        if p.name.endswith('.tar.gz'):
            with tarfile.open(p) as t:
                names=t.getnames();assert len(names)==len(set(names))
                idx=next(n for n in names if n.endswith('/RESULT_INDEX.json'));prefix=idx.rsplit('/',1)[0]+'/'
                entries=json.loads(t.extractfile(idx).read())
                entries={k:v for k,v in entries.items() if isinstance(v,dict) and 'sha256' in v and 'bytes' in v}
                for rel,m in entries.items():
                    data=t.extractfile(prefix+rel).read();assert sha(data)==m['sha256'] and len(data)==m['bytes'],(p,rel)
                members+=len(entries);checked[str(p)]=len(entries)
                rows=[]
                for s in ['SUMMARY.json','summary.json']:
                    if prefix+s in names:
                        x=json.loads(t.extractfile(prefix+s).read());rows=x if isinstance(x,list) else x.get('windows',[]);break
                for row in rows:
                    if not any(row==c or all(c.get(k)==v for k,v in row.items()) for c in rec['cases']):
                        # Digital ledger rows are rebuilt from raw summary; counter rows carry archive provenance fields.
                        candidates=[c for c in rec['cases'] if all(c.get(k)==row.get(k) for k in ['total_uW','window_pJ','duration_ns','setup_slack_ns','hold_slack_ns'])]
                        assert candidates,(id,p,row)
                    total=row['total_uW'];duration=row['duration_ns'];energy=total*duration/1000
                    assert math.isclose(energy,row['window_pJ'],rel_tol=1e-12)
                    assert math.isclose(sum(row[k] for k in ['internal_uW','switching_uW','leakage_uW']),total,rel_tol=.02)
                    for num,den in [('pJ_per_completed_output','completed_outputs'),('pJ_per_frame','frames'),('pJ_per_bin_output','bin_outputs')]:
                        if num in row:
                            assert (row[num] is None) if row[den]==0 else math.isclose(row[num],energy/row[den],rel_tol=1e-12)
                    powerfiles=[n for n in names if n.endswith('/power.rpt')]
                    found=False
                    for pf in powerfiles:
                        text=t.extractfile(pf).read().decode();m=re.search(r'^\s*Total Power\s*=\s*([\deE.+-]+)',text,re.M)
                        u=re.search(r'^\s*Dynamic Power Units?\s*[:=]\s*([\deE.+-]+)\s*(W|mW|uW|nW|pW)',text,re.M)
                        if m and u:
                            value=float(m[1])*float(u[1])*{'W':1e6,'mW':1e3,'uW':1,'nW':.001,'pW':.000001}[u[2]]
                            if math.isclose(value,total,rel_tol=1e-10):found=True;break
                    assert found,('not in original power report',p,total)
                    out['windows'].append({'archive':p.name,'total_uW':total,'window_pJ':energy,'flags':row['review_flags']})
    assert sum(1 for x in out['windows'] if any(x['archive']==Path(a['path']).name for a in rec['artifacts']))==len(rec['cases'])
    out['records'].append({'id':id,'artifacts':len(rec['artifacts']),'members_checked':members,'case_rows':len(rec['cases']),'status':rec['status']})
for zipname,folder,manifest in [('digital_ppa8_ss_tt_100_20261023_v2.zip','digital_ppa_v1/ppa8','package_manifest.json'),('sc_counter_ppa100_20261024_v4.zip','counter_rtl_compare','package_manifest.json'),('sc_cim_frontend_ppa_20261024_v5.zip','sc_cim_frontend_20261023','SOURCE_MANIFEST.json')]:
    with zipfile.ZipFile(ROOT/zipname) as z:
        assert z.testzip() is None
        mp=next(n for n in z.namelist() if n.endswith('/'+manifest));prefix=mp.rsplit('/',1)[0]+'/'
        m=json.loads(z.read(mp));entries=m.get('files',m);same=[];differences=[]
        for rel,h in entries.items():
            b=z.read(prefix+rel);expect=h['sha256'] if isinstance(h,dict) else h
            assert sha(b)==expect,(zipname,rel)
            p=W/'architecture_tlm'/folder/rel
            if p.exists():
                if sha(p.read_bytes())!=expect:differences.append(rel)
                else:same.append(rel)
        out['packages'].append({'archive':zipname,'manifest_members':len(entries),'same_as_checked_out_source':len(same),'differences':differences})
out['unique_archive_members']=sum(checked.values());out['download_count']=len(out['downloads'])
(A/'EVIDENCE_AUDIT.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in out.items() if k not in ['downloads','windows']},ensure_ascii=False,indent=2))
