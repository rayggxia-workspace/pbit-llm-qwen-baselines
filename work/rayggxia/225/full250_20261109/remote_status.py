from pathlib import Path
import json,subprocess,datetime
r=Path(ROOT);s=json.loads((r/'SUBMISSION.json').read_text());ids=','.join(str(s[k]) for k in ('pilot','full_array') if s.get(k))
q=subprocess.run(['squeue','-j',ids,'-h','-o','%i|%j|%T|%M|%R'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
a=subprocess.run(['sacct','-j',ids,'--noheader','--parsable2','--format=JobIDRaw,State,ExitCode,Elapsed,AllocCPUS,MaxRSS'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
cases={}
for name in ('pilot','seed17','seed503','seed1009'):
    work=r/'work'/name;out=r/'outputs'/name;x={}
    for n in ('INVOCATION.json','EXIT.json'):
        if (work/n).exists():x[n]=json.loads((work/n).read_text())
    if (work/'run.log').exists():x['tail']=(work/'run.log').read_text(errors='replace').splitlines()[-5:]
    if (out/'SEAL.json').exists():x['seal']=json.loads((out/'SEAL.json').read_text())
    cases[name]=x
print(json.dumps(dict(observed_UTC=datetime.datetime.utcnow().isoformat(),submission=s,queue=q.stdout.strip().splitlines(),
    accounting=a.stdout.strip().splitlines(),cases=cases)))
