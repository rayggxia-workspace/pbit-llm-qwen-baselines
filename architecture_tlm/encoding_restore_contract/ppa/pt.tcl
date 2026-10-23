source [file join $env(ER_FLOW) common.tcl]
proc main {} {
    require_env {STD_DB STD_LIB_NAME STD_OC_NAME ER_TOP ER_NETLIST ER_SDC ER_VCD ER_START_NS ER_END_NS}
    set_app_var power_enable_analysis true
    set_app_var power_analysis_mode averaged
    set_app_var link_create_black_boxes false
    set_app_var link_path [concat [list "*"] [list $::env(STD_DB)]]
    read_verilog $::env(ER_NETLIST)
    current_design $::env(ER_TOP)
    if {![capture link.log {link_design $::env(ER_TOP)}]} {error "PT link returned false"}
    read_sdc $::env(ER_SDC)
    library_condition
    update_timing
    inventory
    timing_reports
    if {$::env(ER_START_NS)<0 || $::env(ER_END_NS)<=$::env(ER_START_NS)} {error "Invalid active window"}
    capture vcd.log {read_vcd -strip_path tb_ready_valid/dut -time [list $::env(ER_START_NS) $::env(ER_END_NS)] $::env(ER_VCD)}
    capture check_power.rpt {check_power -verbose -override_defaults {missing_table missing_function}}
    capture update_power.log {update_power}
    capture power.rpt {report_power -hierarchy}
    capture activity.rpt {report_switching_activity -list_not_annotated}
    capture cells.rpt {report_power -cell_power}
    save DONE "PT power calculated from checked gate VCD. Review timing/coverage/warnings. No SDF/SPEF/CTS."
}
if {[catch {main} error_text]} {save FAILURE.txt $error_text; puts stderr $error_text; exit 1}
exit 0
