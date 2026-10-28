source [file join $::env(FLOW_PACKAGE) flow common.tcl]
proc main {} {
    library_setup
    define_design_lib WORK -path ./work_library
    set sources [lsort [glob -nocomplain [file join $::env(FLOW_PACKAGE) rtl *.sv]]]
    if {[llength $sources] == 0} {error "No RTL sources"}
    analyze -format sverilog -define {SYNTHESIS} $sources
    elaborate $::env(FLOW_TOP)
    current_design $::env(FLOW_TOP)
    if {![link]} {error "Design link failed"}
    capture check_design.rpt {check_design}
    constraints
    # Portable baseline compile; not a claim of a globally optimum mapping.
    compile -map_effort high
    capture check_design.rpt {check_design}
    inventory
    capture area.rpt {report_area}
    timing_reports dc
    write -format verilog -hierarchy -output mapped.v
    write_sdc mapped.sdc
    # mapped.v/.sdc stay local for optional PT; not included in return archive.
    save_text STAGE_COMPLETE dc
}
if {[catch {main} message]} {
    save_text FLOW_FAILED.txt "$message\n$::errorInfo"
    puts stderr "Error: ISSUE193_DC_FAILED $message"
    exit 2
}
exit 0
