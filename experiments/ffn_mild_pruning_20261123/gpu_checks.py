"""Small independent arithmetic and RNG-coupling checks on a Slurm GPU."""
import torch


def run():
    from pruning import joint_norm_encoding,scores
    from sampling import shared_input_counts
    from sparse_gu import pack_bank,project
    from sparse_sampling import compact
    torch.manual_seed(337)
    w=torch.randint(-8,9,(128,128),device='cuda',dtype=torch.int16)
    lsb=torch.tensor([[.25,.5],[1.,2.]],device='cuda',dtype=torch.float64)
    e=joint_norm_encoding(w,lsb)
    actual=w.cpu().double()*lsb.cpu().repeat_interleave(64,0).repeat_interleave(64,1)
    expected=actual.square().sum(0).sqrt().log2().round().long()
    assert e['exponent']==expected.tolist()
    q=torch.randint(0,257,(4,128),device='cuda');q[0]=0;q[1]=256
    bins=torch.randint(0,4,(4,128),device='cuda')
    tops=torch.tensor([[16.,4.,1.,.25],[8.,2.,.5,.125]],device='cuda')
    fields,unit=scores(q,bins,tops,e)
    reference=q.cpu().double()*tops[:,0].cpu().repeat_interleave(64)[None,:]/(256*(4.**bins.cpu()))
    assert torch.equal(fields['input'].cpu().double()*2.**unit,reference)
    weighted=reference*torch.exp2(expected.double())[None,:]
    assert torch.equal(fields['potnorm'].cpu().double()*2.**(unit+int(expected.min())),weighted)
    g1=torch.Generator(device='cuda').manual_seed(91);g2=torch.Generator(device='cuda').manual_seed(91)
    counts=shared_input_counts(q,64,g1);control=shared_input_counts(q,64,g2)
    keep=fields['input']>int(fields['input'][2].median())
    masked=counts*keep
    assert torch.equal(masked[keep],control[keep]) and not bool(masked[~keep].any())
    assert torch.equal(g1.get_state(),g2.get_state())
    assert torch.equal(counts*(fields['input']>-1),control)
    signs=torch.randint(0,2,q.shape,device='cuda')*2-1;shifts=bins*2
    coeff=torch.ones((2,2),device='cuda',dtype=torch.int64)
    records,pointer,_=compact(masked,signs,shifts)
    observed=project(pack_bank(w,64),records,pointer,coeff,6).cpu()
    values=((masked.long()<<(6-shifts))*signs).cpu()
    assert torch.equal(observed,values@w.cpu().long().T)
    return {'status':'PASS','checks':['offline_norm_includes_real_W8_PoT_LSB_and_both_GU',
        'integer_input_score','integer_PoT_weighted_score','retained_counts_bitwise_original',
        'dropped_counts_zero','no_extra_RNG_consumption','zero_prune_count_noop',
        'selected_weight_integer_dot_vs_independent_CPU'],'tests':8}
