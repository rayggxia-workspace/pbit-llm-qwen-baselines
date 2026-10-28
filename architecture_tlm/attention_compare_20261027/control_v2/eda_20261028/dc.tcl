# Core-boundary synthesis probe. Private library supplied only at execution.
if {[catch {
    set_host_options -max_cores 1
    set_app_var search_path [concat $search_path [list $::env(AC_RTL_DIR)]]
    set_app_var target_library [list $::env(AC_TARGET_DB)]
    set_app_var link_library [concat [list *] $target_library]
    define_design_lib WORK -path ./work
    set paths {}
    foreach f [list ac_scan.sv ac_winner.sv ac_rejection.sv nr_singleton_tree.sv "$::env(AC_TOP).sv"] {
        lappend paths [file join $::env(AC_RTL_DIR) $f]
    }
    analyze -format sverilog -define SYNTHESIS $paths
    elaborate $::env(AC_TOP)
    current_design $::env(AC_TOP)
    if {![link]} {error "link failed"}
    create_clock -name core -period [expr {1000.0/$::env(AC_FREQ_MHZ)}] [get_ports clk]
    set_clock_uncertainty -setup 2.0 [get_clocks core]
    set_clock_uncertainty -hold 0.1 [get_clocks core]
    set_clock_transition 0.1 [get_clocks core]
    set data_inputs [remove_from_collection [all_inputs] [get_ports clk]]
    set_input_transition 0.1 $data_inputs
    set_load 0.02 [all_outputs]
    set_input_delay 0 -clock core $data_inputs
    set_output_delay 0 -clock core [all_outputs]
    check_design > check_design_before.rpt
    compile -map_effort high
    change_names -rules verilog -hierarchy
    check_design > check_design.rpt
    report_units > units.rpt
    report_area -hierarchy > area.rpt
    report_qor > qor.rpt
    report_timing -delay_type max -max_paths 20 > setup.rpt
    report_timing -delay_type min -max_paths 20 > hold.rpt
    report_constraint -all_violators > constraints.rpt
    report_reference > cells.rpt
    write -format verilog -hierarchy -output mapped.v
    write_sdc mapped.sdc
    write -format ddc -hierarchy -output mapped.ddc
    set f [open SYNTHESIS_COMPLETE.txt w];puts $f "completed; timing acceptance separate";close $f
} message]} {
    set f [open failure.txt w];puts $f "$message\n$::errorInfo";close $f
    puts stderr "AC_DC_FAILED: $message";exit 1
}
exit 0
