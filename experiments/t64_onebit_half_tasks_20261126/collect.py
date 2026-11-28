"""Use frozen per-document collector, then render an S2-specific report."""
import importlib.util
import json
from pathlib import Path
import sys

OWN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('half_task_extension', OWN/'runner.py')
extension = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extension)
extension.configure_parent()
spec = importlib.util.spec_from_file_location('frozen_task_collector', extension.TASK_SOURCE/'collect.py')
collector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collector)
collector.OWN = OWN
collector.cases = extension.cases
collector.work_items = extension.previous.work_items


def main():
    collector.main()
    root = Path(sys.argv[1])
    value = collector.sealed(root/'SUMMARY.json')
    if value['status'] == 'blocked':
        return
    plan = json.loads((OWN/'PLAN.json').read_bytes())
    lines = ['# S/S2共享尺度完整任务结果', '',
             f'状态：{value["status"]}；完整组{value["completed_groups"]}/{value["expected_groups"]}；分片{value["completed_parts"]}/{value["expected_parts"]}。',
             '', '|配置|PIQA acc / acc_norm|ARC-C acc / acc_norm|', '|---|---:|---:|']
    for case in extension.cases(plan):
        cells = []
        for task in plan['tasks']:
            row = next((z for z in value['groups'] if z['case']==case and z['task']==task), None)
            cells.append('未完整' if row is None else ' / '.join(f'{100*row["metrics"][k]:.3f}%' for k in ['acc,none','acc_norm,none']))
        lines.append('|'+case['id']+'|'+'|'.join(cells)+'|')
    lines += ['', 'T64/W8、准确SDPA、seed101，g/u组64动态基准与逐元素S/S2一位选择。全题干/答案36层FFN覆盖，不训练、不截断、不套模板。旧S/S4对照独立保留；只能按相同预算、模型和请求ledger配对。']
    (root/'REPORT_ZH.md').write_bytes(('\n'.join(lines)+'\n').encode())


if __name__ == '__main__':
    main()
