set root [file dirname [file normalize [info script]]]
cd $root
set v3 [expr {[info exists ::env(QGEMV_VERSION)] && $::env(QGEMV_VERSION) eq "v3"}]
set project [expr {$v3 ? "qgemv_hls_v3" : "qgemv_hls"}]
set data [expr {$v3 ? "$root/data/v3" : "$root/data"}]
set evidence [expr {$v3 ? "$root/evidence/v3" : "$root/evidence"}]
set version_arg [expr {$v3 ? "v3" : "v2"}]
open_project $project
set_top qgemv
add_files qgemv.cpp -cflags "-I."
add_files -tb tb.cpp -cflags "-I."
open_solution solution1 -flow_target vivado
set_part {xc7z020clg484-1}
create_clock -period 8
if {$::env(QGEMV_STAGE) eq "csim"} {
 csim_design -argv "$data/cases.txt $evidence/csim_comparison.csv $version_arg"
} else {
 csynth_design
 cosim_design -argv "$data/cases.txt $evidence/rtl_comparison.csv $version_arg" -trace_level all -tool xsim
}
exit
