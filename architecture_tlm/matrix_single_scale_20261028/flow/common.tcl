source [file join $::env(CV2_FLOW) library_conditions.tcl]
source $::env(CV2_CONFIG)
proc save_text {path text} {set f [open $path w]; fconfigure $f -translation lf; puts $f $text; close $f}
proc capture {path body} {
    set output "";set value ""
    set rc [catch {redirect -variable output {set value [uplevel 1 $body]}} message]
    save_text $path "$output\nRETURN: $value\nMESSAGE: $message"
    if {$rc || [regexp -nocase {(^|\n)[ \t]*(Error:|Fatal:|Error-)} "$output\n$message"]} {error "Failed $path: $message"}
    return $output
}
proc library_setup {tool} {
    if {$::CV2_GATE_MODE != 0 && $::CV2_GATE_MODE != 2} {error "Behavioral gate is not a technology calibration"}
    if {$tool eq "dc"} {
        set_app_var target_library [list $::CV2_LIBRARY_DB]
        set_app_var link_library [list * $::CV2_LIBRARY_DB]
        set_app_var search_path [concat $::CV2_INCLUDE $::search_path]
    } else {set_app_var link_path [list * $::CV2_LIBRARY_DB]}
    read_db $::CV2_LIBRARY_DB
    set lib [lib_for_ref $::CV2_REF_CELL]
    set report [capture library_private.rpt [list report_lib $lib]]
    set oc [oc_from_report $report $lib library_private.rpt]
    if {![regexp -nocase $::CV2_CORNER_PATTERN [dict get $oc name]]} {error "Operating condition name does not match corner"}
    if {abs([dict get $oc voltage]-$::CV2_VOLTAGE)>1e-6 || abs([dict get $oc temperature]-$::CV2_TEMPERATURE)>1e-6} {error "Library PVT mismatch: $oc"}
    if {![regexp -nocase {Time Unit\s*:\s*([0-9.eE+-]+)\s*ns\M} $report -> unit] || $unit!=1} {error "Require verified ns time unit"}
    if {![regexp -nocase {(?:Capacitance|Capacitive Load) Unit\s*:\s*([0-9.eE+-]+)\s*pF\M} $report -> unit] || $unit!=1} {error "Require verified pF load unit"}
    set ::CV2_LIB $lib;set ::CV2_OC [dict get $oc name]
    save_text pvt.txt "corner_label=$::CV2_CORNER\nvoltage_V=$::CV2_VOLTAGE\ntemperature_C=$::CV2_TEMPERATURE\nlibrary=$lib\ncondition=$::CV2_OC\nperiod_ns=$::CV2_PERIOD_NS\nsetup_uncertainty_ns=$::CV2_UNCERTAINTY_NS"
}
proc constraints {} {
    if {[sizeof_collection [get_ports -quiet clk]]!=1 || [sizeof_collection [get_ports -quiet rst_n]]!=1} {error "Expected clk/rst_n interface"}
    set_operating_conditions -library $::CV2_LIB $::CV2_OC
    create_clock -name core -period $::CV2_PERIOD_NS [get_ports clk]
    set_clock_transition $::CV2_CLOCK_TRANSITION_NS [get_clocks core]
    set_clock_uncertainty -setup $::CV2_UNCERTAINTY_NS [get_clocks core]
    set_clock_uncertainty -hold $::CV2_HOLD_UNCERTAINTY_NS [get_clocks core]
    set ins [remove_from_collection [all_inputs] [get_ports clk]]
    set_input_transition $::CV2_INPUT_TRANSITION_NS $ins
    set_input_delay -max $::CV2_INPUT_DELAY_MAX_NS -clock core $ins
    set_input_delay -min $::CV2_INPUT_DELAY_MIN_NS -clock core $ins
    set_output_delay -max $::CV2_OUTPUT_DELAY_MAX_NS -clock core [all_outputs]
    set_output_delay -min $::CV2_OUTPUT_DELAY_MIN_NS -clock core [all_outputs]
    set_load $::CV2_LOAD_PF [all_outputs]
    # Synchronous reset is timed. No false path, multicycle or hold waiver.
}
proc inventory {} {
    set area 0.0;set count 0;set icgs 0
    set f [open inventory.tsv w];puts $f "instance\tref\tarea_library_units"
    foreach_in_collection c [get_cells -hierarchical * -filter {is_hierarchical == false}] {
        set ref [get_attribute $c ref_name]
        if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {continue}
        set lc [get_lib_cells -quiet "$::CV2_LIB/$ref"]
        if {[sizeof_collection $lc]!=1} {error "Unmapped/ambiguous leaf $ref"}
        set a [get_attribute $lc area]
        if {![string is double -strict $a] || $a<=0} {error "Unknown area $ref"}
        puts $f "[get_object_name $c]\t$ref\t$a"
        set area [expr {$area+$a}];incr count
        if {$ref eq $::CV2_ICG_CELL} {incr icgs}
    }
    close $f
    if {$count==0} {error "Empty mapped design"}
    if {$::CV2_GATE_MODE==2 && $icgs==0} {error "MODE2 has no mapped ICG cell"}
    save_text area_library_units.txt $area
    save_text icg_instances.txt $icgs
}
proc timing_reports {tool} {
    capture setup.rpt {report_timing -delay_type max -max_paths 20 -nets -transition_time -capacitance}
    capture hold.rpt {report_timing -delay_type min -max_paths 20}
    capture constraints.rpt {report_constraint -all_violators}
    capture check_timing.rpt {check_timing}
    foreach d {max min} name {setup hold} {
        set p [get_timing_paths -delay_type $d -max_paths 1]
        if {[sizeof_collection $p]!=1} {error "Missing $name timing path"}
        set v [get_attribute $p slack]
        if {![string is double -strict $v]} {error "Unknown timing slack"}
        save_text [format "%s_slack_ns.txt" $name] $v
    }
    if {$tool eq "pt" && $::CV2_GATE_MODE==2} {
        set gates [get_cells -hierarchical * -filter "ref_name == $::CV2_ICG_CELL"]
        set endpoints [get_pins -quiet __CV2_NO_PIN__]
        foreach_in_collection cell $gates {
            foreach pin [list $::CV2_ICG_EN_PIN $::CV2_ICG_TE_PIN] {
                set p [get_pins -quiet "[get_object_name $cell]/$pin"]
                if {[sizeof_collection $p]!=1} {error "Missing ICG enable/test pin: $pin"}
                set endpoints [add_to_collection $endpoints $p]
            }
        }
        # Liberty must identify genuine gating checks at these ICG endpoints.
        # No invented setup/hold numbers or disabled gate timing checks.
        capture gate_setup.rpt {report_timing -to $endpoints -delay_type max -max_paths 20 -slack_lesser_than 1e9}
        capture gate_hold.rpt {report_timing -to $endpoints -delay_type min -max_paths 20 -slack_lesser_than 1e9}
        foreach delay {max min} label {gate_setup gate_hold} {
            set paths [get_timing_paths -to $endpoints -delay_type $delay -max_paths 1]
            if {[sizeof_collection $paths]==1} {save_text [format "%s_slack_ns.txt" $label] [get_attribute $paths slack]
            } else {save_text [format "%s_slack_ns.txt" $label] NA}
        }
    }
}
