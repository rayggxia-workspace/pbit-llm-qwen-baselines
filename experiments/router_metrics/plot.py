import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path('results/router_metrics_20261007')
rows=json.loads((root/'summary.json').read_text())['results']
fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
variants=[('mean_sigmoid','adaptive','Mean + budget matching','#888888','o'),
          ('max2','moment','2 summaries + mean/std threshold','#4477aa','s'),
          ('max4','stochastic','4 summaries + fixed threshold','#ccaa66','x'),
          ('max4','adaptive','4 summaries + budget matching','#aa3377','^'),
          ('max4','moment','4 summaries + mean/std threshold','#228833','*')]
for ax,ctx in zip(axes,(2048,8192)):
    for method,selection,label,color,marker in variants:
        chosen=[r for r in rows if r['context']==ctx and r['method']==method and r['selection']==selection]
        chosen.sort(key=lambda r:r['total_QK_PV_selector_MAC_ratio'])
        ax.errorbar([r['total_QK_PV_selector_MAC_ratio']*100 for r in chosen],[r['PPL'] for r in chosen],
                    yerr=[r['PPL_seed_sd'] for r in chosen],label=label,color=color,marker=marker,markersize=7)
    baseline=next(r['PPL'] for r in rows if r['context']==ctx and r['method']=='sdpa')
    ax.axhline(baseline,color='black',linestyle='--',linewidth=1,label='Original Qwen')
    ax.set(title=f'{ctx//1024}k context',xlabel='QK/PV + score MACs (% of dense)',ylabel='Sampled suffix PPL')
    ax.grid(alpha=.2)
axes[1].legend(fontsize=7)
fig.savefig(root/'accuracy_compute.png',dpi=160)
