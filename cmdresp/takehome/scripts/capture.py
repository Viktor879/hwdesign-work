"""Attach a port-only VCD capture before xelab finishes; no RTL changes."""
from pathlib import Path
import time
p=Path('build_hls/solution1/sim/verilog/qgemv.tcl')
start=time.time_ns()
while True:
    if p.exists() and p.stat().st_mtime_ns>start:
        s=p.read_text()
        log=next((v for v in s.splitlines() if v.startswith('log_wave ')),None)
        if log and 'run all\nquit' in s:
            s='open_vcd external.vcd\n'+log.replace('log_wave','log_vcd',1)+'\n'+s.replace('run all\nquit','run all\nclose_vcd\nquit')
            p.write_text(s)
            Path('evidence/rtl/capture.tcl').write_text(s)
            break
    if time.time_ns()-start>600_000_000_000: raise TimeoutError('No generated simulator Tcl')
    time.sleep(.1)
