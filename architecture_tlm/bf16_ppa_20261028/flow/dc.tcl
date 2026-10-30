source [file join $::env(CV2_FLOW) common.tcl]
proc main {} {
    library_setup dc
    define_design_lib WORK -path ./work
    analyze -format sverilog -define $::CV2_DEFINES $::CV2_RTL
    elaborate $::CV2_TOP
    current_design $::CV2_TOP
    if {![link]} {error "DC link failed"}
    constraints
    capture check_design_before.rpt {check_design}
    if {$::CV2_GATE_MODE==2} {
        set gates [get_cells -hierarchical * -filter "ref_name == $::CV2_ICG_CELL"]
        if {[sizeof_collection $gates]==0} {error "Expected explicit ICG before compile"}
        set_dont_touch $gates true
    }
    # Explicit RTL ICG, not inferred clock gating. Preserve hierarchy.
    compile_ultra -retime
    capture check_design.rpt {check_design}
    capture area.rpt {report_area -hierarchy}
    inventory
    timing_reports dc
    write -format verilog -hierarchy -output mapped.v
    write_sdc mapped.sdc
    write -format ddc -hierarchy -output mapped.ddc
    save_text STAGE_COMPLETE "DC completed; check reported slack and mapping"
}
if {[catch {main} message]} {save_text FAILURE.txt "$message\n$::errorInfo";puts stderr $message;exit 2}
exit 0
