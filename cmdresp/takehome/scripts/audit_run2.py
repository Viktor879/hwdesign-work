"""Audit actual final Run 2 evidence while retaining historical Run 1 FAIL."""
from pathlib import Path
import csv,json,re,hashlib,subprocess,xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
def rows(p):return list(csv.DictReader((root/p).open()))
def digest(p):return hashlib.sha256((root/p).read_bytes()).hexdigest()
required=['src/kernel.cpp','src/qgemv.hpp','src/qgemv.sv','src/tb.cpp','src/rtl_suite.sv','scripts/model.py','scripts/fixtures.py','scripts/run2.sh','fixtures/cases.txt','fixtures/stress.txt','README.md','results.md','evidence/run2/synthesis/qgemv_core_csynth.xml','evidence/run2/synthesis/integrated_utilization.rpt','evidence/run2/synthesis/integrated_timing.rpt','evidence/run2/rtl/qgemv_core_cosim.rpt','evidence/run2/diagnosis/original-0.log','evidence/run2/diagnosis/original-1.log']
for p in required:assert (root/p).is_file(),p
assert digest('src/kernel.cpp')==digest('evidence/run2/diagnosis/final-source-before-clean-run.cpp')
for p,h in json.loads((root/'evidence/artifact-sha256.json').read_text()).items():
 if p.startswith('evidence/') or p.startswith('fixtures/'):assert digest(p)==h,('Run 1 evidence changed',p)
assert digest('evidence/run1-source/kernel.cpp')==json.loads((root/'evidence/artifact-sha256.json').read_text())['src/kernel.cpp']
spec=subprocess.check_output(['git','show','1adab28:cmdresp/takehome/prompt.md'],cwd=root)
assert spec==(root/'prompt.md').read_bytes(),'prompt changed'
report=(root/'results.md').read_text()
assert re.findall(r'^# (.+)$',report,re.M)==['Interface','Design','Targets','Verification','Assumptions','Open Items','Run History']
assert '**Run 1, Specification v1**' in report and '**Run 2, Specification v1' in report
for path in re.findall(r'\]\(([^)]+)\)',report):
 if path!='evidence/run2/audit.json' and not path.startswith('https://'):assert (root/path.split('#')[0]).exists(),path
checks=json.loads((root/'evidence/run2/python/checks.json').read_text());assert checks['result']=='PASS' and checks['numpy_int64_comparisons']>=3200 and checks['hand_checks']>=7
cases=json.loads((root/'fixtures/manifest.json').read_text());assert len(cases)==67
for i,c in enumerate(cases):
 if c['status'][0]:assert cases[i+1]['name'].startswith('recovery_') and cases[i+1]['status']==[0,0,0]
for p in ['evidence/run2/csim/comparison.csv','evidence/run2/rtl/comparison.csv','evidence/run2/rtl/external_comparison.csv']:
 a=rows(p);assert len(a)==len(cases) and all(v['result']=='PASS' for v in a),p
for p in ['evidence/run2/rtl/word_comparison.csv','evidence/run2/rtl/command_order.csv']:
 a=rows(p);assert a and all(v['result']=='PASS' for v in a),p
assert 'C/RTL co-simulation finished: PASS' in (root/'evidence/run2/rtl/cosim.log').read_text()
x=ET.parse(root/'evidence/run2/synthesis/qgemv_core_csynth.xml').getroot();clock=float(x.findtext('.//EstimatedClockPeriod'));assert clock<10
resources={t:int(x.findtext('.//AreaEstimates/Resources/'+t)) for t in ['LUT','FF','DSP','BRAM_18K']}
loops={}
for label in ['compute','receive']:
 text=(root/f'evidence/run2/synthesis/qgemv_core_Pipeline_{label}_csynth.rpt').read_text()
 line=next(v for v in text.splitlines() if re.search(r'\|-\s*'+label+r'\s*\|',v));parts=[v.strip() for v in line.split('|')]
 loops[label]={'II':int(parts[5]),'depth':int(parts[4])};assert loops[label]['II']==1
integrated=(root/'evidence/run2/synthesis/integrated_utilization.rpt').read_text()
whole={}
for label in ['Slice LUTs','Slice Registers','DSPs','Block RAM Tile']:
 whole[label]=int(re.search(r'\|\s*'+re.escape(label)+r'\*?\s*\|\s*(\d+)',integrated).group(1))
