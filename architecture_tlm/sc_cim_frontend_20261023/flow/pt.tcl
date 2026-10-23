source [file join $::env(PPA_SOURCE) common.tcl]
source [file join $::env(PPA_SOURCE) activity_check.tcl]
proc main {} {
 set_app_var power_enable_analysis true
 set_app_var power_analysis_mode averaged
 set_app_var link_create_black_boxes false
 set_app_var link_path [list * $::env(STD_DB)]
 capture read.rpt {read_verilog $::env(NET_DIR)/mapped.v}
 capture link.rpt {if {![link_design cim_probe_mapped]} {error "PT link failed"}}
 conditions
 capture sdc.rpt {read_sdc $::env(NET_DIR)/mapped.sdc}
 capture units.rpt {report_units}
 capture timing_update.rpt {update_timing}
 timing_reports pt
 set activity [capture activity.rpt {read_vcd -strip_path $::env(STRIP_PATH) $::env(ACTIVITY_VCD)}]
 if {[regexp {PWR-981} $activity]} {error "Partial VCD mapping; do not accept this power result"}
 capture coverage.rpt {report_switching_activity -list_not_annotated}
 capture checks.rpt {check_power -verbose -significant_digits 9}
 capture update.rpt {update_power}
 write_output_activity
 capture power.rpt {report_power -verbose}
 capture hierarchy.rpt {report_power -hierarchy}
 set leaves [get_cells -hierarchical * -filter {is_hierarchical == false}]
 capture cells.rpt [list report_power -cell_power $leaves]
 save_text POWER_CALCULATED "Zero-delay gate activity; no SDF, SPEF, clock tree, physical SRAM or layout."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
