# Run from any directory: dc_shell -f /path/random_service/scripts/synth_dc.tcl
# TARGET_LIBS must be a Tcl list of authorized local .db files; none are bundled.
foreach name {TARGET_LIBS CLOCK_NS INPUT_DELAY_NS OUTPUT_DELAY_NS OUTPUT_LOAD_PF REPORT_DIR} {
  if {![info exists env($name)]} {error "Set environment variable $name explicitly"}
}
set root [file normalize [file join [file dirname [info script]] ..]]
set target_library $env(TARGET_LIBS)
set link_library [concat {*} $target_library]
set top rng_seeded_top
if {[info exists env(TOP)]} {set top $env(TOP)}
set kind 0
if {[info exists env(KIND)]} {set kind $env(KIND)}
file mkdir $env(REPORT_DIR)
define_design_lib WORK -path [file join $env(REPORT_DIR) WORK]
set src {}
foreach f {rng_lfsr32_map.sv rng_shared64_map.sv rng_bivium_map.sv rng_endpoint.sv rng_seed_ingress.sv rng_seeded_top.sv rng_ffn_shared64.sv} {
  lappend src [file join $root rtl $f]
}
analyze -format sverilog $src
if {$top eq "rng_seeded_top"} {
  elaborate $top -parameters "KIND=$kind,RESEED_CYCLES=100000000"
} elseif {$top eq "rng_ffn_shared64"} {
  elaborate $top -parameters "RESEED_CYCLES=100000000"
} else {error "This script supports the two clocked characterization tops only"}
current_design $top
link
create_clock -name clk -period $env(CLOCK_NS) [get_ports clk]
set_input_delay $env(INPUT_DELAY_NS) -clock clk [remove_from_collection [all_inputs] [get_ports {clk rst_n}]]
set_output_delay $env(OUTPUT_DELAY_NS) -clock clk [all_outputs]
# Library load units must be checked before using OUTPUT_LOAD_PF.
set_load $env(OUTPUT_LOAD_PF) [all_outputs]
set_false_path -from [get_ports rst_n]
check_design > [file join $env(REPORT_DIR) check_design.rpt]
compile
report_area -hierarchy > [file join $env(REPORT_DIR) area.rpt]
report_timing -max_paths 20 > [file join $env(REPORT_DIR) timing.rpt]
report_constraint -all_violators > [file join $env(REPORT_DIR) violations.rpt]
write -format verilog -hierarchy -output [file join $env(REPORT_DIR) netlist.v]
write_sdc [file join $env(REPORT_DIR) design.sdc]
write -format ddc -hierarchy -output [file join $env(REPORT_DIR) design.ddc]
quit
