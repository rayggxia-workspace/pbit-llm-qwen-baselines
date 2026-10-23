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
 if {$::env(CIM_KIND)<2} {create_clock -name clk -period 10 [get_ports clk];set inputs [remove_from_collection [all_inputs] [get_ports clk]]} else {create_clock -name clk -period 10;set inputs [all_inputs]}
 set_clock_transition 0.1 [get_clocks clk]
 set_clock_uncertainty -setup 2 [get_clocks clk]
 set_clock_uncertainty -hold 0.1 [get_clocks clk]
 set_input_transition $::env(INPUT_SLEW_NS) $inputs
 set_input_delay -max 1 -clock clk $inputs
 set_input_delay -min 0.2 -clock clk $inputs
 set_output_delay -max 1 -clock clk [all_outputs]
 set_output_delay -min 0.2 -clock clk [all_outputs]
 if {$::env(CIM_KIND)<2} {set_false_path -from [get_ports rst_n]}
 set_load $::env(LOAD_PF) [all_outputs]
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
