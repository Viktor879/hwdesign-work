"""Analyze retained RTL transfers and synthesis reports (no timing model)."""
import os
import csv
import json
import re
from pathlib import Path
import xml.etree.ElementTree as ET

def main():
    v3 = os.environ.get('QGEMV_VERSION') == 'v3'
    data = Path('data/v3' if v3 else 'data')
    evidence = Path('evidence/v3' if v3 else 'evidence')
    project = Path('qgemv_hls_v3' if v3 else 'qgemv_hls')
    cases=json.loads((data/'cases.json').read_text())
    samples=list(csv.DictReader(open(evidence/'rtl_cycles.csv')))
    transfers={p:[r for r in samples if r[p+'_valid']=='1' and r[p+'_ready']=='1'] for p in ['in','out']}
    metrics=[];trace_checks=[];sequencing=[];offset={'in':0,'out':0}
    for c in cases:
        groups={}
        for p,field in [('in','ins'),('out','outs')]:
            n=len(c[field]);start=offset[p];rows=transfers[p][start:start+n];offset[p]+=n
            actual=[(int(r[p+'_data']) & ((1<<64)-1),int(r[p+'_last'])) for r in rows]
            assert actual==[tuple(w[:2]) for w in c[field]],(c['name'],p,actual,c[field])
            if v3:
                enables=[(int(r[p+'_keep']),int(r[p+'_strb'])) for r in rows]
                expected=[tuple(w[2:]) for w in c[field]] if p=='in' else [(255,255)]*n
                assert enables==expected,(c['name'],p,'byte enables',enables,expected)
            groups[p]=rows
        trace_checks.append({'scenario':c['name'],'input_words':len(groups['in']),'output_words':len(groups['out']),'status':'PASS'})
        if v3:
            # Parse only successful commands before the offending command.  Their
            # complete outputs must precede accepting any subsequent header.
            ii=oi=0
            while ii<len(c['ins']) and oi<len(c['outs']):
                cmd=c['ins'][ii][0];param=c['ins'][ii+2][0]
                n=10 if cmd==1 else param
                o=1 if cmd==1 else 1+param
                payload_end=int(groups['in'][ii+3+n-1]['cycle'])
                response_start=int(groups['out'][oi]['cycle'])
                response_end=int(groups['out'][oi+o-1]['cycle'])
                next_header=int(groups['in'][ii+3+n]['cycle'])
                assert response_start>payload_end,(c['name'],'response before validation')
                assert next_header>response_end,(c['name'],'next header before response completion',next_header,response_end)
                sequencing.append(dict(scenario=c['name'],command_index=ii,opcode=cmd,
                    payload_end=payload_end,response_start=response_start,response_end=response_end,
                    next_header=next_header,status='PASS'))
                ii+=3+n;oi+=o
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
        with open(evidence/(name+'.csv'),'w') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    top=ET.parse(project/'solution1/syn/report/qgemv_csynth.xml').getroot()
    compute=ET.parse(project/'solution1/syn/report/qgemv_Pipeline_compute_csynth.xml').getroot()
    synth=dict(clock_ns=float(top.findtext('.//EstimatedClockPeriod')),resources={n:int(top.findtext('.//AreaEstimates/Resources/'+n)) for n in ['LUT','FF','DSP','BRAM_18K']},compute_II=int(compute.findtext('.//compute/PipelineII')),compute_depth=int(compute.findtext('.//compute/PipelineDepth')))
    report=(project/'solution1/syn/report/qgemv_Pipeline_compute_csynth.rpt').read_text()
    instances=[line for line in report.splitlines() if re.match(r'\s*\|(?:mul_8s|mac_muladd_)',line)]
    synth['multiply_instances']=len(instances)
    synth['fabric_multiply_instances']=sum('mac_muladd_' not in line for line in instances)
    synth['dsp_multiply_add_instances']=sum('mac_muladd_' in line for line in instances)
    assert synth['multiply_instances']==64
    (evidence/'synthesis_summary.json').write_text(json.dumps(synth,indent=2))
    for phase in ['csim','rtl']:
        rows=list(csv.DictReader(open(evidence/(phase+'_comparison.csv'))))
        assert len(rows)==len(cases)
        for c,r in zip(cases,rows):
            assert r['scenario']==c['name'] and r['status']=='PASS'
            assert [int(r[k]) for k in ['halted','error','tx_id','words']]==[c['halted'],c['error'],c['tx_id'],len(c['outs'])]
    if v3:
        receive=ET.parse(project/'solution1/syn/report/qgemv_Pipeline_receive_csynth.xml').getroot()
        synth['receive_II']=int(receive.findtext('.//receive/PipelineII'))
        (evidence/'synthesis_summary.json').write_text(json.dumps(synth,indent=2))
        with (evidence/'rtl_sequencing.csv').open('w') as f:
            w=csv.DictWriter(f,fieldnames=list(sequencing[0]));w.writeheader();w.writerows(sequencing)
        assert synth['compute_II']==1 and synth['receive_II']==1
        print('PASS complete validation before response and external sequential command acceptance:',len(sequencing),'commands')
    print(json.dumps(synth,indent=2))
    print('PASS: exact accepted RTL input/output transfers, framing, counts, and C/RTL status comparisons for all',len(cases),'activations')
    for m in metrics:
        if m['nvec']==32:print(m)
if __name__=='__main__':main()
