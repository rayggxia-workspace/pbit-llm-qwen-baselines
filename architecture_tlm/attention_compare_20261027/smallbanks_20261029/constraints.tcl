create_clock -name core -period 10 [get_ports clk]
set_clock_transition 0.1 [get_clocks core]
set_clock_uncertainty -setup 0.5 [get_clocks core]
set_clock_uncertainty -hold 0.05 [get_clocks core]
set ins [remove_from_collection [all_inputs] [get_ports clk]]
set_input_transition 0.1 $ins
set_input_delay -max 1.0 -clock core $ins
set_input_delay -min 0.2 -clock core $ins
set_output_delay -max 1.0 -clock core [all_outputs]
set_output_delay -min 0.02 -clock core [all_outputs]
set_load 0.02 [all_outputs]
