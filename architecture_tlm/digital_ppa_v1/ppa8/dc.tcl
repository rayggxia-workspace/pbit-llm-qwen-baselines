source [file join $::env(PPA_SOURCE) common.tcl]
proc main {} {
    set_app_var target_library [list $::env(STD_DB)]
    set_app_var link_library [list * $::env(STD_DB)]
    set_app_var search_path [concat [get_app_var search_path] [list $::env(PPA_SOURCE)/rtl $::env(PPA_SOURCE)/conversion]]
    set_host_options -max_cores $::env(EDA_CORES)
    define_design_lib WORK -path ./WORK
    set src [concat [lsort [glob $::env(PPA_SOURCE)/rtl/*.sv]] [lsort [glob $::env(PPA_SOURCE)/conversion/*.sv]]]
    capture analyze.rpt [list analyze -format sverilog $src]
    capture elaborate.rpt {elaborate nr_digital_probe -parameters "KIND=$::env(PPA_KIND)"}
    rename_design [current_design] nr_digital_probe_mapped
    capture link.rpt {if {![link]} {error "DC link failed"}}
    conditions
    constraints
    capture check_design_before.rpt {check_design}
    # Retain hierarchy for boundary/core accounting; this is not a flattened optimum.
    capture compile.rpt {compile}
    change_names -rules verilog -hierarchy
    write -format verilog -hierarchy -output mapped.v
    write -format ddc -hierarchy -output mapped.ddc
    write_sdc mapped.sdc
    set f [open hierarchy.txt w]
    foreach_in_collection h [get_cells -hierarchical * -filter {is_hierarchical == true}] {puts $f [get_object_name $h]}
    close $f
    inventory
    capture area.rpt {report_area -hierarchy}
    capture references.rpt {report_reference -hierarchy}
    capture check_design.rpt {check_design}
    timing_reports dc
    save_text SYNTH_COMPLETE "Prelayout mapped circuit; review timing separately."
}
if {[catch {main} msg]} {save_text failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
