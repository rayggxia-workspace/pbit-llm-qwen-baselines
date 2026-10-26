"""Verify archived bytes and recount each heldout bit from its saved Spectre voltage."""
import csv,hashlib,io,json,math,shutil,sys,tarfile,tempfile
from pathlib import Path
TASK=Path(__file__).resolve().parents[3]
ROOT=TASK.parents[1]
SRC=TASK/'architecture_tlm/physical_rng_normal_readout/src'
ARCHIVE=ROOT/'project_archives/normal_readout_20261025/results/normal_readout_38387635.tar.gz'
EXPECTED='d7112d162e1a22351d4e745be22669bae66ffd37d2af2d13805a70e04eebd8f0'
FORMAL=TASK/'architecture_tlm/physical_rng_normal_readout/results/38387635'
DATA=ROOT/'analog_pbit_20261016/normal_readout_38387635'
sys.path.insert(0,str(SRC))
import run_characterization as parser

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1048576),b''):h.update(chunk)
    return h.hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
def corr(a,b):
    n=len(a);sa=sum(a);sb=sum(b)
    den=(n*sum(x*x for x in a)-sa*sa)*(n*sum(y*y for y in b)-sb*sb)
    return (n*sum(x*y for x,y in zip(a,b))-sa*sb)/math.sqrt(den) if den>0 else None
def lag(bits,k):return corr(bits[:-k],bits[k:])
def recount(rows):
    bits=[int(r['bit']) for r in rows]
    return dict(samples=len(rows),P1=sum(bits)/len(bits),MID=sum(r['level']=='MID' for r in rows),
        invalid=sum(r['level_valid']=='False' for r in rows),acf={str(k):lag(bits,k) for k in (1,2,5,10,20,50,100)})
