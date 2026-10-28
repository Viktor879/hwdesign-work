open_project -reset build_run2
set_top qgemv_core
add_files [file normalize src/kernel.cpp] -cflags "-Isrc"
add_files -tb [file normalize src/tb.cpp] -cflags "-Isrc"

open_solution solution1
set_part xc7z020clg484-1
create_clock -period 8
csim_design -argv "[file normalize fixtures/cases.txt]"
file copy -force build_run2/solution1/csim/build/comparison.csv evidence/run2/csim/comparison.csv
csynth_design
exit
