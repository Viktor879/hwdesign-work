open_project -reset build_repro_run1
set_top qgemv
add_files [file normalize evidence/run1-source/kernel.cpp] -cflags "-I[file normalize src]"
open_solution solution1
set_part xc7z020clg484-1
create_clock -period 8
csynth_design
exit
