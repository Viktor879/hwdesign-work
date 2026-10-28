"""Read-only evidence audit plus current staged manifest generation; no EDA runs."""
import hashlib
import re
import subprocess
from pathlib import Path
R = Path(__file__).resolve().parent
REPO = R.parents[1]
E = R/'evidence/v3'
def git(*args):
    return subprocess.check_output(['git',*args], cwd=REPO)
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    tracked = git('ls-files').decode().splitlines()
    removed = (E/'removed_from_tracking.txt').read_text().splitlines()
    assert len(removed)==82
    for n in removed:
        assert n not in tracked and (REPO/n).is_file()
        assert (REPO/n).read_bytes()==git('show','HEAD:'+n)
        subprocess.run(['git','check-ignore','-q',n],cwd=REPO,check=True)
    print('PASS 82 index removals; all local bytes preserved and ignored')
    allowed = set((E/'preserved_native_artifacts.txt').read_text().splitlines())
    native = {n for n in tracked if '/qgemv_hls' in n}
    assert native==allowed
    assert not any('/sim/tv/' in n or n.endswith(('.autotb.v','.protoinst','.wcfg')) for n in native)
    for n in native:
        assert (REPO/n).read_bytes()==git('show','HEAD:'+n)
    print('PASS native allowlist:',len(native),'retained; zero uncited generated simulation trees tracked')
    # Preserve every previously tracked byte except these explicitly authorized document/package edits.
    changed = {'prompt.md','results.md','README.md','.gitignore','evidence/v3/spec.sha256','evidence/v3/submission_manifest.sha256'}
    old = git('ls-tree','-r','--name-only','HEAD','cmdresp/takehome').decode().splitlines()
    for n in old:
        relative=str(Path(n).relative_to('cmdresp/takehome'))
        if relative not in changed:
            assert (REPO/n).read_bytes()==git('show','HEAD:'+n),n
    print('PASS all original sources, fixtures, run logs, measurements, verdicts and historical evidence byte-identical')
    p=(R/'prompt.md').read_bytes(); prev=git('show','HEAD:cmdresp/takehome/prompt.md')
    assert [l for l in p.splitlines() if not l.startswith(b'| 2 |')]==[l for l in prev.splitlines() if not l.startswith(b'| 2 |')]
    assert (E/'spec.sha256').read_text().split()[0]==sha(R/'prompt.md')
    for current,archive in [('spec.sha256','spec_before_packaging.sha256'),('submission_manifest.sha256','submission_manifest_before_packaging.sha256')]:
        assert (E/archive).read_bytes()==git('show','HEAD:cmdresp/takehome/evidence/v3/'+current)
    report=(R/'results.md').read_text()
    assert len(re.findall(r'^## ',report,re.M))==7
    assert report.split('## Run History\n')[1]==git('show','HEAD:cmdresp/takehome/results.md').decode().split('## Run History\n')[1]
    print('PASS only v2 provenance row changed; v3 requirements/history unchanged; seven report sections; historical hashes archived')
    refs=0
    for doc in [R/'results.md',R/'README.md',E/'results_before_v3.md']:
        for ref in re.findall(r'`((?:evidence|data|qgemv_hls(?:_v3)?)/[^`]*?)`',doc.read_text()):
            assert (R/ref).exists(),ref
            if (R/ref).is_file(): assert 'cmdresp/takehome/'+ref in tracked,ref
            refs+=1
    # Script evidence paths stay available; scripts themselves have unchanged bytes.
    for script in ['export_wave.tcl','inspect_wave.tcl']:
        assert (R/script).read_bytes()==git('show','HEAD:cmdresp/takehome/'+script)
    print('PASS',refs,'concrete documentation references resolve; referenced files tracked; waveform scripts unchanged')
    excluded={'cmdresp/takehome/evidence/v3/submission_manifest.sha256','cmdresp/takehome/evidence/v3/packaging_audit.log'}
    names=sorted(n for n in tracked if n.startswith('cmdresp/takehome/') and n not in excluded)
    (E/'submission_manifest.sha256').write_text(''.join(sha(REPO/n)+'  '+n+'\n' for n in names))
    for line in (E/'submission_manifest.sha256').read_text().splitlines():
        digest,n=line.split(maxsplit=1); assert sha(REPO/n)==digest
    subprocess.run(['git','diff','--check'],cwd=REPO,check=True)
    subprocess.run(['git','diff','--cached','--check'],cwd=REPO,check=True)
    print('PASS current manifest:',len(names),'files; self/current audit log excluded; diff checks clean')
if __name__=='__main__': main()
