"""Audit immutable long streams, matrices and prior golden prefixes without new simulation."""
import argparse
import json
from pathlib import Path
import numpy as np
from .ideal_readout import digest,dump
from ..backends import PROFILES


def main():
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args()
    root=Path(__file__).resolve().parents[3]
    read=lambda name:json.loads((a.directory/name).read_text(encoding='utf8'))
    cfg=read('CONFIG.json');cases=read('SUMMARY.json')['cases'];count=0
    def check(ok,label):
        nonlocal count
        if not ok:raise AssertionError(label)
        count+=1
    for name,sha in read('SOURCE_MANIFEST.json').items():check(digest(root/name)==sha,name)
    old=json.loads((root/'architecture_tlm/random_service/quality/results/ideal_20261025/SUMMARY.json').read_text(encoding='utf8'))['cases']
    matrix_elements=0;prefixes=0
    for c in cases:
        files={Path(f['path']).name:Path(f['path']) for f in c['artifacts']}
        for f in c['artifacts']:check(digest(f['path'])==f['sha256'] and Path(f['path']).stat().st_size==f['bytes'],'artifact '+f['path'])
        n=c['frames'];lanes=c['lanes_per_instance'];total=lanes*2
        w=np.fromfile(files['words.bin'],dtype=np.uint8).reshape(n,total)
        with np.load(files['matrices.npz']) as arrays:
            for f in ['word']+['q'+str(q) for q in cfg['thresholds']]+['bit'+str(k) for k in range(8)]:
                t=arrays[f+'_acf'];s=arrays[f+'_cross'];matrix_elements+=t.size+s.size
                check(t.shape==(len(cfg['temporal_lags']),total),'all lane/time dimensions')
                check(s.shape==((1 if f.startswith('bit') else len(cfg['spatial_lags'])),total,total),'all pair dimensions')
                check(np.isfinite(t).all() and np.isfinite(s).all(),'no undefined full-sample correlations')
                check(np.max(abs(t))<=1.0000000001 and np.max(abs(s))<=1.0000000001,'Pearson bounds')
                check(np.allclose(s[0],s[0].T,atol=1e-12),'same-cycle symmetry')
                check(np.allclose(np.diag(s[0]),1,atol=1e-12),'same-cycle self diagonal')
                for ki,k in enumerate([0] if f.startswith('bit') else cfg['spatial_lags']):
                    if k:check(np.allclose(np.diag(s[ki]),t[cfg['temporal_lags'].index(k)],atol=1e-10),'temporal vs diagonal')
                x=w if f=='word' else w<int(f[1:]) if f.startswith('q') else (w>>int(f[3:]))&1
                check(np.array_equal(arrays[f+'_mean'],x.mean(0)),'per-lane marginal')
                if f!='word':
                    length=32;p1=x.mean(0);blocks=x.reshape(-1,length,total).mean(1)
                    ratio=blocks.var(0,ddof=1)/(p1*(1-p1)/length)
                    check(np.allclose(ratio,arrays[f+'_varratio_32'],atol=1e-12),'T32 variance recomputation')
            check(np.array_equal(arrays['q128_acf'],arrays['bit7_acf']),'inverted bit7 temporal identity')
            check(np.array_equal(arrays['q128_cross'][0],arrays['bit7_cross'][0]),'inverted bit7 spatial identity')
            if c['source']=='physical' and c['backend']=='lfsr32_shared64':
                check(not np.logical_xor.reduce(w[:,:4]<128,axis=1).any(),'GF port-a exact parity')
                check(not np.logical_xor.reduce(w[:,lanes:lanes+4]<128,axis=1).any(),'GF port-b exact parity')
        if c['source']=='physical':
            prev=next(o for o in old if o['case_id']==c['case_id']+'-boot0')
            check(digest(prev['artifact']['path'])==prev['artifact']['sha256'],'old golden bytes')
            with np.load(prev['artifact']['path']) as z:
                check(np.array_equal(w[:4096],np.concatenate([z['a'],z['b']],axis=1)),'all4096 original Python golden frames')
            prefixes+=1
            tr=json.loads(files['TRANSPORT.json'].read_text(encoding='utf8'))
            check(tr['last_request_cycle']-tr['first_request_cycle']+1==n,'continuous accepted frames')
            check(tr['network']['cycles']==tr['last_request_cycle']+2,'drained last response')
            for port in tr['network']['ports'].values():
                counts=port['counts'];pr=PROFILES[c['backend']]
                check(counts['frames_generated']==counts['responses_consumed']==n,'frame/consume counts')
                check(counts['recurrence_steps']==(n+pr['warmup'])*pr['steps'],'recurrence counts')
            check(len(tr['network']['seed_events'])==2,'only initial loads, no hidden reseed')
    check(len(cases)==36 and prefixes==18,'complete matrix')
    dump(a.directory/'POST_AUDIT.json',dict(status='PASS',checks=count,matrix_elements=matrix_elements,cases=len(cases),
        golden_prefix_cases=prefixes,golden_frames_per_case=4096,execution_commit='2dd9ec33fa321174f3891b0cd684bc5aac4b589a',
        source_manifest_sha256=digest(a.directory/'SOURCE_MANIFEST.json'),config_sha256=digest(a.directory/'CONFIG.json'),
        scope='all artifact SHA, all matrix dimensions/bounds/symmetry, bitplane identities, moments, operation accounting, golden output prefix'))
    print(json.dumps(dict(status='PASS',checks=count,matrix_elements=matrix_elements,cases=len(cases))))


if __name__=='__main__':main()
