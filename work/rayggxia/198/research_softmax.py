"""Fetch primary paper bytes locally; do not publish copyrighted PDF originals."""
from pathlib import Path
import concurrent.futures
import hashlib
import json
import urllib.request

W=Path(__file__).parent
P=W/'.survey_private'
SOURCES={
 'softgen_final2020.pdf':'https://utw10244.utweb.utexas.edu/pubs/SoftMax___ASAP2020_June27.pdf',
 'li_scis2024.pdf':'https://scis.scichina.com/en/2024/200404.pdf',
 'consmax_v3.pdf':'https://arxiv.org/pdf/2402.10930v3',
 'ita_v1.pdf':'https://arxiv.org/pdf/2307.03493v1',
}

def download(pair):
    name,url=pair;p=P/name
    if not p.exists():
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        with urllib.request.urlopen(req,timeout=55) as r:b=r.read()
        assert b.startswith(b'%PDF'),name;p.write_bytes(b)
    b=p.read_bytes()
    return dict(file=name,url=url,bytes=len(b),sha256=hashlib.sha256(b).hexdigest())

def main():
    P.mkdir(exist_ok=True)
    out=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures={pool.submit(download,pair):pair[0] for pair in SOURCES.items()}
        for f in concurrent.futures.as_completed(futures):
            try:out.append(f.result())
            except Exception as e:out.append(dict(file=futures[f],error=str(e)))
    (P/'DOWNLOADS.json').write_bytes((json.dumps(out,indent=2)+'\n').encode())
    print(json.dumps(out,indent=2))

if __name__=='__main__':main()
