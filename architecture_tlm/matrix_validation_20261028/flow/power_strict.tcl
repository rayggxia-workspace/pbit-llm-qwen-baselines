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
    set leaves [get_cells -hierarchical * -filter {is_hierarchical == false}]
    set boundary [add_to_collection [all_inputs] [all_outputs]]
    set internal [open internal_state_nodes.tsv w];puts $internal "name\tdirection"
    set f [open inventory.tsv w];puts $f "name\tref\tarea\tcategory"
    foreach_in_collection c $leaves {
        set ref [get_attribute $c ref_name]
        if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {continue}
        foreach_in_collection pin [get_pins -of_objects $c] {
            set direction [get_attribute $pin direction]
            if {$direction eq "internal"} {
                puts $internal "[get_object_name $pin]\t$direction"
            } else {set boundary [add_to_collection $boundary $pin]}
        }
        set a [get_attribute [get_lib_cells "$::CV2_LIB/$ref"] area]
        set group combinational_unattributed
        if {[regexp {DFF} $ref]} {set group registers}
        if {$ref eq $::CV2_ICG_CELL} {set group real_icg}
        puts $f "[get_object_name $c]\t$ref\t$a\t$group"
    };close $f;close $internal
    set f [open activity_boundary.txt w]
    foreach_in_collection p $boundary {puts $f [get_object_name $p]};close $f
    if {$::env(CV2_BOUNDARY_ONLY) eq "1"} {save_text BOUNDARY_COMPLETE "All top ports and real library leaf pins";return}
    capture units.rpt {report_units}
    capture timing_update.rpt {update_timing}
    timing_reports pt
    capture activity.rpt {read_vcd -strip_path $::env(CV2_STRIP_PATH) $::env(CV2_VCD)}
    capture coverage.rpt {report_switching_activity -list_not_annotated}
    capture checks.rpt {check_power -verbose}
    capture model_checks.rpt [list check_power -verbose -override_defaults {missing_table missing_function} $leaves]
    capture update.rpt {update_power}
    set f [open output_activity.tsv w];puts $f "name\ttoggle_rate\tstatic_probability"
    foreach_in_collection p $boundary {
        set tr NA;set sp NA
        foreach object [list $p [get_nets -quiet -of_objects $p]] {
            if {[sizeof_collection $object]!=1} {continue}
            if {![catch {set t [get_attribute -quiet $object toggle_rate];set s [get_attribute -quiet $object static_probability]}] && [string is double -strict $t] && [string is double -strict $s]} {set tr $t;set sp $s;break}
        }
        puts $f "[get_object_name $p]\t$tr\t$sp"
    };close $f
    capture power.rpt {report_power -verbose}
    capture hierarchy.rpt {report_power -hierarchy}
    capture cells.rpt [list report_power -cell_power $leaves]
    save_text POWER_CALCULATED "Mapped core including real ICG; no CTS/SDF/SPEF"
}
if {[catch {main} msg]} {save_text FAILURE.txt "$msg\n$::errorInfo";puts stderr $msg;exit 2}
exit 0
