proc putfile {p s} {set f [open $p w];puts $f $s;close $f}
proc constraints {} {
 create_clock -name core -period 10 [get_ports clk]
 set_clock_transition 0.1 [get_clocks core]
 set_clock_uncertainty -setup 0.5 [get_clocks core]
 set_clock_uncertainty -hold 0.05 [get_clocks core]
 set ins [remove_from_collection [all_inputs] [get_ports clk]]
 set_input_transition 0.1 $ins
 set_input_delay -max 1.0 -clock core $ins
 set_input_delay -min 0.2 -clock core $ins
 set_output_delay -max 1.0 -clock core [all_outputs]
 set_output_delay -min 0.02 -clock core [all_outputs]
 # Raw register outputs model one local consumer; integrated comparators use
 # actual mapped internal fanout and 20 fF only at 128 bit outputs.
 set_load $::env(RB_LOAD) [all_outputs]
}
proc inventory {} {
 set total 0.;set f [open inventory.tsv w];puts $f "instance\tref\tarea_um2\tgroup"
 foreach_in_collection c [get_cells -hierarchical * -filter {is_hierarchical == false}] {
  set ref [get_attribute $c ref_name]
  if {$ref eq "**logic_0**" || $ref eq "**logic_1**"} {continue}
  set lc [get_lib_cells -quiet */$ref];if {[sizeof_collection $lc]!=1} {error "unknown cell $ref"}
  set a [get_attribute $lc area];set group logic
  if {[regexp {DFF} $ref]} {set group register}
  if {$ref eq "CKGTX8_9TSVT"} {set group icg}
  puts $f "[get_object_name $c]\t$ref\t$a\t$group";set total [expr {$total+$a}]
 };close $f;putfile area_um2.txt $total
}
proc timing {} {
 update_timing
 report_timing -delay_type max -max_paths 10 -nets -transition_time -capacitance > setup.rpt
 report_timing -delay_type min -max_paths 10 > hold.rpt
 report_constraint -all_violators > constraints.rpt
 check_timing > check_timing.rpt
 report_disable_timing > disabled.rpt
 report_exceptions > exceptions.rpt
 foreach d {max min} n {setup hold} {
  set p [get_timing_paths -delay_type $d -max_paths 1]
  if {[sizeof_collection $p]!=1} {error "missing timing $n"}
  putfile ${n}_ns.txt [get_attribute $p slack]
 }
 set gates [get_cells -quiet -hierarchical * -filter {ref_name == CKGTX8_9TSVT}]
 if {[sizeof_collection $gates]>0} {
  set ends [get_pins -quiet __none__]
  foreach_in_collection g $gates {set ends [add_to_collection $ends [get_pins [get_object_name $g]/E]]}
  report_timing -to $ends -delay_type max -max_paths 32 > gate_setup.rpt
  report_timing -to $ends -delay_type min -max_paths 32 > gate_hold.rpt
  foreach d {max min} n {gate_setup gate_hold} {
   set p [get_timing_paths -to $ends -delay_type $d -max_paths 1]
   putfile ${n}_ns.txt [expr {[sizeof_collection $p] ? [get_attribute $p slack] : "NA"}]
  }
 }
}
