proc write_output_activity {} {
    set f [open output_activity.tsv w]
    puts $f "name\ttoggle_rate\tstatic_probability\tsource"
    foreach_in_collection p [get_ports *] {
        set name [get_object_name $p]
        if {$name ne "clk" && $name ne "out_valid" && ![regexp {^result\[[0-9]+\]$} $name]} {continue}
        set tr NA;set sp NA;set source unavailable
        if {![catch {set t [get_attribute -quiet $p toggle_rate];set s [get_attribute -quiet $p static_probability]}] && [string is double -strict $t] && [string is double -strict $s]} {
            set tr $t;set sp $s;set source port
        } else {
            set ns [get_nets -quiet -of_objects $p]
            if {[sizeof_collection $ns]==1} {
                if {![catch {set t [get_attribute -quiet $ns toggle_rate];set s [get_attribute -quiet $ns static_probability]}] && [string is double -strict $t] && [string is double -strict $s]} {
                    set tr $t;set sp $s;set source net
                }
            }
        }
        puts $f "$name\t$tr\t$sp\t$source"
    }
    close $f
}
