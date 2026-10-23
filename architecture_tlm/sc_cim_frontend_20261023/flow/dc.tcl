source [file join $::env(PPA_SOURCE) common.tcl]
source [file join $::env(PPA_SOURCE) generate_buffer_binding.tcl]
proc main {} {
 set_app_var target_library [list $::env(STD_DB)]
 set_app_var link_library [list * $::env(STD_DB)]
 read_db $::env(STD_DB)
 generate_buffer_binding
 define_design_lib WORK -path ./WORK
 set src [concat [lsort [glob $::env(CIM_ROOT)/rtl/*.sv]] [list buffer_binding.v]]
 capture analyze.rpt {analyze -format sverilog -define CIM_TECH_BUFFER $src}
 set n $::env(CIM_N);set m $::env(CIM_M);set kind $::env(CIM_KIND)
 if {$kind==0} {set top cim_frontend;set params "N=$n,M=$m,T=$::env(CIM_T),K=$::env(CIM_K),EXTERNAL_RNG=$::env(CIM_EXT)"}
 if {$kind==1} {set top cim_sng;set params "N=$n,T=$::env(CIM_T),K=$::env(CIM_K),EXTERNAL_RNG=$::env(CIM_EXT)"}
 if {$kind==2} {set top cim_w8_gate;set params "N=$n,M=$m"}
 if {$kind==3} {set top cim_sram_q_probe;set params "WIDTH=[expr {$n*$m*8}],COPIES=1"}
 capture elaborate.rpt {elaborate $top -parameters $params}
 rename_design [current_design] cim_probe_mapped
 capture link.rpt {if {![link]} {error "DC link failed"}}
 conditions
 constraints
 # Preserve deliberately explicit buffer topology. Mapping is technology-specific.
 set buffers [get_cells -hierarchical * -filter "ref_name == $::env(BUF_REF)"]
 set before [sizeof_collection $buffers]
 if {$before<1} {error "No real driver cells found"}
 set_dont_touch $buffers true
 set wrappers [get_cells -hierarchical * -filter {ref_name =~ cim_buffer* || ref_name =~ cim_fanout* || ref_name == cim_technology_buffer}]
 set_dont_touch $wrappers true
 capture compile.rpt {compile}
 set after [sizeof_collection [get_cells -hierarchical * -filter "ref_name == $::env(BUF_REF)"]]
 if {$after<$before} {error "Explicit drivers disappeared: $before -> $after"}
 save_text driver_count.txt "before=$before\nafter=$after"
 change_names -rules verilog -hierarchy
 write -format verilog -hierarchy -output mapped.v
 write -format ddc -hierarchy -output mapped.ddc
 write_sdc mapped.sdc
 capture area.rpt {report_area -hierarchy}
 capture references.rpt {report_reference -hierarchy}
 capture check_design.rpt {check_design}
 timing_reports dc
 save_text SYNTH_COMPLETE "Synthesis completed; not post-layout PPA."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