assert all(str(n) in report for n in list(resources.values())+list(whole.values()))
stress=[]
for mode in range(5):
 a=rows(f'evidence/run2/rtl/stress-{mode}.csv');log=(root/f'evidence/run2/rtl/stress-{mode}.log').read_text()
 assert len(a)==67 and 'PASS RTL suite' in log and 'Fatal:' not in log and 'ERROR:' not in log
 assert (root/f'evidence/run2/rtl/stress-{mode}.vcd').is_file()
 for c,v in zip(cases,a):assert v['scenario']==c['name'] and v['result']=='PASS' and int(v['input_transfers'])==c['consumed'] and int(v['output_transfers'])==len(c['output']) and v['status']==':'.join(map(str,c['status']))
 totals={key:sum(int(v[key]) for v in a) for key in ['output_transfers','stalled_cycles','header_stalls','payload_stalls','tlast_stalls','after_valid_stalls']}
 if mode<4:assert totals['header_stalls']>0 and totals['payload_stalls']>0 and totals['tlast_stalls']>0
 if mode==1:assert totals['after_valid_stalls']==totals['output_transfers']
 if mode==4:assert totals['stalled_cycles']==0
 stress.append(dict(mode=mode,activations=len(a),**totals,result='PASS'))
(root/'evidence/run2/rtl/stress_summary.json').write_text(json.dumps(stress,indent=2)+'\n')
assert digest('src/rtl_stress.sv')==digest('evidence/run1-source/rtl_stress.sv')
assert 'PASS RTL stress completed' in (root/'evidence/run2/rtl/original-checker.log').read_text() and 'Fatal:' not in (root/'evidence/run2/rtl/original-checker.log').read_text()
assert 'VALID_WAIT' in (root/'evidence/run2/diagnosis/original-0.log').read_text()
assert 'STABILITY_WITHDRAW' in (root/'evidence/run2/diagnosis/original-1.log').read_text()
timing=rows('evidence/run2/rtl/timing.csv');assert len(timing)>=4 and all(float(v['cycles_per_vector'])<=32 and v['result']=='PASS' for v in timing)
assert all(float(v['clock_ns'])==8 for v in timing)
for p in ['qgemv_core.v','qgemv_core_control_s_axi.v','qgemv_core_regslice_both.v']:
 assert digest('evidence/run2/synthesis/'+p)==digest('build_run2/solution1/syn/verilog/'+p),('generated RTL changed',p)
maptext=(root/'evidence/run2/synthesis/qgemv_core_control_s_axi.v').read_text()
for offset,label in [('0x10','halted'),('0x20','error'),('0x30','tx_id')]:assert offset+' : Data signal of '+label in maptext
wrapper=(root/'src/qgemv.sv').read_text();assert 'out_r_TVALID && out_r_TREADY' in wrapper and not re.search(r'\b(force|release)\b',wrapper)
assert not any(v in wrapper for v in ['TUSER','TDEST','TID'])
candidates=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=root,text=True).splitlines()
staged=subprocess.check_output(['git','diff','--cached','--name-only'],cwd=root,text=True).splitlines()
for p in candidates+staged:
 assert not re.search(r'(^|/)(build|build_hls|build_run2|build_probe|build_repro_run1)(/|$)|/sim/tv/|autotb',p),p
 assert not p.startswith(('.aws/','.codex/auth.json')),p
summary=dict(run=2,specification=1,overall='PASS',production_top='src/qgemv.sv',prompt_unchanged=True,prompt_sha256=hashlib.sha256(spec).hexdigest(),run1_evidence_preserved=True,generated_rtl_unmodified=True,clock_estimate_ns=clock,loops=loops,hls_resources=resources,whole_vivado_resources=whole,c_activations=len(cases),native_core_rtl_activations=len(cases),integrated_rtl_activations=sum(e['activations'] for e in stress),external_modes=stress,measured_batches=len(timing),first_result_cycles=timing[0]['first_result_cycles'],batch_cycles=timing[0]['batch_cycles'],cycles_per_vector=timing[0]['cycles_per_vector'],all_report_paths_resolve=True,generated_trees_excluded=True,no_required_open_items=True,v2_needed=False,commit_status='Uncommitted; no automatic commit/push')
(root/'evidence/run2/audit.json').write_text(json.dumps(summary,indent=2)+'\n')
paths=required+['evidence/run2/rtl/stress_summary.json','evidence/run2/rtl/timing.csv','evidence/run2/rtl/comparison.csv']+[f'evidence/run2/rtl/stress-{m}.vcd' for m in range(5)]
(root/'evidence/run2/artifact-sha256.json').write_text(json.dumps({p:digest(p) for p in paths},indent=2)+'\n')
(root/'evidence/run2/git-candidates.txt').write_text('\n'.join(candidates)+'\n')
print(json.dumps(summary,indent=2))
