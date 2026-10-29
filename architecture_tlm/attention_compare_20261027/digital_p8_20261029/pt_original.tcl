if {[catch {
 source $::env(P8_SOURCE)/common.tcl
 set_host_options -max_cores 1
 set_app_var power_enable_analysis true
 set_app_var power_analysis_mode averaged
 set_app_var link_create_black_boxes false
 set_app_var link_path [list * $::env(P8_DB)]
 read_verilog $::env(P8_NETLIST)
 if {![link_design $::env(P8_TOP)]} {error "PT link failed"}
 read_sdc $::env(P8_SDC)
 set_propagated_clock [get_clocks core]
 # Propagated clocks use the root input slew; set_clock_transition alone is
 # ignored here. Avoid a zero-slew extrapolation at every ICG CK pin.
 set_input_transition 0.1 [get_ports clk]
 inventory
 timing
 report_units > units.rpt
 read_vcd -strip_path tb/dut -time [list $::env(P8_START) $::env(P8_END)] $::env(P8_VCD)
 report_switching_activity -list_not_annotated > activity.rpt
 check_power -verbose > check_power.rpt
 update_power
 report_power -verbose > power.rpt
 report_power -hierarchy > hierarchy.rpt
 report_power -cell_power [get_cells -hierarchical * -filter {is_hierarchical == false}] > cell_power.rpt
 putfile PT_COMPLETE "calculated, prelayout zero-delay activity"
} msg]} {putfile FAILURE.txt "$msg\n$::errorInfo";exit 1}
exit 0
