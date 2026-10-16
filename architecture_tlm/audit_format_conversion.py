"""Attribute existing encoding/postprocessing proxies, without claiming converter PPA."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def main():
    s=json.loads((ROOT/'configs/model_config.json').read_text())
    folder=ROOT/'results/cacti_memory_20261016'
    rows=[]
    for name in ('original_no_flags','cacti_b8','cacti_b16'):
        d=json.loads((folder/(name+'_decode.json')).read_text())
        c=d['config'];h=s['hidden_size'];m=s['intermediate_size'];layers=s['num_hidden_layers']
        count=c['decode_tokens']
        inputs=layers*(h+m);outputs=layers*(2*m+h)
        partials=layers*((h//64)*(2*m)+(m//64)*h)
        assert partials*count==d['actions']['sc_tile_frames']*64
        encode=inputs*c['sc_cost']['input_encode_vector_ops']
        restore=partials*c['sc_cost']['finalize_vector_ops_per_partial']
        ops=encode+restore
        logic=ops*c['digital']['vector_op_pJ']*1e-12
        memory=ops*c['digital']['vector_interface_bytes_per_op']/2*(
            c['scratchpad']['read_pJ_per_byte']+c['scratchpad']['write_pJ_per_byte'])*1e-12
        assert ops*count<=d['actions']['vector_ops']
        assert logic*count<=d['energy_J']['digital_vector']+1e-15
        assert memory*count<=d['energy_J']['scratch_access']+1e-15
        row=dict(scenario=name,scope='full24 FFN, batch1 decode per token',
            logical_input_encodes=inputs,logical_gu_continuous_outputs=layers*2*m,
            logical_down_continuous_outputs=layers*h,logical_output_values=outputs,
            partial_scale_alignment_results=partials,input_encode_proxy_ops=encode,
            partial_postprocess_proxy_ops=restore,proxy_logic_uJ=logic*1e6,
            proxy_vector_interface_uJ=memory*1e6,proxy_combined_mJ=(logic+memory)*1000,
            proxy_fraction_of_scenario=(logic+memory)/(d['metrics']['scenario_mJ_per_token']/1000),
            proxy_vector_service_ms=ops/c['digital']['vector_ops_per_cycle']/c['frequency_hz']*1000,
            offline_weight_conversion_runtime_energy_J=0,
            measured_converter_energy_J=None,converter_area_mm2=None,
            note='attributed existing broad proxy, NOT converter measurement or upper bound; '
                 'includes partial alignment/reduction; excludes separate partial buffer traffic, '
                 'nonlinear/SwiGLU and RNG. Do not add this on top of existing total.')
        rows.append(row)
    target=ROOT/'results/format_conversion_audit_20261016.json'
    target.write_text(json.dumps(rows,indent=2)+'\n')
    for r in rows:print(json.dumps(r),flush=True)


if __name__=='__main__':main()
