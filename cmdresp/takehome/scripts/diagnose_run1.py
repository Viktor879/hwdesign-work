"""Reproducible, pre-edge extraction of actual Run 1 pending-output signals."""
from pathlib import Path
import csv,json
from vcdvcd import VCDVCD
root=Path(__file__).resolve().parents[1]
v=VCDVCD(str(root/'evidence/run2/diagnosis/run1-reproduction.vcd'))
prefix='rtl_stress.dut.'
names=['out_r_TVALID','out_r_TREADY','grp_qgemv_Pipeline_compute_fu_631.ap_enable_reg_pp0_iter10','grp_qgemv_Pipeline_compute_fu_631.ap_block_pp0_stage0_11001_grp1']
def before(name,t):
 value='x'
 for time,val in v[prefix+name].tv:
  if time>=t:break
  value=val
 return value
rows=[]
for time in range(1404000,1744001,8000):
 row=dict(time_ps=time,cycle_1based=(time-4000)//8000+1)
 row.update({name:before(name,time) for name in names});rows.append(row)
with (root/'evidence/run2/diagnosis/run1-cycles.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
assert before(names[2],1524000)=='1' and before(names[0],1524000)=='0' and before(names[1],1524000)=='0'
(root/'evidence/run2/diagnosis/diagnosis.md').write_text('''Run 1 reproduction uses the original compiled native qgemv snapshot at build/stress, with the original external-pin testbench. Command: cd build/stress; /eda/xilinx/2026.1/Vivado/bin/xsim stress -tclbatch ../../scripts/reproduce_run1.tcl. The supplied Tcl adds only waveform probes, no design/stimulus changes. Raw log: reproduction.log; raw trace: run1-reproduction.vcd; pre-edge samples: run1-cycles.csv.

The PROCESS response header transfers at 1420 ns. READY is withdrawn at 1424 ns, before any result is available. At 1516 ns the compute pipeline's ap_enable_reg_pp0_iter10 becomes 1, indicating the result is pending at its output stage. The first subsequent sampled rising edge is 1524 ns (cycle 191, numbering the first edge at 4 ns as cycle 1). It observes iter10=1, READY=0, block=1, VALID=0. The result remains pending until the test aborts at 1744 ns; this is a genuine dependency, not a false assertion during computation.

The retained generated compute RTL defines block = !READY && iter10 and VALID = !block && iter10, algebraically VALID = READY && iter10. Thus dropping READY after VALID is asserted can also drop VALID with a pending beat. The Run 1 test did not actually cover this second situation: it withdrew READY before the first result's VALID, and after accepting the two response headers. It also did not hold READY low before the first CONFIG response. Its stability assertion hardcoded TLAST=1 and therefore was insufficient for multi-vector payloads. Run 2 corrects these coverage gaps rather than treating old PASS checks as proof.
''')
print('Confirmed genuine dependency: pending result at cycle 191 / 1524 ns; original abort 1744 ns')
