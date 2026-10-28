"""Add protocol sequencing gates to existing independently generated fixtures."""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cases=json.loads((root/'fixtures/manifest.json').read_text())
with (root/'fixtures/stress.txt').open('w') as f:
 f.write(str(len(cases))+'\n')
 for c in cases:
  gates=[0]*len(c['input']);required=[];headers=[];ip=op=0
  while ip<len(c['input']):
   for j in range(ip,min(ip+3,len(gates))):gates[j]=op
   if ip+3>c['consumed']:break
   h=c['input'][ip:ip+3];opcode=h[0][0];n=h[2][0]
   if any(w[0]>>32 or w[2:]!=[255,255] or w[1]!=(j==2) for j,w in enumerate(h)):break
   if opcode not in (1,2,3) or h[1][0]==0xffffffff or opcode==3:break
   if (opcode==1 and n>15) or (opcode==2 and not 1<=n<=32):break
   count=10 if opcode==1 else n
   end=ip+3+count
   if end>c['consumed']:break
   payload=c['input'][ip+3:end]
   if any(w[1]!=(j==count-1) for j,w in enumerate(payload)):break
   nout=1 if opcode==1 else n+1
   if op+nout>len(c['output']):break
   required += [end]*nout;headers += [1]+[0]*(nout-1)
   op+=nout;ip=end
  assert len(required)==len(c['output']),c['name']
  f.write(f"{c['name']} {len(c['input'])} {len(c['output'])} {' '.join(map(str,c['status']))} {c['consumed']}\n")
  for w,g in zip(c['input'],gates):f.write(' '.join(map(str,w+[g]))+'\n')
  for w,r,h in zip(c['output'],required,headers):f.write(' '.join(map(str,w+[r,h]))+'\n')
