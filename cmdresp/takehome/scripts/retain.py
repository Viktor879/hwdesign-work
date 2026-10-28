"""Allowlist evidence copies: never copy a Vitis project or transaction tree."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1]
sol=root/'build_hls/solution1'
files={
 'csim/build/comparison.csv':'csim/comparison.csv',
 'csim/report/qgemv_csim.log':'csim/qgemv_csim.log',
 'sim/wrapc_pc/comparison.csv':'rtl/comparison.csv',
 'sim/report/qgemv_cosim.rpt':'rtl/qgemv_cosim.rpt',
 'sim/verilog/external.vcd':'rtl/external.vcd',
 'sim/qgemv_cosim_random_stall.json':'rtl/qgemv_cosim_random_stall.json',
 'syn/verilog/qgemv_control_s_axi.v':'synthesis/qgemv_control_s_axi.v',
}
for name in ['qgemv_csynth.rpt','qgemv_csynth.xml','qgemv_Pipeline_compute_csynth.rpt','qgemv_Pipeline_receive_csynth.rpt']:
 files['syn/report/'+name]='synthesis/'+name
for source,dest in files.items():shutil.copyfile(sol/source,root/'evidence'/dest)
print('Retained',len(files),'allowlisted reports and traces')
