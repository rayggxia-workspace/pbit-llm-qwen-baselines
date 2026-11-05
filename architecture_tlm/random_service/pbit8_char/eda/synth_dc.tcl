# Run from an empty per-top/per-frequency result directory, user supplies library.
# Required environment: PKG, TOP, TARGET_DB (Tcl list), PERIOD_NS.
foreach k {PKG TOP TARGET_DB PERIOD_NS} {if {![info exists ::env($k)]} {error "Missing $k"}}
set pkg [file normalize $::env(PKG)]
set top $::env(TOP)
if {$top ni {pbit_compare8_lt pbit_compare8_q256 pbit_sigmoid8_lut pbit_sigmoid8_reg pbit_sample8_reg}} {error "Unknown top"}
set_app_var target_library $::env(TARGET_DB)
set_app_var link_library [concat {*} $target_library]
define_design_lib WORK -path ./work
analyze -format sverilog [glob $pkg/rtl/*.sv]
elaborate $top
current_design $top
if {![link]} {error "Link failed"}
set period $::env(PERIOD_NS)
if {[sizeof_collection [get_ports -quiet clk]]} {
  create_clock -name core -period $period [get_ports clk]
  set data_in [remove_from_collection [all_inputs] [get_ports {clk rst_n}]]
  set_false_path -from [get_ports rst_n]
} else {
  create_clock -name core -period $period
  set data_in [all_inputs]
}
# Units MUST be checked in report_lib: assumptions below ns and pF.
set_clock_uncertainty [expr {0.2*$period}] [get_clocks core]
set_input_delay [expr {0.1*$period}] -clock core $data_in
set_output_delay [expr {0.1*$period}] -clock core [all_outputs]
set_input_transition 0.1 [all_inputs]
set_load 0.001 [all_outputs]
redirect libraries.rpt {foreach_in_collection l [get_libs] {report_lib [get_object_name $l]}}
check_design > check_design.rpt
compile_ultra
change_names -rules verilog -hierarchy
write -format verilog -hierarchy -output mapped.v
write_sdc mapped.sdc
write -format ddc -hierarchy -output mapped.ddc
report_area -hierarchy > area.rpt
report_timing -delay_type max -max_paths 10 > setup.rpt
report_timing -delay_type min -max_paths 10 > hold.rpt
report_constraint -all_violators > constraints.rpt
check_design > check_design_final.rpt
quit
