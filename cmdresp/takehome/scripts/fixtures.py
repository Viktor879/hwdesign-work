import json, random
from pathlib import Path
import numpy as np
from model import evaluate
root=Path(__file__).resolve().parents[1]
rng=random.Random(814)
I=[[int(i==j) for j in range(8)] for i in range(8)]
Z=[[0]*8 for _ in range(8)]
checks=[(I,[0]*8,[10,-5,20,3,8,0,-12,7],0,[10,-5,20,3,8,0,-12,7]),
 ([[1,-1,2,0,0,0,0,0]]*8,[3]*8,[1,2,3,0,0,0,0,0],0,[8]*8),
 (Z,[0]*8,[127]*8,0,[0]*8),
 (Z,[3,-3,2,-2,1,-1,0,4],[0]*8,1,[2,-2,1,-1,1,-1,0,2]),
 (Z,[1,-1,32767,-32768,16384,-16384,16383,-16383],[0]*8,15,[0,0,1,-1,1,-1,0,0]),
 ([[127]*8]*8,[0]*8,[127]*8,0,[127]*8),([[127]*8]*8,[0]*8,[-128]*8,0,[-128]*8)]
for w,b,x,s,y in checks: assert evaluate(w,b,x,s)==y
for _ in range(3200):
 w=[[rng.randrange(-128,128) for _ in range(8)] for _ in range(8)]
 b=[rng.randrange(-32768,32768) for _ in range(8)];x=[rng.randrange(-128,128) for _ in range(8)];s=rng.randrange(16)
 a=np.array(w,dtype=np.int64)@np.array(x,dtype=np.int64)+np.array(b,dtype=np.int64)
 # Independent signed floor division plus remainder distance, no magnitude algorithm.
 d=np.int64(1<<s);lo=a//d;rem=a%d
 q=lo+((2*rem>d)|((2*rem==d)&(a>=0)))
 assert evaluate(w,b,x,s)==np.clip(q,-128,127).tolist()
(root/'evidence/python/checks.json').write_text(json.dumps({'hand_checks':len(checks),'numpy_int64_comparisons':3200,'seed':814,'result':'PASS'},indent=2)+'\n')
def word(d,last=0,keep=255,strb=255):return [d&((1<<64)-1),int(last),keep,strb]
def pack(v,bits):return sum((int(a)&((1<<bits)-1))<<(bits*i) for i,a in enumerate(v))
def header(op,id,p):return [word(op),word(id),word(p,1)]
cases=[]
def add(name,inp,out=[],status=(0,0,0),consumed=None):cases.append(dict(name=name,input=inp,output=out,status=status,consumed=len(inp) if consumed is None else consumed))
def good(name,w=I,b=[0]*8,s=0,n=1):
 xs=[[rng.randrange(-128,128) for _ in range(8)] for _ in range(n)]
 payload=[word(pack(row,8),False) for row in w]+[word(pack(b[:4],16)),word(pack(b[4:],16),1)]
 inp=header(1,0,s)+payload;out=[word(0,1)]
 for repeat in range(2):
  inp+=header(2,0,n)+[word(pack(x,8),i==n-1) for i,x in enumerate(xs)]
  out+=[word(0,1)]+[word(pack(evaluate(w,b,x,s),8),i==n-1) for i,x in enumerate(xs)]
 inp+=header(3,123,0);add(name,inp,out)
for j in range(4):good('batch32_'+str(j),[[rng.randrange(-128,128) for _ in range(8)] for _ in range(8)],[rng.randrange(-32768,32768) for _ in range(8)], [0,15,1,7][j],32)
for j,(w,b,x,s,y) in enumerate(checks):
 payload=[word(pack(row,8)) for row in w]+[word(pack(b[:4],16)),word(pack(b[4:],16),1)]
 add('hand_'+str(j),header(1,9,s)+payload+header(2,10,1)+[word(pack(x,8),1)]+header(3,0,0),[word(9,1),word(10,1),word(pack(y,8),1)])
# Atomic configuration replacement and legal maximum ID.
a=cases[4]; bb=cases[5]
add('replacement',a['input'][:-3]+bb['input'][:-3]+header(3,0xfffffffe,0),a['output']+bb['output'])
def bad(name,inp,code,id,consumed=None):
 add(name,inp,[],(1,code,id),consumed);good('recovery_'+name)
for k in range(3):
 for field,value in [(0,1<<40),(1,1 if k!=2 else 0),(2,0),(3,0)]:
  h=header(2,44,1);h[k][field]=value if field else h[k][0]|value
  bad(f'header_{k}_{field}',h,1,44 if k==2 or (k==1 and field==1) else 0xffffffff,k+1)
for name,op,id,p,code in [('unknown',99,42,0,2),('unknown_reserved',99,0xffffffff,0,2),('reserved_count',2,0xffffffff,0,3),('reserved',1,0xffffffff,0,3),('shift16',1,4,16,3),('shift_negative',1,4,0xffffffff,3),('end_parameter',3,4,1,3),('count0',2,4,0,4),('count33',2,4,33,4),('count_negative',2,4,0xffffffff,4),('unconfigured',2,4,1,5)]:bad(name,header(op,id,p),code,id)
for op,n in [(1,10),(2,2)]:
 for early in [True,False]:
  prefix=[];out=[]
  if op==2:prefix=cases[4]['input'][:13];out=[word(9,1)]
  payload=[word(0,early if i==0 else False) for i in range(1 if early else n)]
  name=f'payload_{op}_{early}'
  add(name,prefix+header(op,66,0 if op==1 else n)+payload,out,(1,6 if early else 7,66));good('recovery_'+name)
# Payload byte enables are deliberately ignored.
c=cases[4];inp=[v.copy() for v in c['input']];inp[3][2:]=[0,0];inp[16][2:]=[0,0];add('payload_sidebands',inp,c['output'])
with (root/'fixtures/cases.txt').open('w') as f:
 f.write(str(len(cases))+'\n')
 for c in cases:
  f.write(f"{c['name']} {len(c['input'])} {len(c['output'])} {' '.join(map(str,c['status']))} {c['consumed']}\n")
  for w in c['input']+c['output']:f.write(' '.join(map(str,w))+'\n')
(root/'fixtures/manifest.json').write_text(json.dumps(cases,indent=2)+'\n')
print('PASS independent golden checks; generated',len(cases),'activations')
