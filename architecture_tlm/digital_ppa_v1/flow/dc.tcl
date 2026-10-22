# User runs in their licensed 55nm environment. No library files in Git/bundle.
# ROOT=repo/bundle root, KIND0..17/20..22, STD_DB=list, OUT_DIR=new directory.
foreach name {ROOT STD_DB OUT_DIR} {if {![info exists env($name)]} {error "missing $name"}}
set root [file normalize $env(ROOT)]
set target_library $env(STD_DB)
set link_library [concat [list "*"] $target_library]
set app [file join $root architecture_tlm digital_ppa_v1]
set search_path [concat $search_path [list [file join $app rtl] [file join $root format_conversion_rtl_20261016 rtl]]]
set out [file normalize $env(OUT_DIR)];file mkdir $out
set sources [concat [glob [file join $app rtl *.sv]] [glob [file join $root format_conversion_rtl_20261016 rtl *.sv]]]
analyze -format sverilog $sources
set case_type arithmetic
if {[info exists env(CASE_TYPE)]} {set case_type $env(CASE_TYPE)}
if {$case_type=="router"} {
 elaborate nr_sram_router -parameters "PORTS=4,BANKS=16,DATA_W=32,ROW_W=4"
 set mapped_top nr_sram_router_mapped
} elseif {$case_type=="dma"} {
 elaborate nr_dma_window -parameters "WINDOW=4,BURST_BYTES=64"
 set mapped_top nr_dma_window_mapped
} elseif {$case_type=="arithmetic"} {
 if {![info exists env(KIND)]} {error "KIND required"}
 elaborate nr_digital_probe -parameters "KIND=$env(KIND)"
 set mapped_top nr_digital_probe_mapped
} else {error "unknown CASE_TYPE"}
rename_design [current_design] $mapped_top
link
redirect [file join $out check_design.rpt] {check_design}
set period 10.0
if {[info exists env(PERIOD_NS)]} {set period $env(PERIOD_NS)}
create_clock -name core_clk -period $period [get_ports clk]
set_clock_uncertainty -setup 2.0 [get_clocks core_clk]
set_clock_uncertainty -hold 0.1 [get_clocks core_clk]
set_clock_transition 0.1 [get_clocks core_clk]
set data_inputs [remove_from_collection [all_inputs] [get_ports {clk rst_n}]]
set_input_delay -max 1.0 -clock core_clk $data_inputs
set_input_delay -min 0.2 -clock core_clk $data_inputs
set_input_transition 0.1 $data_inputs
set_output_delay -max 1.0 -clock core_clk [all_outputs]
set_output_delay -min 0.2 -clock core_clk [all_outputs]
set_load 0.02 [all_outputs]
# Synchronous reset is not a free false path. Use real operating conditions.
if {[info exists env(OC_NAME)]} {set_operating_conditions $env(OC_NAME)}
compile_ultra
change_names -rules verilog -hierarchy
redirect [file join $out area.rpt] {report_area -hierarchy}
redirect [file join $out timing.rpt] {report_timing -delay_type max -max_paths 20}
redirect [file join $out hold.rpt] {report_timing -delay_type min -max_paths 20}
redirect [file join $out constraints.rpt] {report_constraint -all_violators}
redirect [file join $out cells.rpt] {report_reference -hierarchy}
write -format verilog -hierarchy -output [file join $out mapped.v]
write_sdc [file join $out mapped.sdc]
write -format ddc -hierarchy -output [file join $out mapped.ddc]
quit
