source [file join $::env(CV2_FLOW) common.tcl]
proc main {} {
    set_app_var link_create_black_boxes false
    library_setup pt
    capture read.rpt {read_verilog $::env(CV2_NETLIST)}
    if {![link_design $::CV2_TOP]} {error "PT link failed"}
    constraints
    inventory
    capture units.rpt {report_units}
    capture design.rpt {report_design}
    timing_reports pt
    save_text STAGE_COMPLETE "Pre-layout STA completed; no CTS, SDF or SPEF"
}
if {[catch {main} message]} {save_text FAILURE.txt "$message\n$::errorInfo";puts stderr $message;exit 2}
exit 0
