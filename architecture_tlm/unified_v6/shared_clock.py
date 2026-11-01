"""Named chip clocks and explicit macro cycle contracts; no STA claim."""
from dataclasses import dataclass
import math

PROFILES=('chip100','legacy_mixed')

@dataclass(frozen=True)
class SharedClock:
    name:str='chip100'
    chip_hz:int=100_000_000
    def __post_init__(self):
        if self.name not in PROFILES:raise ValueError('unknown shared clock profile')
    @property
    def synchronous(self):return self.name=='chip100'
    @property
    def period_ns(self):return 1e9/self.chip_hz
    @property
    def mac_hz(self):return self.chip_hz if self.synchronous else 500_000_000
    @property
    def mac_period_ns(self):return 1e9/self.mac_hz
    def service_ns(self,name,legacy_ns):
        if not self.synchronous:return legacy_ns
        # These five old macro durations were specified in500MHz cycles.
        # Preserve their explicit cycle contracts; do not retain their2ns ticks.
        fast_cycles={'GU_crossK_align_add_macro':5,'down_crossK_align_add_macro':2,
            'GU_fixed8_quant_macro':4,'final_BF16_macro':3,'streaming_argmax_macro':7}
        cycles=fast_cycles.get(name,math.ceil(legacy_ns/self.period_ns-1e-8))
        return cycles*self.period_ns
    def report(self):
        return dict(profile=self.name,chip_hz=self.chip_hz,period_ns=self.period_ns,
            frequencies_hz=dict(QKV_O_lm_head=self.mac_hz,QK=self.chip_hz,PV_add=self.chip_hz,
                FFN_GU=self.chip_hz,FFN_NL_Wd=self.chip_hz,SRAM=self.chip_hz,
                DMA_front=self.chip_hz,macros=self.chip_hz if self.synchronous else 'mixed_legacy_contracts'),
            all_onchip_one_clock=self.synchronous,DDR_clock='independent DDR4-1866 timings from DRAMSys config',
            array_MAC_lanes=2048,array_MAC_pipeline_cycles=2,
            array_MAC_pipeline_status='FMA2 cycle anchor; complete2048lane array/mapping/STA not characterized; scalar hold warning retained',
            measured_frame_cycles=dict(GU=66,NL=66),
            pipeline_cycle_anchors=dict(QK=14,PV_feedback=7),
            fast_macro_cycles=dict(GU_crossK=5,Wd_crossK=2,GU_quant=4,BF16_exit=3,argmax=7),
            proxy_rounding='other legacy100MHz durations rounded UP to whole chip cycles; not new RTL-derived pipelines',
            synchronous_capture=self.synchronous,clock_tree_power_included=False,
            evidence='digital_circuit_simulation_registry/03_算子周期与时延依据.md; 05_随机版功耗重算.md; 11_矩阵与算术模块功耗面积时钟索引.md')
