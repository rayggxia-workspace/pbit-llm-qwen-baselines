"""Standalone figures for the frozen conditional projection experiment."""
import argparse,json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def main():
 p=argparse.ArgumentParser();p.add_argument('--summary',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 s=json.loads(a.summary.read_text(encoding='utf-8'));t=s['table'];labels=[x['candidate'].replace('_','\n') for x in t];x=np.arange(len(t));a.output.mkdir(parents=True,exist_ok=True)
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(2,1,figsize=(13,8),layout='constrained',gridspec_kw={'height_ratios':[2,1]})
 axes[0].bar(x-.18,[r['sc_us'] for r in t],width=.36,label='SC B4/T32',color='#236c9b')
 axes[0].bar(x+.18,[r['w8_us'] for r in t],width=.36,label='Matched W8',color='#d78532')
 axes[0].set_ylabel('Short projection latency (us)');axes[0].set_xticks(x,labels);axes[0].set_ylim(0,max(r['sc_us'] for r in t)*1.2);axes[0].legend(loc='upper right');axes[0].grid(axis='y',alpha=.2);axes[0].set_axisbelow(True)
 for i,r in enumerate(t):axes[0].text(i,max(r['sc_us'],r['w8_us'])+3,f"{r['sc_us']:.2f} / {r['w8_us']:.2f}",ha='center',fontsize=8)
 axes[1].bar(x,[r['local_budget_bytes']/1024 for r in t],width=.6,color='#728c66');axes[1].set_xticks(x,labels);axes[1].set_ylabel('Listed local state (KiB)');axes[1].grid(axis='y',alpha=.2);axes[1].set_axisbelow(True)
 fig.suptitle('Recovery and dataflow: paired finite-resource consumer study\n4 groups x 8 tiles x 64 rows; 100 MHz core / 80 MHz SRAM',fontsize=14)
 fig.supxlabel('Three numeric seeds have identical deterministic timing. Local state is a partial inventory.\nConditional projection only: excludes DRAM fill, encoder/RNG generation, full FFN, physical PPA and model PPL.',fontsize=10)
 fig.savefig(a.output/'paired_dataflow.png',dpi=160);fig.savefig(a.output/'paired_dataflow.svg');plt.close(fig)
 print('Standalone PNG/SVG saved')

if __name__=='__main__':main()
