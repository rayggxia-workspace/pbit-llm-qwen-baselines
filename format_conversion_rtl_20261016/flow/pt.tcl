# Use a separate simulation directory per design/activity mode, with power.vcd
# and window.txt. Report absolute power plus idle-subtracted dynamics separately.
foreach v {STD_DB STD_LIB_NAME OC_NAME NET_DIR SIM_DIR CASE_TYPE} {
 if {![info exists ::env($v)]} {error "Missing environment $v"}
}
set_app_var search_path [concat $search_path [list $::env(NET_DIR)]]
set_app_var link_path [list * $::env(STD_DB)]
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
read_verilog $::env(NET_DIR)/mapped.v
if {$::env(CASE_TYPE) eq "conversion"} {current_design fc_conversion_probe} else {current_design fc_accum_probe}
link_design
set_operating_conditions -library $::env(STD_LIB_NAME) $::env(OC_NAME)
read_sdc $::env(NET_DIR)/mapped.sdc
set f [open $::env(SIM_DIR)/window.txt r]
set window [split [string trim [read $f]]];close $f
if {[llength $window]!=2} {error "Malformed window.txt"}
read_vcd -strip_path tb_power/dut -time $window $::env(SIM_DIR)/power.vcd
update_timing
check_power > $::env(SIM_DIR)/check_power.rpt
update_power
report_power -hierarchy -levels 6 > $::env(SIM_DIR)/power_hierarchy.rpt
report_power > $::env(SIM_DIR)/power.rpt
report_switching_activity -list_not_annotated > $::env(SIM_DIR)/activity_missing.rpt
report_timing -delay_type max -max_paths 20 > $::env(SIM_DIR)/setup.rpt
report_timing -delay_type min -max_paths 20 > $::env(SIM_DIR)/hold.rpt
report_constraint -all_violators > $::env(SIM_DIR)/constraints.rpt
report_units > $::env(SIM_DIR)/units.rpt
quit
