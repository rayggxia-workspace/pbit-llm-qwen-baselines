source [file join $::env(PPA_SOURCE) library_conditions.tcl]
proc save_text {path text} {set f [open $path w];puts $f $text;close $f}
proc capture {path body} {
    set output "";set value ""
    set rc [catch {redirect -variable output {set value [uplevel 1 $body]}} msg]
    save_text $path "$output\nRETURN: $value\nMESSAGE: $msg"
    if {$rc || [regexp -nocase {(^|\n)[ \t]*(Error:|Fatal:|Error-)} "$output\n$msg"]} {
        puts stderr "COMMAND_FAILED $path\n$output\n$msg"
        error "Failed $path: $msg"
    }
    return $output
}
proc conditions {} {
    set lib [lib_for_ref INVX1_9TSVT]
    set text [capture library.rpt [list report_lib $lib]]
    set oc [oc_from_report $text $lib library.rpt]
    if {$::env(PPA_CORNER) eq "ss"} {set v 1.08;set t 125;set pattern {ss|slow}} else {set v 1.2;set t 25;set pattern {tt|typ}}
    if {abs([dict get $oc voltage]-$v)>1e-6 || abs([dict get $oc temperature]-$t)>1e-6 || ![regexp -nocase $pattern [dict get $oc name]]} {
        error "Wrong PVT: $oc; expected $::env(PPA_CORNER) $v V $t C"
    }
    set_operating_conditions -library $lib [dict get $oc name]
    save_text pvt.txt "corner=$::env(PPA_CORNER)\nvoltage_V=$v\ntemperature_C=$t\nlibrary=$lib\ncondition=[dict get $oc name]"
}
proc constraints {} {
    create_clock -name clk -period 10 [get_ports clk]
    set_clock_transition 0.1 [get_clocks clk]
    set_clock_uncertainty -setup 2 [get_clocks clk]
    set_clock_uncertainty -hold 0.1 [get_clocks clk]
    set inputs [remove_from_collection [all_inputs] [get_ports clk]]
    set_input_transition 0.1 $inputs
    set_input_delay -max 1 -clock clk $inputs
    set_input_delay -min 0.2 -clock clk $inputs
    set_output_delay -max 1 -clock clk [all_outputs]
    set_output_delay -min 0.2 -clock clk [all_outputs]
    set_false_path -from [get_ports rst_n]
    set_load 0.02 [all_outputs]
}
proc inventory {} {
    set leaves [get_cells -hierarchical * -filter {is_hierarchical == false}]
    set f [open inventory.tsv w];puts $f "name\tref\tarea\tcategory"
    foreach_in_collection c $leaves {
        set name [get_object_name $c];set ref [get_attribute $c ref_name]
        if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {set leaves [remove_from_collection $leaves $c];continue}
        if {![string match *_9TSVT $ref]} {error "Unmapped/unknown cell $name $ref"}
        set lc [get_lib_cells -quiet "*/$ref"]
        if {[sizeof_collection $lc]!=1} {error "Missing/ambiguous cell $ref"}
        set area [get_attribute $lc area]
        if {![string is double -strict $area] || $area<=0} {error "Invalid area $name"}
        set group core_logic
        if {[get_attribute $lc is_sequential]} {
            set group core_registers
            if {![string match */* $name]} {
                set group boundary_control_registers
                if {[regexp {^(ar|br|u0|u1|exp_r|mean_r)_reg} $name]} {set group boundary_input_registers}
                if {[regexp {^result_reg} $name]} {set group boundary_output_registers}
            }
        } elseif {![string match */* $name]} {set group boundary_logic}
        puts $f "$name\t$ref\t$area\t$group"
    }
    close $f
    if {[sizeof_collection $leaves]==0} {error "Empty circuit"}
    return $leaves
}
proc timing_reports {tool} {
    capture setup.rpt {report_timing -delay_type max -max_paths 20 -nets -transition_time -capacitance}
    capture hold.rpt {report_timing -delay_type min -max_paths 20}
    capture constraints.rpt {report_constraint -all_violators}
    if {$tool eq "dc"} {capture check_timing.rpt {check_timing}} else {capture check_timing.rpt {check_timing -verbose}}
    foreach delay {max min} name {setup hold} {
        set paths [get_timing_paths -delay_type $delay -max_paths 1]
        if {[sizeof_collection $paths]!=1} {error "Missing $name path"}
        save_text ${name}_slack_ns.txt [get_attribute $paths slack]
    }
}
