source [file join $::env(EP_SOURCE) ppa common.tcl]
proc main {} {
    set_app_var power_enable_analysis true
    set_app_var power_analysis_mode averaged
    set_app_var link_create_black_boxes false
    set_app_var link_path [list * $::env(STD_DB)]
    capture read.rpt {read_verilog $::env(NET_DIR)/mapped.v}
    capture link.rpt {if {![link_design swiglu_epilogue_q10]} {error "PT link failed"}}
    conditions
    capture sdc.rpt {read_sdc $::env(NET_DIR)/mapped.sdc}
    set leaves [inventory]
    capture timing_update.rpt {update_timing}
    timing_reports
    capture activity.rpt {read_vcd -strip_path tb_epilogue_power/dut $::env(SIM_DIR)/active.vcd}
    capture coverage.rpt {report_switching_activity -list_not_annotated}
    set check [capture model_checks.rpt [list check_power -verbose -override_defaults {missing_table missing_function} $leaves]]
    if {[regexp -nocase {Warning:|missing function|has no internal power} $check]} {error "Review missing cell power models"}
    capture checks.rpt {check_power -verbose}
    capture update.rpt {update_power}
    capture power.rpt {report_power -verbose}
    capture hierarchy.rpt {report_power -hierarchy}
    capture cells.rpt [list report_power -cell_power $leaves]
    capture units.rpt {report_units}
    save_text POWER_CALCULATED "Pre-layout zero-delay activity, ideal clock. Not post-route or SDF signoff."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
