"""Explicit v6 assumptions. Price values are scenario parameters, not new PPA."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(model='qwen', legacy=False):
    with (HERE/'configs'/('model_'+model+'.json')).open(encoding='utf-8') as f:
        model_record = json.load(f)
    shape = model_record['shape']
    cfg = dict(core_hz=100000000, context_tokens=2048, decode_tokens=1, seed=0,
        macs_per_cycle=512, mac_startup_cycles=2, vector_lanes=64,
        digital_w8_restore='block64',
        nonlinear_lanes=16, weight_chunk_bytes=65536, double_buffer=True,
        trace_event_limit=80, row_receipt_limit=16,
        ffn=dict(mode='sc', bins=4, samples=32, strata=32, engines=8,
                 startup_cycles=1, sample_II_cycles=1, drain_cycles=1),
        attention=dict(mode='screen_rejection', tile_tokens=128,
            samples=None, sample_ratio=1/16, minimum_samples=1,
            winner_update_multiplier=8, candidate_blocks=8,
            selection='fixed_budget', selector_bias=-1.5, selector_temperature=1.,
            synthetic_logit_std=1.5, trace_file=None, selector_calibration=None,
            serial_burn=16, serial_spacing=4, serial_cycles_per_attempt=6),
        random=dict(backend='integrated_service',clock_hz=100000000,
            reseed_cycles=100000000,seed_word_interval_cycles=100,seed_startup_cycles=10,
            sigmoid_step=.125,lut_lanes=16,config_lanes=64,cpu_fast=True,
            startup_cycles=1, frame_cycles=1, restore_cycles=1),
        sampler_v5=dict(drive_bits=32, drive_step=None, max_proposals_per_sample=128,
            offset_update_mode='per_candidate', source_command_cycles=1,
            source_settle_cycles=2, source_capture_cycles=1,
            source_min_interval_cycles=1, tree_levels_per_cycle=2,
            burn_updates=0, record_events=False, energy_pJ={}, idle_W=None, area={}),
        sram=dict(capacity_bytes=(1 if model=='qwen' else 8)*1024**2,
            banks=16, word_bytes=16, macro_depth=4096, corner='SS',
            clock_hz=80000000, fabric_GBs=16., cdc_ns=20.,
            calibration='llama7b/runtime/results/sram_calibration_v1_20261016/calibration.json'),
        dram=dict(backend='link', bandwidth_GBs=16., latency_ns=80.,
            burst_bytes=64, max_pending=32),
        prices_pJ={
            'bf16_mac':2., 'fp32_mac':None, 'vector_op':1., 'nonlinear_op':10.,
            'dram_read':64., 'dram_write':64., 'dram_background_ns':50.,
            'FP32_to_BF16':None, 'weight_scale_op':None,
            'SC_encode_op':None, 'SC_restore_op':None,
            'digital_idle_ns':None, 'sc_idle_ns':None,'control_interconnect_ns':None,
            'rng_seed':None,'rng_frame':None,'rng_restore':None,'rng_uniform_bit':None,
            'rng_biased_response':None,'selector_compare':None,
            'budget_compare_exchange':None,'candidate_compact':None,
            'V_selection_add':0.},
        cost_policy=dict(full_physical_PPA='unknown',
            measured_anchor='55nm SS SRAM macro internal energy/area/timing table',
            conditional_prices='legacy digital 2pJ BF16 MAC,1pJ vector,10pJ nonlinear; DRAM64pJ/B,50mW background',
            null_prices='uncharacterized components, NOT zero energy',
            V_selection_add='activity alias only: energy already in vector_op; do not price twice',
            SC_restore='counts signed bit-plane reconstruction/bin alignment/W scale application; no duplicate conversion fee',
            SRAM='internal energy only; do not overlap with a whole-memory measured price'))
    cfg['model_record'] = model_record
    if not legacy:
        from .ffn_latest import defaults
        cfg['ffn'].update(defaults())
    return cfg, copy.deepcopy(shape)


def tiny():
    cfg, _ = load('qwen', legacy=True)
    shape = dict(hidden_size=64, intermediate_size=128, num_attention_heads=2,
        num_key_value_heads=1, num_hidden_layers=1, vocab_size=128,
        tie_word_embeddings=True, attention_bias=False, max_position_embeddings=2048)
    cfg.update(context_tokens=129, trace_event_limit=20000, weight_chunk_bytes=32768)
    # Frozen legacy mechanism fixture. Integrated-source checks opt in explicitly.
    cfg['random']['backend']='local_prng_interface'
    cfg['attention'].update(candidate_blocks=3, samples=8, winner_update_multiplier=2)
    cfg['ffn'].update(engines=2)
    return cfg, shape
