# Read-only connectivity audit. Never tie, disable timing, or modify the netlist.
source [file join $::env(PPA_SOURCE) common.tcl]
proc literal_pattern {name} {
    return [string map [list "\\" "\\\\" "\[" "\\\[" "\]" "\\\]" "*" "\\*" "?" "\\?"] $name]
}
proc classify_xz {name} {
    global leaf_ref
    set pattern [literal_pattern $name]
    set port [get_ports -quiet $pattern]
    if {[sizeof_collection $port] > 0} {return [list REQUIRED top_port $name]}
    set pin [get_pins -quiet $pattern]
    if {[sizeof_collection $pin] > 1} {return [list UNRESOLVED multiple_pins $name]}
    if {[sizeof_collection $pin] == 1} {
        set owner [get_object_name [get_cells -of_objects $pin]]
        if {[info exists leaf_ref($owner)]} {return [list REQUIRED leaf_pin $name]}
        set nets [get_nets -quiet -of_objects $pin]
        if {[sizeof_collection $nets] == 0} {return [list DISCONNECTED hierarchical_pin_no_net $name]}
    } else {
        set nets [get_nets -quiet $pattern]
    }
    if {[sizeof_collection $nets] > 0} {
        set endpoints {}
        foreach_in_collection net $nets {
            set connected [all_connected -leaf $net]
            if {[sizeof_collection $connected] > 0} {
                foreach_in_collection endpoint $connected {
                    lappend endpoints [get_object_name $endpoint]
                    if {[llength $endpoints] >= 16} {break}
                }
            }
        }
        if {[llength $endpoints] > 0} {return [list REQUIRED connected_net [join $endpoints ,]]}
        return [list DISCONNECTED net_zero_leaf_or_top_connections [get_object_name $nets]]
    }
    # A path below a linked library leaf but not one of its pins is model-only.
    set parent $name
    while {[set at [string last / $parent]] >= 0} {
        set parent [string range $parent 0 [expr {$at-1}]]
        if {[info exists leaf_ref($parent)]} {
            return [list MODEL_INTERNAL library_model_variable "${parent}:$leaf_ref($parent)"]
        }
    }
    return [list UNRESOLVED not_in_linked_design $name]
}
proc main {} {
    global leaf_ref
    set_app_var link_create_black_boxes false
    set_app_var link_path [list * $::env(STD_DB)]
    capture xz_read.rpt {read_verilog $::env(NET_DIR)/mapped.v}
    capture xz_link.rpt {if {![link_design sc_counter_tile_mapped]} {error "PT link failed"}}
    array set leaf_ref {}
    set leaves [inventory]
    foreach_in_collection cell $leaves {
        set leaf_ref([get_object_name $cell]) [get_attribute $cell ref_name]
    }
    set input [open $::env(XZ_REQUESTS) r]
    set output [open xz_classification.tsv w]
    puts $output "name\tclassification\treason\tevidence"
    set count 0
    while {[gets $input name] >= 0} {
        if {$name eq "" || [regexp {[\t\r\n]} $name]} {error "Malformed request"}
        set answer [classify_xz $name]
        puts $output "$name\t[join $answer \t]"
        incr count
    }
    close $input
    close $output
    if {$count == 0} {error "No X/Z requests"}
    save_text XZ_PROBE_COMPLETE "Classified $count aliases; no power calculated by this probe."
}
if {[catch {main} msg]} {save_text xz_failure.txt "$msg\n$::errorInfo";puts stderr $msg;exit 1}
exit 0
