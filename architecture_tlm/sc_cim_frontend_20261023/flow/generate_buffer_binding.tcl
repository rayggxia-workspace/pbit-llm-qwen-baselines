# Called inside DC after target library load. Never silently use the wire fallback.
proc generate_buffer_binding {} {
 set ref $::env(BUF_REF)
 set cell [get_lib_cells -quiet */$ref]
 if {[sizeof_collection $cell]!=1} {error "Select one real non-inverting buffer BUF_REF; missing/ambiguous $ref"}
 set ip [get_lib_pins -of_objects $cell -filter {direction == in}]
 set op [get_lib_pins -of_objects $cell -filter {direction == out}]
 if {[sizeof_collection $ip]!=1 || [sizeof_collection $op]!=1} {error "BUF_REF must have one input and one output"}
 set i [file tail [get_object_name $ip]]
 set o [file tail [get_object_name $op]]
 set fn [string trim [get_attribute $op function] { ()"}]
 if {$fn ne $i} {error "BUF_REF is not a non-inverting buffer: $fn"}
 save_text buffer_binding.v "module cim_technology_buffer(input a,output y); $ref cell_inst(.$i(a),.$o(y)); endmodule"
 save_text buffer_binding.txt "ref=$ref\ninput=$i\noutput=$o\narea=[get_attribute $cell area]"
}
