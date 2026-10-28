open_vcd reproduction.vcd
log_vcd [get_objects -filter {type == in_port || type == out_port || type == inout_port || type == port} /rtl_suite/dut/*]
log_vcd [get_objects /rtl_suite/dut/ap_CS_fsm]
run all
close_vcd
quit
