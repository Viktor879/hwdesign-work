open_vcd suite.vcd
log_vcd [get_objects -filter {type == in_port || type == out_port || type == inout_port || type == port} /rtl_suite/dut/*]
run all
close_vcd
quit
