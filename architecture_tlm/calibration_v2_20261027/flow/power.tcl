source [file join $::env(CV2_FLOW) common.tcl]
proc main {} {
    set_app_var power_enable_analysis true
    set_app_var power_analysis_mode averaged
    set_app_var link_create_black_boxes false
    library_setup pt
    capture read.rpt {read_verilog $::env(CV2_NETLIST)}
    if {![link_design $::CV2_TOP]} {error "PT link failed"}
    constraints
    inventory
    capture units.rpt {report_units}
    timing_reports pt
    # PT time unit verified as 1 ns; annotate only this measured window.
    set range [list $::env(CV2_START_NS) $::env(CV2_END_NS)]
    capture activity.rpt {read_vcd -zero_delay -strip_path $::env(CV2_STRIP_PATH) -time $range $::env(CV2_VCD)}
    capture coverage.rpt {report_switching_activity -list_not_annotated}
    capture checks.rpt {check_power -verbose}
    capture update.rpt {update_power}
    capture power.rpt {report_power -verbose}
    capture hierarchy.rpt {report_power -hierarchy}
    set leaves [get_cells -hierarchical * -filter {is_hierarchical == false}]
    capture cells.rpt {report_power -cell_power $leaves}
    set f [open activity_boundary.tsv w];puts $f "name\ttoggle_rate\tstatic_probability"
    set boundary [add_to_collection [all_inputs] [all_outputs]]
    foreach_in_collection c $leaves {set boundary [add_to_collection $boundary [get_pins -of_objects $c]]}
    foreach_in_collection p $boundary {
        set tr NA;set sp NA
        catch {set tr [get_attribute -quiet $p toggle_rate]}
        catch {set sp [get_attribute -quiet $p static_probability]}
        puts $f "[get_object_name $p]\t$tr\t$sp"
    }
    close $f
    save_text POWER_CALCULATED "PROVISIONAL; review coverage/check_power/gating checks; zero-delay gate activity; no CTS/SPEF/external memory/RNG"
}
if {[catch {main} message]} {save_text FAILURE.txt "$message\n$::errorInfo";puts stderr $message;exit 2}
exit 0
