# Set private AC_TARGET_DB, AC_TOP, AC_RTL_DIR and AC_FREQ_MHZ before launch.
# Run once per new empty case directory. No library copied or modified.
set search_path [concat $search_path [list $::env(AC_RTL_DIR)]]
set target_library [list $::env(AC_TARGET_DB)]
set link_library [concat [list *] $target_library]
define_design_lib WORK -path ./work
set files [list ac_scan.sv ac_winner.sv ac_rejection.sv nr_singleton_tree.sv "$::env(AC_TOP).sv"]
set paths {};foreach f $files {lappend paths [file join $::env(AC_RTL_DIR) $f]}
analyze -format sverilog -define SYNTHESIS $paths
elaborate $::env(AC_TOP)
current_design $::env(AC_TOP)
if {![link]} {error "link failed"}
create_clock -name core -period [expr {1000.0/$::env(AC_FREQ_MHZ)}] [get_ports clk]
set_clock_uncertainty -setup 2.0 [get_clocks core]
set_clock_uncertainty -hold 0.1 [get_clocks core]
set_input_transition 0.1 [remove_from_collection [all_inputs] [get_ports clk]]
set_load 0.02 [all_outputs]
# This is a core-boundary probe. Integration IO budgets must be supplied as
# explicit additional constraints; no guessed delay used to claim Fmax.
set_input_delay 0 -clock core [remove_from_collection [all_inputs] [get_ports clk]]
set_output_delay 0 -clock core [all_outputs]
check_design > check_design_before.rpt
compile -map_effort high
check_design > check_design.rpt
report_area -hierarchy > area.rpt
report_timing -delay_type max -max_paths 20 > setup.rpt
report_timing -delay_type min -max_paths 20 > hold.rpt
report_constraint -all_violators > constraints.rpt
report_reference > cells.rpt
write -format verilog -hierarchy -output mapped.v
write_sdc mapped.sdc
write -format ddc -hierarchy -output mapped.ddc
exit
