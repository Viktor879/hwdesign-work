open_project build_hls
open_solution solution1
cosim_design -argv "[file normalize fixtures/cases.txt]" -trace_level port -tool xsim
exit
