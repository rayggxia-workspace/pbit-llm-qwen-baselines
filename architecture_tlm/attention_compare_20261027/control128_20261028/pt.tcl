# Prelayout averaged power from the matching mapped-netlist VCD. No SPEF/CTS.
if {[catch {
    set_host_options -max_cores 1
    set_app_var power_enable_analysis true
    set_app_var power_analysis_mode averaged
    set_app_var link_create_black_boxes false
    set_app_var link_path [list * $::env(AC_TARGET_DB)]
    read_verilog $::env(AC_NETLIST)
    if {![link_design $::env(AC_TOP)]} {error "link failed"}
    read_sdc $::env(AC_SDC)
    update_timing
    report_units > units.rpt
    report_clock > clocks.rpt
    check_timing > check_timing.rpt
    report_timing -delay_type max -max_paths 10 > setup.rpt
    report_timing -delay_type min -max_paths 10 > hold.rpt
    report_constraint -all_violators > constraints.rpt
    report_analysis_coverage > analysis_coverage.rpt
    report_analysis_coverage -status_details untested > untested.rpt
    report_disable_timing > disable_timing.rpt
    report_exceptions > exceptions.rpt
    report_timing -from [all_registers -clock_pins] -to [all_registers -data_pins] -delay_type max -max_paths 10 > reg_setup.rpt
    report_timing -from [all_registers -clock_pins] -to [all_registers -data_pins] -delay_type min -max_paths 10 > reg_hold.rpt
    set f [open SLACK.json w]
    set maxp [get_timing_paths -delay_type max -max_paths 1]
    set minp [get_timing_paths -delay_type min -max_paths 1]
    if {[sizeof_collection $maxp]!=1 || [sizeof_collection $minp]!=1} {error "timing paths missing"}
    puts $f "{\"setup_ns\":[get_attribute $maxp slack],\"hold_ns\":[get_attribute $minp slack]}";close $f
    read_vcd -strip_path tb_eda/dut -time [list $::env(AC_START_NS) $::env(AC_END_NS)] $::env(AC_VCD)
    report_switching_activity > activity.rpt
    report_switching_activity -list_not_annotated > activity_unannotated.rpt
    check_power > check_power.rpt
    update_power
    report_power -verbose > power.rpt
    report_power -hierarchy > power_hierarchy.rpt
    set f [open POWER_COMPLETE.txt w];puts $f "calculated; review activity and timing separately";close $f
} message]} {
    set f [open failure.txt w];puts $f "$message\n$::errorInfo";close $f
    puts stderr "AC_PT_FAILED: $message";exit 1
}
exit 0
