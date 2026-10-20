source [file join $::env(EP_SOURCE) ppa library_conditions.tcl]
proc save_text {path text} {set f [open $path w];puts $f $text;close $f}
proc capture {path body} {
    set output "";set value ""
    set rc [catch {redirect -variable output {set value [uplevel 1 $body]}} msg]
    save_text $path "$output\nRETURN: $value\nMESSAGE: $msg"
    if {$rc || [regexp -nocase {(^|\n)[ \t]*(Error:|Fatal:|Error-)} "$output\n$msg"]} {error "Failed $path: $msg"}
    return $output
}
proc conditions {} {
    set lib [lib_for_ref INVX1_9TSVT]
    set report [capture library.rpt [list report_lib $lib]]
    set oc [oc_from_report $report $lib library.rpt]
    if {$::env(PVT) eq "TT"} {set v 1.2;set t 25;set pattern {tt|typical}} else {set v 1.08;set t 125;set pattern {ss|slow}}
    if {abs([dict get $oc voltage]-$v)>1e-6 || abs([dict get $oc temperature]-$t)>1e-6 || ![regexp -nocase $pattern [dict get $oc name]]} {error "PVT mismatch: $oc"}
    set_operating_conditions -library $lib [dict get $oc name]
    save_text pvt.txt "corner=$::env(PVT)\nvoltage_V=$v\ntemperature_C=$t\nlibrary=$lib\ncondition=[dict get $oc name]"
}
proc constraints {} {
    create_clock -name clk -period 10 [get_ports clk]
    set_clock_transition 0.1 [get_clocks clk]
    set_clock_uncertainty -setup 2.0 [get_clocks clk]
    set_clock_uncertainty -hold 0.1 [get_clocks clk]
    set inputs [remove_from_collection [all_inputs] [get_ports clk]]
    set_input_transition 0.1 $inputs
    set_input_delay -max 1.0 -clock clk $inputs
    set_input_delay -min 0.2 -clock clk $inputs
    set_output_delay -max 1.0 -clock clk [all_outputs]
    set_output_delay -min 0.2 -clock clk [all_outputs]
    set_load 0.02 [all_outputs]
}
proc inventory {} {
    set leaves [get_cells -hierarchical * -filter {is_hierarchical == false}]
    set f [open inventory.tsv w];puts $f "name\tref\tarea\tcategory"
    foreach_in_collection c $leaves {
        set name [get_object_name $c];set ref [get_attribute $c ref_name]
        if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {set leaves [remove_from_collection $leaves $c];continue}
        if {![string match *_9TSVT $ref]} {error "Unmapped or unknown leaf $name $ref"}
        set lc [get_lib_cells -quiet "*/$ref"]
        if {[sizeof_collection $lc]!=1} {error "Ambiguous library cell $ref"}
        set area [get_attribute $lc area]
        if {![string is double -strict $area] || $area<=0} {error "Missing cell area $name"}
        set category combinational_unattributed
        if {[get_attribute $lc is_sequential]} {
            set category other_registers
            foreach {pattern group} {^(g_q|u_q)_reg input_registers ^(gu_q|sigma_q)_reg mul1_sigma_registers ^product_q_reg mul2_registers ^(y_out|saturated|inexact)_reg output_registers ^(v0|v1|v2|out_valid)_reg valid_registers} {
                if {[regexp $pattern $name]} {set category $group;break}
            }
        }
        if {[string match CKGT* $ref]} {set category clock_gate}
        puts $f "$name\t$ref\t$area\t$category"
    }
    close $f
    if {[sizeof_collection $leaves]==0} {error "Empty mapped circuit"}
    return $leaves
}
proc timing_reports {} {
    capture setup.rpt {report_timing -delay_type max -max_paths 20 -nets -transition_time -capacitance}
    capture hold.rpt {report_timing -delay_type min -max_paths 20}
    capture constraints.rpt {report_constraint -all_violators}
    capture check_timing.rpt {check_timing -verbose}
    foreach delay {max min} name {setup hold} {
        set paths [get_timing_paths -delay_type $delay -max_paths 1]
        if {[sizeof_collection $paths]!=1} {error "Missing $name path"}
        save_text ${name}_slack_ns.txt [get_attribute $paths slack]
    }
}
