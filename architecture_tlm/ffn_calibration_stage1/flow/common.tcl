# Issue193. PVT parser reused from the audited 20261024_v4 package.
source [file join $::env(FLOW_PACKAGE) flow library_conditions.tcl]
proc save_text {path text} {
    set f [open $path w]; fconfigure $f -translation lf; puts $f $text; close $f
}
proc capture {path body} {
    set output ""; set value ""
    set rc [catch {redirect -variable output {set value [uplevel 1 $body]}} msg]
    save_text $path "$output\nRETURN: $value\nMESSAGE: $msg"
    if {$rc || [regexp -nocase {(^|\n)[ \t]*(Error:|Fatal:|Error-)} "$output\n$msg"]} {
        error "Failed $path: $msg"
    }
    return $output
}
proc library_setup {} {
    foreach name {STD_DB STD_REF_CELL FLOW_CORNER FLOW_TOP FLOW_PACKAGE} {
        if {![info exists ::env($name)] || $::env($name) eq ""} {error "Missing $name"}
    }
    if {![file isfile $::env(STD_DB)]} {error "STD_DB is not one regular library file"}
    if {$::env(FLOW_TOOL) eq "dc"} {
        set_app_var target_library [list $::env(STD_DB)]
        set_app_var link_library [concat [list *] [list $::env(STD_DB)]]
    } else {
        set_app_var link_path [concat [list *] [list $::env(STD_DB)]]
    }
    read_db $::env(STD_DB)
    set lib [lib_for_ref $::env(STD_REF_CELL)]
    set text [capture library_private.rpt [list report_lib $lib]]
    set oc [oc_from_report $text $lib library_private.rpt]
    switch -- $::env(FLOW_CORNER) {
        ss {set v 1.08; set temp 125; set pattern {ss|slow}}
        tt {set v 1.20; set temp 25; set pattern {tt|typ}}
        default {error "Unknown corner"}
    }
    if {abs([dict get $oc voltage]-$v)>1e-6 || abs([dict get $oc temperature]-$temp)>1e-6 || ![regexp -nocase $pattern [dict get $oc name]]} {
        error "Wrong/unknown PVT: $oc"
    }
    # Constraints below are expressed in ns/pF. Reject unknown units rather
    # than silently applying nanoseconds to a library using another unit.
    if {![regexp -nocase {Time Unit\s*:\s*([0-9.eE+-]+)\s*ns\M} $text -> time_factor] || $time_factor != 1} {error "Require verified 1 ns library unit"}
    if {![regexp -nocase {(?:Capacitance|Capacitive Load) Unit\s*:\s*([0-9.eE+-]+)\s*pF\M} $text -> cap_factor] || $cap_factor != 1} {error "Require verified 1 pF library unit"}
    set ::FLOW_LIBRARY $lib
    set ::FLOW_CONDITION [dict get $oc name]
    # Apply after elaboration/link as some tool releases require a design.
    save_text pvt.txt "corner=$::env(FLOW_CORNER)\nvoltage_V=$v\ntemperature_C=$temp\nlibrary=$lib\ncondition=$::FLOW_CONDITION\ntime_unit=ns\ncapacitance_unit=pF"
}
proc constraints {} {
    if {[sizeof_collection [get_ports -quiet clk]] != 1 || [sizeof_collection [get_ports -quiet rst_n]] != 1} {error "Expected fixed clk/rst_n top interface"}
    set_operating_conditions -library $::FLOW_LIBRARY $::FLOW_CONDITION
    create_clock -name clk -period 10 [get_ports clk]
    set_clock_transition 0.1 [get_clocks clk]
    set_clock_uncertainty -setup 2 [get_clocks clk]
    set_clock_uncertainty -hold 0.1 [get_clocks clk]
    set inputs [remove_from_collection [all_inputs] [get_ports clk]]
    set_input_transition 0.1 $inputs
    set_input_delay -max 1.0 -clock clk $inputs
    set_input_delay -min 0.2 -clock clk $inputs
    set_output_delay -max 1.0 -clock clk [all_outputs]
    set_output_delay -min 0.2 -clock clk [all_outputs]
    set_load 0.02 [all_outputs]
    # rst_n is SYNCHRONOUS. It stays a timed input; no reset false path,
    # case-analysis, multicycle exception or hold waiver is introduced.
}
proc inventory {} {
    set leaves [get_cells -hierarchical * -filter {is_hierarchical == false}]
    set cells 0; set area 0.0; set unknown 0
    foreach_in_collection c $leaves {
        set ref [get_attribute $c ref_name]
        if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {continue}
        set lc [get_lib_cells -quiet "$::FLOW_LIBRARY/$ref"]
        if {[sizeof_collection $lc] != 1} {incr unknown; continue}
        set value [get_attribute $lc area]
        if {![string is double -strict $value] || $value <= 0} {error "Invalid mapped area for $ref"}
        set area [expr {$area + $value}]; incr cells
    }
    save_text mapping_audit.txt "mapped_leaf_cells=$cells\nunmapped_leaf_cells=$unknown\nnonlibrary_leaf_cells=$unknown\narea_library_units=$area"
    if {$cells == 0 || $unknown != 0} {error "Unmapped/non-library/empty design: $unknown unknown, $cells mapped"}
    return $area
}
proc timing_reports {tool} {
    capture setup.rpt {report_timing -delay_type max -max_paths 20 -nets -transition_time -capacitance}
    capture hold.rpt {report_timing -delay_type min -max_paths 20}
    capture constraints.rpt {report_constraint -all_violators}
    if {$tool eq "dc"} {capture check_timing.rpt {check_timing}} else {capture check_timing.rpt {check_timing -verbose}}
    foreach delay {max min} name {setup hold} {
        set paths [get_timing_paths -delay_type $delay -max_paths 1]
        if {[sizeof_collection $paths] != 1} {error "Missing $name path"}
        set value [get_attribute $paths slack]
        if {![string is double -strict $value]} {error "Unknown $name slack"}
        save_text ${name}_slack_ns.txt $value
    }
}
