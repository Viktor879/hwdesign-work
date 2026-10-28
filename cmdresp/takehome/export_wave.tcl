# Read-only extraction from the one completed RTL simulation; no simulation rerun.
set v3 [expr {[info exists ::env(QGEMV_VERSION)] && $::env(QGEMV_VERSION) eq "v3"}]
set project [expr {$v3 ? "qgemv_hls_v3" : "qgemv_hls"}]
set evidence [expr {$v3 ? "evidence/v3" : "evidence"}]
open_wave_database $project/solution1/sim/verilog/qgemv.wdb
set base /apatb_qgemv_top/AESL_inst_qgemv
set f [open $evidence/rtl_cycles.csv w]
set columns "cycle,time_ps,in_valid,in_ready,in_data,in_last,out_valid,out_ready,out_data,out_last"
if {$v3} {append columns ",in_keep,in_strb,out_keep,out_strb"}
puts $f $columns
set signals {in_r_TVALID in_r_TREADY in_r_TDATA in_r_TLAST out_r_TVALID out_r_TREADY out_r_TDATA out_r_TLAST}
if {$v3} {lappend signals in_r_TKEEP in_r_TSTRB out_r_TKEEP out_r_TSTRB}
set cycles [expr {$v3 ? 15000 : 5000}]
# The generated testbench starts clock low, with rising edges at 4+8*k ns.
# Sample 1 ps before each rising edge, before nonblocking edge updates.
for {set k 0} {$k < $cycles} {incr k} {
 set ps [expr {3999+8000*$k}]
 set row [list $k $ps]
 foreach signal $signals {
  lappend row [get_value_database -radix unsigned -time ${ps}ps $base/$signal]
 }
 puts $f [join $row ,]
}
close $f
puts "CLOCK_BEFORE [get_value_database -time 3999ps $base/ap_clk] CLOCK_AFTER [get_value_database -time 4001ps $base/ap_clk]"
exit
