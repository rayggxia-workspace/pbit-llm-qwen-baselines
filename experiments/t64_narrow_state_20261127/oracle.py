"""Scalar arbitrary-integer oracle for the state alignment contract."""
from fractions import Fraction
def rne(value,delta):
    if delta>=0:return value<<delta
    k=-delta;a=abs(value);q,r=divmod(a,1<<k)
    return (-1 if value<0 else 1)*(q+int(2*r>1<<k or (2*r==1<<k and q%2)))
def ceil_log(x):return (x-1).bit_length()
def state(values,exponents,bound,width):
    base=ceil_log(bound)-(width-2);total=0
    for value,e in zip(values,exponents):
        v=rne(value,e-base)
        if not -(1<<(width-1))<=v<1<<(width-1):raise OverflowError('align')
        total+=v
        if not -(1<<(width-1))<=total<1<<(width-1):raise OverflowError('sum')
    return Fraction(total)*Fraction(2)**base,base
