"""Independent GQA numeric, lifetime, transport and address adversaries."""
import copy
from collections import Counter
import struct
import unittest
from dataclasses import replace

from architecture_tlm.cycle_v1.attention import AttentionConfig, SamplerCapError
from architecture_tlm.cycle_v1.gqa import GQAConfig, address_layout, build_gqa, make_gqa
from architecture_tlm.cycle_v1.audit.gqa_oracles import overlap_fixture, scalar_query


class IndependentGQAAudit(unittest.TestCase):
    def run_pair(self, fixture, configs=None, group_config=None, **kw):
        pairs=[]
        for mode in ("cycle", "event"):
            kernel,state=make_gqa(copy.deepcopy(fixture), configs, group_config, **kw)
            result=kernel.run(mode=mode)
            for name,spec in kernel.buffer_specs.items():
                self.assertEqual(result.buffer_final[name], spec.initial, name)
            self.assertEqual(set(result.accepted_ps), set(kernel.operations))
            self.assertEqual(set(result.completion_ps), set(kernel.operations))
            self.check_shared_transport(kernel,state,result)
            pairs.append((kernel,state,result))
        self.assertEqual(pairs[0][1],pairs[1][1])
        self.assertEqual(pairs[0][2].equivalence_payload(),pairs[1][2].equivalence_payload())
        return pairs[0]

    def check_shared_transport(self,kernel,state,result):
        for kind in ("K","V"):
            reads=state[kind+"_read_ids"]
            self.assertEqual(sorted(reads),state[kind+"_union"])
            self.assertEqual(result.actions["shared_"+kind+"_rows"],len(reads))
            accept=[r for r in result.trace if r["kind"]=="accept" and r.get("op") in reads.values()]
            self.assertEqual(len(accept),len(reads))
            self.assertEqual(sorted(r["address"] for r in accept),sorted(state[kind+"_addresses"]))
            for token,read in reads.items():
                release=state[kind+"_release_ids"][token]
                consumers=state[kind+"_consumers"][token]
                self.assertTrue(consumers)
                self.assertEqual(set(kernel.operations[release].deps),set(consumers))
                for consumer in consumers:
                    self.assertLess(result.completion_ps[read],result.accepted_ps[consumer])
                    self.assertLess(result.completion_ps[consumer],result.accepted_ps[release])
        for query in state["queries"]:
            raw=kernel.read_memory("sram",query["output_address"],query["output_bytes"])
            self.assertEqual(list(struct.unpack("<"+"f"*(len(raw)//4),raw)),query["output"])

    def test_exact_overlap_slot_one_window_one_preserves_numeric_order(self):
        for reverse in (False,True):
            data=overlap_fixture(reverse_heads=reverse)
            k,state,r=self.run_pair(data,AttentionConfig(),GQAConfig(k_slots=1,v_slots=1),
                                     memory_window=1,memory_banks=1)
            self.assertEqual(state["K_union"],[1,2,3,10])
            self.assertEqual(state["V_union"],[1,2,3,10])
            self.assertEqual(r.actions["K_read_bytes"],4*2*4)
            self.assertEqual(r.actions["V_read_bytes"],4*3*4)
            self.assertEqual(r.actions["shared_cache_read_bytes"],6*(2+3)*4)
            for query,actual in zip(data["queries"],state["queries"]):
                self.assertEqual(actual["output"],scalar_query(data,query))

    def test_pv_duplicates_are_per_head_and_union_reads_once(self):
        data=overlap_fixture(mode="pv")
        c=AttentionConfig(mode="pv",samples=6,random_backend="replay")
        _,state,r=self.run_pair(data,c,GQAConfig(k_slots=1,v_slots=1),memory_window=1,memory_banks=1)
        for query,actual in zip(data["queries"],state["queries"]):
            counts={token:2 for token in query["candidate_ids"]}
            self.assertEqual(actual["histogram"],counts)
            self.assertEqual(actual["retained_samples"],6)
            self.assertEqual(actual["output"],scalar_query(data,query,physical_counts=counts))
        self.assertEqual(r.actions["sample_output"],12)
        self.assertEqual(r.actions["V_read_bytes"],48)

    def test_nonuniform_exact_scores_have_independent_scalar_answers(self):
        data=overlap_fixture()
        data["queries"][0]["q"]=[.125,-.0625]
        data["queries"][1]["q"]=[-.25,.125]
        _,state,_=self.run_pair(data,AttentionConfig(),GQAConfig(k_slots=1,v_slots=1))
        for query,actual in zip(data["queries"],state["queries"]):
            self.assertEqual(actual["output"],scalar_query(data,query))

    def test_mixed_exact_and_delayed_pv_wait_for_every_head_before_v(self):
        data=overlap_fixture(mode="pv")
        del data["queries"][0]["random_replay"]
        configs=[AttentionConfig(mode="exact"),AttentionConfig(mode="pv",samples=6,
                 random_backend="replay",histogram_delay_cycles=31)]
        k,state,r=self.run_pair(data,configs,GQAConfig(k_slots=1,v_slots=1))
        barrier=state["V_barrier_id"]
        self.assertEqual(len(k.operations[barrier].deps),2)
        for dep in k.operations[barrier].deps:
            self.assertLess(r.completion_ps[dep],r.accepted_ps[barrier])
        for read in state["V_read_ids"].values():
            self.assertLess(r.completion_ps[barrier],r.accepted_ps[read])
        self.assertEqual(state["queries"][0]["output"],scalar_query(data,data["queries"][0]))
        self.assertEqual(state["queries"][1]["output"],scalar_query(data,data["queries"][1],
                         physical_counts={10:2,3:2,2:2}))

    def test_return_reordering_cannot_release_shared_slot_before_all_consumers(self):
        data=overlap_fixture()
        gc=GQAConfig(k_slots=2,v_slots=2)
        layouts,_=address_layout(data,group_config=gc)
        slow={layouts[0]["k"]+1*8:23,layouts[0]["k"]+2*8:1,
              layouts[0]["v"]+1*12:23,layouts[0]["v"]+2*12:1}
        k,state,r=self.run_pair(data,AttentionConfig(),gc,
                                memory_latency_by_address=slow,memory_window=4)
        for kind in ("K","V"):
            reads=state[kind+"_read_ids"]
            self.assertLess(r.completion_ps[reads[2]],r.completion_ps[reads[1]])
            self.assertGreater(r.accepted_ps[reads[3]],r.completion_ps[state[kind+"_release_ids"][1]])

    def test_actual_shared_k_and_v_bytes_are_checked(self):
        data=overlap_fixture()
        for region in ("k","v"):
            k,state=make_gqa(data)
            layouts,_=address_layout(data)
            row_bytes=8 if region=="k" else 12
            k.load_memory("dram",layouts[0][region]+row_bytes,struct.pack("<f",123.0))
            with self.assertRaisesRegex(AssertionError,"payload mismatch"):
                k.run(mode="event")

    def test_query_addresses_disjoint_and_group_capacity_rejects(self):
        data=overlap_fixture()
        data["queries"]*=6
        gc=GQAConfig(base_address=0x80000003)
        layouts,regions=address_layout(data,group_config=gc)
        self.assertEqual(len(layouts),12)
        for i,left in enumerate(regions):
            self.assertEqual(left["address"]%64,0)
            for right in regions[i+1:]:
                self.assertTrue(left["address"]+left["size_bytes"]<=right["address"] or
                                right["address"]+right["size_bytes"]<=left["address"])
        _,state,_=self.run_pair(data,AttentionConfig(),gc,memory_window=1)
        self.assertEqual(len(set(q["output_address"] for q in state["queries"])),12)
        with self.assertRaisesRegex(ValueError,"group budget"):
            make_gqa(data,group_config=replace(gc,query_state_capacity_bytes=12*32768-1))

    def test_existing_address_owner_and_bad_inputs_rejected(self):
        data=overlap_fixture()
        k,_=make_gqa(data)
        with self.assertRaisesRegex(ValueError,"overlaps"):
            build_gqa(k,data,prefix="second")
        bad=copy.deepcopy(data)
        bad["queries"][1]["candidate_ids"]=[2,2]
        with self.assertRaisesRegex(ValueError,"unique"):
            make_gqa(bad)
        bad=copy.deepcopy(data)
        bad["queries"][1]["q"]=[0.0]
        with self.assertRaisesRegex(ValueError,"shape"):
            make_gqa(bad)
        with self.assertRaisesRegex(ValueError,"nonempty"):
            make_gqa(dict(data,queries=[]))

    def test_shared_cache_port_bandwidth_is_finite(self):
        data=overlap_fixture()
        _,fast,fr=self.run_pair(data,group_config=GQAConfig(cache_bytes_per_cycle=64))
        _,slow,sr=self.run_pair(data,group_config=GQAConfig(cache_bytes_per_cycle=1))
        self.assertEqual([q["output"] for q in fast["queries"]],[q["output"] for q in slow["queries"]])
        self.assertGreater(sr.finish_ps,fr.finish_ps)
        self.assertEqual(sr.actions["shared_cache_read_bytes"],fr.actions["shared_cache_read_bytes"])

    def test_native_per_head_sources_are_distinct_and_all_credits_return(self):
        data=overlap_fixture()
        c=AttentionConfig(mode="pv",samples=6,seed_word_interval=1,seed_startup=0)
        k,state,r=self.run_pair(data,c,GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        instances=state["provenance"]["source_instances"]
        self.assertEqual([q["seed"] for q in instances],[0,1])
        self.assertTrue(all(q["native_network"] for q in instances))
        for head,query in enumerate(state["queries"]):
            self.assertIsNotNone(query["native_random"])
            self.assertEqual(query["histogram"],{token:2 for token in data["queries"][head]["candidate_ids"]})
            self.assertEqual(query["output"],scalar_query(data,data["queries"][head],
                physical_counts={token:2 for token in data["queries"][head]["candidate_ids"]}))

    def test_failed_head_sampler_does_not_fabricate_group_outputs(self):
        data=overlap_fixture()
        data["queries"][1]["random_replay"]={"frames":[[True,True],[True,True]]}
        configs=[AttentionConfig(),AttentionConfig(mode="rejection",samples=1,random_backend="replay",
                   max_proposals_per_sample=2)]
        k,state=make_gqa(data,configs)
        with self.assertRaises(SamplerCapError):
            k.run(mode="event")
        self.assertIsNone(state["V_union"])
        self.assertTrue(all(q["output"] is None for q in state["queries"]))

    def test_winner_hold_multiplicities_share_only_selected_v_union(self):
        data=overlap_fixture()
        for query in data["queries"]:
            query["random_replay"]={"frames":[[False,False,False],[False,True,True],
                [True,False,True],[True,True,False]],"fair":[1,0]}
        c=AttentionConfig(mode="winner",samples=4,source_lanes=2,random_backend="replay")
        _,state,r=self.run_pair(data,c,GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        self.assertEqual(state["K_union"],[1,2,3,10])
        self.assertEqual(state["V_union"],[1,2,10])
        for query,actual in zip(data["queries"],state["queries"]):
            ids=query["candidate_ids"]
            counts={ids[0]:2,ids[2]:2}
            self.assertEqual(actual["local_indices"],[0,2,2,0])
            self.assertEqual(actual["histogram"],counts)
            self.assertEqual(actual["output"],scalar_query(data,query,physical_counts=counts))
        self.assertEqual(r.actions["V_read_bytes"],36)

    def test_rejection_keeps_each_heads_failed_attempts_and_histogram(self):
        data=overlap_fixture()
        for query in data["queries"]:
            query["random_replay"]={"frames":[[True,True],[False,False],[False,True],[False,False]],"fair":[1]}
        c=AttentionConfig(mode="rejection",samples=2,source_lanes=1,random_backend="replay")
        _,state,r=self.run_pair(data,c,GQAConfig(k_slots=1,v_slots=1),memory_window=1)
        self.assertEqual(state["V_union"],[1,2,10])
        for query,actual in zip(data["queries"],state["queries"]):
            ids=query["candidate_ids"]
            counts={ids[0]:1,ids[2]:1}
            self.assertEqual(actual["local_indices"],[2,0])
            self.assertEqual(actual["proposals"],4)
            self.assertEqual(actual["rejected_multi"],1)
            self.assertEqual(actual["rejected_empty"],1)
            self.assertEqual(actual["output"],scalar_query(data,query,physical_counts=counts))

    def test_union_metadata_exact_capacity_and_runtime_scan_cost(self):
        data=overlap_fixture()
        # Each of two directories has four entries: 12B ID/refcount/scratch
        # plus one byte for two head bits; each head also owns 16B cursors.
        expected_bytes=2*4*(12+1)+2*16
        self.assertEqual(expected_bytes,136)
        with self.assertRaisesRegex(ValueError,"metadata"):
            make_gqa(data,group_config=GQAConfig(metadata_capacity_bytes=135))
        pairs=[]
        for lanes in (1,16):
            k,state,r=self.run_pair(data,group_config=GQAConfig(metadata_capacity_bytes=136,union_scan_lanes=lanes))
            self.assertEqual(sum(state["metadata_bytes"].values()),136)
            self.assertEqual(r.actions["gqa_metadata_reserve_bytes"],136)
            self.assertEqual(r.actions["gqa_metadata_release_bytes"],136)
            self.assertEqual(r.actions["gqa_histogram_scan_entries"],6)
            self.assertEqual(r.actions["gqa_union_bitmap_tests"],4)
            for suffix,count in (("scan",6),("compact",4)):
                ident="gqa.V.union_"+suffix
                self.assertEqual(r.completion_ps[ident]-r.accepted_ps[ident],((count+lanes-1)//lanes)*10000)
            for read in state["V_read_ids"].values():
                self.assertLess(r.completion_ps["gqa.V.union_compact"],r.accepted_ps[read])
            self.assertEqual(state["complete_ps"],r.finish_ps)
            self.assertEqual(r.buffer_final["gqa.metadata.free"],136)
            pairs.append((state,r))
        self.assertEqual([q["output"] for q in pairs[0][0]["queries"]],
                         [q["output"] for q in pairs[1][0]["queries"]])
        self.assertGreater(pairs[0][1].finish_ps,pairs[1][1].finish_ps)

    def test_single_operand_slot_holds_from_cache_issue_through_mac_completion(self):
        data=overlap_fixture(mode="pv")
        c=AttentionConfig(mode="pv",samples=6,random_backend="replay")
        gc=GQAConfig(k_slots=1,v_slots=1,operand_slots=1)
        k,state,r=self.run_pair(data,c,gc,memory_window=1,memory_banks=1)
        self.assertEqual(state["operand_capacity_bytes"],12)
        rows=[]
        for ident,op in k.operations.items():
            if op.resource!="gqa.cache": continue
            consumers=[other for other in k.operations.values() if ident in other.deps]
            self.assertEqual(len(consumers),1)
            consumer=consumers[0]
            self.assertEqual(op.inputs["gqa.operand.free"],12)
            self.assertEqual(consumer.outputs["gqa.operand.free"],12)
            rows.append((r.accepted_ps[ident],r.completion_ps[consumer.id]))
        self.assertEqual(len(rows),12)
        rows.sort()
        for previous,current in zip(rows,rows[1:]):
            self.assertLess(previous[1],current[0])
        self.assertEqual(r.buffer_final["gqa.operand.free"],12)

    def test_heads_cannot_silently_reconfigure_shared_arithmetic_resources(self):
        data=overlap_fixture()
        base=AttentionConfig()
        for field in ("source_latency","source_ii","exp_latency","cdc_cycles","mac_lanes",
                      "vector_lanes","exp_lanes","reciprocal_latency","drive_latency","lut_latency"):
            with self.subTest(field=field):
                with self.assertRaisesRegex(ValueError,"shared physical"):
                    make_gqa(data,[base,replace(base,**{field:getattr(base,field)+1})])


if __name__=="__main__":
    unittest.main()
