import copy,json,unittest
from pathlib import Path
from .estimate import HERE,load,model_from_config,quantities,estimate_model,energy_budget,time_budget

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.c=load(HERE/'CALIBRATION.json')
        cls.m={k:model_from_config(k,load(HERE/'evidence'/(k+'_config.json')))
               for k in ('qwen3_4b','llama32_3b','deepseek_7b')}

    def test_original_three_seed_anchor(self):
        z=estimate_model(self.m['qwen3_4b'],self.c,True);s=z['scenarios']['reference_efficiency']
        self.assertAlmostEqual(z['quantities']['external_bytes'],self.c['reference']['external_bytes'],places=4)
        for k,v in self.c['reference']['onchip_components_mJ'].items():
            self.assertAlmostEqual(s['onchip_components_mJ'][k],v,places=8)
        self.assertAlmostEqual(s['time_ms'],49.56325,places=9)

    def test_official_model_parameter_counts(self):
        identities={x['key']:x for x in load(HERE/'evidence/MODEL_IDENTITIES.json')}
        for key,m in self.m.items():
            L,d,f,q,kv,h,V=(m[k] for k in ('layers','hidden','ffn','q_heads','kv_heads','head_dim','vocab'))
            count=L*(3*d*f+2*d*(q+kv)*h+2*d+(2*h if m['qk_norm'] else 0))+d
            count+=(1 if m['tie_word_embeddings'] else 2)*V*d
            if identities[key]['public_parameter_count'] is not None:
                self.assertEqual(count,identities[key]['public_parameter_count'],key)

    def test_capacity_and_logical_head_folding(self):
        llama=quantities(self.m['llama32_3b'],self.c);ds=quantities(self.m['deepseek_7b'],self.c)
        self.assertEqual(llama['query_heads_per_KV'],3);self.assertEqual(ds['query_heads_per_KV'],1)
        self.assertEqual(llama['physical_KVgroup_waves_per_layer'],1)
        self.assertEqual(ds['physical_KVgroup_waves_per_layer'],4)
        self.assertEqual(ds['memory_placement']['normalization_policy'],'layer_stream_double_buffer')
        self.assertTrue(ds['memory_placement']['original_resident_layout_failing_banks'])
        for z in (llama,ds):self.assertLessEqual(z['memory_placement']['physical_allocated_bytes'],2621440)
        self.assertEqual(ds['metadata_per_layer_bytes'],33024)

    def test_no_free_random_memory_or_area_scaling(self):
        areas=[]
        for m in self.m.values():
            z=estimate_model(m,self.c,m['key']=='qwen3_4b');s=z['scenarios']['reference_efficiency']
            areas.append(s['covered_area55_mm2'])
            self.assertEqual(s['onchip_components_mJ']['FFN_random_service_proxy'],0)
            self.assertTrue(s['FFN_RNG_already_inside_core'])
            self.assertAlmostEqual(sum(s['onchip_components_mJ'].values()),s['onchip_mJ'],places=8)
            self.assertAlmostEqual(s['covered_system_mJ_at4pJ'],s['onchip_mJ']+z['quantities']['external_bytes']*32e-9,places=8)
            self.assertLess(s['covered_system_mJ_at4pJ'],s['onchip_mJ']+s['external_mJ_by_pJ_per_bit']['6.6'])
        self.assertTrue(all(abs(a-67.54144608182283)<1e-10 for a in areas))

    def test_streaming_bytes_are_not_model_storage(self):
        m=self.m['deepseek_7b'];z=quantities(m,self.c)
        # Untied embedding table exists in DRAM but decode reads only one row;
        # lm_head is fully streamed once. No second full embedding scan.
        self.assertEqual(z['physical_mixed_weight_storage_bytes']-
            sum(z['dram_bytes_by_kind'][k] for k in ('QKV_weights','O_weights','GU_weights','down_weights','lm_head_weights')),
            2*m['vocab']*m['hidden'])
        self.assertLess(z['weight_plus_KV_storage_bytes'],16*1024**3)

    def test_efficiency_and_V_sensitivity_monotonic(self):
        z=estimate_model(self.m['deepseek_7b'],self.c)
        self.assertLess(z['scenarios']['util90']['time_ms'],z['scenarios']['util65']['time_ms'])
        self.assertGreater(z['scenarios']['util90']['covered_system_average_W_at4pJ'],z['scenarios']['util65']['covered_system_average_W_at4pJ'])
        a,b=z['V_reuse_bounds_at_reference_efficiency']
        self.assertLess(a['external_bytes'],b['external_bytes'])
        self.assertLess(a['system_mJ_at4pJ'],b['system_mJ_at4pJ'])

if __name__=='__main__':unittest.main()
