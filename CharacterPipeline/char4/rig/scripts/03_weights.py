"""Skin weights for the Tripo body (procedural, per labelled part, chain blending at joints), then a
pose test render. Head/neck keep their VRoid weights. Saves rig/rig_v2.blend."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, math, sys
import numpy as np
from mathutils import Vector, Matrix, Quaternion

R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v1.blend'))
arm = bpy.data.objects['Char4_Armature']; body = bpy.data.objects['Body']
me = body.data
B = {b.name: (np.array(b.head_local[:]), np.array(b.tail_local[:])) for b in arm.data.bones}
V = np.array([v.co[:] for v in me.vertices]); N = len(V)
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
vpart = np.full(N, -1)
for p in me.polygons:
    for vi in p.vertices:
        if vpart[vi] < 0: vpart[vi] = part[p.index]
W = {}
def add(name, w):
    W[name] = W.get(name, np.zeros(N)) + w

def sstep(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def chain_param(P, pts):
    """arc-length parameter of the nearest point on polyline pts (unclamped at both ends)."""
    best = np.full(len(P), np.inf); s = np.zeros(len(P)); acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]; ab = b - a; L = np.linalg.norm(ab)
        t = (P - a) @ ab / (L * L)
        tc = np.clip(t, 0 if i > 0 else -np.inf, 1 if i < len(pts) - 2 else np.inf)
        q = a + tc[:, None] * ab; d = np.linalg.norm(P - q, axis=1)
        m = d < best; best[m] = d[m]; s[m] = acc + tc[m] * L
        acc += L
    return s, best

def band_weights(s, joints, widths):
    """segments split at joints (arc positions) with smooth blend widths -> list of weight arrays."""
    out = []; n = len(joints)
    for i in range(n + 1):
        lo = np.ones_like(s) if i == 0 else sstep(joints[i - 1] - widths[i - 1], joints[i - 1] + widths[i - 1], s)
        hi = np.zeros_like(s) if i == n else sstep(joints[i] - widths[i], joints[i] + widths[i], s)
        out.append(lo - hi)
    return out

def spine_w(P):
    z = P[:, 2]
    J = [B['J_Bip_C_Spine'][0][2], B['J_Bip_C_Chest'][0][2], B['J_Bip_C_UpperChest'][0][2], B['J_Bip_C_Neck'][0][2]]
    ws = band_weights(z, J, [0.035, 0.04, 0.05, 0.03])
    return dict(zip(['J_Bip_C_Hips', 'J_Bip_C_Spine', 'J_Bip_C_Chest', 'J_Bip_C_UpperChest', 'J_Bip_C_Neck'], ws))

FING = ('Thumb', 'Index', 'Middle', 'Ring', 'Little')
def arm_w(P, side, sleeve=False):
    p = f'J_Bip_{side}_'
    pts = [B[p + 'Shoulder'][0], B[p + 'UpperArm'][0], B[p + 'LowerArm'][0], B[p + 'Hand'][0], B[p + 'Middle1'][0]]
    s, _ = chain_param(P, pts)
    L = np.cumsum([0] + [np.linalg.norm(pts[i + 1] - pts[i]) for i in range(len(pts) - 1)])
    # sleeve (owner screenshot 2026-11-10, bow_draw): the sleeve cap had ~58% Shoulder weight, so a raised arm left
    # it behind, the cap folded in and the torso shoulder under it showed through. The sleeve is cloth on the upper
    # arm: shoulder blend moved inward and narrowed so the cap rides the UpperArm.
    j1, w1 = (L[1] - 0.12, 0.02) if sleeve else (L[1], 0.035)
    ws = band_weights(s, [j1, L[2], L[3]], [w1, 0.035, 0.02])
    out = dict(zip([p + 'Shoulder', p + 'UpperArm', p + 'LowerArm'], ws[:3]))
    hand = ws[3]
    # hand group: palm segment (wrist -> middle1) vs finger bone segments, inverse distance
    segs = [(p + 'Hand', B[p + 'Hand'][0], B[p + 'Middle1'][0])]
    for b in B:
        if b.startswith(p) and any(f in b for f in FING):
            segs.append((b, B[b][0], B[b][1]))
    D = []
    for name, a, b in segs:
        ab = b - a; t = np.clip((P - a) @ ab / (ab @ ab), 0, 1); D.append(np.linalg.norm(P - (a + t[:, None] * ab), axis=1))
    D = np.array(D) + 1e-4
    D[0] *= 0.85                                 # palm wins ties
    G = D ** -6; G /= G.sum(0)
    for i, (name, _, _) in enumerate(segs):
        out[name] = out.get(name, 0) + hand * G[i]
    return out

def leg_w(P, side, boot=False):
    p = f'J_Bip_{side}_'
    pts = [B[p + 'UpperLeg'][0], B[p + 'LowerLeg'][0], B[p + 'Foot'][0], B[p + 'ToeBase'][0], B[p + 'ToeBase'][1]]
    s, _ = chain_param(P, pts)
    L = np.cumsum([0] + [np.linalg.norm(pts[i + 1] - pts[i]) for i in range(len(pts) - 1)])
    if boot:  # below the ankle: foot by forward distance, never shin
        ank = pts[2]; under = P[:, 2] < ank[2] + 0.01
        fwd = (ank[1] - P[:, 1]); toe_s = L[2] + np.clip(fwd, 0, None) / max(ank[1] - pts[3][1], 1e-3) * (L[3] - L[2])
        s = np.where(under, np.maximum(toe_s, L[2] + 0.03), s)
    ws = band_weights(s, [L[1], L[2], L[3]], [0.045, 0.03, 0.015])
    out = dict(zip([p + 'UpperLeg', p + 'LowerLeg', p + 'Foot', p + 'ToeBase'], ws))
    hz = B[p + 'UpperLeg'][0][2]
    f = sstep(hz - 0.03, hz + 0.05, P[:, 2]) * 0.6
    res = {k: v * (1 - f) for k, v in out.items()}
    res['J_Bip_C_Hips'] = f
    return res

def blend(a, b, f):
    out = {}
    for k, v in a.items(): out[k] = out.get(k, 0) + v * (1 - f)
    for k, v in b.items(): out[k] = out.get(k, 0) + v * f
    return out

def put(mask, d):
    for k, v in d.items():
        w = np.zeros(N); w[mask] = v if np.isscalar(v) else v
        add(k, w)

for side, sx, parts in (('L', 1, (7,)), ('R', -1, (11, 12, 13))):
    m = np.isin(vpart, parts); put(m, arm_w(V[m], side, sleeve=True))
for side, thigh, boot in (('L', 8, 5), ('R', 9, 6)):
    m = vpart == thigh; put(m, leg_w(V[m], side))
    m = vpart == boot; put(m, leg_w(V[m], side, boot=True))
# torso / capelet / pendant: spine + shoulder blend at the sides
m = np.isin(vpart, (4, 1, 14)); P = V[m]
sw = spine_w(P)
f_sh = sstep(0.085, 0.17, np.abs(P[:, 0])) * sstep(0.98, 1.08, P[:, 2])
aw = {}
for side, sgn in (('L', 1), ('R', -1)):
    side_m = (P[:, 0] * sgn) > 0
    for k, v in arm_w(P, side).items():
        aw[k] = aw.get(k, 0) + v * side_m
put(m, blend(sw, aw, f_sh))
# skirt / belt / shorts: spine + legs toward the hem
m = vpart == 0; P = V[m]
sw = spine_w(P)
lw = {}
dleg = np.full(len(P), np.inf)
for side, sgn in (('L', 1), ('R', -1)):
    side_m = (P[:, 0] * sgn) > 0
    _, d = chain_param(P, [B[f'J_Bip_{side}_UpperLeg'][0], B[f'J_Bip_{side}_LowerLeg'][0]])
    dleg = np.where(side_m, d, dleg)
    for k, v in leg_w(P, side).items():
        lw[k] = lw.get(k, 0) + v * side_m
# shorts (close to the leg) follow the leg exactly like the thigh below them, so a raised thigh cannot pierce them
f_leg = np.where(dleg < 0.085, sstep(0.88, 0.80, P[:, 2]), 0.45 * sstep(0.82, 0.70, P[:, 2]))
put(m, blend(sw, lw, f_leg))

# write groups: top-4, normalised
names = sorted(W); M = np.array([W[n] for n in names])
M[M < 1e-3] = 0
order = np.argsort(-M, axis=0)
keep = np.zeros_like(M, bool)
for r in range(4): keep[order[r], np.arange(N)] = True
M = np.where(keep, M, 0); M /= np.maximum(M.sum(0), 1e-9)
# laplacian smoothing along mesh edges (2 passes, factor 0.5), then top-4 again
E = np.array([e.vertices[:] for e in me.edges])
deg = np.bincount(E.ravel(), minlength=N).astype(float)
for _ in range(2):
    acc = np.zeros_like(M)
    np.add.at(acc.T, E[:, 0], M[:, E[:, 1]].T); np.add.at(acc.T, E[:, 1], M[:, E[:, 0]].T)
    avg = np.where(deg > 0, acc / np.maximum(deg, 1), M)
    M = 0.5 * M + 0.5 * avg
order = np.argsort(-M, axis=0); keep = np.zeros_like(M, bool)
for r in range(4): keep[order[r], np.arange(N)] = True
M = np.where(keep, M, 0); M /= np.maximum(M.sum(0), 1e-9)
unweighted = int((M.sum(0) < 0.5).sum())
print('WEIGHTS bones', len(names), 'unweighted verts', unweighted)
body.vertex_groups.clear()
for i, n in enumerate(names):
    g = body.vertex_groups.new(name=n)
    nz = np.nonzero(M[i])[0]
    for vi in nz: g.add([int(vi)], float(M[i, vi]), 'REPLACE')
bpy.ops.object.select_all(action='DESELECT'); body.select_set(True); bpy.context.view_layer.objects.active = body
body.modifiers.clear(); md = body.modifiers.new('Armature', 'ARMATURE'); md.object = arm
# hair: rigid on the head bone for now (strand bones come in the cloth/hair step)
hs = bpy.data.objects.get('HairStatic')
if hs:
    mw = hs.matrix_world.copy(); hs.parent = arm; hs.parent_type = 'BONE'; hs.parent_bone = 'J_Bip_C_Head'
    hs.matrix_world = mw
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(R, 'rig_v2.blend'))

# ------------------------------------------------------------------ pose test
def rot_world(pb, axis, deg):
    """rotate a pose bone about a world axis (applied on top of its current local rotation)."""
    pb.rotation_mode = 'QUATERNION'
    M = arm.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()
    ax = (M.inverted() @ Vector(axis)).normalized()
    pb.rotation_quaternion = Quaternion(ax, math.radians(deg)) @ pb.rotation_quaternion

def reset():
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)

PB = arm.pose.bones
POSES = {
    'rest': [],
    'tpose': [('J_Bip_L_UpperArm', (0, -1, 0), 50), ('J_Bip_R_UpperArm', (0, 1, 0), 50)],
    'walk': [('J_Bip_L_UpperLeg', (-1, 0, 0), 45), ('J_Bip_L_LowerLeg', (1, 0, 0), 70), ('J_Bip_R_UpperLeg', (1, 0, 0), 25),
             ('J_Bip_L_UpperArm', (1, 0, 0), 25), ('J_Bip_R_UpperArm', (-1, 0, 0), 30), ('J_Bip_R_LowerArm', (-1, 0, 0), 40)],
    'bow': [('J_Bip_L_UpperArm', (0, -1, 0), 50), ('J_Bip_L_UpperArm', (0, 0, -1), 70),
            ('J_Bip_R_UpperArm', (0, 1, 0), 50), ('J_Bip_R_UpperArm', (0, 0, 1), 60), ('J_Bip_R_LowerArm', (0, 0, 1), 120),
            ('J_Bip_C_Spine', (0, 0, 1), 20), ('J_Bip_C_Head', (0, 0, 1), -35)],
    'crouch': [('J_Bip_C_Spine', (1, 0, 0), 25), ('J_Bip_C_Chest', (1, 0, 0), 10),
               ('J_Bip_L_UpperLeg', (-1, 0, 0), 80), ('J_Bip_L_LowerLeg', (1, 0, 0), 110), ('J_Bip_L_Foot', (-1, 0, 0), 30),
               ('J_Bip_R_UpperLeg', (-1, 0, 0), 20), ('J_Bip_R_LowerLeg', (1, 0, 0), 60),
               ('J_Bip_L_UpperArm', (0, -1, 0), 20), ('J_Bip_L_LowerArm', (0, 0, -1), 60), ('J_Bip_R_UpperArm', (1, 0, 0), -40)],
}
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'
cam = bpy.data.objects.new('dbgcam', bpy.data.cameras.new('dbgcam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.9
sc.render.resolution_x = 700; sc.render.resolution_y = 900
os.makedirs(os.path.join(R, 'debug', 'pose'), exist_ok=True)
for name, ops in POSES.items():
    reset()
    for b, ax, deg in ops: rot_world(PB[b], ax, deg)
    bpy.context.view_layer.update()
    for yaw, tag in ((0, 'f'), (-40, 'q')):
        a_ = math.radians(yaw); c_ = Vector((0, 0, 0.82))
        cam.location = c_ + Vector((math.sin(a_), -math.cos(a_), 0)) * 5; cam.rotation_euler = (math.radians(90), 0, a_)
        sc.render.filepath = os.path.join(R, 'debug', 'pose', f'{name}_{tag}.png'); bpy.ops.render.render(write_still=True)
print('DONE')
