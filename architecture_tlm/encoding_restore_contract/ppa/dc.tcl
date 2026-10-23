source [file join $env(ER_FLOW) common.tcl]
proc main {} {
    require_env {STD_DB STD_LIB_NAME STD_OC_NAME ER_TOP ER_SOURCE_LIST ER_CPUS}
    set_app_var target_library [list $::env(STD_DB)]
    set_app_var link_library [concat [list "*"] [list $::env(STD_DB)]]
    set_host_options -max_cores $::env(ER_CPUS)
    define_design_lib WORK -path ./WORK
    set f [open $::env(ER_SOURCE_LIST) r]; set source_text [read $f]; close $f
    set sources {}
    foreach path [split $source_text "\n"] {if {[string trim $path] ne ""} {lappend sources [string trimright $path "\r"]}}
    if {[llength $sources] == 0} {error "Empty source closure"}
    capture analyze.log {analyze -format sverilog -define SYNTHESIS $sources}
    capture elaborate.log {elaborate $::env(ER_TOP)}
    current_design $::env(ER_TOP)
    if {![capture link.log {link}]} {error "Link returned false"}
    library_condition
    constraints
    capture check_design.rpt {check_design}
    capture compile.log {compile_ultra}
    inventory
    timing_reports
    capture area.rpt {report_area -hierarchy}
    capture references.rpt {report_reference -hierarchy}
    capture design.rpt {report_design}
    change_names -rules verilog -hierarchy
    write -format verilog -hierarchy -output mapped.v
    write_sdc mapped.sdc
    write -format ddc -hierarchy -output mapped.ddc
    save DONE "Synthesis executed; inspect STA. Not signoff."
}
if {[catch {main} error_text]} {save FAILURE.txt $error_text; puts stderr $error_text; exit 1}
exit 0