def main():
    assert sha(ARCHIVE)==EXPECTED,'Archive checksum mismatch'
    FORMAL.mkdir(parents=True,exist_ok=True)
    DATA.mkdir(parents=True,exist_ok=False)
    payload={};actual={};source={};waves={};logs={}
    with tempfile.TemporaryDirectory(dir=str(DATA),prefix='audit-') as temp:
        with tarfile.open(ARCHIVE,'r|gz') as tar:
            for member in tar:
                assert member.isfile() and member.name.startswith('38387635/')
                name=member.name[len('38387635/'):]
                assert '..' not in Path(name).parts
                stream=tar.extractfile(member);h=hashlib.sha256()
                keep=name.endswith(('.json','.csv','.txt','.log')) or name.startswith('source/')
                chunks=[];wave=None
                if name.startswith('validation_seed') and name.endswith('/raw/tranNoise.tran.tran'):
                    wave=Path(temp)/(name.split('/')[0]+'.tran');dest=wave.open('wb')
                else:dest=None
                size=0
                try:
                    for data in iter(lambda:stream.read(1048576),b''):
                        h.update(data);size+=len(data)
                        if keep:chunks.append(data)
                        if dest:dest.write(data)
                finally:
                    if dest:dest.close()
                actual[name]=dict(bytes=size,sha256=h.hexdigest())
                if keep:payload[name]=b''.join(chunks)
                if wave:waves[name.split('/')[0]]=wave
        manifest=json.loads(payload['result_manifest.json'])
        assert set(actual)==set(manifest)|{'result_manifest.json'}
        for name,value in manifest.items():assert actual[name]==value,('Manifest mismatch',name)
        package=json.loads(payload['source/package_manifest.json'])
        for name,digest in package.items():
            assert actual['source/'+name]['sha256']==digest
            assert sha(SRC/name)==digest,('Source differs from submitted snapshot',name)
        summary=json.loads(payload['summary.json']);config=json.loads(payload['config.json'])
        metadata=json.loads(payload['metadata.json']);frozen=json.loads(payload['frozen_reference.json'])
        assert summary['status']=='STATISTICS_COMPLETE_REVIEW_REQUIRED_NOT_ENTROPY_QUALIFIED'
        assert metadata['source_git_commit']=='01d63b66aa5653dffb4d116e1b1d5f9c951b1571'
        assert actual['source/package_manifest.json']['sha256']==metadata['source_manifest_sha256']
        assert actual['config.json']['sha256']==metadata['config_sha256']
        assert actual['frozen_reference.json']['sha256']==summary['details']['frozen_reference_sha256']
        assert not set(config['validation_seeds'])&(set(config['calibration_seeds'])|set(config['numeric_seeds']))
        failures=[r for r in summary['cases'] if r['status']!='COMPLETED_REVIEW_REQUIRED']
        assert len(summary['cases'])==58 and [r['case'] for r in failures]==['svt_i20u_op']
        assert all(r['aggregate_audit'][:2]==[0,0] for r in summary['cases'])
        reports=[];exports={}
        for seed in (64007,64013,64033):
            prefix='validation_seed'+str(seed);case=next(r for r in summary['cases'] if r['case']==prefix)
            rows=list(csv.DictReader(io.StringIO(payload[prefix+'/raw_1us.csv'].decode('utf-8'))))
            assert len(rows)==20000 and case['metrics']['actual_sample_bits']==20000
            bits=[int(r['bit']) for r in rows]
            assert bits==[int(b) for b in payload[prefix+'/raw_1us_bits.txt'].splitlines()]
            core_bits=[];q=case['setting']['q'];seen=0;dense=0;dense_mid=0
            for j,r in enumerate(parser.checked_trace(waves[prefix],.022,1e-7,['out','bit'])):
                index=j-20000
                if 0<=index<200000:
                    dense+=1;dense_mid+=.24+1e-12<r['bit']<.96-1e-12
                    if index%10==0:
                        row=rows[seen]
                        assert int(row['raw_index'])==seen
                        assert abs(float(row['time_s'])-(.002+seen*1e-6))<1e-12
                        assert abs(float(row['core_V'])-r['out'])<1e-12 and abs(float(row['comparator_V'])-r['bit'])<1e-12
                        level='LOW' if r['bit']<=.24+1e-12 else 'HIGH' if r['bit']>=.96-1e-12 else 'MID'
                        assert row['level']==level and (row['level_valid']=='True')==(level!='MID')
                        assert int(row['bit'])==int(r['bit']>.6)
                        core_bits.append(int(r['out']>.6));seen+=1
            assert seen==20000 and dense==200000
            raw=recount(rows);quality=json.loads(payload[prefix+'/quality.json'])
            assert raw['P1']==quality['raw']['p1']==case['metrics']['actual_P1']
            assert raw['MID']==quality['raw']['invalid_level_bits']==case['metrics']['actual_MID']
            assert abs(dense_mid/dense-case['metrics']['midrail_fraction'])<1e-12
            for k,rho in raw['acf'].items():assert abs(rho-quality['raw']['sequence_lag_acf'][k]['correlation'])<1e-12
            pairs=[];vn=[]
            for i in range(0,len(rows),2):
                a,b=rows[i:i+2]
                if a['bit']!=b['bit'] and a['level_valid']=='True' and b['level_valid']=='True':
                    vn.append((int(b['raw_index']),float(b['time_s']),int(a['bit'])))
            saved_vn=list(csv.DictReader(io.StringIO(payload[prefix+'/vn_valid_emitted.csv'].decode('utf-8'))))
            assert vn==[(int(r['raw_index']),float(r['time_s']),int(r['bit'])) for r in saved_vn]
            assert len(vn)==quality['vn_valid']['bits']
            assert sum(r[2] for r in vn)/len(vn)==quality['vn_valid']['p1']
            packet_summary={label:{kind:{k:v for k,v in values.items() if k in ('complete_packets','invalid_level_packets','adjacent_repeat_count','repeated_packet_occurrences','adjacent_hamming_mean','zero_state_packets')} for kind,values in by_kind.items()} for label,by_kind in quality['seed_packets'].items()}
            reports.append(dict(seed=seed,raw=raw,dense_MID_fraction=dense_mid/dense,core_ideal_0p6V=dict(P1=sum(core_bits)/len(core_bits),acf={str(k):lag(core_bits,k) for k in (1,2,5,10,20,50,100)}),
                vn_valid=dict(samples=len(vn),P1=quality['vn_valid']['p1'],lag1=quality['vn_valid']['sequence_lag_acf']['1']['correlation'],retention=len(vn)/20000,
                blocks=quality['vn_valid']['blocks'],arrival_gap_s=quality['vn_valid']['arrival_gap_s']),raw_blocks=quality['raw']['blocks'],seed_packets=packet_summary,
                comparator_dense_acf=case['metrics']['dense_acf'],simulator_elapsed_s=case['simulator_elapsed_s']))
            for name in ('raw_1us.csv','raw_1us_bits.txt','vn_pairs.csv','vn_all_emitted.csv','vn_valid_emitted.csv','raw_words32.csv','vn_valid_words32.csv','quality.json'):
                target=DATA/('seed'+str(seed)+'_'+name);target.write_bytes(payload[prefix+'/'+name]);exports[target.name]=dict(archive_member='38387635/'+prefix+'/'+name,**actual[prefix+'/'+name])
        review=dict(job=38387635,status='COMPLETED_ARCHIVE_RECOUNT_PASS_NOT_ENTROPY_QUALIFIED',elapsed_slurm='03:45:08',
            allocated_CPUs=8,total_CPU='12:01:03',archive=str(ARCHIVE),archive_bytes=ARCHIVE.stat().st_size,archive_sha256=EXPECTED,
            members_verified=len(actual),manifest_files_verified=len(manifest),embedded_source_files_verified=len(package)+1,
            executed_source_commit=metadata['source_git_commit'],source_manifest_sha256=metadata['source_manifest_sha256'],config_sha256=metadata['config_sha256'],
            frozen_reference_V=frozen['reference_V'],frozen_reference_sha256=actual['frozen_reference.json']['sha256'],
            numerical_screen=json.loads(payload['numerical_screen.json']),parallel=json.loads(payload['parallel_summary.json']),
            cases=58,expected_rejected_cases=[r['case'] for r in failures],spectre_errors=0,spectre_warnings=0,
            waveform_samples_recounted=60000,validation=reports,
            limitations=['Continuous TT25C channel,500Hz floor; no10Hz long drift/PVT/mismatch/PEX/sharedMUX/latch.',
                'Bits at MID are diagnostic threshold values, not guaranteed physical digital samples; raw MID retained.',
                'VN valid extraction uses analog-voltage validity oracle; a hardware receiver must implement readout/validity before using this path.',
                'No IID/entropy/security or dynamic-energy certification. Nanosecond deterministic delay is not independentbit throughput.',
                'Three noise seeds are repeated temporal simulations, not three simultaneously simulated spatial channels.',
                'Short numerical screening has preset mean tolerances; widening100to200MHz changed meanP1 by1.76 percentagepoints and meanACF by.0226; not proof of strict bandwidth convergence.'])
        save(FORMAL/'REVIEW.json',review);save(DATA/'REVIEW.json',review)
        index=dict(archive=str(ARCHIVE),bytes=ARCHIVE.stat().st_size,sha256=EXPECTED,remote_archive='/public3/home/t6s011227/analog_pbit_20261016/normal_readout_v1/normal_readout_38387635.tar.gz',members=actual,exports=exports)
        save(FORMAL/'ARCHIVE_INDEX.json',index)
        save(DATA/'manifest.json',exports)
    print(json.dumps(dict(archive_sha256=EXPECTED,verified_members=review['members_verified'],verified_source_files=review['embedded_source_files_verified'],seeds=[dict(seed=r['seed'],raw=r['raw'],vn={k:v for k,v in r['vn_valid'].items() if k not in ('blocks','arrival_gap_s')}) for r in reports]),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
