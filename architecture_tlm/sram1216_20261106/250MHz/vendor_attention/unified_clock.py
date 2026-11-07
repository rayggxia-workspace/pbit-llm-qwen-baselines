"""A single4ns on-chip clock. External LPDDR timing is unchanged."""
import math

class Unified250Clock:
 name='chip250';chip_hz=250_000_000;synchronous=True
 period_ns=4.;mac_hz=250_000_000;mac_period_ns=4.
 def service_ns(self,name,legacy_ns):
  # Preserve original100MHz macro cycle counts, including original fast anchors.
  fast={'GU_crossK_align_add_macro':5,'down_crossK_align_add_macro':2,
        'GU_fixed8_quant_macro':4,'final_BF16_macro':3,'streaming_argmax_macro':7}
  return fast.get(name,math.ceil(legacy_ns/10.-1e-8))*4.
 def report(self):
  return dict(profile=self.name,chip_hz=self.chip_hz,period_ns=4.,all_onchip_one_clock=True,
   frequencies_hz={k:250_000_000 for k in ('QKV_O_lm_head','QK','PV_add','SRAM','DMA_front','macros')},
   DRAM='independent pinned LPDDR5X timings unchanged',scope='Attention prefix only; no FFN/whole-token validation',
   macro_policy='preserve legacy100MHz macro cycle counts; no new vector RTL STA',clock_tree_power_included=False)

def install_clock(model):
 h=model.h;mem=h.mem
 assert h.now==0 and not h.events and not h.descriptors and not mem.queue and not mem.scheduled
 assert mem.period==10 and h.issue_period==10 and h.common_period_ns==10
 before=dict(SRAM_period_ns=mem.period,DMA_period_ns=h.issue_period,fabric_words_per_cycle=mem.fabric_words,issue_per_cycle=h.issue_n)
 # Existing library extraction E: read minimum3.468ns, write3.4271ns,
 # CLK->Q2.8767ns at retained source slew/load. This is not routed timing signoff.
 assert 4.>=max(3.468,3.4271) and mem.access_ns<=4.
 mem.period=4.;h.issue_period=4.;h.common_period_ns=4.
 # Preserve physical word/bank/port count and issue width, not a fixedGB/s cap.
 # Keeping the width while changing its clock is not adding ports.
 model.clock=Unified250Clock();model.mac_hz=250_000_000
 model.unified_clock_contract=dict(before=before,SRAM_MHz=250,DMA_front_MHz=250,compute_MHz=250,
   period_ns=4.,SRAM_access_ns=mem.access_ns,SRAM_min_period_ns=3.468,
   fabric_words_per_cycle=mem.fabric_words,issue_per_cycle=h.issue_n,
   physical_banks=mem.nbank,capacity_bytes=mem.capacity,bank_ports='1RW',word_bytes=mem.word,
   read_write_energy='retain event prices, never multiply pJ by2.5',
   clock_idle='CEoff plus root gating assumptions;250MHz clock distribution unmeasured',
   library_evidence='sram-38071895-library, caseE SS1.08V125C; proxy retained, not TT250 measurement')
 model.compact_memory.update(bank_clock_MHz=250)
