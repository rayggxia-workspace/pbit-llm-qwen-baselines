# Private AC_TARGET_DB, AC_TOP, AC_NETLIST, AC_SDC and AC_VCD are required.
# AC_STRIP_PATH must identify the actual activity DUT hierarchy (TB or mapped
# top wrapper); verify annotation rather than silently accepting zero coverage.
set link_path [list * $::env(AC_TARGET_DB)]
set power_enable_analysis true
set power_analysis_mode time_based
read_verilog $::env(AC_NETLIST)
current_design $::env(AC_TOP)
link_design
read_sdc $::env(AC_SDC)
check_timing > check_timing.rpt
report_timing -delay_type max -max_paths 20 > setup.rpt
report_timing -delay_type min -max_paths 20 > hold.rpt
read_vcd $::env(AC_VCD) -strip_path $::env(AC_STRIP_PATH) -time [list $::env(AC_START_NS) $::env(AC_END_NS)]
report_switching_activity -list_not_annotated > activity_unannotated.rpt
check_power > check_power.rpt
update_power
report_power -hierarchy > power.rpt
report_power -verbose > power_verbose.rpt
exit
