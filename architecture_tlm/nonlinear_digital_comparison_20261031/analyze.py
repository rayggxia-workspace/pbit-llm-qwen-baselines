"""Digital g/u-to-Wd workflow and conditional budgets; no new RTL/PPA/model run."""
from pathlib import Path
import hashlib,json,re,statistics
P=Path(__file__).resolve().parent;OWN=P.parents[1];WS=OWN.parents[1]
def read(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode())
def rne(n,b):
 q,r=divmod(n,1<<b);h=1<<(b-1)
 return q+int(r>h or(r==h and q&1))
def main():
 sc_path=OWN/'architecture_tlm/nonlinear_wd_shared32_20261031/results/SUMMARY_SMALL.json'
 mac_path=OWN/'architecture_tlm/a9w8_parallel64_20261030/results/FINAL_SUMMARY.json'
 fp_path=OWN/'architecture_tlm/bf16_ppa_20261028/results/FINAL_SUMMARY.json'
 q10_path=WS/'digital_circuit_simulation_registry/records/swiglu-38100634-ss.json'
 lut_path=OWN/'architecture_tlm/nonlinear_wd_shared32_20261031/rtl/sigmoid.sv'
 sc,mac,fp,q10=[read(p) for p in (sc_path,mac_path,fp_path,q10_path)]
 baseline=next(r for r in sc['table'] if r['case']=='g8_weighted_full')
 a9=next(r for r in mac['PPA'] if r['case']['name']=='a9w8')
 bf=next(r for r in fp['PPA'] if r['case']['name']=='dot64_4')
 q={int(a,16):int(v) for a,v in re.findall(r"8'h([0-9a-fA-F]{2}):\s*q9=9'd(\d+)",lut_path.read_text())};assert len(q)==256
 maxima=dict(fused_LUT_unsigned16=0,product_unsigned24=0,z_unsigned8=0,requantization_error_numerator=0);checked=0
 for k in range(-128,128):
  sigma=q[k&255]
  for eg in (3,4,5,6):
   d=5-eg;ag=min(255,abs(k)<<d if d>=0 else rne(abs(k),-d));f=ag*sigma;assert f<1<<16
   for um in range(128):
    au=um<<1;prod=f*au;z=rne(prod,16)
    assert prod<1<<24 and z<=255
    error=abs((z<<16)-prod);assert error<=1<<15
    maxima={key:max(maxima[key],value) for key,value in [('fused_LUT_unsigned16',f),('product_unsigned24',prod),('z_unsigned8',z),('requantization_error_numerator',error)]};checked+=1
 energy=baseline['profiles']['replay32']['energy_pJ'];peak=a9['profiles']['p8peak']['energy_pJ'];paced=a9['profiles']['p8paced']['energy_pJ']
 q10_anchors={profile:statistics.mean(c['total_pJ_per_output'] for c in q10['cases'] if c['profile']==profile and c['mode']=='active') for profile in ('full','central')}
 output=dict(kind='FLOW_AND_CONDITIONAL_BUDGET_NO_NEW_PPA',date='2026-10-31',issue=204,source_base='af40cc769797b0d487e5d1861bd4e92079feb403',scope='Already encodedg/u through same nonlinear function andfixedWd64x8;no GU,inputencoding,SRAM,RNG,crossK/BF16cost in current SC comparison',
  recommended_matched_integer=dict(input_g='signed8 k,unit1/8,originalg retained for sigmoid address',input_u='sign+mag7,au=mag7<<1,P8 amplitude',shared_scales='Sg=2^eg,Su=2^eu,W=qW*2^ew;all64 share each scale',
   sigmoid='q=existingLUT(k),unsigned0..256;do not substitute sigmoid(ag)',amplitude='ag=clip255(RNE(abs(k)*2^(5-eg)));au=um<<1',
   exact_reference='P=ag*au*q,unsigned24 plus independent sign;z=sign*P*2^(eg+eu-24)',
   baseline_z='z8mag=RNE(P/2^16);signed9 carrier =sign*z8mag;sharedSz=Sg*Su',
   matrix='D_j=sum_i signed9(z_i)*signed8(W_ij);output D_j*2^(eg+eu+ew-8)',
   sampling_reference='SC C_j=sum_t,sum_i sign*zbit_it*W_ij;output C_j*2^(eg+eu+ew-5);OR4 is another approximation',
   fused_candidate='F[k,scale_select]=ag(k,eg)*q(k),unsigned16;one16x8 multiply F*au then sameRNE. Four test scales require a10bit logical LUT address,not automatically a single256entry table',
   validation='Existing256-entry sigma table and all131072(k,eg,um) cases;fused ag*q representation fits16bits,P24fits,z<=253;sign supplied separately',range_cases=checked,range_maxima=maxima,
   requantization='One additional deterministic rounding versus exact conditional mean;absolute normalized error<=1/512;not a model/PPL acceptance or proof of equivalence to sampledT32',
   output_bits='23bit generic A9xW8 sum tree/32bit interface reuse;undercurrentabs(z)<=253,abs(W)<=127 a22bit signed sum suffices mathematically,butno new narrowtreePPA measured'),
  operation_counts=dict(N=64,M=8,sigmoid_or_fused_lookups=64,unfused_nonlinear_integer_multiplications=128,fused_nonlinear_integer_multiplications=64,z_requantizations=64,Wd_multiplications=512,Wd_tree_additions=504,nonlinear_reuse='One z perinput drivesall8outputcolumns;do not repeat nonlinearity8times',clock_policy='Gate data pipeline/valid waiting periods;measure coldload,drain,hold andfullframe,no free overlap'),
  resource_points=[dict(name='Primary requested64-way parallel control',nonlinear_lanes=64,Wd_MAC_lanes=512,pipeline='lookup/convert -> one or two multiply stages -> RNE -> existingparallelA9/W8 tree;4-5stages initial target,STA determines actual edges',status='NOT_IMPLEMENTED_NOT_MEASURED'),dict(name='Additional throughput-matched stream point',nonlinear_lanes=[2,4],Wd_MAC_lanes=[16,32],issue_cycles=[32,16],pipeline='Share each2/4 z across8columns,localintegerpartial sums;carry indices/weights/scales through pipeline;no full64probabilitybank required',status='OPTIONAL_NOT_IMPLEMENTED_NOT_MEASURED')],
  existing_anchors=dict(SC_full_nonlinearity_Wd_pJ_frame8outputs=energy,SC_frame_ns=340,A9W8_p8peak_pJ_per64dot=peak,A9W8_p8paced350ns_pJ_per64dot=paced,
   replicated8output_MAC_only_peak_pJ=8*peak,replicated8output_MAC_only_paced_pJ=8*paced,
   conditional_frontend_budget_to_tie_SC_using_peak_MAC_pJ=energy-8*peak,conditional_budget_per_gu_pair_pJ=(energy-8*peak)/64,
   old_Q10_pJ_per_gu_pair=q10_anchors,old_Q10_bulk64_pJ={k:64*v for k,v in q10_anchors.items()},
   old_BF16_dot64_4_pJ_per_dot=bf['profiles']['normal']['energy_pJ'],old_BF16_8copies_MAC_only_pJ=8*bf['profiles']['normal']['energy_pJ']),
  interpretation='SC versus oldBF16reference looks favorable,butmatchedquantizeddigital may be comparable or lower. PeakMACreplication andQ10 are separate synthetic activities/widths/schedules;do not call their sum an integratedPPA orassume347.76paced is optimalgated. Complete matched digitalpath remains unmeasured.',
  BF16_control='Separate higher-precision reference:g/uBF16 -> suitableSigmoid/SiLUapproximation -> BF16multiplication -> BF16weights/FP32accumulation. Sameold9bitprobabilityLUT does not establish a fullBF16activation accuracy. Do not require exactexp/divider ifLUT/PWL meets error budget.',
  sources=[dict(file=str(p.relative_to(OWN)) if OWN in p.parents else 'digital_circuit_simulation_registry/records/'+p.name,sha256=sha(p),availability='local project evidence;A9PPAnotyetpublished asfullrawhistory') for p in (sc_path,mac_path,fp_path,q10_path,lut_path)],
  new_RTL=0,new_EDA=0,new_model_or_PPL=0,registry_new_run=False)
 save(P/'ANALYSIS.json',output)
 print(json.dumps(dict(range_cases=checked,maxima=maxima,SC_pJ=energy,digital_MAC_only_8_peak_pJ=8*peak,frontend_budget_pJ=energy-8*peak,frontend_budget_per_pair_pJ=(energy-8*peak)/64,Q10_anchors=q10_anchors)))
if __name__=='__main__':main()
