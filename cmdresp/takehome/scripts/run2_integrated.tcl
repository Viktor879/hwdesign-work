read_verilog [glob build_run2/solution1/syn/verilog/*.v]
read_verilog -sv src/qgemv.sv
synth_design -top qgemv -part xc7z020clg484-1 -mode out_of_context
create_clock -period 8 [get_ports ap_clk]
report_utilization -file evidence/run2/synthesis/integrated_utilization.rpt
report_timing_summary -file evidence/run2/synthesis/integrated_timing.rpt
exit
