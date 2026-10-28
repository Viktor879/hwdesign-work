open_wave_database qgemv_hls/solution1/sim/verilog/qgemv.wdb
foreach cmd {get_value_database get_wave_objects get_waveforms get_wave_data} {
 catch "$cmd -help" msg
 puts "$cmd HELP: $msg"
}
puts "COMMANDS [info commands *wave*]"
exit
