from pathlib import Path
import json,subprocess,datetime
r=Path(ROOT);s=json.loads((r/'SUBMISSION.json').read_text());ids=','.join(str(s[k]) for k in ('pilot','full_array') if s.get(k))
q=subprocess.run(['squeue','-j',ids,'-h','-o','%i|%j|%T|%M|%R'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
a=subprocess.run(['sacct','-j',ids,'--noheader','--parsable2','--format=JobIDRaw,State,ExitCode,Elapsed,AllocCPUS,MaxRSS'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
cases={}
for phase in ('pilot','full'):
    for scheme in s['schemes']:
        case=phase+'_'+scheme;w=r/'work'/case;o=r/'outputs'/case;x={}
        for n in ('INVOCATION.json','EXIT.json'):
            if (w/n).exists():x[n]=json.loads((w/n).read_text())
        if (w/'run.log').exists():x['tail']=(w/'run.log').read_text(errors='replace').splitlines()[-4:]
        if (o/'SEAL.json').exists():x['seal']=json.loads((o/'SEAL.json').read_text())
        cases[case]=x
print(json.dumps(dict(observed_UTC=datetime.datetime.utcnow().isoformat(),submission=s,queue=q.stdout.strip().splitlines(),accounting=a.stdout.strip().splitlines(),cases=cases)))
