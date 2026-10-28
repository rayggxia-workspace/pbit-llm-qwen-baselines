if {[catch {
 source $::env(RB_SOURCE)/common.tcl
 set_host_options -max_cores 1
 set_app_var target_library [list $::env(RB_DB)]
 set_app_var link_library [list * $::env(RB_DB)]
 define_design_lib WORK -path ./work
 analyze -format sverilog [list $::env(RB_SOURCE)/bank.sv $::env(RB_SOURCE)/$::env(RB_TOP).sv]
 elaborate $::env(RB_TOP)
 current_design $::env(RB_TOP)
 if {![link]} {error "link failed"}
 constraints
 set gates [get_cells -hierarchical * -filter {ref_name == CKGTX8_9TSVT}]
 if {$::env(RB_GATED)==1 && [sizeof_collection $gates]!=32} {error "expected 32 real ICGs"}
 if {[sizeof_collection $gates]>0} {set_dont_touch $gates true}
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
