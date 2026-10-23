source [file join $::env(PPA_SOURCE) common.tcl]
source [file join $::env(PPA_SOURCE) activity_check.tcl]
proc main {} {
    set_app_var power_enable_analysis true
    set_app_var power_analysis_mode averaged
    set_app_var link_create_black_boxes false
    set_app_var link_path [list * $::env(STD_DB)]
    capture read.rpt {read_verilog $::env(NET_DIR)/mapped.v}
    capture link.rpt {if {![link_design sc_counter_tile_mapped]} {error "PT link failed"}}
    conditions
    capture sdc.rpt {read_sdc $::env(NET_DIR)/mapped.sdc}
    set leaves [inventory]
    capture units.rpt {report_units}
    capture timing_update.rpt {update_timing}
    timing_reports pt
    set activity [capture activity.rpt {read_vcd -strip_path tb_counter/dut $::env(ACTIVITY_VCD)}]
    if {[regexp {PWR-981} $activity]} {error "Partial VCD mapping persists; inspect scalar waveform"}
    capture coverage.rpt {report_switching_activity -list_not_annotated}
    capture checks.rpt {check_power -verbose -significant_digits 9}
    capture ranges.rpt [list check_power -verbose -significant_digits 9 -override_defaults {out_of_table_range} $leaves]
    capture model_checks.rpt [list check_power -verbose -override_defaults {missing_table missing_function} $leaves]
    capture update.rpt {update_power}
    write_output_activity
    capture power.rpt {report_power -verbose}
    capture hierarchy.rpt {report_power -hierarchy}
    capture cells.rpt [list report_power -cell_power $leaves]
    save_text POWER_CALCULATED "Zero-delay gate VCD, no SDF/SPEF/CTS. Timing and coverage are separate checks."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
