"""Audit completed full-WT2 results and derive sampling/activity bounds.

No GPU or PPA model: energy examples are explicitly normalized assumptions.
Input manifests remain immutable. Write each analysis JSON to a new filename.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import statistics
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strat_variance(q, T):
    if not 0 <= q <= 255 or T <= 0 or 256 % T:
        raise ValueError('A8 stratum scheme requires T dividing 256')
    w = 256 // T
    frac = (q % w)/w
    return frac*(1-frac)/(T*T)


def activity(q, T):
    p = q/256
    w = 256//T
    whole, remainder = divmod(q, w)
    frac = remainder/w
    pzero = 1-frac if whole == 0 else 0.
    pfull = frac if whole == T-1 else 0.
    return {'q': q, 'T': T, 'iid_expected_within_frame_bit_transitions': (T-1)*2*p*(1-p),
            'ordered_expected_within_frame_bit_transitions': 1-pzero-pfull,
            'ordered_within_frame_max_transitions': 1,
            'frame_boundaries_and_configuration': 'excluded',
            'scope': 'one fixed threshold comparator output; not whole-core power'}


def build(results):
    analysis_path = Path(__file__).resolve().relative_to(ROOT).as_posix()
    analysis_commit = subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
    committed_source = subprocess.check_output(['git','-C',str(ROOT),'show',analysis_commit+':'+analysis_path])
    if committed_source != Path(__file__).read_bytes():
        raise RuntimeError('Commit the exact LF analysis source before generating evidence')
    base = read(results/'bf16_reference/summary.json')
    calibration_sha = sha(results/'calibration/calibration.json')
    expected_identity = read(results/'bf16_reference/identity.json')
    expected_tokens = read(results/'bf16_reference/tokenization.json')
    cases = read(ROOT/'experiments/llama2_ffn_precision/configs/cases.json')
    values = {}
    audit = []
    for name in cases:
        folder = results/name
        if not (folder/'ARTIFACT_MANIFEST.json').is_file():
            continue
        for filename, record in read(folder/'ARTIFACT_MANIFEST.json').items():
            # Long per-window logs may remain on the verified server. The
            # collector already checked them there before copying small JSONs.
            if (folder/filename).exists():
                assert sha(folder/filename) == record['sha256'], str(folder/filename)
        summary = read(folder/'summary.json')
        protocol = read(folder/'protocol.json')
        config = read(folder/'config.json')
        identity = read(folder/'identity.json')
        assert summary['status'] == 'completed'
        assert summary['protocol'] == 'full_wikitext2_raw_sliding_window_ppl'
        assert summary['scored_tokens'] == expected_tokens['expected_scored_tokens'] == 335686
        assert summary['source_commit'] == 'a8ea21f75ae6d736b2bc0136f8ee55977b082060'
        assert identity == expected_identity
        assert protocol['full_token_ids_sha256'] == expected_tokens['token_ids_sha256']
        assert protocol['data_raw_sha256'] == base['data_sha256']
        assert protocol['window'] == 2048 and protocol['stride'] == 512
        assert protocol['attention'] == 'unchanged BF16 SDPA; no PV sampling or Ising'
        assert protocol['calibration_sha256'] == calibration_sha
        assert protocol['config_sha256'] == sha(ROOT/'experiments/llama2_ffn_precision/configs'/f'{name}.json')
        quant_ref = read(results/'a8_exact/summary.json')['ppl']
        values[name] = {'ppl': summary['ppl'], 'post': config['post'],
                        'method': config.get('method', config['mode']),
                        'T': config.get('T'), 'seed': config['seed'],
                        'delta_vs_same_quantized_exact_SiLU_percent':
                        100*(summary['ppl']/quant_ref-1) if config['post']=='exact' else None}
        if (folder/'layer_stats.json').is_file():
            stats = read(folder/'layer_stats.json')
            stage_stats = {}
            for stage in ('x', 'z'):
                if stage+'_values' not in stats[0]:
                    continue
                n = sum(s[stage+'_values'] for s in stats)
                stage_stats[stage] = {'exposures_including_window_overlap': n,
                    'mean_encoded_probability': sum(s[stage+'_sum_probability'] for s in stats)/n,
                    'zero_code_fraction': sum(s[stage+'_zero_codes'] for s in stats)/n}
                if stage+'_zero_event_counts' in stats[0]:
                    stage_stats[stage]['zero_event_fraction'] = sum(s[stage+'_zero_event_counts'] for s in stats)/n
            values[name]['stages'] = stage_stats
        audit.append({'name':name,'summary_sha256':sha(folder/'summary.json'),
                      'protocol_sha256':sha(folder/'protocol.json'),'all_checks_passed':True})
    groups = {}
    for method, lengths in [('iid',[256,4096]),('stratified',[16,32,64,128])]:
        for T in lengths:
            completed = [values[f'{method}_T{T}_s{s}']['ppl'] for s in range(3)
                         if f'{method}_T{T}_s{s}' in values]
            groups[f'{method}_T{T}'] = {'completed_seeds':len(completed),'required_seeds':3,
                'values':completed,'formal_three_seed_mean':statistics.mean(completed) if len(completed)==3 else None,
                'formal_sample_std':statistics.stdev(completed) if len(completed)==3 else None}
    variance_rows=[]
    for q in [1,2,3,4,64,128,255]:
        for T in [64,128,256,4096]:
            p=q/256
            iid=p*(1-p)/T
            v=strat_variance(q,T) if T<=256 else None
            if v is not None:
                assert v <= iid+1e-15
            variance_rows.append({'q':q,'T':T,'iid_variance':iid,
                'iid_std_in_A8_LSB':256*math.sqrt(iid),
                'stratified_variance':v,
                'stratified_std_in_A8_LSB':256*math.sqrt(v) if v is not None else None})
    scenarios=[]
    for original_T in [4096,256]:
        for fixed in [0.,.5,.8]:
            ratio=fixed+(1-fixed)*64/original_T
            scenarios.append({'original_T':original_T,'new_T':64,
                 'unaffected_original_energy_fraction':fixed,'assumed_sample_window_power_ratio':1.,
                 'new_energy_fraction':ratio,'conditional_energy_improvement':1/ratio,
                 'not_measured':True,'accuracy_matched':False})
    return {'generated_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
       'analysis_code_sha256':sha(Path(__file__)),
       'analysis_source_commit':analysis_commit,
       'results_path':str(results),'completed_cases':len(values),'configured_cases':len(cases),
       'comparison_audit':audit,'results':values,'three_seed_groups':groups,
       'single_lane_variance_examples':variance_rows,
       'comparator_activity_examples':[activity(q,64) for q in [1,4,16,64,128,255]],
       'conditional_energy_scenarios':scenarios,
       'power_measurement':'none; no stratified VCD/SAIF/PT characterization yet',
       'limitations':['FP32 restored matrix reference, not complete bit-true hardware',
          'single-lane variance bound is not full-network PPL',
          'activity bounds exclude internal glitches, clock, accumulators, memory and RNG',
          'energy scenarios assume equal active power and no scheduling bottleneck; not matched-accuracy claims']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results',type=Path,default=ROOT/'llama2/results/ffn_precision_20261018')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    record=build(args.results)
    with args.output.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(record,f,ensure_ascii=False,allow_nan=False,indent=2)
        f.write('\n')
    print(json.dumps({'completed_cases':record['completed_cases'],'audit_passed':True,
                      'power_measured':False,'output':str(args.output)}))


if __name__=='__main__':
    main()
