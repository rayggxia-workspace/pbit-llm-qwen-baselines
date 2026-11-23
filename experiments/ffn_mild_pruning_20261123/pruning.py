"""Frozen per-token pruning masks around the original stratified P-FFN."""
import math
import torch
import gu_adapter as original_gu
from sparse_sampling import input_mass


def joint_norm_encoding(codes, lsb):
    """Offline only. Norms include both GU branches and real tile scales."""
    m,n=codes.shape
    assert m%64==n%64==0 and tuple(lsb.shape)==(m//64,n//64)
    squares=codes.double().reshape(m//64,64,n//64,64).square().sum(1)
    norm=(squares*lsb.double().square()[:,:,None]).sum(0).flatten().sqrt()
    positive=norm>0
    exponent=torch.zeros(n,device=codes.device,dtype=torch.int64)
    exponent[positive]=torch.log2(norm[positive]).round().long()
    if bool(positive.any()):exponent[~positive]=exponent[positive].min()
    spread=int(exponent.max()-exponent.min())
    assert spread<=24,'norm exponent range requires a wider declared score'
    return {'exponent':exponent.cpu().tolist(),'zero_indices':(~positive).nonzero().flatten().cpu().tolist(),
            'exponent_spread':spread,'distinct_exponents':int(exponent.unique().numel()),
            'norm_min':float(norm.min()),'norm_max':float(norm.max())}


def scores(codes,bins,tops,encoding):
    mass,_,unit=input_mass(codes,bins,tops)
    exponent=torch.tensor(encoding['exponent'],device=codes.device,dtype=torch.int64)
    shift=exponent-exponent.min()
    assert int(mass.max()).bit_length()+int(shift.max())<63
    weighted=mass<<shift[None,:]
    if encoding['zero_indices']:weighted[:,encoding['zero_indices']]=0
    return {'input':mass,'potnorm':weighted},unit


class PrunedGU(original_gu.GUOverride):
    def __init__(self,case,banks,calibration=None,collect=False,encodings=None,verify_dense=False):
        super().__init__(case,banks,verify_dense)
        self.calibration=calibration
        self.collect=collect
        self.encodings={} if encodings is None else encodings
        self.collected={}
        self.prune_stats={}

    def sampled(self,codes,enc,module,case,generator,original_sampler):
        baseline={'kind':'original','samples':64}
        s=self.saved_sample(codes,enc,module,baseline,generator,original_sampler)
        if not self.collect and case['kind']=='original':return s
        layer=str(module.layer)
        if layer not in self.encodings:
            self.encodings[layer]=joint_norm_encoding(module.frozen_gu_codes,module.frozen_gu_lsb)
        fields,_=scores(codes.reshape(-1,codes.shape[-1]),enc['bin_id'].reshape(-1,codes.shape[-1]),
                        module.x_scales,self.encodings[layer])
        if self.collect:
            rows=self.collected.setdefault(layer,{'input':[],'potnorm':[]})
            for name,value in fields.items():rows[name].append(value[::64].cpu())
            return s
        threshold=self.calibration['thresholds'][layer][case['score']][str(case['prune_percent'])]
        keep=fields[case['score']]>threshold
        original_counts=s['counts'].reshape_as(keep)
        s['counts']=(original_counts*keep.long()).reshape_as(s['counts'])
        s['prune_audit']={'possible':keep.numel(),'pruned':int((~keep).sum()),
            'baseline_nonzero':int((original_counts>0).sum()),
            'removed_nonzero':int(((original_counts>0)&~keep).sum()),
            'removed_events':int((original_counts*~keep).sum()),
            'input_mass':float(fields['input'].double().sum()),
            'removed_input_mass':float((fields['input'].double()*~keep).sum()),
            'score_square_mass':float(fields[case['score']].double().square().sum()),
            'removed_score_square_mass':float((fields[case['score']].double().square()*~keep).sum())}
        return s

    def __enter__(self):
        self.saved_sample=original_gu.sample
        original_gu.sample=self.sampled
        try:return super().__enter__()
        except BaseException:
            original_gu.sample=self.saved_sample
            raise

    def __exit__(self,*args):
        try:return super().__exit__(*args)
        finally:original_gu.sample=self.saved_sample

    def record(self,module,s,*args):
        super().record(module,s,*args)
        if 'prune_audit' in s:
            row=self.prune_stats.setdefault(str(module.layer),{})
            for k,v in s['prune_audit'].items():row[k]=row.get(k,0)+v

    def summary(self):
        out=super().summary()
        total={}
        for row in self.prune_stats.values():
            for k,v in row.items():total[k]=total.get(k,0)+v
        if total:
            total['actual_pruned_fraction']=total['pruned']/total['possible']
            total['removed_input_mass_fraction']=total['removed_input_mass']/total['input_mass']
            total['removed_score_square_fraction']=total['removed_score_square_mass']/total['score_square_mass']
        out['pruning']={'total':total,'per_layer':self.prune_stats,
                        'mask_scope':'per_token_layer_fixed_all64ticks_all_GU_stripes',
                        'compensation':'none;deliberately_biased_pruning'}
        return out

    def calibration_value(self,plan):
        assert len(self.collected)==36
        thresholds={}
        for layer,fields in self.collected.items():
            thresholds[layer]={}
            for name,chunks in fields.items():
                values=torch.cat(chunks).flatten()
                thresholds[layer][name]={str(p):int(values.kthvalue(math.ceil(values.numel()*p/100)).values)
                                         for p in [10,20]}
        return {'thresholds':thresholds,'norm_encodings':self.encodings,
                'sampled_tokens_per_layer':{layer:sum(v.shape[0] for v in f['input']) for layer,f in self.collected.items()},
                'fit_scope':plan['calibration'],'no_test_set_fit':True}
