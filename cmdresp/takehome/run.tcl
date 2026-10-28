set root [file dirname [file normalize [info script]]]
cd $root
open_project qgemv_hls
set_top qgemv
add_files qgemv.cpp -cflags "-I."
add_files -tb tb.cpp -cflags "-I."
open_solution solution1 -flow_target vivado
set_part {xc7z020clg484-1}
create_clock -period 8
if {$::env(QGEMV_STAGE) eq "csim"} {
 csim_design -argv "$root/data/cases.txt $root/evidence/csim_comparison.csv"
} else {
 csynth_design
 cosim_design -argv "$root/data/cases.txt $root/evidence/rtl_comparison.csv" -trace_level all -tool xsim
}
exit
