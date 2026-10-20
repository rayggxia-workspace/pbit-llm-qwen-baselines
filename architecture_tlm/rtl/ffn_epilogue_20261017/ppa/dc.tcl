source [file join $::env(EP_SOURCE) ppa common.tcl]
proc main {} {
    set_app_var target_library [list $::env(STD_DB)]
    set_app_var link_library [list * $::env(STD_DB)]
    set_app_var search_path [concat [list $::env(EP_SOURCE)] $::search_path]
    set_host_options -max_cores $::env(EDA_CORES)
    define_design_lib WORK -path ./WORK
    capture analyze.rpt {analyze -format sverilog $::env(EP_SOURCE)/swiglu_epilogue_q10.sv}
    capture elaborate.rpt {elaborate swiglu_epilogue_q10 -parameters OUT_W=24}
    current_design swiglu_epilogue_q10
    capture link.rpt {if {![link]} {error "DC link failed"}}
    conditions
    constraints
    capture check_design_before.rpt {check_design}
    capture resources.rpt {report_resources}
    capture compile.rpt {compile_ultra -no_autoungroup}
    change_names -rules verilog -hierarchy
    write -format verilog -hierarchy -output mapped.v
    write -format ddc -hierarchy -output mapped.ddc
    write_sdc mapped.sdc
    inventory
    capture area.rpt {report_area -hierarchy}
    capture references.rpt {report_reference -hierarchy}
    capture check_design.rpt {check_design}
    timing_reports
    save_text SYNTH_COMPLETE "Mapped. Inspect setup/hold/constraints; not signoff."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
