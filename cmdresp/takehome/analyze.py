"""Analyze retained RTL transfers and synthesis reports (no timing model)."""
import csv
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    cases=json.loads(Path('data/cases.json').read_text())
    samples=list(csv.DictReader(open('evidence/rtl_cycles.csv')))
    transfers={p:[r for r in samples if r[p+'_valid']=='1' and r[p+'_ready']=='1'] for p in ['in','out']}
    metrics=[];trace_checks=[];offset={'in':0,'out':0}
    for c in cases:
        groups={}
        for p,field in [('in','ins'),('out','outs')]:
            n=len(c[field]);start=offset[p];rows=transfers[p][start:start+n];offset[p]+=n
            actual=[(int(r[p+'_data']) & ((1<<64)-1),int(r[p+'_last'])) for r in rows]
            assert actual==[tuple(w) for w in c[field]],(c['name'],p,actual,c[field])
            groups[p]=rows
        trace_checks.append({'scenario':c['name'],'input_words':len(groups['in']),'output_words':len(groups['out']),'status':'PASS'})
        if c['error']:continue
        ii=oi=0
        while ii<len(c['ins']):
            cmd=c['ins'][ii][0];tx=c['ins'][ii+1][0];param=c['ins'][ii+2][0];ii+=3
            if cmd==3:break
            if cmd==1:ii+=10;oi+=1;continue
            start=int(groups['in'][ii]['cycle'])
            first=int(groups['out'][oi+1]['cycle']);last=int(groups['out'][oi+param]['cycle'])
            cycles=last-start+1
            # Check absence of external stalls over measured PROCESS interval.
            # Data must be available whenever the DUT is ready to accept payload.
            input_end=int(groups['in'][ii+param-1]['cycle'])
            input_gaps=[int(r['cycle']) for r in samples if start<=int(r['cycle'])<=input_end and r['in_ready']=='1' and r['in_valid']!='1']
            output_stalls=[int(r['cycle']) for r in samples if start<=int(r['cycle'])<=last and r['out_valid']=='1' and r['out_ready']!='1']
            assert not input_gaps and not output_stalls,(c['name'],input_gaps,output_stalls)
            metrics.append(dict(scenario=c['name'],tx_id=tx,nvec=param,first_input_cycle=start,first_output_cycle=first,last_output_cycle=last,first_output_latency_inclusive=first-start+1,batch_cycles_inclusive=cycles,cycles_per_vector=cycles/param,vectors_per_second_at_8ns=param/(cycles*8e-9),external_stalls=0,target_status='PASS' if param==32 and cycles/param<=32 else ('FAIL' if param==32 else 'no target')))
            ii+=param;oi+=1+param
    for p in ['in','out']:assert offset[p]==len(transfers[p]),(p,offset[p],len(transfers[p]))
    for name,rows in [('rtl_protocol_checks',trace_checks),('rtl_process_timing',metrics)]:
        with open('evidence/'+name+'.csv','w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    top=ET.parse('qgemv_hls/solution1/syn/report/qgemv_csynth.xml').getroot()
    compute=ET.parse('qgemv_hls/solution1/syn/report/qgemv_Pipeline_compute_csynth.xml').getroot()
    synth=dict(clock_ns=float(top.findtext('.//EstimatedClockPeriod')),resources={n:int(top.findtext('.//AreaEstimates/Resources/'+n)) for n in ['LUT','FF','DSP','BRAM_18K']},compute_II=int(compute.findtext('.//compute/PipelineII')),compute_depth=int(compute.findtext('.//compute/PipelineDepth')))
    report=Path('qgemv_hls/solution1/syn/report/qgemv_Pipeline_compute_csynth.rpt').read_text()
    instances=[line for line in report.splitlines() if re.match(r'\s*\|(?:mul_8s|mac_muladd_)',line)]
    synth['multiply_instances']=len(instances)
    synth['fabric_multiply_instances']=sum('mac_muladd_' not in line for line in instances)
    synth['dsp_multiply_add_instances']=sum('mac_muladd_' in line for line in instances)
    assert synth['multiply_instances']==64
    Path('evidence/synthesis_summary.json').write_text(json.dumps(synth,indent=2))
    for phase in ['csim','rtl']:
        rows=list(csv.DictReader(open('evidence/'+phase+'_comparison.csv')))
        assert len(rows)==len(cases)
        for c,r in zip(cases,rows):
            assert r['scenario']==c['name'] and r['status']=='PASS'
            assert [int(r[k]) for k in ['halted','error','tx_id','words']]==[c['halted'],c['error'],c['tx_id'],len(c['outs'])]
    print(json.dumps(synth,indent=2))
    print('PASS: exact accepted RTL input/output transfers, framing, counts, and C/RTL status comparisons for all',len(cases),'activations')
    for m in metrics:
        if m['nvec']==32:print(m)
if __name__=='__main__':main()
