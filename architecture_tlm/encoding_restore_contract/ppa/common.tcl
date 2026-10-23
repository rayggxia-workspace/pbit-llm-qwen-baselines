# Fail closed on command errors. No library contents are copied by this flow.
proc save {name value} {set f [open $name w]; puts $f $value; close $f}
proc capture {name script} {
    set output ""; set value ""
    set rc [catch {redirect -variable output {set value [uplevel 1 $script]}} message]
    save $name "$output\nRETURN: $value\nMESSAGE: $message"
    if {$rc || [regexp -nocase {(^|\n)[ \t]*(Error:|Fatal:|Error-)} "$output\n$message"]} {
        error "Command/report failed: $name ($message)"
    }
    return $value
}
proc require_env {names} {
    foreach name $names {if {![info exists ::env($name)] || $::env($name) eq ""} {error "Missing $name"}}
}
proc library_condition {} {
    if {[sizeof_collection [get_libs -quiet $::env(STD_LIB_NAME)]] != 1} {error "Missing/ambiguous exact library name"}
    capture condition.log {set_operating_conditions -library $::env(STD_LIB_NAME) $::env(STD_OC_NAME)}
    capture library.rpt {report_lib $::env(STD_LIB_NAME)}
    capture units.rpt {report_units}
    capture design.rpt {report_design}
}
proc constraints {} {
    create_clock -name core_clk -period 10.0 [get_ports clk]
    set_clock_transition 0.1 [get_clocks core_clk]
    set_clock_uncertainty -setup 2.0 [get_clocks core_clk]
    set_clock_uncertainty -hold 0.1 [get_clocks core_clk]
    set inputs [remove_from_collection [all_inputs] [get_ports clk]]
    set_input_transition 0.1 $inputs
    set_input_delay -max 1.0 -clock core_clk $inputs
    set_input_delay -min 0.2 -clock core_clk $inputs
    set_output_delay -max 1.0 -clock core_clk [all_outputs]
    set_output_delay -min 0.2 -clock core_clk [all_outputs]
    set_load 0.02 [all_outputs]
    # Synchronous reset, ready/valid, tags and occupancy are constrained ports.
    # No false paths, free CDC, input register removal or unconstrained endpoints.
}
proc inventory {} {
    set area 0.0; set count 0
    set f [open inventory.tsv w]; puts $f "cell\tref\tarea_library_units"
    foreach_in_collection cell [get_cells -hierarchical * -filter {is_hierarchical == false}] {
        set ref [get_attribute $cell ref_name]
        if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {continue}
        set libcell [get_lib_cells -quiet "$::env(STD_LIB_NAME)/$ref"]
        if {[sizeof_collection $libcell] != 1} {error "Unmapped or ambiguous cell $ref"}
        set a [get_attribute $libcell area]
        if {![string is double -strict $a] || $a <= 0} {error "Invalid mapped area"}
        set area [expr {$area+$a}]; incr count
        puts $f "[get_object_name $cell]\t$ref\t$a"
    }
    close $f
    if {$count == 0} {error "Empty mapped design"}
    save area.txt $area
}
proc timing_reports {} {
    capture clock.rpt {report_clock}
    capture setup.rpt {report_timing -delay_type max -max_paths 20 -nets -transition_time -capacitance}
    capture hold.rpt {report_timing -delay_type min -max_paths 20}
    capture constraints.rpt {report_constraint -all_violators}
    capture check_timing.rpt {check_timing -verbose}
    foreach delay {max min} name {setup hold} {
        set paths [get_timing_paths -delay_type $delay -max_paths 1]
        if {[sizeof_collection $paths] != 1} {error "Missing $name path"}
        save ${name}_slack.txt [get_attribute $paths slack]
    }
    set clocks [get_clocks core_clk]
    if {[sizeof_collection $clocks] != 1 || abs([get_attribute $clocks period]-10.0)>1e-9} {
        error "Missing or wrong 10ns clock"
    }
}
