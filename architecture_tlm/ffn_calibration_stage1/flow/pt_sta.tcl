# Optional STA-only cross-check: no read_vcd, update_power or report_power.
source [file join $::env(FLOW_PACKAGE) flow common.tcl]
proc main {} {
    library_setup
    read_verilog [file join $::env(FLOW_DC_DIR) mapped.v]
    if {![link_design $::env(FLOW_TOP)]} {error "PT link failed"}
    constraints
    capture check_design.rpt {report_design}
    set area [inventory]
    # PT has no portable DC report_area command. Sum verified library cells;
    # the driver records this distinction, and compares with the DC design.
    save_text area.rpt "PT mapped library-cell sum\nTotal cell area: $area"
    timing_reports pt
    save_text STAGE_COMPLETE pt
}
if {[catch {main} message]} {
    save_text FLOW_FAILED.txt "$message\n$::errorInfo"
    puts stderr "Error: ISSUE193_PT_STA_FAILED $message"
    exit 2
}
exit 0
