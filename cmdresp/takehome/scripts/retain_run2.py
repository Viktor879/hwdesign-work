"""Allowlisted native Run 2 evidence; no simulator transaction trees."""
from pathlib import Path
import shutil
root=Path(__file__).resolve().parents[1];sol=root/'build_run2/solution1';dest=root/'evidence/run2'
files={'csim/build/comparison.csv':'csim/comparison.csv','csim/report/qgemv_core_csim.log':'csim/qgemv_core_csim.log','sim/wrapc_pc/comparison.csv':'rtl/comparison.csv','sim/report/qgemv_core_cosim.rpt':'rtl/qgemv_core_cosim.rpt','syn/verilog/qgemv_core_control_s_axi.v':'synthesis/qgemv_core_control_s_axi.v','syn/verilog/qgemv_core.v':'synthesis/qgemv_core.v','syn/verilog/qgemv_core_regslice_both.v':'synthesis/qgemv_core_regslice_both.v'}
for filename in ['qgemv_core_csynth.rpt','qgemv_core_csynth.xml','qgemv_core_Pipeline_compute_csynth.rpt','qgemv_core_Pipeline_receive_csynth.rpt']:
 files['syn/report/'+filename]='synthesis/'+filename
for source,target in files.items():shutil.copyfile(sol/source,dest/target)
print('Retained',len(files),'native reports/RTL files')
