"""Clip a VCD into explicit windows without replacing any X/Z value."""
import csv,json,pathlib,re,sys

def clip(src,dst,start_ns,end_ns):
    header=[];widths={};names={};scope=[];values={};unknown=set();count=0
    with src.open() as f,dst.open('w') as out:
        for line in f:
            header.append(line);a=line.split()
            if a and a[0]=='$scope':scope.append(a[2])
            elif a and a[0]=='$upscope':scope.pop()
            elif a and a[0]=='$var':
                widths[a[3]]=int(a[2]);names[a[3]]='/'.join(scope+[a[4]])
            if '$enddefinitions' in line:break
        else:raise ValueError('Missing header')
        h=''.join(header)
        m=re.search(r'\$timescale\s*(\d+)\s*(s|ms|us|ns|ps|fs)\s*\$end',h)
        if not m:raise ValueError('Unknown timescale')
        scale=int(m[1])*dict(s=1e9,ms=1e6,us=1e3,ns=1,ps=.001,fs=.000001)[m[2]]
        begin=round(start_ns/scale);end=round(end_ns/scale)
        if begin>=end:raise ValueError('Empty window')
        out.write(h);time=0;started=False;last_time=0
        def begin_dump():
            out.write('#0\n$dumpvars\n')
            for code,width in widths.items():
                value=values.get(code,'x')
                out.write((value+code if width==1 and len(value)==1 else 'b'+value+' '+code)+'\n')
                if re.search('[xz]',value,re.I):unknown.add(code)
            out.write('$end\n')
        for line in f:
            s=line.strip()
            if not s or s.startswith('$'):continue
            if s.startswith('#'):
                time=int(s[1:]);last_time=time
                if time>=begin and not started:begin_dump();started=True
                if time>=end:out.write('#{}\n'.format(end-begin));break
                if started:out.write('#{}\n'.format(time-begin))
            elif s[0] in 'bB01xXzZ':
                if s[0] in 'bB':value,code=s[1:].split()
                else:value,code=s[0],s[1:]
                values[code]=value
                if started:
                    out.write(line);count+=1
                    if re.search('[xz]',value,re.I):unknown.add(code)
            elif s.startswith('r'):
                raise ValueError('Unexpected real signal in DUT wave')
        if not started or last_time<end:raise ValueError('Truncated VCD')
    return dict(duration_ns=end_ns-start_ns,events=count,signals=len(widths),
                xz_signals=len(unknown),xz_examples=[names[x] for x in sorted(unknown)[:30]],
                note='No X/Z replacement or isolated-net waiver; internal uninitialized memories may require review.')

if __name__=='__main__':
    folder=pathlib.Path(sys.argv[1]);report={}
    with (folder/'windows.csv').open() as f:
        for r in csv.DictReader(f):
            phase=r['phase'];report[phase]=clip(folder/'activity.vcd',folder/(phase+'.vcd'),float(r['start_ns']),float(r['end_ns']))
    (folder/'wave_audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
