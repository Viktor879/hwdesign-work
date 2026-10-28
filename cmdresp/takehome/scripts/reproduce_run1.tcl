open_vcd run1-reproduction.vcd
log_vcd [get_objects -filter {type == in_port || type == out_port || type == inout_port || type == port} /rtl_stress/dut/*]
log_vcd [get_objects /rtl_stress/dut/grp_qgemv_Pipeline_compute_fu_631/ap_enable_reg_pp0_iter10]
log_vcd [get_objects /rtl_stress/dut/grp_qgemv_Pipeline_compute_fu_631/ap_block_pp0_stage0_11001_grp1]
run all
close_vcd
quit
