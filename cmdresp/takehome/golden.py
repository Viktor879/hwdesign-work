"""Untimed integer golden model, independent NumPy checks, and protocol fixtures."""
import json
import os
from pathlib import Path
import numpy as np

def quantize(a, shift):
    if shift:
        q, r = divmod(abs(a), 1 << shift)
        a = (-1 if a < 0 else 1) * (q + (2*r >= (1 << shift)))
    return min(127, max(-128, a))

def gemv(w, b, x, shift):
    return [quantize(int(b[i])+sum(int(w[i][j])*int(x[j]) for j in range(8)), shift) for i in range(8)]

def numpy_ref(w,b,x,s):
    a = np.asarray(w,dtype=np.int64) @ np.asarray(x,dtype=np.int64) + np.asarray(b,dtype=np.int64)
    # Independent signed floor-division rule; negative ties adjust downward.
    d = np.int64(1 << s)
    floor = a // d
    rem = a % d
    y = floor + np.where(a >= 0, 2*rem >= d, 2*rem > d)
    return np.clip(y,-128,127).tolist()

def pack(vals,bits):
    return sum((int(v)&((1<<bits)-1))<<(bits*i) for i,v in enumerate(vals))

def header(cmd,tx,param=0): return [(cmd,0),(tx,0),(param,1)]
def config(w,b,s,tx):
    return header(1,tx,s)+[(pack(row,8),0) for row in w]+[(pack(b[:4],16),0),(pack(b[4:],16),1)]
def process(xs,tx): return header(2,tx,len(xs))+[(pack(x,8),int(k==len(xs)-1)) for k,x in enumerate(xs)]
def response(w,b,s,xs,tx): return [(tx,1)]+[(pack(gemv(w,b,x,s),8),int(k==len(xs)-1)) for k,x in enumerate(xs)]

