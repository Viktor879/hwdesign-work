"""Independent retained-evidence audit and explicit submission manifest.

--prepare writes new submission metadata only. --index checks the actual Git
index, without staging, committing, pushing or changing original tool outputs.
"""
from pathlib import Path
from bisect import bisect_left,bisect_right
import argparse,csv,hashlib,io,json,re,shutil,subprocess,tempfile
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
SUB=ROOT/'evidence/submission'
def sha(data):return hashlib.sha256(data).hexdigest()
def readcsv(p):return list(csv.DictReader((ROOT/p).open()))
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def selection():return json.loads((SUB/'selection.json').read_text())['files']
def raw_unchanged():
 p=Path('/tmp/qgemv-original-raw-sha256.json')
 if p.exists():
  values=json.loads(p.read_text())
  for path,digest in values.items():assert sha((ROOT/path).read_bytes())==digest,('Original raw evidence changed',path)
  return len(values)
 return None
class Trace:
 """Parse VCD transitions, then use binary-search pre-edge sampling.

 Independent of the production analyzer's timestamp-batch algorithm.
 """
 def __init__(self,path):
  self.series={};codes={};time=0;scope=[]
  with (ROOT/path).open() as f:
   for line in f:
    a=line.strip().split()
    if not a:continue
    if a[0]=='$scope':scope.append(a[2])
    elif a[0]=='$upscope':scope.pop()
    elif a[0]=='$var' and scope==['rtl_suite','dut']:
     codes[a[3]]=a[4];self.series[a[4]]=[]
    elif a[0].startswith('#'):time=int(a[0][1:])
    elif a[0].startswith('b') and len(a)==2 and a[1] in codes:self.series[codes[a[1]]].append((time,a[0][1:]))
    elif a[0][0] in '01xz' and a[0][1:] in codes:self.series[codes[a[0][1:]]].append((time,a[0][0]))
  self.times={n:[p[0] for p in a] for n,a in self.series.items()}
  self.edges=[t for t,v in self.series['ap_clk'] if v=='1']
  assert set(b-a for a,b in zip(self.edges,self.edges[1:]))=={8000}
 def value(self,n,t,after=False):
  i=(bisect_right if after else bisect_left)(self.times[n],t)-1
  return self.series[n][i][1] if i>=0 else 'x'
 def number(self,n,t,after=False):return int(self.value(n,t,after),2)
 def beat(self,port,t,after=False):
  return [self.number(port+'_'+n,t,after) for n in ['TDATA','TLAST','TKEEP','TSTRB']]
 def audit(self,cases):
  ins=[];outs=[];pending=None;address=[];statuses=[];status=[];stalled=0
  for t in self.edges:
   v=self.value('out_r_TVALID',t);r=self.value('out_r_TREADY',t)
   if pending is not None:assert v=='1' and self.beat('out_r',t)==pending,('held beat',t)
   pending=self.beat('out_r',t) if v=='1' and r=='0' else None
   if pending is not None:stalled+=1
   if self.value('in_r_TVALID',t)=='1' and self.value('in_r_TREADY',t)=='1':ins.append((t,self.beat('in_r',t)))
   if v=='1' and r=='1':outs.append((t,self.beat('out_r',t)))
   if self.value('s_axi_control_ARVALID',t)=='1' and self.value('s_axi_control_ARREADY',t)=='1':address.append(self.number('s_axi_control_ARADDR',t))
   if self.value('s_axi_control_RVALID',t)=='1' and self.value('s_axi_control_RREADY',t)=='1':
    assert address
    reg=address.pop(0);data=self.number('s_axi_control_RDATA',t)
    assert self.number('s_axi_control_RRESP',t)==0
    if reg in (0x10,0x20,0x30):
     assert reg==(0x10,0x20,0x30)[len(status)];status.append(data)
     if len(status)==3:statuses.append(status);status=[]
  withdrawals=0
  for t,val in self.series['out_r_TREADY']:
   if val=='0' and self.value('out_r_TREADY',t)=='1' and self.value('out_r_TVALID',t)=='1':
    assert self.value('out_r_TVALID',t,True)=='1' and self.beat('out_r',t)==self.beat('out_r',t,True),('READY withdrawal',t)
    withdrawals+=1
  assert [b for _,b in ins]==[w for c in cases for w in c['input'][:c['consumed']]]
  assert [b for _,b in outs]==[w for c in cases for w in c['output']]
  assert statuses==[c['status'] for c in cases]
  batches=[];ii=oo=0
  for c in cases:
   ci=ins[ii:ii+c['consumed']];co=outs[oo:oo+len(c['output'])]
   # Independently known CONFIG(13 words), PROCESS(35 words) layout in
   # the four measured fixtures; each has two 32-vector PROCESS commands.
   if c['name'].startswith('batch32_'):
    for k in range(2):
     start=ci[13+k*35+3][0];first=co[1+k*33+1][0];end=co[1+k*33+32][0]
     batches.append(dict(scenario=c['name'],command=k+1,first_input_ps=start,first_result_ps=first,final_result_ps=end,first_result_cycles=(first-start)//8000+1,batch_cycles=(end-start)//8000+1))
   # Decode complete successful commands independently from the input
   # encoding, checking accepted next headers against prior final output.
   ip=op=0;prior=None;configured=False
   while ip+3<=len(ci):
    h=c['input'][ip:ip+3];opcode=h[0][0];param=h[2][0]
    if any(w[0]>>32 or w[2:]!=[255,255] or w[1]!=(j==2) for j,w in enumerate(h)):break
    if opcode not in (1,2,3) or h[1][0]==0xffffffff:break
    if prior is not None:assert ci[ip][0]>prior
    if opcode==3:break
    if opcode==1 and param>15 or opcode==2 and (not 1<=param<=32 or not configured):break
    n=10 if opcode==1 else param;end=ip+3+n
    if end>len(ci) or any(w[1]!=(j==n-1) for j,w in enumerate(c['input'][ip+3:end])):break
    count=1 if opcode==1 else n+1
    assert op+count<=len(co) and co[op][0]>ci[end-1][0]
    prior=co[op+count-1][0]
    if end<len(ci):assert ci[end][0]>prior
    configured=True;ip=end;op+=count
   ii+=len(ci);oo+=len(co)
  return dict(input_transfers=len(ins),output_transfers=len(outs),statuses=len(statuses),stalled_cycles=stalled,ready_withdrawals_after_valid=withdrawals,batches=batches)
def science():
 spec=git('show','1adab28:cmdresp/takehome/prompt.md');assert spec==(ROOT/'prompt.md').read_bytes()
 report=(ROOT/'results.md').read_text()
 assert re.findall(r'^# (.+)$',report,re.M)==['Interface','Design','Targets','Verification','Assumptions','Open Items','Run History']
 assert 'Run 1 — retained historical FAIL' in report and '**Run 2, Specification v1' in report
 old=json.loads((ROOT/'evidence/artifact-sha256.json').read_text())
 for p,h in old.items():
  if p.startswith(('evidence/','fixtures/')):assert sha((ROOT/p).read_bytes())==h,p
 assert sha((ROOT/'evidence/run1-source/kernel.cpp').read_bytes())==old['src/kernel.cpp']
 intentional=[]
 for p,h in json.loads((ROOT/'evidence/run2/artifact-sha256.json').read_text()).items():
  if sha((ROOT/p).read_bytes())!=h:
   assert p in ('README.md','results.md'),p
   assert sha((ROOT/'evidence/run2/submission-baseline'/p).read_bytes())==h,('Historical document hash',p)
   intentional.append(p)
 cases=json.loads((ROOT/'fixtures/manifest.json').read_text());assert len(cases)==67
 # Re-execute the independent hand/NumPy checks in a scratch copy, preserving
 # all historical evidence and fixture bytes in the actual project.
 with tempfile.TemporaryDirectory(prefix='qgemv-submission-') as tmp:
  scratch=Path(tmp);(scratch/'scripts').mkdir();(scratch/'fixtures').mkdir();(scratch/'evidence/python').mkdir(parents=True)
  for n in ('model.py','fixtures.py','stress_fixtures.py'):shutil.copyfile(ROOT/'scripts'/n,scratch/'scripts'/n)
  proc=subprocess.run(['/home/cp4523/hwdesign/.venv/bin/python',str(scratch/'scripts/fixtures.py')],capture_output=True,text=True,check=True)
  py=json.loads((scratch/'evidence/python/checks.json').read_text())
  assert py==json.loads((ROOT/'evidence/run2/python/checks.json').read_text()) and py['hand_checks']==7 and py['numpy_int64_comparisons']==3200
  for n in ('cases.txt','manifest.json'):assert (scratch/'fixtures'/n).read_bytes()==(ROOT/'fixtures'/n).read_bytes()
  subprocess.run(['/home/cp4523/hwdesign/.venv/bin/python',str(scratch/'scripts/stress_fixtures.py')],check=True)
  assert (scratch/'fixtures/stress.txt').read_bytes()==(ROOT/'fixtures/stress.txt').read_bytes()
 for p,log in [('evidence/run2/csim/comparison.csv','evidence/run2/csim/qgemv_core_csim.log'),('evidence/run2/rtl/comparison.csv','evidence/run2/rtl/cosim.log')]:
  a=readcsv(p);assert len(a)==67 and 'PASS 67 activations' in (ROOT/log).read_text()
  for c,v in zip(cases,a):assert v['scenario']==c['name'] and v['result']=='PASS' and v['status']==':'.join(map(str,c['status'])),(p,c['name'])
 assert 'C/RTL co-simulation finished: PASS' in (ROOT/'evidence/run2/rtl/cosim.log').read_text()
 traces=[]
 for mode in range(5):
  log=(ROOT/f'evidence/run2/rtl/stress-{mode}.log').read_text();a=readcsv(f'evidence/run2/rtl/stress-{mode}.csv')
  names=re.findall(r'PASS mode='+str(mode)+r' scenario=(\S+)',log)
  assert names==[c['name'] for c in cases] and len(a)==67 and 'Fatal:' not in log and 'ERROR:' not in log
  for c,v in zip(cases,a):assert v['scenario']==c['name'] and v['result']=='PASS' and v['status']==':'.join(map(str,c['status']))
  data=Trace(f'evidence/run2/rtl/stress-{mode}.vcd').audit(cases)
  assert data['stalled_cycles']==sum(int(v['stalled_cycles']) for v in a)
  if mode<4:assert data['stalled_cycles']>0
  else:
   assert data['stalled_cycles']==0
   recorded=readcsv('evidence/run2/rtl/timing.csv');assert len(recorded)==len(data['batches'])==8
   for actual,claimed in zip(data['batches'],recorded):
    for key,value in actual.items():assert str(value)==claimed[key],(key,value,claimed[key])
    assert actual['batch_cycles']==80 and actual['first_result_cycles']==49 and float(claimed['cycles_per_vector'])==2.5
  traces.append(dict(mode=mode,activations=len(a),**data))
 errors=[]
 for i,c in enumerate(cases):
  if c['status'][0]:
   assert cases[i+1]['name']=='recovery_'+c['name'] and cases[i+1]['status']==[0,0,0]
   errors.append(c['name'])
 assert {c['status'][1] for c in cases}==set(range(8))
 for n in ['replacement','hand_0','hand_1','hand_2','hand_3','hand_4','hand_5','hand_6','reserved_count','unknown_reserved','payload_sidebands','count0','count33','count_negative','shift16','shift_negative','end_parameter','unconfigured']:
  assert any(c['name']==n for c in cases)
 x=ET.parse(ROOT/'evidence/run2/synthesis/qgemv_core_csynth.xml').getroot();clock=float(x.findtext('.//EstimatedClockPeriod'));assert clock==6.943
 loops={}
 for name in ('compute','receive'):
  text=(ROOT/f'evidence/run2/synthesis/qgemv_core_Pipeline_{name}_csynth.rpt').read_text()
  fields=next(v for v in text.splitlines() if re.search(r'\|-\s*'+name+r'\s*\|',v)).split('|')
  loops[name]=dict(II=int(fields[5]),depth=int(fields[4]));assert loops[name]['II']==1
 for n in ['qgemv_core.v','qgemv_core_control_s_axi.v','qgemv_core_regslice_both.v']:
  p=ROOT/'build_run2/solution1/syn/verilog'/n
  if p.exists():assert p.read_bytes()==(ROOT/'evidence/run2/synthesis'/n).read_bytes()
 assert (ROOT/'src/kernel.cpp').read_bytes()==(ROOT/'evidence/run2/diagnosis/final-source-before-clean-run.cpp').read_bytes()
 assert (ROOT/'src/rtl_stress.sv').read_bytes()==(ROOT/'evidence/run1-source/rtl_stress.sv').read_bytes()
 assert 'PASS RTL stress completed' in (ROOT/'evidence/run2/rtl/original-checker.log').read_text()
 assert 'VALID_WAIT' in (ROOT/'evidence/run2/diagnosis/original-0.log').read_text()
 assert 'STABILITY_WITHDRAW' in (ROOT/'evidence/run2/diagnosis/original-1.log').read_text()
 return dict(result='PASS',specification=1,prompt_sha256=sha(spec),run1_preserved_as='FAIL',run2_verified_as='PASS',python=py,python_reexecution_stdout=proc.stdout.strip(),c_scenarios=67,native_rtl_scenarios=67,integrated_rtl_scenarios=335,external_traces=traces,immediate_error_recoveries_per_mode=len(errors),synthesis_estimate_ns=clock,loops=loops,production_top='src/qgemv.sv',source_level_fix_and_wrapper_present=True,no_required_open_items=True,v2_necessary=False,intentional_packaging_document_updates=intentional,original_raw_files_checked_unchanged=raw_unchanged(),hardware_tools_rerun_for_submission=False,commit_or_push_performed=False)
def prepare():
 result=science();entries=selection();paths={v['path'] for v in entries}
 for document in ('results.md','README.md'):
  for path in re.findall(r'\]\(([^)#]+)(?:#[^)]*)?\)',(ROOT/document).read_text()):
   if not path.startswith('https://'):assert path in paths or git('ls-files','--',path).strip(),('Unstaged evidence dependency',document,path)
 result['reviewed_file_count']=len(entries)
 (SUB/'audit.json').write_text(json.dumps(result,indent=2)+'\n')
 sumspath='evidence/submission/SHA256SUMS';manifestpath='evidence/submission/staged-files.tsv'
 def sums(dummy=False):return ''.join(('0'*64 if dummy else sha((ROOT/p).read_bytes()))+'  '+p+'\n' for p in sorted(paths) if p!=sumspath)
 (ROOT/sumspath).write_text(sums(True))
 size=0
 for _ in range(10):
  text='path\tbytes\tpurpose\n'+''.join(v['path']+'\t'+str(size if v['path']==manifestpath else (ROOT/v['path']).stat().st_size)+'\t'+v['purpose']+'\n' for v in entries)
  new=len(text.encode())
  if size==new:break
  size=new
 else:raise AssertionError('Manifest size did not converge')
 (ROOT/manifestpath).write_text(text);(ROOT/sumspath).write_text(sums())
 for row in readcsv_tsv(manifestpath):assert int(row['bytes'])==(ROOT/row['path']).stat().st_size
 Path('/tmp/qgemv-submission-paths.nul').write_bytes(b''.join(v['path'].encode()+b'\0' for v in entries))
 print(json.dumps(dict(result='PASS',reviewed_files=len(entries),bytes=sum((ROOT/v['path']).stat().st_size for v in entries),stage_pathspec='/tmp/qgemv-submission-paths.nul')))
def readcsv_tsv(p):return list(csv.DictReader((ROOT/p).open(),delimiter='\t'))
def index_check():
 entries=selection();repo=Path(git('rev-parse','--show-toplevel').decode().strip());prefix=ROOT.relative_to(repo).as_posix()+'/'
 expected={prefix+v['path']:v for v in entries}
 actual=subprocess.check_output(['git','diff','--cached','--name-only','--no-relative','-z'],cwd=repo).decode().split('\0');actual={p for p in actual if p}
 assert actual==set(expected),('Index differs from explicit selection',actual^set(expected))
 payload=subprocess.check_output(['git','cat-file','--batch'],cwd=repo,input=''.join(':'+p+'\n' for p in sorted(actual)).encode());stream=io.BytesIO(payload);receipt=[]
 for path in sorted(actual):
  oid,kind,size=stream.readline().decode().strip().split();assert kind=='blob'
  data=stream.read(int(size));assert stream.read(1)==b'\n' and data==(repo/path).read_bytes(),path
  assert not re.search(r'/(build[^/]*|sim/tv|autotb|\.aws|__pycache__)/|\.(o|exe|wdb|pyc)$',path),path
  receipt.append(dict(path=expected[path]['path'],bytes=len(data),sha256=sha(data),git_blob=oid,purpose=expected[path]['purpose']))
 for line in (SUB/'SHA256SUMS').read_text().splitlines():
  digest,path=line.split('  ',1);assert sha((ROOT/path).read_bytes())==digest,path
 for row in readcsv_tsv('evidence/submission/staged-files.tsv'):assert int(row['bytes'])==(ROOT/row['path']).stat().st_size
 docs=[v['path'] for v in entries if v['path'].endswith('.md') or v['path'].endswith('.gitignore')]
 subprocess.run(['git','diff','--cached','--check','--',*docs],cwd=ROOT,check=True)
 subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
 assert not git('diff','--','prompt.md').strip();raw_unchanged()
 result=dict(result='PASS',staged_files=len(receipt),staged_bytes=sum(v['bytes'] for v in receipt),documentation_whitespace='PASS',original_raw_files_unchanged=True,unrelated_staged_paths=[],files=receipt,commit_or_push_performed=False)
 (SUB/'index-receipt.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:v for k,v in result.items() if k!='files'},indent=2))
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--index',action='store_true');args=parser.parse_args()
 index_check() if args.index else prepare()
