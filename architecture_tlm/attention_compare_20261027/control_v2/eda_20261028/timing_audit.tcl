# Post-run diagnostic only: same mapped netlist and unchanged constraints.
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
    report_timing -delay_type min -max_paths 5 > hold.rpt
    report_timing -delay_type max -max_paths 5 > setup.rpt
    set f [open AUDIT_COMPLETE.txt w];puts $f "diagnostic completed; constraints unchanged";close $f
} message]} {
    set f [open failure.txt w];puts $f "$message\n$::errorInfo";close $f
    puts stderr "AC_AUDIT_FAILED: $message";exit 1
}
exit 0
