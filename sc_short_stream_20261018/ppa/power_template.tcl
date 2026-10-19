# PT-PX template: mapped netlist + matching gate-level active-frame VCD.
# Use the user's existing library/OC/constraint conventions unchanged.
foreach name {TOP_NAME STD_LIB_DBS OPERATING_LIBRARY OPERATING_CONDITION MAPPED_NETLIST SDC_FILE ACTIVE_GATE_VCD VCD_STRIP_PATH} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {error "Required environment variable: $name"}
}
foreach name {MAPPED_NETLIST SDC_FILE ACTIVE_GATE_VCD} {
    if {![file exists $::env($name)]} {error "Missing $name: $::env($name)"}
}
set_app_var power_enable_analysis true
set_app_var power_analysis_mode averaged
set_app_var link_create_black_boxes false
set_app_var link_path [concat [list *] $::env(STD_LIB_DBS)]
read_verilog $::env(MAPPED_NETLIST)
if {![link_design $::env(TOP_NAME)]} {error "Design link failed"}
set_operating_conditions -library $::env(OPERATING_LIBRARY) $::env(OPERATING_CONDITION)
read_sdc $::env(SDC_FILE)
update_timing
redirect -file check_timing.rpt {check_timing -verbose}
redirect -file timing.rpt {report_timing -delay_type max -max_paths 20}
redirect -file constraints.rpt {report_constraint -all_violators}
redirect -file clocks.rpt {report_clock}
redirect -file activity_read.rpt {read_vcd -strip_path $::env(VCD_STRIP_PATH) $::env(ACTIVE_GATE_VCD)}
redirect -file activity_coverage.rpt {report_switching_activity -list_not_annotated}
redirect -file check_power.rpt {check_power -verbose}
# Inspect missing models, slew/load table range and annotation coverage before
# accepting totals. A successful tool exit alone is not PPA signoff.
update_power
redirect -file power.rpt {report_power -verbose}
redirect -file hierarchy.rpt {report_power -hierarchy}
redirect -file cells.rpt {report_power -cell_power [get_cells -hierarchical * -filter {is_hierarchical == false}]}
exit
