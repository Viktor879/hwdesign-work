"""Measure accepted external RTL transfers. Samples PRE-edge values, never a timing model."""
import csv,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=Path(sys.argv[1]) if len(sys.argv)>1 else root/'evidence/rtl/external.vcd'
p=p.resolve()
names={}; vals={}; changes={}; events=[]; rises=[];samples=[];timestamp=0
# The capture has only top-level DUT ports. At a clock edge, handshake uses
# the values before that timestamp's delta-cycle updates.
def flush():
 global changes
 clk=names.get('ap_clk')
 if clk and vals.get(clk)=='0' and changes.get(clk)=='1':
  rises.append(timestamp)
  sample={name:vals.get(code,'x') for name,code in names.items()}
  samples.append((timestamp,sample))
  for port in ['in_r','out_r']:
   if sample[port+'_TVALID']=='1' and sample[port+'_TREADY']=='1':
    events.append(dict(time_ps=timestamp,port=port,data=int(sample[port+'_TDATA'],2),last=int(sample[port+'_TLAST'],2),keep=int(sample[port+'_TKEEP'],2),strb=int(sample[port+'_TSTRB'],2)))
 vals.update(changes);changes={}
with p.open() as f:
 for line in f:
  line=line.strip()
  if line.startswith('$var'):
   a=line.split();names[a[4]]=a[3]
  elif line.startswith('#'):
   flush();timestamp=int(line[1:])
  elif line.startswith('b'):
   v,c=line[1:].split();changes[c]=v
  elif line and line[0] in '01xz':changes[line[1:]]=line[0]
flush()
periods=[b-a for a,b in zip(rises,rises[1:])];assert periods and len(set(periods))==1
period=periods[0];assert period==8000
ins=[e for e in events if e['port']=='in_r'];outs=[e for e in events if e['port']=='out_r']
cases=json.loads((root/'fixtures/manifest.json').read_text());ii=oo=0;timing=[];order=[];comparisons=[];words=[]
for c in cases:
 ci=ins[ii:ii+c['consumed']];co=outs[oo:oo+len(c['output'])]
 assert len(ci)==c['consumed'] and len(co)==len(c['output']),c['name']
 for index,(actual,expected) in enumerate(zip(ci+co,c['input'][:c['consumed']]+c['output'])):
  assert [actual[k] for k in ['data','last','keep','strb']]==expected,(c['name'],actual,expected)
  words.append(dict(scenario=c['name'],port=actual['port'],index=index,time_ps=actual['time_ps'],expected_data=expected[0],actual_data=actual['data'],expected_last=expected[1],actual_last=actual['last'],expected_keep=expected[2],actual_keep=actual['keep'],expected_strb=expected[3],actual_strb=actual['strb'],result='PASS'))
 comparisons.append(dict(scenario=c['name'],input_transfers=len(ci),output_transfers=len(co),result='PASS'))
 # Walk complete successful commands. A failed header/payload has no output.
 ip=op=0;previous=None;command=0
 while ip+3<=len(ci):
  h=c['input'][ip:ip+3];opcode=h[0][0];n=h[2][0]
  if opcode not in (1,2,3):break
  if any(w[0]>>32 or w[2:]!=[255,255] or w[1]!=(k==2) for k,w in enumerate(h)):break
  if h[1][0]==0xffffffff:break
  if opcode==3:break
  count=10 if opcode==1 else n
  if (opcode==1 and n>15) or (opcode==2 and not 1<=n<=32):break
  if ip+3+count>len(ci):break
  payload=ci[ip+3:ip+3+count]
  if any(w['last']!=(k==count-1) for k,w in enumerate(payload)):break
  outcount=1 if opcode==1 else n+1
  if op+outcount>len(co):break
  response=co[op:op+outcount]
  assert response[0]['time_ps']>payload[-1]['time_ps'],c['name']
  if previous is not None:assert ci[ip]['time_ps']>previous,c['name']
  next_ip=ip+3+count
  next_time=ci[next_ip]['time_ps'] if next_ip<len(ci) else None
  if next_time is not None:assert next_time>response[-1]['time_ps'],(c['name'],'prefetch')
  order.append(dict(scenario=c['name'],command=command,opcode=opcode,payload_end_ps=payload[-1]['time_ps'],response_start_ps=response[0]['time_ps'],response_end_ps=response[-1]['time_ps'],next_header_ps=next_time,result='PASS'))
  if opcode==2 and n==32:
   start=payload[0]['time_ps'];first=response[1]['time_ps'];end=response[-1]['time_ps']
   def cycles(a,b):return (b-a)//period+1
   assert all(b['time_ps']-a['time_ps']==period for a,b in zip(payload,payload[1:])), 'input stall'
   output_spacing=sorted(set((b['time_ps']-a['time_ps'])//period for a,b in zip(response[1:],response[2:])))
   for t,s in samples:
    if start<=t<=end:
     assert not(s['out_r_TVALID']=='1' and s['out_r_TREADY']!='1'),'backpressure in measured batch'
   full=cycles(start,end)
   timing.append(dict(scenario=c['name'],command=command,nvec=n,first_input_ps=start,first_result_ps=first,final_result_ps=end,clock_ns=period/1000,output_spacing_cycles=';'.join(map(str,output_spacing)),first_result_cycles=cycles(start,first),batch_cycles=full,cycles_per_vector=full/n,first_result_ns=cycles(start,first)*period/1000,batch_ns=full*period/1000,result='PASS' if full/n<=32 else 'FAIL'))
  previous=response[-1]['time_ps'];ip=next_ip;op+=outcount;command+=1
 ii+=len(ci);oo+=len(co)
assert ii==len(ins) and oo==len(outs),(ii,len(ins),oo,len(outs))
assert len(timing)>=4
outdir=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root/'evidence/rtl'
outdir.mkdir(parents=True,exist_ok=True)
def write(name,rows):
 with (outdir/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
write('word_comparison.csv',words);write('handshakes.csv',events);write('external_comparison.csv',comparisons);write('command_order.csv',order);write('timing.csv',timing)
(outdir/'measurement.json').write_text(json.dumps(dict(source=str(p.relative_to(root)),clock_ps=period,activations=len(cases),input_transfers=len(ins),output_transfers=len(outs),measured_batches=len(timing),pre_edge_sampling=True,result='PASS'),indent=2)+'\n')
print(json.dumps(timing,indent=2))
