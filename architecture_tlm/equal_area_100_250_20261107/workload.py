"""Structural work and weight-byte audit; no simulated latency or power."""
def counts(model, context=2048, candidates=128):
    h,f,L,q,kv,d,v=(model[k] for k in ('hidden','ffn','layers','q_heads','kv_heads','head_dim','vocab'))
    assert 0<candidates<=context and q%kv==0
    qkvo=h*(q*d+2*kv*d)+q*d*h
    gu=2*h*f;down=h*f;head=h*v
    return dict(per_layer=dict(QKVO_MAC=qkvo,GU_MAC=gu,Wd_MAC=down,
        dense_QK_MAC=q*context*d,dense_PV_MAC=q*context*d,
        SparQ_coarse_MAC=q*context*32,SparQ_selected_QK_MAC=q*candidates*d,
        selected_exact_PV_MAC=q*candidates*d,
        dense_softmax_score_elements=q*context,
        selected_softmax_score_elements=q*candidates,
        BF16_projection_weight_bytes=2*qkvo,BF16_FFN_weight_bytes=2*(gu+down),
        W8_FFN_weight_bytes=gu+down),
        lm_head_MAC=head,lm_head_weight_bytes=2*head,
        total_weight_bytes_including_head=dict(BF16=L*2*(qkvo+gu+down)+2*head,
            W8_FFN=L*(2*qkvo+gu+down)+2*head),
        boundary='weights only; excludes KV, metadata, normalization weights and embedding row; no latency claim')
