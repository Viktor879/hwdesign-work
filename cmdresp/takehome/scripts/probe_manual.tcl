open_project -reset build_probe
set_top manual
add_files [file normalize evidence/run2/diagnosis/manual.cpp]
add_files -tb [file normalize evidence/run2/diagnosis/manual_tb.cpp]
open_solution solution1
set_part xc7z020clg484-1
create_clock -period 8
csim_design
csynth_design
cosim_design -trace_level port
exit
