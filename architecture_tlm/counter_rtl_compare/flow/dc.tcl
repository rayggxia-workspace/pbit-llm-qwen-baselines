source [file join $::env(PPA_SOURCE) common.tcl]
proc main {} {
 set_app_var target_library [list $::env(STD_DB)]
 set_app_var link_library [list * $::env(STD_DB)]
 set_host_options -max_cores $::env(EDA_CORES)
 define_design_lib WORK -path ./WORK
 set src [lsort [glob $::env(SC_ROOT)/rtl/*.sv]]
 capture analyze.rpt [list analyze -format sverilog $src]
 capture elaborate.rpt {elaborate sc_counter_tile -parameters "ARCH=$::env(SC_ARCH),N=64,M=$::env(SC_M),T=$::env(SC_T),PIPE=$::env(SC_PIPE)"}
 rename_design [current_design] sc_counter_tile_mapped
 capture link.rpt {if {![link]} {error "DC link failed"}}
 conditions
 constraints
 capture check_design_before.rpt {check_design}
 # The same synthesis command for A/B, no weight constants, no preserved DFF bank.
 capture compile.rpt {compile}
 change_names -rules verilog -hierarchy
 write -format verilog -hierarchy -output mapped.v
 write -format ddc -hierarchy -output mapped.ddc
 write_sdc mapped.sdc
 inventory
 capture area.rpt {report_area -hierarchy}
 capture references.rpt {report_reference -hierarchy}
 capture check_design.rpt {check_design}
 timing_reports dc
 save_text SYNTH_COMPLETE "Netlist generated. Physical timing and power remain separate."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
