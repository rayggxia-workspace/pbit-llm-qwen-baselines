# Pre-layout PX template. Optional SPEF must match the very same netlist/corner.
foreach name {STD_DB NET_DIR SIM_DIR OUT_DIR} {if {![info exists env($name)]} {error "missing $name"}}
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
set link_path [concat [list "*"] $env(STD_DB)]
read_verilog [file join $env(NET_DIR) mapped.v]
set case_type arithmetic
if {[info exists env(CASE_TYPE)]} {set case_type $env(CASE_TYPE)}
if {$case_type=="router"} {set mapped_top nr_sram_router_mapped;set strip tb_memory/router;set window_file router_window.txt
} elseif {$case_type=="dma"} {set mapped_top nr_dma_window_mapped;set strip tb_memory/dma;set window_file dma_window.txt
} else {set mapped_top nr_digital_probe_mapped;set strip tb_power/dut;set window_file window.txt}
current_design $mapped_top
link
read_sdc [file join $env(NET_DIR) mapped.sdc]
if {[info exists env(OC_NAME)]} {set_operating_conditions $env(OC_NAME)}
if {[info exists env(SPEF)]} {read_parasitics $env(SPEF)}
set f [open [file join $env(SIM_DIR) $window_file] r];set window [read $f];close $f
if {![regexp {start_ns=([0-9.]+)} $window -> begin]} {error "missing window start"}
if {![regexp {end_ns=([0-9.]+)} $window -> end]} {error "missing window end"}
if {$end<=$begin} {error "invalid window"}
set vcd_name power.vcd
if {[info exists env(VCD_NAME)]} {set vcd_name $env(VCD_NAME)}
read_vcd -strip_path $strip -time [list $begin $end] [file join $env(SIM_DIR) $vcd_name]
update_timing
update_power
file mkdir $env(OUT_DIR)
redirect [file join $env(OUT_DIR) power.rpt] {report_power -hierarchy}
redirect [file join $env(OUT_DIR) activity.rpt] {report_switching_activity -list_not_annotated}
redirect [file join $env(OUT_DIR) timing.rpt] {report_timing -delay_type max -max_paths 20}
redirect [file join $env(OUT_DIR) hold.rpt] {report_timing -delay_type min -max_paths 20}
redirect [file join $env(OUT_DIR) constraints.rpt] {report_constraint -all_violators}
quit
