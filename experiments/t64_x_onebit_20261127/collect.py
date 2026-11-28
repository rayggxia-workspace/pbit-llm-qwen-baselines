import importlib.util,json,sys
from pathlib import Path
OWN=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('x_extension',OWN/'runner.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.configure()
# Frozen collector's runner import must resolve to the configured old runner.
sys.modules['runner']=m.tasks
spec=importlib.util.spec_from_file_location('frozen_collector',m.TASK/'collect.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
c.OWN=OWN;c.cases=m.cases;c.work_items=m.tasks.work_items

if __name__=='__main__':
    c.main();root=Path(sys.argv[1]);tasks=c.sealed(root/'SUMMARY.json')
    ppl=c.sealed(root/'ppl/RESULT.json') if (root/'ppl/RESULT.json').exists() else None
    result=dict(status='completed' if tasks['status']=='completed' and ppl and ppl['status']=='completed' else 'incomplete',
                tasks=tasks,ppl=ppl)
    c.save(root/'FINAL_RESULT.json',result)
    lines=['# x共享基准＋1bit，GU16/Wd32','',f'状态：{result["status"]}；任务{tasks.get("completed_groups",0)}/2，分片{tasks.get("completed_parts",0)}/25。',
           '', '|任务|acc|acc_norm|','|---|---:|---:|']
    for row in tasks.get('groups',[]):
        lines.append('|'+row['task']+'|'+f'{100*row["metrics"]["acc,none"]:.3f}%|{100*row["metrics"]["acc_norm,none"]:.3f}%|')
    lines+=['','|PPL范围|配置|PPL|','|---|---|---:|']
    if ppl:
        for scope in ['pilot','full']:
            for row in ppl[scope]:lines.append(f'|{scope}|{row["case"]["id"]}|{row["result"]["ppl"]:.6f}|')
    lines+=['','固定T64/W8、准确Attention、seed101，无训练。pilot为8窗9215目标，full为292窗299077目标，范围分别比较。旧S2/x纯共享与原四档任务对照独立保留，不能标为新结果。']
    (root/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())
    print(json.dumps(dict(status=result['status'],task_groups=tasks.get('completed_groups'),ppl_completed=ppl is not None)))
