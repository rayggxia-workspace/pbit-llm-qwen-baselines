# Template only: run AFTER mapped-netlist simulation passes the same TB.
# Required TOP TARGET_DB NETLIST SDC VCD START_NS END_NS GATE_LOG.
# Window from ACTIVITY_PASS. VCD scope tb_activity.c.dut; zero-delay, no CTS/RC.
foreach k {TOP TARGET_DB NETLIST SDC VCD START_NS END_NS GATE_LOG} {
  if {![info exists ::env($k)]} {error "Missing $k"}
}
set f [open $::env(GATE_LOG) r]; set log [read $f]; close $f
if {![regexp {ACTIVITY_PASS} $log] || [regexp -nocase {fatal|error} $log]} {
  error "Gate functional check did not pass; do not use RTL VCD"
}
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
set_app_var link_path [concat {*} $::env(TARGET_DB)]
read_verilog $::env(NETLIST)
current_design $::env(TOP)
if {![link]} {error "Link failed"}
read_sdc $::env(SDC)
read_vcd -strip_path tb_activity.c.dut -time [list $::env(START_NS) $::env(END_NS)] $::env(VCD)
check_power > check_power.rpt
report_switching_activity -list_not_annotated > unannotated.rpt
update_timing
report_timing -delay_type max -max_paths 10 > setup_pt.rpt
report_timing -delay_type min -max_paths 10 > hold_pt.rpt
update_power
report_power -hierarchy > power_hierarchy.rpt
report_power -verbose > power_total.rpt
report_power -cell -verbose > power_cells.rpt
# No 'PASS' PPA flag here: review annotation, X/Z, units, library warnings and STA.
quit
