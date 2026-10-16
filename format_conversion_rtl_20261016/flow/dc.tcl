# Run from the package root. This template has not been executed with the user's
# licensed DC/library. No hidden false paths or automatic timing waivers.
foreach v {STD_DB STD_LIB_NAME OC_NAME CASE_TYPE OUT_DIR} {
 if {![info exists ::env($v)]} {error "Missing environment $v"}
}
set_app_var target_library [list $::env(STD_DB)]
set_app_var link_library [concat [list *] $target_library]
set rtl [glob rtl/*.sv]
file mkdir $::env(OUT_DIR)
analyze -format sverilog $rtl
if {$::env(CASE_TYPE) eq "conversion"} {
 if {![info exists ::env(KIND)]} {error "Need KIND=0..17"}
 elaborate fc_conversion_probe -parameters "KIND=$::env(KIND)"
 set top fc_conversion_probe
} elseif {$::env(CASE_TYPE) eq "accum"} {
 if {![info exists ::env(FIXED)] || ![info exists ::env(ACC_W)]} {error "Need FIXED and ACC_W"}
 elaborate fc_accum_probe -parameters "FIXED=$::env(FIXED),ACC_W=$::env(ACC_W)"
 set top fc_accum_probe
} else {error "CASE_TYPE must be conversion or accum"}
current_design $top
link
set_operating_conditions -library $::env(STD_LIB_NAME) $::env(OC_NAME)
create_clock -name clk -period 10 [get_ports clk]
set_clock_transition 0.1 [get_clocks clk]
set_clock_uncertainty 0.1 [get_clocks clk]
set inputs [remove_from_collection [all_inputs] [get_ports clk]]
set_input_transition 0.1 $inputs
set_input_delay -max 1.0 -clock clk $inputs
set_input_delay -min 0.2 -clock clk $inputs
set_output_delay -max 1.0 -clock clk [all_outputs]
set_output_delay -min 0.2 -clock clk [all_outputs]
set_load 0.02 [all_outputs]
check_design > $::env(OUT_DIR)/check_design.rpt
compile_ultra
write -format verilog -hierarchy -output $::env(OUT_DIR)/mapped.v
write_sdc $::env(OUT_DIR)/mapped.sdc
write -format ddc -hierarchy -output $::env(OUT_DIR)/mapped.ddc
report_area -hierarchy > $::env(OUT_DIR)/area.rpt
report_reference -hierarchy > $::env(OUT_DIR)/references.rpt
report_timing -delay_type max -max_paths 20 > $::env(OUT_DIR)/setup.rpt
report_timing -delay_type min -max_paths 20 > $::env(OUT_DIR)/hold.rpt
report_constraint -all_violators > $::env(OUT_DIR)/constraints.rpt
report_clock > $::env(OUT_DIR)/clock.rpt
report_lib $::env(STD_LIB_NAME) > $::env(OUT_DIR)/library.rpt
quit
