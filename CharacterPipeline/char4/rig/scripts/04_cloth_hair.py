"""Cloth + hair bones. Skirt chains (Hips), capelet chains + hood chain + pendant (UpperChest), weights blended
into the body weights; the rigged CLI twin-tail hair (48 strand bones) merged under J_Bip_C_Head.
Saves rig/rig_v3.blend and rig/cloth_chains.json (chain list for the UE AnimDynamics step)."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, math, json
import numpy as np
from mathutils import Vector, Matrix

R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
HAIR_BLEND = os.path.join(ANIME_GAME_ROOT, r"hair_twintail\hair_twintail_rig.blend")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v2.blend'))
arm = bpy.data.objects['Char4_Armature']; body = bpy.data.objects['Body']; me = body.data
B = {b.name: (np.array(b.head_local[:]), np.array(b.tail_local[:])) for b in arm.data.bones}
V = np.array([v.co[:] for v in me.vertices]); N = len(V)
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
vpart = np.full(N, -1)
for p in me.polygons:
    for vi in p.vertices:
        if vpart[vi] < 0: vpart[vi] = part[p.index]

def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def seg_dist(P, a, b):
    ab = b - a; t = np.clip((P - a) @ ab / (ab @ ab), 0, 1); return np.linalg.norm(P - (a + t[:, None] * ab), axis=1)

# current weights -> dense matrix
gnames = [g.name for g in body.vertex_groups]
Wd = {n: np.zeros(N) for n in gnames}
for v in me.vertices:
    for g in v.groups:
        Wd[gnames[g.group]][v.index] = g.weight

CHAINS = []          # (chain name, [bone names], parent)
NEWB = []            # (name, head, tail, parent)

def build_ring(prefix, mask, center_xy, angles, z_top, nb, parent, inset=0.006, min_pts=25):
    """chains around a vertical axis: for each angle sector, bones from z_top down to the sector hem."""
    P = V[mask]; cx, cy = center_xy
    phi = np.degrees(np.arctan2(P[:, 0] - cx, -(P[:, 1] - cy)))
    rad = np.hypot(P[:, 0] - cx, P[:, 1] - cy)
    out = []
    for i, a in enumerate(angles):
        sec = np.abs((phi - a + 180) % 360 - 180) < 14
        if sec.sum() < min_pts:
            print('SKIP', prefix, a, int(sec.sum())); continue
        hem = np.percentile(P[sec, 2], 2)
        zs = [z_top + (hem - z_top) * k / nb for k in range(nb + 1)]
        pts = []
        for z in zs:
            near = sec & (np.abs(P[:, 2] - z) < 0.02)
            if near.sum() < 5: near = sec & (np.abs(P[:, 2] - z) < 0.045)
            r = np.percentile(rad[near], 80) - inset if near.sum() else np.percentile(rad[sec], 80)
            d = np.array([math.sin(math.radians(a)), -math.cos(math.radians(a))])
            pts.append(np.array([cx + r * d[0], cy + r * d[1], z]))
        nm = f'{prefix}_{len(out) + 1:02d}'
        names = []
        for k in range(nb):
            bn = f'J_Sec_{nm}_{k + 1}'; names.append(bn)
            NEWB.append((bn, pts[k], pts[k + 1], parent if k == 0 else names[k - 1]))
        out.append(dict(name=nm, angle=a, pts=pts, bones=names))
        CHAINS.append(dict(chain='J_Sec_' + nm, bones=names, parent=parent))
    return out

def ring_weights(mask, chains, center_xy, joints_z_fn):
    """angular interpolation between neighbouring chains, z bands along each chain."""
    P = V[mask]; cx, cy = center_xy
    phi = np.degrees(np.arctan2(P[:, 0] - cx, -(P[:, 1] - cy)))
    ang = np.array([c['angle'] for c in chains]); order = np.argsort(ang); ang = ang[order]; chs = [chains[i] for i in order]
    out = {}
    n = len(chs)
    for j in range(n):
        a0 = ang[j]; a1 = ang[(j + 1) % n] + (360 if j == n - 1 else 0)
        rel = (phi - a0) % 360; span = (a1 - a0) % 360 or 360
        inside = rel <= span
        t = np.clip(rel / span, 0, 1)
        for c, w_ang in ((chs[j], 1 - t), (chs[(j + 1) % n], t)):
            zj = [p[2] for p in c['pts']]
            for k, bn in enumerate(c['bones']):
                hi = np.ones(len(P)) if k == 0 else sstep(zj[k] + 0.02, zj[k] - 0.02, P[:, 2])
                lo = np.zeros(len(P)) if k == len(c['bones']) - 1 else sstep(zj[k + 1] + 0.02, zj[k + 1] - 0.02, P[:, 2])
                out[bn] = out.get(bn, 0) + np.where(inside, w_ang * (hi - lo), 0)
    return out

def mix_in(mask, new, f):
    idx = np.nonzero(mask)[0]
    for k in Wd: Wd[k][idx] *= (1 - f)
    for k, v in new.items():
        Wd.setdefault(k, np.zeros(N)); Wd[k][idx] += v * f

# ------------------------------------------------------------------ skirt
hipc = (0.0, 0.5 * (B['J_Bip_L_UpperLeg'][0][1] + B['J_Bip_R_UpperLeg'][0][1]))
m0 = vpart == 0
dleg = np.full(N, np.inf)
for s in ('L', 'R'):
    d = seg_dist(V, B[f'J_Bip_{s}_UpperLeg'][0], B[f'J_Bip_{s}_LowerLeg'][0])
    sm = (V[:, 0] > 0) if s == 'L' else (V[:, 0] <= 0)
    dleg = np.where(sm, d, dleg)
skirt = m0 & (dleg > 0.085) & (V[:, 2] < 0.95)
SK = build_ring('Skirt', skirt, hipc, [25, 60, 95, 130, 165, -165, -130, -95, -60, -25], 0.92, 3, 'J_Bip_C_Hips')
mix_in(skirt, ring_weights(skirt, SK, hipc, None), sstep(0.95, 0.89, V[skirt, 2]))
# collision fix: the skirt over each thigh partly rides the thigh, so a raised leg lifts the panel instead of
# piercing it (physics adds the swing on top). Stronger toward the hem and away from the centre line.
LEG_FOLLOW = 0.5
for s_, sgn in (('L', 1), ('R', -1)):
    sm = skirt & (V[:, 0] * sgn > 0)
    front = sstep(hipc[1] - 0.02, hipc[1] - 0.08, V[sm, 1])     # panel in front of the thigh lifts with it more
    g = (LEG_FOLLOW + 0.3 * front) * sstep(0.95, 0.80, V[sm, 2]) * sstep(0.0, 0.06, np.abs(V[sm, 0]))
    mix_in(sm, {f'J_Bip_{s_}_UpperLeg': np.ones(int(sm.sum()))}, g)
print('SKIRT chains', len(SK), 'verts', int(skirt.sum()))

# ------------------------------------------------------------------ capelet + hood + pendant
m1 = vpart == 1
chc = (0.0, float(B['J_Bip_C_UpperChest'][0][1]))
hood = m1 & (V[:, 1] > chc[1] + 0.04) & (V[:, 2] > 1.19) & (np.abs(V[:, 0]) < 0.13)
cape = m1 & ~hood
CP = build_ring('Cape', cape, chc, [35, 80, 125, 165, -165, -125, -80, -35], 1.20, 2, 'J_Bip_C_UpperChest')
# collision fix: capelet over the shoulders keeps most of its shoulder/upper-arm weight so raised arms lift it
mix_in(cape, ring_weights(cape, CP, chc, None), 0.8 * sstep(1.215, 1.15, V[cape, 2]) * (1 - 0.65 * sstep(0.11, 0.19, np.abs(V[cape, 0]))))
print('CAPE chains', len(CP), 'verts', int(cape.sum()), 'hood verts', int(hood.sum()))
H = V[hood]
hb = np.array([0, np.percentile(H[:, 1], 40), 1.205]); ht = H[np.argmax(H[:, 2])]; ht = np.array([0, ht[1], ht[2]])
hm = 0.5 * (hb + ht) + np.array([0, 0.015, 0])
NEWB += [('J_Sec_Hood_1', hb, hm, 'J_Bip_C_UpperChest'), ('J_Sec_Hood_2', hm, ht, 'J_Sec_Hood_1')]
CHAINS.append(dict(chain='J_Sec_Hood', bones=['J_Sec_Hood_1', 'J_Sec_Hood_2'], parent='J_Bip_C_UpperChest'))
tz = (H[:, 2] - hb[2]) / max(ht[2] - hb[2], 1e-3)
w2 = sstep(0.4, 0.6, tz)
mix_in(hood, {'J_Sec_Hood_1': 1 - w2, 'J_Sec_Hood_2': w2}, 0.9 * sstep(0.0, 0.25, tz))
m14 = vpart == 14; Pp = V[m14]
pt = np.array([Pp[:, 0].mean(), Pp[:, 1].mean(), Pp[:, 2].max()]); pb_ = np.array([Pp[:, 0].mean(), Pp[:, 1].mean(), Pp[:, 2].min() - 0.01])
NEWB.append(('J_Sec_Pendant', pt, pb_, 'J_Bip_C_UpperChest'))
mix_in(m14, {'J_Sec_Pendant': np.ones(int(m14.sum()))}, 1.0)
CHAINS.append(dict(chain='J_Sec_Pendant', bones=['J_Sec_Pendant'], parent='J_Bip_C_UpperChest'))

# ------------------------------------------------------------------ layer sync (owner screenshot 2026-11-10, bow_draw)
# Tripo layers overlap: the torso shirt runs on under the sleeves and the capelet. Where an inner vertex sits close
# under an outer garment it takes the outer vertex's weights, so both layers move together and the inner one cannot
# poke through (orange torso slivers on the sleeve top / capelet). The capelet hem over the upper arm partly takes
# the sleeve weights so a raised arm lifts the hem instead of piercing it.
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree
PL = [list(p.vertices) for p in me.polygons]
def follow_outer(inner, outer_parts, d0, d1, gain, only_under=True, mask_f=None):
    """inner verts behind the outer layer's surface (rest pose, within d1) blend toward the nearest outer vertex's
    weights: full gain closer than d0, fading to 0 at d1."""
    outer = np.isin(vpart, outer_parts)
    bvh = BVHTree.FromPolygons([Vector(x) for x in V], [p for p, k in zip(PL, part) if k in outer_parts], all_triangles=False)
    oi = np.nonzero(outer)[0]; kd = KDTree(len(oi))
    for j, i in enumerate(oi): kd.insert(V[i], j)
    kd.balance()
    ii = np.nonzero(inner & ~outer)[0]; src = np.zeros(len(ii), int); dist = np.full(len(ii), 9.0)
    for j, i in enumerate(ii):
        p = Vector(V[i]); h = bvh.find_nearest(p, d1)
        if h[0] is None or (only_under and h[1].dot(p - h[0]) > 0): continue
        dist[j] = h[3]; src[j] = oi[kd.find(p)[1]]
    f = gain * sstep(d1, d0, dist) * (mask_f(V[ii]) if mask_f else 1)
    snap = {k: Wd[k][src].copy() for k in Wd}
    for k in Wd: Wd[k][ii] = Wd[k][ii] * (1 - f) + snap[k] * f
    print('FOLLOW', outer_parts, int((f > 0.01).sum()), 'full', int((f > 0.5 * gain).sum()))
torso = vpart == 4
follow_outer(cape, (7, 11, 13), 0.015, 0.045, 0.85, only_under=False)   # capelet hem over the upper arms
follow_outer(torso, (1,), 0.02, 0.04, 1.0)                               # shirt under the capelet
follow_outer(torso, (7, 11, 13), 0.045, 0.065, 1.0)                      # shirt armhole ring 1-4 cm inside the sleeve
# shirt shoulder above the sleeve top (4-6 cm off the sleeve at rest): a raised arm drove the rigid sleeve cap into it
# and the shirt poked out through the sleeve. Outer shoulder rides the sleeve, fading out toward the neck.
follow_outer(torso, (7, 11, 13), 0.03, 0.07, 0.9, only_under=False,
             mask_f=lambda P: sstep(0.085, 0.13, np.abs(P[:, 0])) * sstep(1.03, 1.08, P[:, 2]))
# shirt past the shoulder joint along the arm axis (armhole ring + deltoid) is arm, full stop
for s_ in ('L', 'R'):
    a, b = B[f'J_Bip_{s_}_UpperArm'][0], B[f'J_Bip_{s_}_LowerArm'][0]; ax = (b - a) / np.linalg.norm(b - a)
    sm = torso & ((V[:, 0] > 0) if s_ == 'L' else (V[:, 0] <= 0))
    along = (V[sm] - a) @ ax
    radial = np.linalg.norm((V[sm] - a) - along[:, None] * ax, axis=1)     # only inside the arm tube, not the waist
    mix_in(sm, {f'J_Bip_{s_}_UpperArm': np.ones(int(sm.sum()))},
           sstep(-0.07, -0.035, along) * sstep(0.075, 0.055, radial) * sstep(0.14, 0.10, along))

# ------------------------------------------------------------------ bones
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for name, h, t, par in NEWB:
    b = eb.new(name); b.head = Vector(h); b.tail = Vector(t); b.parent = eb[par]; b.use_connect = False
    b.roll = 0
bpy.ops.object.mode_set(mode='OBJECT')

# capelet + hood are several overlapping shells; weights that differ between neighbouring shells (hood mask edge,
# neck band, chain sectors) opened see-through cracks at the collar when posed. Spatial smoothing over 1.5 cm
# (any shell) makes overlapping shells move together.
ci = np.nonzero(m1)[0]; kdc = KDTree(len(ci))
for j, i in enumerate(ci): kdc.insert(V[i], j)
kdc.balance()
nbr = [[ci[j] for _, j, _ in kdc.find_range(V[i], 0.015)] for i in ci]
for it in range(2):
    new = {k: np.array([Wd[k][nb].mean() for nb in nbr]) for k in Wd if Wd[k][ci].max() > 1e-4}
    for k, v in new.items(): Wd[k][ci] = v
print('CAPE spatial smooth verts', len(ci))
# UV-seam twins (glTF import keeps split verts): coincident verts of different parts got different weights and
# cracked open when posed -> every coincident group shares the mean weights
kdw = KDTree(N)
for i in range(N): kdw.insert(V[i], i)
kdw.balance(); twins = 0
for i in range(N):
    grp = [j for _, j, _ in kdw.find_range(V[i], 1e-5)]
    if len(grp) > 1 and min(grp) == i:
        twins += 1
        for k in Wd: Wd[k][grp] = Wd[k][grp].mean()
print('TWIN groups welded', twins)
# write weights: top 4 normalised
names = sorted(k for k in Wd if Wd[k].max() > 1e-4); M = np.array([Wd[k] for k in names])
order = np.argsort(-M, axis=0); keep = np.zeros_like(M, bool)
for r in range(4): keep[order[r], np.arange(N)] = True
M = np.where(keep & (M > 1e-3), M, 0); M /= np.maximum(M.sum(0), 1e-9)
body.vertex_groups.clear()
for i, n in enumerate(names):
    g = body.vertex_groups.new(name=n)
    for vi in np.nonzero(M[i])[0]: g.add([int(vi)], float(M[i, vi]), 'REPLACE')
print('BODY groups', len(names))
# sphere colliders for UE AnimDynamics (spherical limits): outer shell radius around each body bone, measured
# from the vertices that bone drives (capelet included at the chest so hair stays outside the cloth)
COLL = []
def spheres(bone, P, n=2, pct=85, pad=0.008):
    h, t = B[bone]; ax = t - h; L = np.linalg.norm(ax); u = ax / L
    tt = (P - h) @ u / L; rr = np.linalg.norm((P - h) - np.outer(tt * L, u), axis=1)
    for k in range(n):
        c = (k + 0.5) / n; sel = np.abs(tt - c) < 0.5 / n + 0.1
        if sel.sum() < 10: continue
        COLL.append(dict(bone=bone, offset_along_bone_cm=round(float(c * L * 100), 2), radius_cm=round(float((np.percentile(rr[sel], pct) + pad) * 100), 2)))
gi = {n: i for i, n in enumerate(names)}
for bone, n in (('J_Bip_C_Hips', 1), ('J_Bip_C_Spine', 1), ('J_Bip_C_Chest', 1), ('J_Bip_C_UpperChest', 2),
                ('J_Bip_L_UpperArm', 2), ('J_Bip_R_UpperArm', 2), ('J_Bip_L_LowerArm', 2), ('J_Bip_R_LowerArm', 2),
                ('J_Bip_L_UpperLeg', 3), ('J_Bip_R_UpperLeg', 3), ('J_Bip_L_LowerLeg', 2), ('J_Bip_R_LowerLeg', 2)):
    sel = M[gi[bone]] > 0.5 if bone in gi else np.zeros(N, bool)
    if sel.sum() > 20: spheres(bone, V[sel], n)
fc = bpy.data.objects['Face']
FV = np.array([fc.matrix_world @ v.co for v in fc.data.vertices])
spheres('J_Bip_C_Head', FV, 2, 90, 0.004)
for c in COLL: print('COLL', c)

# ------------------------------------------------------------------ CLI hair (rigged) under the head
hs = bpy.data.objects['HairStatic']
with bpy.data.libraries.load(HAIR_BLEND, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in ('Hair', 'HairRig')]
for o in dst.objects: bpy.context.scene.collection.objects.link(o)
hair = bpy.data.objects['Hair']; hrig = bpy.data.objects['HairRig']
hrig.animation_data_clear(); hair.animation_data_clear()
for pb in hrig.pose.bones:
    pb.location = (0, 0, 0); pb.rotation_quaternion = (1, 0, 0, 0); pb.rotation_euler = (0, 0, 0); pb.scale = (1, 1, 1)
bpy.context.view_layer.update()
Mfit = hs.matrix_world @ hair.matrix_world.inverted()
s_fit = Mfit.to_scale()[0]
hrig.matrix_world = Mfit @ hrig.matrix_world
bpy.context.view_layer.update()
for o in (hrig, hair):
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
for md in hair.modifiers:
    if md.type == 'SOLIDIFY': md.thickness *= s_fit
bpy.data.objects.remove(hs)
print('HAIR fit scale', round(s_fit, 4))
# drop the hair rig's Root/Head bones, join into the character armature, parent strands to J_Bip_C_Head
bpy.ops.object.select_all(action='DESELECT'); hrig.select_set(True); bpy.context.view_layer.objects.active = hrig
bpy.ops.object.mode_set(mode='EDIT')
for n in ('Root', 'Head'):
    if n in hrig.data.edit_bones: hrig.data.edit_bones.remove(hrig.data.edit_bones[n])
bpy.ops.object.mode_set(mode='OBJECT')
if 'Head' in hair.vertex_groups: hair.vertex_groups['Head'].name = 'J_Bip_C_Head'
roots = [b.name for b in hrig.data.bones if b.parent is None]
bpy.ops.object.select_all(action='DESELECT'); hrig.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.join()
bpy.ops.object.mode_set(mode='EDIT')
for n in roots:
    arm.data.edit_bones[n].parent = arm.data.edit_bones['J_Bip_C_Head']
bpy.ops.object.mode_set(mode='OBJECT')
hair.parent = arm
for md in hair.modifiers:
    if md.type == 'ARMATURE': md.object = arm
# owner (2026-11-10, red marks): bangs must reach the top of the eyes -> stretch the front hair down.
# The crown stays put; the stretch grows from the hairline to the bang tips, front strands only.
BANG_TARGET_ABOVE_EYE = 0.010
eye_z = arm.data.bones['J_Adj_L_FaceEye'].head_local.z
head_y = arm.data.bones['J_Bip_C_Head'].head_local.y
hv = hair.data.vertices; hmw = hair.matrix_world; hmi = hmw.inverted()
gi = {g.index: g.name for g in hair.vertex_groups}
eye_x = abs(arm.data.bones['J_Adj_L_FaceEye'].head_local.x) + 0.02
bang_z = [(hmw @ v.co).z for v in hv if any(gi[g.group].startswith('Hair_Bang') and g.weight > 0.5 for g in v.groups)]
top_f = max(bang_z)
# fringe tip over the eyes: lowest front hair above the eye centre, in the eye columns
col = [(hmw @ v.co) for v in hv]
col = [p.z for p in col if abs(abs(p.x) - eye_x) < 0.015 and p.y < head_y - 0.05 and p.z > eye_z - 0.004]
tip = float(np.percentile(col, 5))
print('FRINGE column verts', len(col), 'z pct', [round(float(x), 4) for x in np.percentile(col, [0, 5, 25, 50])])
D = max(0.0, tip - (eye_z + BANG_TARGET_ABOVE_EYE))
def sst(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0))); return t * t * (3 - 2 * t)
def stretch(p):
    wz = sst(top_f, tip, p.z)                       # 0 at the hairline, 1 at the bang tips and below
    wy = sst(head_y - 0.005, head_y - 0.055, p.y)  # front strands only
    return Vector((p.x, p.y, p.z - D * wz * wy))
for v in hv:
    v.co = hmi @ stretch(hmw @ v.co)
hair.data.update()
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
for b in arm.data.edit_bones:
    if b.name.startswith('Hair_'):
        h, t = stretch(b.head.copy()), stretch(b.tail.copy())
        b.head = h; b.tail = t
bpy.ops.object.mode_set(mode='OBJECT')
print('BANGS stretched', round(D * 1000, 1), 'mm; tip was', round(tip, 4), 'eye', round(eye_z, 4), 'hairline', round(top_f, 4))
for side in ('L', 'R'):
    for ch in ('A', 'B'):
        CHAINS.append(dict(chain=f'Hair_Tail{side}_{ch}', bones=[f'Hair_Tail{side}_{ch}_{k}' for k in range(1, 7)], parent='J_Bip_C_Head'))
    CHAINS.append(dict(chain=f'Hair_Side{side}', bones=[f'Hair_Side{side}_{k}' for k in range(1, 5)], parent='J_Bip_C_Head'))
    CHAINS.append(dict(chain=f'Hair_Back{side}', bones=[f'Hair_Back{side}_{k}' for k in range(1, 5)], parent='J_Bip_C_Head'))
    CHAINS.append(dict(chain=f'Hair_Bang{side}', bones=[f'Hair_Bang{side}_{k}' for k in range(1, 3)], parent='J_Bip_C_Head'))
CHAINS.append(dict(chain='Hair_BangC', bones=['Hair_BangC_1', 'Hair_BangC_2'], parent='J_Bip_C_Head'))
CHAINS.append(dict(chain='Hair_Ahoge', bones=['Hair_Ahoge_1', 'Hair_Ahoge_2'], parent='J_Bip_C_Head'))
# CLI hair defect: a grey face-shaped patch painted on the back of the hair cap -> delete it (hair cap shows through)
import bmesh, colorsys
hm = hair.data
himg = [n.image for n in hm.materials[0].node_tree.nodes if n.type == 'TEX_IMAGE'][0]
Wt, Ht = himg.size; hpx = np.empty(Wt * Ht * 4, np.float32); himg.pixels.foreach_get(hpx); hpx = hpx.reshape(Ht, Wt, 4)
huv = hm.uv_layers.active.data
SV = np.zeros((len(hm.polygons), 2))
for p in hm.polygons:
    u = sum((huv[i].uv for i in p.loop_indices), Vector((0, 0))) / p.loop_total
    c = hpx[min(Ht - 1, int(u.y * Ht)), min(Wt - 1, int(u.x * Wt)), :3]
    _, sat, val = colorsys.rgb_to_hsv(*c); SV[p.index] = (sat, val)
hbm = bmesh.new(); hbm.from_mesh(hm); hbm.faces.ensure_lookup_table()
def in_patch(c): return abs(c.x) < 0.12 and c.y > -0.02 and 1.28 < c.z < 1.48
seed = [f.index for f in hbm.faces if f.material_index == 0 and SV[f.index, 0] < 0.07 and 0.35 < SV[f.index, 1] < 0.9
        and abs(f.calc_center_median().x) < 0.09 and f.calc_center_median().y > 0 and 1.30 < f.calc_center_median().z < 1.48]
Rg = set(seed); st = list(seed)
while st:
    f = hbm.faces[st.pop()]
    for e in f.edges:
        for g in e.link_faces:
            if g.index not in Rg and SV[g.index, 0] < 0.10 and 0.3 < SV[g.index, 1] < 0.92 and in_patch(g.calc_center_median()):
                Rg.add(g.index); st.append(g.index)
bmesh.ops.delete(hbm, geom=[hbm.faces[i] for i in Rg], context='FACES'); hbm.to_mesh(hm); hbm.free()
print('HAIR grey patch faces removed', len(Rg))
# sleeve top caps (owner screenshot 2026-11-10): each Tripo part is an open shell; the sleeve tube's top end sits
# under the capelet at rest but a raised arm swings it into view (see-through arc). Fill that end loop.
cbm = bmesh.new(); cbm.from_mesh(me); cbm.edges.ensure_lookup_table(); cbm.faces.ensure_lookup_table()
fpc = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', fpc)
open_e = [e for e in cbm.edges if len(e.link_faces) == 1 and fpc[e.link_faces[0].index] in (7, 11)]
seen = set(); capped = []
for e in open_e:
    if e.index in seen: continue
    st = [e]; comp = []
    while st:
        x = st.pop()
        if x.index in seen: continue
        seen.add(x.index); comp.append(x)
        for v in x.verts:
            for y in v.link_edges:
                if len(y.link_faces) == 1 and y.index not in seen and fpc[y.link_faces[0].index] in (7, 11): st.append(y)
    c = np.mean([v.co[:] for x in comp for v in x.verts], 0)
    side = 'L' if c[0] > 0 else 'R'
    if np.linalg.norm(c - B[f'J_Bip_{side}_UpperArm'][0]) < 0.10 and len(comp) > 20:
        capped.append((side, len(comp), comp))
uvc = cbm.loops.layers.uv.active; pl = cbm.faces.layers.int.get('part')
for side, n, comp in capped:
    k0 = fpc[comp[0].link_faces[0].index]; mi = comp[0].link_faces[0].material_index
    ref_uv = comp[0].link_loops[0][uvc].uv.copy()
    res = bmesh.ops.holes_fill(cbm, edges=comp, sides=0)
    newf = res['faces']
    if newf: bmesh.ops.triangulate(cbm, faces=newf)
    newf = [f for f in cbm.faces if f.is_valid and f.index < 0] if not newf else None
    print('CAP', side, 'loop edges', n)
cbm.faces.index_update()
for f in cbm.faces:
    if f.index >= len(fpc):
        f[pl] = 11 if f.calc_center_median().x <= 0 else 7
        f.material_index = 0
        # sleeve colour: copy a neighbouring face's UV centre onto the whole cap face
        nb = next((g for e in f.edges for g in e.link_faces if g.index < len(fpc)), None)
        if nb is not None:
            u = sum((l[uvc].uv for l in nb.loops), Vector((0, 0))) / len(nb.loops)
            for l in f.loops: l[uvc].uv = u
# sleeve liner: the shoulder puff / sleeve junction is jagged with cracks (hidden under the capelet at rest, seen
# with a raised arm). A closed tube just inside the upper sleeve (fitted per ring to the sleeve's inner radius,
# UpperArm only, sleeve colour) fills what shows through the cracks.
cbm.verts.ensure_lookup_table(); dl = cbm.verts.layers.deform.active
upper_gi = {sd: body.vertex_groups[f'J_Bip_{sd}_UpperArm'].index for sd in ('L', 'R')}
SV = np.array([v.co[:] for v in cbm.verts])
sl_mask = np.zeros(len(SV), bool)
for f in cbm.faces:
    if f[pl] in (7, 11):
        for v in f.verts: sl_mask[v.index] = True
# liner UV: a sleeve face mid upper arm, facing out (plain cream, away from trims)
ra_, rb_ = B['J_Bip_R_UpperArm'][0], B['J_Bip_R_LowerArm'][0]; rax = (rb_ - ra_) / np.linalg.norm(rb_ - ra_)
best = None
for f in cbm.faces:
    if f[pl] != 11: continue
    c = np.array(f.calc_center_median()[:]); t = (c - ra_) @ rax
    out = c - (ra_ + t * rax); out /= max(np.linalg.norm(out), 1e-6)
    sc_ = abs(t - 0.09) - 0.02 * float(np.dot(out, np.array(f.normal[:])))
    if best is None or sc_ < best[0]: best = (sc_, f)
ref_uv = sum((l[uvc].uv for l in best[1].loops), Vector((0, 0))) / len(best[1].loops)
NSEG, RINGS = 20, np.linspace(-0.02, 0.13, 6); nlin = 0
for sd in ('L', 'R'):
    a_, b_ = B[f'J_Bip_{sd}_UpperArm'][0], B[f'J_Bip_{sd}_LowerArm'][0]; ax_ = (b_ - a_) / np.linalg.norm(b_ - a_)
    u_ = np.cross(ax_, [0, 1, 0]); u_ /= np.linalg.norm(u_); w_ = np.cross(ax_, u_)
    side_m = sl_mask & ((SV[:, 0] > 0) if sd == 'L' else (SV[:, 0] <= 0))
    al = (SV - a_) @ ax_; rad = np.linalg.norm((SV - a_) - al[:, None] * ax_, axis=1)
    rings = []
    for t in RINGS:
        m_ = side_m & (np.abs(al - t) < 0.02) & (rad < 0.09)
        r = (np.percentile(rad[m_], 5) - 0.008) if m_.sum() > 10 else 0.03
        ring = []
        for k in range(NSEG):
            ph = 2 * math.pi * k / NSEG
            v = cbm.verts.new(Vector(a_ + t * ax_ + r * (math.cos(ph) * u_ + math.sin(ph) * w_)))
            v[dl][upper_gi[sd]] = 1.0; ring.append(v)
        rings.append(ring)
    new_f = []
    for i in range(len(rings) - 1):
        for k in range(NSEG):
            new_f.append(cbm.faces.new((rings[i][k], rings[i][(k + 1) % NSEG], rings[i + 1][(k + 1) % NSEG], rings[i + 1][k])))
    new_f.append(cbm.faces.new(list(reversed(rings[0])))); new_f.append(cbm.faces.new(rings[-1]))
    for f in new_f:
        f[pl] = 7 if sd == 'L' else 11; f.material_index = 0; f.smooth = True
        for l in f.loops: l[uvc].uv = ref_uv
    bmesh.ops.recalc_face_normals(cbm, faces=new_f); nlin += len(new_f)
print('LINER faces', nlin)
cbm.to_mesh(me); cbm.free()
print('CAPPED loops', len(capped), 'faces now', len(me.polygons))
# loose verts on the body
bbm = bmesh.new(); bbm.from_mesh(me)
loose = [v for v in bbm.verts if not v.link_faces]
bmesh.ops.delete(bbm, geom=loose, context='VERTS'); bbm.to_mesh(me); bbm.free()
print('BODY loose verts removed', len(loose))
missing = [b for c in CHAINS for b in c['bones'] if b not in arm.data.bones]
print('BONES total', len(arm.data.bones), 'chains', len(CHAINS), 'missing', missing)
json.dump(CHAINS, open(os.path.join(R, 'cloth_chains.json'), 'w'), indent=1)
json.dump(COLL, open(os.path.join(R, 'colliders.json'), 'w'), indent=1)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(R, 'rig_v3.blend'))
print('DONE')
