open_project -reset build_probe
set_top direct
add_files [file normalize evidence/run2/diagnosis/direct.cpp]
open_solution solution1
set_part xc7z020clg484-1
create_clock -period 8
csynth_design
exit
