import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys, math, numpy as np
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree
R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v3.blend'))
arm = bpy.data.objects['Char4_Armature']; PB = arm.pose.bones; body = bpy.data.objects['Body']; me = body.data
src = open(os.path.join(R, 'scripts', '07_collide_check.py')).read()
ns = {}; exec(src[src.index('POSES = {'):src.index('GROUPS = ')], {}, ns); POSES = ns['POSES']
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
V0 = np.array([v.co[:] for v in me.vertices])
def ev():
    dg = bpy.context.evaluated_depsgraph_get(); e = body.evaluated_get(dg); m = e.to_mesh()
    V = np.array([v.co[:] for v in m.vertices]); e.to_mesh_clear(); return V
def rot_world(pb, axis, deg):
    pb.rotation_mode = 'QUATERNION'; M = pb.bone.matrix_local.to_3x3(); ax = (M.inverted() @ Vector(axis)).normalized()
    pb.rotation_quaternion = Quaternion(ax, math.radians(deg)) @ pb.rotation_quaternion
polys = [list(p.vertices) for p in me.polygons]
def side(V, inner, outer):
    bvh = BVHTree.FromPolygons([Vector(x) for x in V], [p for p, k in zip(polys, part) if k in outer])
    vi = sorted({i for p, k in zip(polys, part) if k in inner for i in p})
    res = {}
    for i in vi:
        h = bvh.find_nearest(Vector(V[i]), 0.04)
        if h[0] is not None: res[i] = h[1].dot(Vector(V[i]) - h[0])
    return res
rest = ev()
for o_name, inner, outer in (('torso vs sleeve', (4,), (11,)), ('torso vs cape', (4,), (1,)), ('sleeve vs cape', (11,), (1,))):
    pass
r0 = {k: side(rest, *io) for k, io in {'t_s': ((4,), (11,)), 't_c': ((4,), (1,)), 's_c': ((11,), (1,))}.items()}
for b, ax, d in POSES['bow_draw']: rot_world(PB[b], ax, d)
bpy.context.view_layer.update(); P = ev()
gn = [g.name for g in body.vertex_groups]
for k, io in {'t_s': ((4,), (11,)), 't_c': ((4,), (1,)), 's_c': ((11,), (1,))}.items():
    r1 = side(P, *io)
    out = [i for i, s in r1.items() if s > 0.002 and r0[k].get(i, 1) < 0]
    print(k, 'inside at rest, out in pose:', len(out))
    if out:
        X = V0[out]; print('  rest centre', X.mean(0).round(3), 'min', X.min(0).round(3), 'max', X.max(0).round(3))
        acc = {}
        for i in out:
            for g in me.vertices[i].groups: acc[gn[g.group]] = acc.get(gn[g.group], 0) + g.weight / len(out)
        print('  weights', sorted(((round(v, 2), n) for n, v in acc.items()), reverse=True)[:6])
# detail for torso popped out of sleeve
r1 = side(P, (4,), (11,)); out = [i for i, s in r1.items() if s > 0.002 and r0['t_s'].get(i, 1) < 0]
d0 = np.array([r0['t_s'][i] for i in out]); print('rest signed dist to sleeve: pct', np.percentile(d0, [10, 50, 90]).round(4))
outer = [p for p, k in zip(polys, part) if k in (7, 11, 13)]
bvh = BVHTree.FromPolygons([Vector(x) for x in rest], outer)
dd = []; 
for i in out:
    h = bvh.find_nearest(Vector(rest[i]), 0.06); dd.append((h[3], h[1].dot(Vector(rest[i]) - h[0])))
dd = np.array(dd); print('vs 7/11/13 unsigned', np.percentile(dd[:, 0], [10, 50, 90]).round(4), 'signed', np.percentile(dd[:, 1], [10, 50, 90]).round(4))
# how many popped verts also share a face with sleeve (boundary verts)
vpp = [set() for _ in range(len(rest))]
for p, k in zip(polys, part):
    for v in p: vpp[v].add(int(k))
print('popped boundary verts', sum(1 for i in out if len(vpp[i]) > 1), 'parts', {k: sum(1 for i in out if k in vpp[i]) for k in (1, 4, 11)})
