"""Follow-up registered after initial .75 mean failed; same 512-token protocol.

Separate immutable execution. Includes p=1-only control to distinguish the
endpoint change from clipping, then .95/.90 amplitude limits. This is an
exploratory follow-up, not an independent test set or a test-tuned final score.
"""
import run_clipping as base

POLICIES={
 'dynamic100_one': dict(range_policy='dynamic', endpoint='one'),
 'dynamic095': dict(range_policy='dynamic', endpoint='one', x_factor=.95, z_factor=.95),
 'dynamic090': dict(range_policy='dynamic', endpoint='one', x_factor=.90, z_factor=.90),
}


def cases():
    rows=[]
    for policy, options in POLICIES.items():
        for kind, seeds in [('mean',(0,)), ('dual',(0,1,2))]:
            for seed in seeds:
                rows.append(dict(name=f'{policy}_{kind}_n512_T256_s{seed}',
                    policy=policy,kind=kind,input_tokens=512,cycles=256,seed=seed,
                    bits=8,input_sharing=64,scope='all',options=options))
    return rows


if __name__=='__main__':
    base.cases=cases
    base.CONFIRM=()
    base.main()
