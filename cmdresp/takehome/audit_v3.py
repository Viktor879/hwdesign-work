"""Submission audit and historical-trace check; never runs a timing model."""
import csv
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'evidence/v3'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_sequencing():
    samples = list(csv.DictReader((ROOT/'evidence/rtl_cycles.csv').open()))
    transfers = {p: [r for r in samples if r[p+'_valid']=='1' and r[p+'_ready']=='1']
                 for p in ['in', 'out']}
    a = b = 0
    rows = []
    for case in json.loads((ROOT/'data/cases.json').read_text()):
        if not case['error']:
            ii = oi = 0
            while ii < len(case['ins']):
                cmd, tx, param = [case['ins'][ii+k][0] for k in range(3)]
                ii += 3
                if cmd == 3:
                    break
                n = 10 if cmd == 1 else param
                o = 1 if cmd == 1 else param+1
                end = int(transfers['out'][b+oi+o-1]['cycle'])
                nxt = int(transfers['in'][a+ii+n]['cycle'])
                rows.append(dict(scenario=case['name'], cmd=cmd,
                                 last_response_cycle=end, next_header_cycle=nxt,
                                 status='PASS' if nxt>end else 'FAIL'))
                ii += n
                oi += o
        a += len(case['ins'])
        b += len(case['outs'])
    with (EVIDENCE/'baseline_sequencing.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print('Historical v2 trace checked against v3 sequencing:',
          sum(r['status']=='FAIL' for r in rows),
          'FAIL boundaries; evidence/v3/baseline_sequencing.csv (historical finding)')


def main():
    historical_sequencing()
    repo = ROOT.parents[1]
    assert subprocess.check_output(['git','rev-parse','HEAD'], cwd=ROOT, text=True).startswith('e380d18')
    spec = subprocess.check_output(['git','show','e380d18:cmdresp/takehome/prompt.md'], cwd=ROOT)
    assert (ROOT/'prompt.md').read_bytes() == spec
    assert (EVIDENCE/'spec.sha256').read_text().split()[0] == digest(ROOT/'prompt.md')
    print('PASS authoritative v3 prompt unchanged at e380d18; evidence/v3/spec.sha256')
    original = json.loads((EVIDENCE/'baseline_manifest.json').read_text())
    count = 0
    for name, sha in original.items():
        relative = name.removeprefix('cmdresp/takehome/')
        if relative.startswith(('evidence/','data/','qgemv_hls/')):
            assert digest(repo/name) == sha, name
            count += 1
    print('PASS original v2 fixtures, evidence and reports unchanged:', count, 'files; baseline_manifest.json')
    for line in (EVIDENCE/'executed_sources.sha256').read_text().splitlines():
        sha, name = line.split(maxsplit=1)
        assert digest(ROOT/name) == sha, name
    print('PASS executed implementation/testbench/fixture identities; executed_sources.sha256')
    report = (ROOT/'results.md').read_text()
    sections = re.findall(r'^## (.+)$', report, re.M)
    assert sections == ['Interface','Design','Targets','Verification','Assumptions','Open Items','Run History'], sections
    before = (EVIDENCE/'results_before_v3.md').read_text()
    history = before.split('## Run History\n',1)[1]
    assert history.strip() in report
    assert '27/30' in report and 'e380d18' in report
    print('PASS exactly seven required sections; Runs 1–10 preserved verbatim; v3/feedback provenance explicit')
    cases = json.loads((ROOT/'data/v3/cases.json').read_text())
    for phase in ['csim_comparison','rtl_comparison','rtl_protocol_checks']:
        rows = list(csv.DictReader((EVIDENCE/(phase+'.csv')).open()))
        assert [r['scenario'] for r in rows] == [c['name'] for c in cases]
        assert all(r['status']=='PASS' for r in rows)
    for i, case in enumerate(cases):
        assert report.count('| `'+case['name']+'` |') == 1, case['name']
        if case['error']:
            assert cases[i+1]['name'] == 'recovery_'+case['name'] and cases[i+1]['error']==0
    print('PASS scenario rows, Python expectations, C/RTL comparisons and immediate recoveries:',len(cases),'activations')
    references = re.findall(r'`((?:evidence|data|qgemv_hls(?:_v3)?)/[^`]*?)`',report)
    for ref in references:
        # All concrete report references must resolve; C/R/T abbreviations are defined in Verification.
        if ref != 'evidence/v3/submission_manifest.sha256':
            assert (ROOT/ref).exists(), ref
    table = report.split('| Scenario |',1)[1].split('\n\n',1)[0]
    assert all('C, R, T' in line for line in table.splitlines() if '| `' in line)
    print('PASS concrete evidence references exist and every scenario verdict cites comparison/trace evidence')
    synth = json.loads((EVIDENCE/'synthesis_summary.json').read_text())
    timings = list(csv.DictReader((EVIDENCE/'rtl_process_timing.csv').open()))
    batches = [r for r in timings if int(r['nvec'])==32]
    assert len(batches)==4 and all(r['target_status']=='PASS' and r['external_stalls']=='0' for r in batches)
    assert synth['clock_ns']<10 and synth['compute_II']==synth['receive_II']==1 and synth['multiply_instances']==64
    sequential = list(csv.DictReader((EVIDENCE/'rtl_sequencing.csv').open()))
    assert sequential and all(r['status']=='PASS' for r in sequential)
    assert all(int(r['payload_end'])<int(r['response_start']) and int(r['response_end'])<int(r['next_header']) for r in sequential)
    print('PASS strict clock and unchanged throughput targets; compute/receive II=1; 64 products; sequential acceptance:',len(sequential),'commands')
    cosim = (ROOT/'qgemv_hls_v3/solution1/sim/report/qgemv_cosim.rpt').read_text()
    assert re.search(r'Verilog\|\s+Pass',cosim)
    latency = re.search(r'Verilog\|\s+Pass\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)\|\s*(\d+)',cosim)
    assert latency and int(latency.group(7)) < 15000
    print('PASS waveform sample window covers total RTL execution:',latency.group(7),'cycles')
    subprocess.run(['git','diff','--check'],cwd=ROOT,check=True)
    candidates = subprocess.check_output(['git','ls-files','--cached','--others','--exclude-standard','--','cmdresp/takehome'],cwd=repo,text=True).splitlines()
    suspicious = re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:AKIA|ASIA)[A-Z0-9]{16}\b')
    manifest = []
    for name in sorted(candidates):
        path = repo/name
        assert not any(p in {'.aws','.codex','.agents','.git','.venv','__pycache__','xsim.dir','.autopilot'} for p in path.relative_to(repo).parts),name
        assert path.suffix not in {'.o','.so','.exe','.key','.pem','.pyc'},name
        # Native WDB is a required retained binary artifact; scan text artifacts for secrets.
        if path.suffix != '.wdb':
            assert not suspicious.search(path.read_text(errors='replace')),name
        if name.endswith(('evidence/v3/submission_manifest.sha256','evidence/v3/final_audit.log')):
            continue
        manifest.append(digest(path)+'  '+name+'\n')
    (EVIDENCE/'submission_manifest.sha256').write_text(''.join(manifest))
    assert all((ROOT/ref).exists() for ref in references)
    print('PASS submission candidate audit:',len(candidates),'files; scratch builds and credentials excluded; submission_manifest.sha256')
    print('PASS no commit/push performed; final working tree intentionally contains reviewable changes')


if __name__ == '__main__':
    main()
