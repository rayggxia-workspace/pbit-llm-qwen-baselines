"""Resolve VCS escaped bit-net / vector-port duplicate names by proving equality.

Only duplicate declarations are renamed. Data events and all mapped boundary
names remain present. Independent codes must agree after settling each timestamp,
matching the zero-delay settling convention of the existing activity checker.
"""
import re
def normalize(src,dst):
 scope=[];names={};widths={};pairs=[];renamed=[];header=[]
 with src.open() as f,dst.open('w') as out:
  for line in f:
   a=line.split()
   if a[:1]==['$scope']:scope.append(a[2])
   elif a[:1]==['$upscope']:scope.pop()
   elif a[:1]==['$var']:
    width=int(a[2]);code=a[3];ref=a[4];widths[code]=width
    suffix=''.join(a[5:-1]);z=re.fullmatch(r'\[(-?\d+)(?::(-?\d+))?\]',suffix) if suffix else None
    if suffix and not z:raise ValueError('Unsupported alias range')
    if z:
     left=int(z[1]);right=int(z[2]) if z[2] else left
     indices=list(range(left,right+(1 if right>=left else -1),1 if right>=left else -1))
    else:indices=list(range(width-1,-1,-1))
    if len(indices)!=width:raise ValueError('Alias width mismatch')
    full=['/'.join(scope+[ref.lstrip('\\')+('[%d]'%i if width>1 or z else '')]) for i in indices]
    duplicate=[x in names for x in full]
    if any(duplicate):
     if not all(duplicate):raise ValueError('Partial duplicate vector requires explicit handling')
     for j,name in enumerate(full):
      if names[name]!=(code,j):pairs.append((names[name],(code,j),name))
     renamed.append(full)
     line='$var %s %d %s __mv_verified_alias_%d %s $end\n'%(a[1],width,code,len(renamed),suffix)
    else:
     for j,name in enumerate(full):names[name]=(code,j)
   header.append(line)
   if '$enddefinitions' in line:break
  else:raise ValueError('Missing VCD header')
  out.write(''.join(header))
  required={x[0] for p in pairs for x in p[:2]};state={};points=0;started=False
  def check():
   nonlocal points
   for a,b,name in pairs:
    if a not in state or b not in state or state[a] not in '01' or state[b] not in '01' or state[a]!=state[b]:
     raise ValueError('Conflicting duplicate VCD waveform '+name)
   points+=1
  for line in f:
   s=line.strip()
   if s.startswith('#'):
    if started:check()
    started=True
   elif s and not s.startswith('$'):
    if s[0] in 'bB':value,code=s[1:].split()
    elif s[0] in '01xXzZ':value,code=s[0],s[1:]
    else:raise ValueError('Unsupported VCD value during alias proof')
    if code in required:
     value=value.lower();value=value.rjust(widths[code],value[0] if value[0] in 'xz' else '0')
     if len(value)!=widths[code]:raise ValueError('Bad alias value width')
     for j,v in enumerate(value):state[code,j]=v
   out.write(line)
  if started:check()
 return {'duplicate_declarations_renamed':len(renamed),'independent_bit_pairs_verified':len(pairs),
         'settled_timestamps_checked':points,'all_duplicate_waveforms_equal':True}
