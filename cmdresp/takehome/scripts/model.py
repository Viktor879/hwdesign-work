"""Unbounded-integer numerical golden; no timing model."""
def evaluate(w,b,x,shift):
    result=[]
    for row,bias in zip(w,b):
        acc=int(bias)+sum(int(a)*int(v) for a,v in zip(row,x))
        q,r=divmod(abs(acc),1<<shift)
        if shift and 2*r >= 1<<shift: q+=1
        q=q if acc>=0 else -q
        result.append(max(-128,min(127,q)))
    return result
