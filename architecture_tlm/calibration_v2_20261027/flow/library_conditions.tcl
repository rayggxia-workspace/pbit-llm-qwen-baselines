# Parse report_lib rather than relying on unsupported Liberty attributes in PT 2018.
proc oc_store_block {rowsVar block path} {
    upvar 1 $rowsVar rows
    if {[dict size $block] == 0} {return}
    foreach key {name process temperature voltage} {
        if {![dict exists $block $key]} {error "Incomplete operating condition ($key) in $path"}
    }
    set name [dict get $block name]
    if {[dict exists $rows $name]} {error "Duplicate operating condition in $path: $name"}
    dict set rows $name $block
}
proc oc_from_report {text library path} {
    set active 0
    set columns {}
    set rows [dict create]
    set default ""
    set block [dict create]
    foreach line [split $text "\n"] {
        if {[regexp -nocase {^\s*Default operating conditions?\s*:\s*(\S+)\s*$} $line -> value]} {
            set default [string trim $value {"'}]
            set active 0
            continue
        }
        if {[regexp -nocase {^\s*Operating conditions?\s*:\s*$} $line]} {
            set active 1
            set columns {}
            continue
        }
        if {!$active} {continue}
        # DC 2018 emits named fields; PT can emit a column table instead.
        if {[regexp -nocase {^\s*Operating Condition Name\s*:\s*(\S+)\s*$} $line -> name]} {
            oc_store_block rows $block $path
            set block [dict create name [string trim $name {"'}]]
            continue
        }
        if {[dict size $block] != 0} {
            if {[regexp -nocase {^\s*(Process|Temperature|Voltage)\s*:\s*(\S+)\s*$} $line -> key value]} {
                set key [string tolower $key]
                if {![string is double -strict $value] || [dict exists $block $key]} {
                    error "Invalid/duplicate operating-condition field in $path: $line"
                }
                dict set block $key $value
                continue
            }
            if {[regexp -nocase {^\s*(Library|Interconnect Model)\s*:} $line] || [string trim $line] eq ""} {continue}
            oc_store_block rows $block $path
            set block [dict create]
            set active 0
            continue
        }
        set tokens [regexp -all -inline {\S+} [string trim $line]]
        if {[llength $tokens] == 0 || [regexp {^[-= ]+$} $line]} {continue}
        set lower [string tolower $tokens]
        if {[lindex $lower 0] eq "name" && [lsearch -exact $lower process] >= 0} {
            set columns $lower
            continue
        }
        if {[llength $columns] == 0} {continue}
        if {[regexp {^\s*[^:]+:\s*} $line]} {set active 0; continue}
        set values [dict create]
        foreach {key alternatives} {process {process} temperature {temp temperature} voltage {volt voltage}} {
            set index -1
            foreach label $alternatives {
                set index [lsearch -exact $columns $label]
                if {$index >= 0} {break}
            }
            set value [lindex $tokens $index]
            if {$index < 0 || ![string is double -strict $value]} {
                error "Unrecognized operating-condition row in $path: $line"
            }
            dict set values $key $value
        }
        set name [string trim [lindex $tokens 0] {*()}]
        if {[dict exists $rows $name]} {error "Duplicate operating condition in $path"}
        dict set values name $name
        dict set rows $name $values
    }
    oc_store_block rows $block $path
    if {$default ne "" && [dict exists $rows $default]} {return [dict get $rows $default]}
    if {$default eq "" && [dict size $rows] == 1} {return [dict get $rows [lindex [dict keys $rows] 0]]}
    error "Cannot choose operating condition for $library; see $path"
}
proc lib_for_ref {ref} {
    set cell [get_lib_cells -quiet "*/$ref"]
    if {[sizeof_collection $cell]!=1} {error "Missing/ambiguous library cell $ref"}
    return [lindex [split [get_object_name $cell] /] 0]
}