def main():
    v3 = os.environ.get('QGEMV_VERSION') == 'v3'
    data = Path('data/v3' if v3 else 'data'); evidence = Path('evidence/v3' if v3 else 'evidence')
    data.mkdir(exist_ok=True); evidence.mkdir(exist_ok=True)
    eye=np.eye(8,dtype=int).tolist();zero=[[0]*8 for _ in range(8)];b0=[0]*8
    x=[10,-5,20,3,8,0,-12,7]
    checks=[]
    def check(name,got,exp):
        assert got==exp,(name,got,exp)
        checks.append(dict(name=name,result='PASS',observed=got,expected=exp))
    check('identity',gemv(eye,b0,x,0),x)
    check('dot_bias',gemv([[1,-1,2,0,0,0,0,0]]*8,[3]*8,[1,2,3,0,0,0,0,0],0),[8]*8)
    check('zero',gemv(zero,b0,x,15),b0)
    for a,s,y in [(3,1,2),(-3,1,-2),(1,2,0),(-1,2,0),(5,2,1),(-5,2,-1),(16384,15,1),(-16384,15,-1),(16383,15,0),(-16383,15,0),(32767,15,1),(-32768,15,-1)]:
        check(f'round_{a}_{s}',quantize(a,s),y)
    check('sat_positive',gemv([[127]*8]*8,b0,[127]*8,0),[127]*8)
    check('sat_negative',gemv([[127]*8]*8,b0,[-128]*8,0),[-128]*8)
    rng=np.random.default_rng(20261028)
    for s in range(16):
        for k in range(200):
            w=rng.integers(-128,128,(8,8)).tolist();b=rng.integers(-32768,32768,8).tolist();xx=rng.integers(-128,128,8).tolist()
            assert gemv(w,b,xx,s)==numpy_ref(w,b,xx,s)
    checks.append(dict(name='numpy_int64_3200_vectors_all_shifts',result='PASS'))
    (evidence/'python_checks.json').write_text(json.dumps(checks,indent=2))
    cases=[]
    def add(name,ins,outs,h=0,e=0,t=0):cases.append(dict(name=name,ins=ins,outs=outs,halted=h,error=e,tx_id=t))
    def valid(name,w,b,s,xs):
        add(name,config(w,b,s,10)+process(xs,11)+header(3,12),[(10,1)]+response(w,b,s,xs,11))
    valid('identity_n1',eye,b0,0,[x])
    valid('dot_bias',[[1,-1,2,0,0,0,0,0]]*8,[3]*8,0,[[1,2,3,0,0,0,0,0]])
    valid('zero_n32',zero,b0,0,[[0]*8]*32)
    valid('saturation',[[127]*8]*8,b0,0,[[127]*8,[-128]*8])
    valid('ties_shift1',zero,[3,-3,1,-1,5,-5,0,127],1,[x])
    valid('nonties_shift2',zero,[1,-1,5,-5,6,-6,7,-7],2,[x])
    valid('shift15',zero,[16384,-16384,16383,-16383,32767,-32768,0,1],15,[x])
    w=rng.integers(-128,128,(8,8)).tolist();b=rng.integers(-32768,32768,8).tolist()
    xs=rng.integers(-128,128,(32,8)).tolist();xs[0]=[127,-128,0,1,-1,126,-127,0]
    valid('mixed_n32_shift0',w,b,0,xs)
    valid('mixed_n32_shift15',w,b,15,xs)
    add('persistence_replacement',config(eye,b0,0,0)+process([x],0xfffffffe)+process([x,x],20)+config(w,b,7,21)+process(xs,22)+header(3,23),[(0,1)]+response(eye,b0,0,[x],0xfffffffe)+response(eye,b0,0,[x,x],20)+[(21,1)]+response(w,b,7,xs,22))
    add('end_only',header(3,44),[])
    def failure(name,tail,e,t,configured=False):
        prefix=config(eye,b0,0,99)+process([x],98) if configured else []
        outs=[(99,1)]+response(eye,b0,0,[x],98) if configured else []
        add(name,prefix+tail,outs,1,e,t)
        valid('recovery_'+name,eye,b0,0,[x])
    failure('header_undecodable',[(2,1)],1,0xffffffff,True)
    failure('header_decodable',[(2,0),(123,1)],1,123,True)
    failure('header_missing_last',[(2,0),(124,0),(1,0)],1,124)
    failure('header_padding',[(2,0),(125,0),((1<<32)|1,1)],1,125)
    failure('header_bad_tx_padding',[(2,0),((1<<32)|126,0)],1,0xffffffff,True)
    failure('unknown',header(99,127,99),2,127)
    failure('reserved',header(2,0xffffffff,0),3,0xffffffff)
    failure('config_shift16',header(1,128,16),3,128,True)
    failure('config_shift_unsignedmax',header(1,129,0xffffffff),3,129)
    failure('process_zero',header(2,130,0),4,130)
    failure('process_33',header(2,131,33),4,131)
    failure('process_unsignedmax',header(2,132,0xffffffff),4,132)
    failure('no_config',header(2,133,1),5,133)
    failure('config_early',header(1,134)+[(0,1)],6,134,True)
    failure('config_missing',header(1,135)+[(0,0)]*10,7,135,True)
    failure('process_early',header(2,136,32)+[(0,1)],6,136,True)
    failure('process_missing',header(2,137,1)+[(0,0)],7,137,True)
    failure('end_param',header(3,138,1),3,138)
    failure('reserved_end',header(3,0xffffffff),3,0xffffffff)
    if v3:
        for tx in [0, 7, 0xfffffffe]:
            add(f'repeated_id_{tx}',
                config(eye,b0,0,tx)+process([x],tx)+process([x,x],tx)
                +config(zero,[3,-3,1,-1,5,-5,0,127],1,tx)+process([x],tx)+header(3,tx),
                [(tx,1)]+response(eye,b0,0,[x],tx)+response(eye,b0,0,[x,x],tx)
                +[(tx,1)]+response(zero,[3,-3,1,-1,5,-5,0,127],1,[x],tx))
        # Check each header position, each enable independently, and missing low/high bytes.
        for k in range(3):
            for side in ['keep','strb']:
                for mask in [0, 0xfe, 0x7f]:
                    words = [(d,last,255,255) for d,last in header(2,201,1)[:k+1]]
                    w = list(words[-1]); w[2 if side=='keep' else 3] = mask; words[-1] = tuple(w)
                    failure(f'header_{k}_{side}_{mask}',words,1,201 if k==2 else 0xffffffff,True)
        failure('unknown_reserved',header(99,0xffffffff,0xffffffff),2,0xffffffff)
        failure('unknown_malformed',[(99,1)],1,0xffffffff)
        failure('reserved_config_shift',header(1,0xffffffff,16),3,0xffffffff)
        failure('reserved_process_33',header(2,0xffffffff,33),3,0xffffffff)
        failure('end_param_after_results',header(3,202,0xffffffff),3,202,True)
        # Receiver must ignore payload enables for CONFIG and PROCESS, even all zero.
        ins = config(eye,b0,0,203)+process([x,x],203)+header(3,203)
        ins = [(d,last,0,0) if 3<=i<13 or 16<=i<18 else (d,last,255,255)
               for i,(d,last) in enumerate(ins)]
        add('payload_enables_ignored',ins,[(203,1)]+response(eye,b0,0,[x,x],203))
        for c in cases:
            c['ins'] = [tuple(w) if len(w)==4 else (*w,255,255) for w in c['ins']]
        # Preserve the historical scenarios as an exact prefix, apart from enable serialization.
        old = json.loads(Path('data/cases.json').read_text())
        for a,b in zip(old,cases):
            assert a['name']==b['name'] and a['outs']==[list(w) for w in b['outs']]
            assert a['ins']==[list(w[:2]) for w in b['ins']]
        for i,c in enumerate(cases):
            if c['error']:
                assert cases[i+1]['name']=='recovery_'+c['name'] and cases[i+1]['error']==0
    (data/'cases.json').write_text(json.dumps(cases,indent=2))
    with open(data/'cases.txt','w') as f:
        f.write(str(len(cases))+'\n')
        for c in cases:
            f.write(f"{c['name']} {len(c['ins'])} {len(c['outs'])} {c['halted']} {c['error']} {c['tx_id']}\n")
            for w in c['ins']+c['outs']: f.write(' '.join(str(v) for v in w)+'\n')
    print(f'PASS independent hand checks, 3200 NumPy comparisons; {len(cases)} activation fixtures')
if __name__=='__main__':main()
