#!/usr/bin/env python3
import base64,struct,sys
import b
P,_,_,_,_,S=b.build(sys.argv[1])
def f(q,p):
 z=q
 while z%p==0:z//=p
 return z==1
R=[z for z in S if z[0]&1 and f(z[0],3)]
x=base64.b64decode('Uh/Z/7C7cV+a6oaQTgCRNOFKkvaNFNqDW+J5k0foXnkFtRdlbKR5HAB00JFa72/g7iTcxbmMC0Td5RfL3CwavygfNZUPgt/YM5LQifYFfPXlgaT65E2DErmrlc/9E79BxRAB9DonGuDU2Vu8cixzBDZHjvdhny/R+IewE4BVcSsF')
X=[(x[i>>3]>>(i&7))&1 for i in range(len(P))]
assert len(R)==57 and all(t==0 for q,a,t,m in R)
assert all(sum(a[i]*X[i] for i in range(len(P)))%3==0 for q,a,t,m in R)
with open(sys.argv[2],'wb') as o:
 o.write(struct.pack('<II',len(R),len(P)))
 o.write(struct.pack('<%dI'%len(R),*(q for q,a,t,m in R)))
 for q,a,t,m in R:o.write(struct.pack('<%dH'%len(P),*a))
 o.write(bytes(X))
if len(sys.argv)>3:
 R5=[z for z in S if z[0]&1 and f(z[0],5)]
 assert len(R5)==29
 with open(sys.argv[3],'wb') as o:
  o.write(struct.pack('<II',len(R5),len(P)))
  for q,a,t,m in R5:
   o.write(struct.pack('<II',q,t))
   o.write(struct.pack('<%dH'%len(P),*a))
