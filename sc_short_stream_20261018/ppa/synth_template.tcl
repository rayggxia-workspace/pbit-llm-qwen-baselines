# Generic DC template. No foundry library or license is distributed.
# Run in a fresh output directory; source lists are Tcl lists, not shell code.
foreach name {TOP_NAME STD_LIB_DBS SC_RTL_SOURCES OPERATING_LIBRARY OPERATING_CONDITION INPUT_DRIVER_CELL OUTPUT_LOAD_LIB_UNITS INPUT_DELAY_NS OUTPUT_DELAY_NS CLOCK_UNCERTAINTY_NS} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {error "Required environment variable: $name"}
}
set_app_var target_library $::env(STD_LIB_DBS)
set_app_var link_library [concat [list *] $::env(STD_LIB_DBS)]
foreach f $::env(SC_RTL_SOURCES) {if {![file exists $f]} {error "Missing RTL: $f"}}
analyze -format sverilog $::env(SC_RTL_SOURCES)
elaborate $::env(TOP_NAME)
current_design $::env(TOP_NAME)
if {![link]} {error "Design link failed"}
set_operating_conditions -library $::env(OPERATING_LIBRARY) $::env(OPERATING_CONDITION)
create_clock -name core_clk -period 10.0 [get_ports clk]
set_clock_uncertainty $::env(CLOCK_UNCERTAINTY_NS) [get_clocks core_clk]
set data_inputs [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay $::env(INPUT_DELAY_NS) -clock core_clk $data_inputs
set_output_delay $::env(OUTPUT_DELAY_NS) -clock core_clk [all_outputs]
set_driving_cell -lib_cell $::env(INPUT_DRIVER_CELL) $data_inputs
set_load $::env(OUTPUT_LOAD_LIB_UNITS) [all_outputs]
# Keep weight/probability ports variable. Do not set_case_analysis to freeze
# this test vector into a constant-coefficient hardware design.
redirect -file check_design.rpt {check_design}
compile_ultra
redirect -file area.rpt {report_area -hierarchy}
redirect -file timing.rpt {report_timing -delay_type max -max_paths 20}
redirect -file constraints.rpt {report_constraint -all_violators}
redirect -file reference.rpt {report_reference -hierarchy}
redirect -file resources.rpt {report_resources -hierarchy}
redirect -file libraries.rpt {list_libs}
write -format verilog -hierarchy -output mapped.v
write_sdc mapped.sdc
write -format ddc -hierarchy -output mapped.ddc
exit
