"""Small, standard-library simulation evidence registry. No EDA or network access."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys
import tarfile

HERE = Path(__file__).resolve().parent
LEVELS = {'DC_GATE_PT_PRELAYOUT','POSTLAYOUT_PROVISIONAL','GATE_FUNCTIONAL',
          'RTL_FUNCTIONAL','LIBRARY_EXTRACTION','CALIBRATED_ESTIMATE','DESIGN_PROOF',
          'PARTIAL_FLOW','ARCHIVE_METADATA'}


def read(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))


def write(p,x):
    Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def digest(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()


def validate(r):
    for key in ['schema_version','id','name','family','registered_on','owner','issue',
                'evidence_level','status','stages','boundary','conditions','limitations','source','artifacts','cases','next_action']:
        if key not in r:raise ValueError('missing '+key)
    if r['schema_version']!=1 or not re.fullmatch(r'[a-z0-9][a-z0-9-]+',r['id']):raise ValueError('invalid schema/id')
    if r['evidence_level'] not in LEVELS:raise ValueError('invalid evidence level')
    if not r['boundary'] or not r['limitations'] or not r['artifacts']:raise ValueError('boundary/limits/evidence required')
    if set(r['stages'])!={'functional','synthesis','sta','power','postlayout'}:raise ValueError('all five stages required')
    if r['stages']['power']=='calculated' and r['evidence_level'] not in {'DC_GATE_PT_PRELAYOUT','POSTLAYOUT_PROVISIONAL'}:
        raise ValueError('calculated power needs circuit evidence')
    if r['evidence_level'] in {'RTL_FUNCTIONAL','DESIGN_PROOF','CALIBRATED_ESTIMATE'}:
        if r['stages']['power']!='not_run':raise ValueError('functional/design/estimate is not measured PPA')
    for a in r['artifacts']:
        if not isinstance(a.get('present_at_registration'),bool):raise ValueError('artifact availability required')
        if a['present_at_registration']:
            if not re.fullmatch('[0-9a-f]{64}',a.get('sha256') or ''):raise ValueError('SHA256 required')
            if not isinstance(a.get('bytes'),int):raise ValueError('byte size required')
        elif not a.get('missing_reason'):raise ValueError('explain unavailable evidence')
        if 'member' in a and not re.fullmatch('[0-9a-f]{64}',a.get('member_sha256') or ''):raise ValueError('member SHA required')
    for c in r['cases']:
        if not isinstance(c,dict):raise ValueError('case must be object')
    return True


def records():
    result=[]
    for p in sorted((HERE/'records').glob('*.json')):
        r=read(p);validate(r)
        if p.stem!=r['id']:raise ValueError('filename/id mismatch: '+str(p))
        result.append(r)
    if len({r['id'] for r in result})!=len(result):raise ValueError('duplicate run id')
    cat=read(HERE/'catalog.json')
    if set(cat['record_ids'])!={r['id'] for r in result}:raise ValueError('catalog/records mismatch')
    return result


def check(local=False, members=False):
    rr=records();checked={};missing=[];member_count=0
    def filecheck(path,sha,size):
        if not local:return
        p=Path(path)
        if not p.is_file():missing.append(path);return
        if path not in checked:checked[path]=(digest(p),p.stat().st_size)
        if checked[path]!=(sha,size):raise ValueError('evidence bytes changed: '+path)
    for r in rr:
        for a in r['artifacts']:
            if not a['present_at_registration']:continue
            filecheck(a['path'],a['sha256'],a['bytes'])
            if members and Path(a['path']).is_file() and 'member' in a:
                with tarfile.open(a['path']) as t:
                    b=t.extractfile(a['member']).read()
                if len(b)!=a['member_bytes'] or hashlib.sha256(b).hexdigest()!=a['member_sha256']:
                    raise ValueError('archive member changed: '+a['member'])
                member_count+=1
    ar=list(csv.DictReader((HERE/'archive_inventory.csv').open(encoding='utf-8',newline='')))
    for a in ar:
        if not re.fullmatch('[0-9a-f]{64}',a['sha256']):raise ValueError('archive SHA missing')
        filecheck(a['path'],a['sha256'],int(a['bytes']))
    return dict(records=len(rr),case_rows=sum(len(r['cases']) for r in rr),archive_candidates=len(ar),
        local_files_sha_checked=len(checked),archive_members_sha_checked=member_count,
        unavailable_here=sorted(set(missing)),status='PASS' if not missing else 'PORTABLE_SCHEMA_PASS_LOCAL_PATHS_UNAVAILABLE',
        note='Hash checks are provenance checks, not a new circuit simulation or acceptance of every archived run')


def link(p,label=None):
    return '['+(label or p)+'](<'+p+'>)'


def render():
    rr=records();lines=['# 数字电路仿真总览','',
        f'更新：{read(HERE/"catalog.json")["as_of"]}；Issue110。先查此表，再打开记录中的原始结果地址。**已计算PPA、功能通过、库提取、估计、失败历史分别列示。**',
        '',f'当前 {len(rr)} 条批次/模块记录，{sum(len(r["cases"]) for r in rr)} 行配置/seed/窗口数据；这些行不等于独立实验数。',
        '','| 模块/批次 | 证据 | 功能 | 综合 | STA | 功耗 | 配置行 |','|---|---|---|---|---|---|---:|']
    for r in rr:
        s=r['stages'];lines.append('| '+link('records/'+r['id']+'.json',r['name'])+' | '+r['evidence_level']+' | '+s['functional']+' | '+s['synthesis']+' | '+s['sta']+' | '+s['power']+' | '+str(len(r['cases']))+' |')
    lines+=['','`calculated`表示工具算出功耗，**不表示STA闭合、无告警或硅片实测**。`library_only`是库表，`not_run`不是零功耗。',
        '','布局前结果不含真实CTS/布线寄生；共享数字p-bit后端的后布局材料单独标记，不能当作LLM运算核。',
        '',link('01_结果地址索引.md','按模块查精确文件地址和SHA-256')+' · '+link('02_覆盖与待补.md','查看模块覆盖与待补')+' · '+link('archive_inventory.csv','已发现数字结果原始归档索引')]
    (HERE/'00_总览.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    detail=['# 仿真结果地址索引','',
        '路径是当前本机原件/审核文件，不搬移原件。仓库外文件需要访问对应本机或约定共享存储；GitHub用户可读记录和SHA，但不会凭此获得本机文件。',
        '','执行源码不确定时明确写unknown并链接原manifest，不能用登记时HEAD冒充执行版本。']
    for r in rr:
        detail+=['','## '+r['name']+' / '+r['id'],'',
            '**'+r['evidence_level']+' / '+r['status']+'**。'+r['boundary'],
            '', '条件：`'+json.dumps(r['conditions'],ensure_ascii=False)+'`。',
            '', '执行绑定：`'+json.dumps(r['source'],ensure_ascii=False)+'`。',
            '', '| 作用 | 结果文件或归档 | SHA-256（原字节） |', '|---|---|---|']
        for a in r['artifacts']:
            loc=link(a['path'])
            if 'member' in a:loc+=' 内 `'+a['member']+'`（成员SHA '+a['member_sha256']+'）'
            detail.append('| '+a['role']+' | '+loc+' | '+(a.get('sha256') or '原件缺失/待恢复')+' |')
        detail+=['','限制：'+'；'.join(r['limitations']),'','下一步：'+r['next_action']]
    (HERE/'01_结果地址索引.md').write_text('\n'.join(detail)+'\n',encoding='utf-8',newline='\n')
    fieldnames=['id','family','name','evidence_level','status','cases','functional','synthesis','sta','power','postlayout']
    with (HERE/'runs.csv').open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fieldnames,lineterminator='\n');w.writeheader()
        for r in rr:w.writerow({**{k:r[k] for k in fieldnames[:5]},'cases':len(r['cases']),**r['stages']})
    with (HERE/'artifact_locations.csv').open('w',encoding='utf-8',newline='') as f:
        fields=['record_id','role','path','member','bytes','sha256','member_sha256','present_at_registration']
        w=csv.DictWriter(f,fieldnames=fields,lineterminator='\n');w.writeheader()
        for r in rr:
            for a in r['artifacts']:w.writerow(dict(record_id=r['id'],**{k:a.get(k,'') for k in fields[1:]}))


def add(path):
    r=read(path);validate(r);dest=HERE/'records'/(r['id']+'.json')
    if dest.exists():raise ValueError('run already registered; new simulation needs a new run id')
    write(dest,r)
    cat=read(HERE/'catalog.json');cat['record_ids'].append(r['id']);cat['as_of']=max(cat['as_of'],r['registered_on']);write(HERE/'catalog.json',cat)
    render()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    c=sub.add_parser('check');c.add_argument('--local',action='store_true');c.add_argument('--members',action='store_true')
    sub.add_parser('render');a=sub.add_parser('add');a.add_argument('record')
    args=p.parse_args()
    if args.command=='check':print(json.dumps(check(args.local or args.members,args.members),ensure_ascii=False,indent=2))
    elif args.command=='render':render()
    else:add(args.record)
