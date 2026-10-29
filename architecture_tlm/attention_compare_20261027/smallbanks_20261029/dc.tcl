if {[catch {
 set_app_var target_library [list $::env(SB_STD_DB)]
 set_app_var link_library [list * $::env(SB_STD_DB) $::env(SB_MACRO_DB)]
 read_verilog $::env(SB_SOURCE)/banks.sv
 current_design banks
 link
 source $::env(SB_SOURCE)/constraints.tcl
 compile_ultra -no_autoungroup
 change_names -rules verilog -hierarchy
 check_design > check_design.rpt
 report_area -hierarchy > area.rpt
 report_reference -hierarchy > references.rpt
 write -format verilog -hierarchy -output mapped.v
 write_sdc mapped.sdc
 set f [open COMPLETE w];puts $f ok;close $f
} msg]} {puts $msg;puts $::errorInfo;exit 1}
exit 0
