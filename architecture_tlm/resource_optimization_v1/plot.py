"""Standalone figures; all displayed area is explicitly SRAM macro area only."""
import argparse
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def main():
    p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    data=json.loads(a.summary.read_text(encoding='utf-8'));rows=data['rows'];means=data['aggregates'];a.output.mkdir(parents=True,exist_ok=False)
    methods=['bf16_exact','w8_exact','sc_exact','sc_screen_pv'];labels=['BF16 exact','W8 exact','SC exact','SC screen/PV'];colors=['#6c7a89','#146b9b','#bf6854','#8b4e9f']
    candidates=['baseline_1m','mapped_1m','vector_128','balanced_2m','wide_4m'];names=['Baseline\n1 MiB','Mapping\n1 MiB','Vector 128\n1 MiB','Balanced\n2 MiB','Wide\n4 MiB']
    fig,axes=plt.subplots(1,2,figsize=(13,4.6),sharey=True)
    for ax,context in zip(axes,[2048,8192]):
        for i,method in enumerate(methods):
            values=[];errs=[]
            for candidate in candidates:
                row=next(r for r in means if r['method']==method and r['context']==context and r['candidate']==candidate)
                values.append(row['TPOT_mean_ms']);errs.append(row['TPOT_stdev_ms'] or 0)
            ax.bar(np.arange(len(candidates))+(i-1.5)*.19,values,.19,yerr=errs,label=labels[i],color=colors[i])
        ax.set_xticks(range(len(candidates)),names);ax.set_title(f'Qwen, batch 1, context {context}');ax.set_ylabel('Conditional decode time (ms/token)');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    handles,legend=axes[0].get_legend_handles_labels();fig.legend(handles,legend,loc='upper center',ncol=4,frameon=False)
    fig.suptitle('Resource configurations: synthetic TLM, not equal total area or quality proof',y=1.04,fontsize=12);fig.tight_layout(rect=(0,.05,1,.93))
    fig.text(.5,.01,'Bars: mean ± sample SD, n=3 for all five representative configurations',ha='center',fontsize=9)
    fig.savefig(a.output/'latency.png',dpi=180,bbox_inches='tight');fig.savefig(a.output/'latency.svg',bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4.3),sharey=True)
    for ax,context in zip(axes,[2048,8192]):
        for i,method in enumerate(methods):
            subset=[r for r in rows if r['method']==method and r['context']==context and r['seed']==0]
            ax.scatter([r['SRAM_macro_area_mm2'] for r in subset],[r['TPOT_ms'] for r in subset],label=labels[i],color=colors[i],alpha=.8)
        ax.set_title(f'Context {context}, seed 0, 16 common designs');ax.set_xlabel('SRAM macro area only (mm²)');ax.set_ylabel('Conditional decode time (ms/token)');ax.grid(alpha=.2)
    axes[0].legend(frameon=False);fig.suptitle('Partial storage-cost scatter: compute / interface area missing; not a full ASIC Pareto front',fontsize=11);fig.tight_layout()
    fig.savefig(a.output/'partial_area.png',dpi=180,bbox_inches='tight');fig.savefig(a.output/'partial_area.svg',bbox_inches='tight');plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4.2),sharey=True)
    for ax,context in zip(axes,[2048,8192]):
        subset=[next(r for r in rows if r['candidate']=='baseline_1m' and r['method']==m and r['context']==context and r['seed']==0) for m in methods]
        for i,(key,name,color) in enumerate([('fixed_traffic_LB_ms','Fixed traffic bound','#8bc4c9'),('fixed_service_LB_ms','Fixed service bound','#438a97'),('TPOT_ms','Scheduled time','#263c59')]):
            ax.bar(np.arange(4)+(i-1)*.25,[r[key] for r in subset],.25,label=name,color=color)
        ax.set_xticks(range(4),['BF16','W8','SC exact','SC screen/PV']);ax.set_title(f'Baseline 1 MiB, context {context}');ax.set_ylabel('ms/token');ax.grid(axis='y',alpha=.2);ax.set_axisbelow(True)
    axes[0].legend(frameon=False);fig.suptitle('Bounds use max across resources; ideal overlap may be unrealizable',fontsize=12);fig.tight_layout()
    fig.savefig(a.output/'bounds.png',dpi=180,bbox_inches='tight');fig.savefig(a.output/'bounds.svg',bbox_inches='tight');plt.close(fig)


if __name__=='__main__':main()
