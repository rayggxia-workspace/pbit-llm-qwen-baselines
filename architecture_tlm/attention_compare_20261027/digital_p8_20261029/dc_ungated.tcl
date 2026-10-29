if {[catch {
 source $::env(P8_SOURCE)/common.tcl
 set_host_options -max_cores 1
 set_app_var target_library [list $::env(P8_DB)]
 set_app_var link_library [list * $::env(P8_DB)]
 define_design_lib WORK -path ./work
 set_app_var search_path [concat $search_path [list $::env(P8_SOURCE)]]
 analyze -format sverilog [list $::env(P8_SOURCE)/design.sv $::env(P8_SOURCE)/rng_bivium_map.sv $::env(P8_SOURCE)/$::env(P8_TOP).sv]
 elaborate $::env(P8_TOP)
 current_design $::env(P8_TOP)
 if {![link]} {error "link failed"}
 constraints
 set_fix_hold [get_clocks core]
 compile -map_effort high
 change_names -rules verilog -hierarchy
 check_design > design.rpt
 report_area -hierarchy > area.rpt
 report_reference > cells.rpt
 report_qor > qor.rpt
 report_units > units.rpt
 inventory
 write -format verilog -hierarchy -output mapped.v
 write_sdc mapped.sdc
 putfile DC_COMPLETE "completed"
} msg]} {putfile FAILURE.txt "$msg\n$::errorInfo";exit 1}
exit 0
