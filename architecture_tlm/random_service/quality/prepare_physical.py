"""Read existing Spectre PSF-ASCII in an audited archive; never run Spectre.

Stores compact thresholded records outside Git. Source bytes remain untouched.
"""
import argparse, hashlib, io, json, tarfile
from pathlib import Path
import numpy as np


def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1<<20),b''): h.update(chunk)
    return h.hexdigest()


def parse(payload, signal, dt, threshold):
    current={}; bits=[]; times=[]; in_values=False
    def row():
        if 'time' not in current: return
        t=current['time']
        if signal not in current: raise ValueError('missing signal')
        if .002-1e-12 <= t < .02-1e-12:
            times.append(t);bits.append(current[signal]>threshold)
    for line in io.StringIO(payload.decode('ascii')):
        s=line.strip()
        if s=='VALUE': in_values=True;continue
        if not in_values: continue
        if s=='END': row();current={};break
        p=s.split()
        if len(p)!=2: continue
        name=p[0].strip('"')
        try: value=float(p[1])
        except ValueError: continue
        if name=='time': row();current={}
        current[name]=value
    if current: row()
    a=np.asarray(times)
    if len(a)!=round(.018/dt) or not np.allclose(a,.002+np.arange(len(a))*dt,rtol=0,atol=1e-12):
        raise ValueError('incomplete/nonuniform retained record')
    return np.asarray(bits,dtype=np.uint8)


def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--audit',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();audit=json.loads(a.audit.read_text(encoding='utf-8'))
    if a.out.exists(): raise FileExistsError(a.out)
    if digest(a.archive)!=audit['sha256']:raise ValueError('archive hash mismatch')
    wanted={f'{kind}_long_seed{seed}/raw/tranNoise.tran.tran':(kind,seed)
            for kind in ('bare','buffers_x2','b1_p2_b2_n2') for seed in (401,503,607)}
    arrays={};records=[]
    with tarfile.open(a.archive,'r|gz') as tar:
        for member in tar:
            rel='/'.join(member.name.split('/')[1:])
            if rel not in wanted:continue
            kind,seed=wanted[rel];payload=tar.extractfile(member).read()
            sha=hashlib.sha256(payload).hexdigest()
            if sha!=audit['members'][rel]['sha256']:raise ValueError('member hash mismatch')
            dt=2e-8 if kind=='bare' else 1e-7
            bits=parse(payload,'out' if kind=='bare' else 'bit',dt,.6 if kind=='bare' else .4)
            key=f'{kind}_{seed}';arrays[key]=bits
            records.append(dict(key=key,kind=kind,seed=seed,dt_s=dt,n=len(bits),
                member=member.name,member_sha256=sha,bits_sha256=hashlib.sha256(bits.tobytes()).hexdigest(),
                signal='out' if kind=='bare' else 'bit',threshold_V=.6 if kind=='bare' else .4))
            print(key,len(bits),flush=True)
    if len(arrays)!=9:raise ValueError('missing physical records')
    a.out.mkdir(parents=True);np.savez_compressed(a.out/'bits.npz',**arrays)
    meta=dict(archive=str(a.archive),archive_sha256=audit['sha256'],records=records,
        evidence='existing Spectre transient-noise replay, TT25C; not silicon data or simultaneous array channels',
        discard_s=.002,stop_s=.02,npz_sha256=digest(a.out/'bits.npz'))
    (a.out/'manifest.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':main()
