proc put {p s} {set f [open $p w];puts $f $s;close $f}
if {[catch {
 set_host_options -max_cores 1
 set_app_var power_enable_analysis true
 set_app_var power_analysis_mode averaged
 set_app_var link_create_black_boxes false
 set_app_var link_path [list * $::env(SB_STD_DB) $::env(SB_MACRO_DB)]
 read_verilog $::env(SB_NETLIST)
 if {![link_design banks]} {error "link failed"}
 read_sdc $::env(SB_SDC)
 # Optional explicit interface contract matching the testbench: upstream
 # launches requests on the falling edge, SRAM consumes on the rising edge.
 # Preserve original rising-edge reports separately; do not hide violations.
 if {[info exists ::env(SB_FALLING_INTERFACE)] && $::env(SB_FALLING_INTERFACE) eq "1"} {
  set ins [remove_from_collection [all_inputs] [get_ports clk]]
  remove_input_delay $ins
  set_input_delay -max 1.0 -clock core -clock_fall $ins
  set_input_delay -min 0.0 -clock core -clock_fall $ins
 }
 set_propagated_clock [get_clocks core]
 set_input_transition 0.1 [get_ports clk]
 update_timing
 report_timing -delay_type max -max_paths 8 > setup.rpt
 report_timing -delay_type min -max_paths 8 > hold.rpt
 report_constraint -all_violators > constraints.rpt
 check_timing > check_timing.rpt
 report_disable_timing > disabled.rpt
 report_exceptions > exceptions.rpt
 foreach d {max min} n {setup hold} {
  set p [get_timing_paths -delay_type $d -max_paths 1]
  if {[sizeof_collection $p]!=1} {error "missing path"}
  put ${n}_ns.txt [get_attribute $p slack]
 }
 set count 0;set area 0.;set f [open inventory.tsv w];puts $f "instance\tref\tarea_um2"
 foreach_in_collection c [get_cells -hierarchical * -filter {is_hierarchical == false}] {
  set ref [get_attribute $c ref_name];set lc [get_lib_cells -quiet */$ref]
  if {[sizeof_collection $lc]!=1} {error "unknown cell $ref"}
  set a [get_attribute $lc area];set area [expr {$area+$a}]
  if {$ref eq "SB_D64_W2"} {incr count}
  puts $f "[get_object_name $c]\t$ref\t$a"
 };close $f
 if {$count!=128} {error "expected 128 SRAM macros, found $count"}
 put area_um2.txt $area
 read_vcd -strip_path tb/dut -time [list $::env(SB_START) $::env(SB_END)] $::env(SB_VCD)
 report_switching_activity -list_not_annotated > activity.rpt
 check_power -verbose > check_power.rpt
 update_power
 report_units > units.rpt
 report_power -verbose > power.rpt
 report_power -hierarchy > hierarchy.rpt
 report_power -cell_power [get_cells -hierarchical * -filter {is_hierarchical == false}] > cell_power.rpt
 put COMPLETE "calculated prelayout activity; no CTS/SPEF/SDF"
} msg]} {put FAILURE.txt "$msg\n$::errorInfo";exit 1}
exit 0
