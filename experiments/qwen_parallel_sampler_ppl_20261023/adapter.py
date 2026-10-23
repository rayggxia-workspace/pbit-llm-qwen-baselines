"""Keep Issue50 QKV/screening/cache/scorer unchanged; replace indices only."""
from unittest.mock import patch
from experiments.qwen_joint_stratified_attention_20261019 import joint_evaluate
from experiments.qwen_joint_stratified_attention_20261019.upstream_attention import attention


def evaluate(model,ids,case,calibration):
    method=case['sampler']
    base=attention.JointAttentionController
    class Controller(base):
        def _sample_indices(self,logits,layer):
            if method not in ('winner','rejection'):
                return super()._sample_indices(logits,layer)
            from .kernels import sample
            out,activity=sample(logits,self.samples,method,
                generator=self._generator(layer,logits.device,'sampler'))
            if not hasattr(self,'kernel_activity'):
                self.kernel_activity={}
            values=activity.sum(0)
            self.kernel_activity[layer]=self.kernel_activity.get(layer,0)+values
            return out,dict(kind=method,proposal_stats='accumulated_at_end',ideal_response=True)
        def stats(self):
            result=super().stats()
            result['actual_sampler']=method
            result['kernel_activity_columns']=['proposals_or_updates','accepted_or_retained','collisions','empty_rejections','reference_accepts','final_shift_sum']
            result['kernel_activity']={str(k):v.cpu().tolist() for k,v in getattr(self,'kernel_activity',{}).items()}
            return result
    with patch.object(attention,'JointAttentionController',Controller):
        result=joint_evaluate.evaluate_case(model,ids,case,calibration)
    result['attention_sampling']=method
    result['sampler_detail']=dict(method=method,samples=case['samples'],
        winner_initialization='argmax',winner_burn=0,winner_spacing=1,winner_shift=0.,
        rejection_initial_shift=0,rejection_max_shift=24,rejection_cap_factor=128,
        drive_quantization=None,probability_bits=None,source='Triton Philox ideal FP32 Bernoulli; no hardware RNG replay',
        no_second_PV_draw=True)
    return result
