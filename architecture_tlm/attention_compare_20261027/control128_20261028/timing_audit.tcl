# Same netlist and SDC, separate internal and external timing without exceptions.
if {[catch {
    set_host_options -max_cores 1
    set_app_var link_create_black_boxes false
    set_app_var link_path [list * $::env(AC_TARGET_DB)]
    read_verilog $::env(AC_NETLIST)
    if {![link_design $::env(AC_TOP)]} {error "link failed"}
    read_sdc $::env(AC_SDC)
    update_timing
    report_disable_timing > disable_timing.rpt
    report_analysis_coverage -status_details untested > untested.rpt
    report_exceptions > exceptions.rpt
    check_timing -verbose > check_timing.rpt
    report_timing -delay_type min -slack_lesser_than 100 -max_paths 10 > hold.rpt
    report_timing -delay_type max -slack_lesser_than 100 -max_paths 10 > setup.rpt
    set regs_from [all_registers -clock_pins]
    set regs_to [all_registers -data_pins]
    set a [get_timing_paths -from $regs_from -to $regs_to -delay_type max -max_paths 1]
    set b [get_timing_paths -from $regs_from -to $regs_to -delay_type min -max_paths 1]
    if {[sizeof_collection $a]!=1 || [sizeof_collection $b]!=1} {error "internal paths missing"}
    set f [open INTERNAL_SLACK.json w]
    puts $f "{\"setup_ns\":[get_attribute $a slack],\"hold_ns\":[get_attribute $b slack]}"
    close $f
    report_timing -from $regs_from -to $regs_to -delay_type max -slack_lesser_than 100 -max_paths 5 > reg_setup.rpt
    report_timing -from $regs_from -to $regs_to -delay_type min -slack_lesser_than 100 -max_paths 5 > reg_hold.rpt
    set f [open AUDIT_COMPLETE.txt w];puts $f "diagnostic completed; constraints unchanged";close $f
} message]} {
    set f [open failure.txt w];puts $f "$message\n$::errorInfo";close $f
    puts stderr "AC_AUDIT_FAILED: $message";exit 1
}
exit 0
