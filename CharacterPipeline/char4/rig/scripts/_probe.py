import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, numpy as np
from mathutils.kdtree import KDTree
R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v3.blend'))
arm = bpy.data.objects['Char4_Armature']; body = bpy.data.objects['Body']; me = body.data
V = np.array([v.co[:] for v in me.vertices]); N = len(V)
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
vp = [set() for _ in range(N)]
for p in me.polygons:
    for vi in p.vertices: vp[vi].add(int(part[p.index]))
B = {b.name: (np.array(b.head_local[:]), np.array(b.tail_local[:])) for b in arm.data.bones}
a, b = B['J_Bip_R_UpperArm'][0], B['J_Bip_R_LowerArm'][0]
print('UpperArm R head', a.round(3), 'elbow', b.round(3))
def segd(P):
    ab=b-a; t=np.clip((P-a)@ab/(ab@ab),0,1); return np.linalg.norm(P-(a+t[:,None]*ab),axis=1), t
sl = np.array([11 in s or 13 in s for s in vp]); to = np.array([4 in s for s in vp])
print('shared torso/sleeve verts', int((sl&to).sum()))
oi=np.nonzero(sl)[0]; kd=KDTree(len(oi))
for j,i in enumerate(oi): kd.insert(V[i],j)
kd.balance()
near = to & (np.linalg.norm(V-a,axis=1)<0.10) & (V[:,0]<0)
ii=np.nonzero(near)[0]
d=np.array([kd.find(V[i])[2] for i in ii]); src=np.array([oi[kd.find(V[i])[1]] for i in ii])
di,ti=segd(V[ii]); ds,_=segd(V[src])
print('torso near R shoulder', len(ii))
for q in (10,50,90): print('pct',q,'dist',np.percentile(d,q).round(4),'di-ds',np.percentile(di-ds,q).round(4),'t',np.percentile(ti,q).round(2))
print('inside tube (di<ds) & d<3cm', int(((di<ds)&(d<0.03)).sum()))
gn=[g.name for g in body.vertex_groups]
# weights of sleeve verts at shoulder cap
cap = sl & (np.linalg.norm(V-a,axis=1)<0.05)
acc={}
for vi in np.nonzero(cap)[0]:
    for g in me.vertices[vi].groups: acc[gn[g.group]]=acc.get(gn[g.group],0)+g.weight
print('sleeve cap verts', int(cap.sum()), sorted(((round(v/cap.sum(),2),k) for k,v in acc.items()),reverse=True)[:6])
acc={}
tn = near & (np.linalg.norm(V-a,axis=1)<0.05)
for vi in np.nonzero(tn)[0]:
    for g in me.vertices[vi].groups: acc[gn[g.group]]=acc.get(gn[g.group],0)+g.weight
print('torso cap verts', int(tn.sum()), sorted(((round(v/max(tn.sum(),1),2),k) for k,v in acc.items()),reverse=True)[:6])
print('sleeve z range near shoulder', V[cap,2].min().round(3), V[cap,2].max().round(3), 'torso', V[tn,2].min().round(3) if tn.any() else None, V[tn,2].max().round(3) if tn.any() else None)
