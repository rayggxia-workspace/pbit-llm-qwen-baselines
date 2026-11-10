from pathlib import Path
import subprocess,json,datetime
r=Path(ROOT);s=json.loads((r/'SUBMISSION.json').read_text());mf=json.loads((r/'FROZEN_MANIFEST.json').read_text())
ids=','.join([str(s['pilot'])]+[str(x['job_id']) for x in s['full_jobs']])
q=subprocess.run(['squeue','-j',ids,'-h','-o','%i|%j|%T|%M|%R|%C'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
a=subprocess.run(['sacct','-j',ids,'--noheader','--parsable2','--format=JobIDRaw,State,ExitCode,Elapsed,AllocCPUS,MaxRSS'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
cases={}
for phase,key in [('pilot','gates'),('full','full')]:
    for c in mf[key]:
        name=phase+'_'+c['model']+'_'+c['scheme']+'_s'+str(c['seed']);w=r/'work'/name;o=r/'outputs'/name;x={}
        for n in ('INVOCATION.json','EXIT.json'):
            if (w/n).exists():x[n]=json.loads((w/n).read_text())
        if (w/'run.log').exists():x['tail']=(w/'run.log').read_text(errors='replace').splitlines()[-4:]
        if (o/'SEAL.json').exists():x['seal']=json.loads((o/'SEAL.json').read_text())
        cases[name]=x
print(json.dumps(dict(observed_UTC=datetime.datetime.utcnow().isoformat(),submission=s,queue=q.stdout.strip().splitlines(),
    accounting=a.stdout.strip().splitlines(),cases=cases)))
