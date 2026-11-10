"""Fit the VRoid J_Bip skeleton to the Tripo body (A-pose kept; every bone frame = VRoid frame rotated
onto the new bone direction, so J_Bip clips stay valid), graft the VRoid head (Face + neck, own weights
and shape keys) scaled onto the Tripo neck, fit the CLI twin-tail hair. Saves rig/rig_v1.blend."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, os, sys, math
import numpy as np
from mathutils import Vector, Matrix
sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"char4\face_compare\scripts"))
import common as C

R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
VRM = os.path.join(ANIME_GAME_ROOT, r"karakter_final.vrm")
S = 1.6736
T_EYE = Vector((0.0276, -0.0840, 0.8337)) * S    # Tripo eye centre (L) from face_compare rim fit
T_CHIN_Z = 0.777 * S
LOG = []
def log(*a):
    s = ' '.join(str(x) for x in a); print(s); LOG.append(s)

bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'body_prep.blend'))
body = bpy.data.objects['Body']
me = body.data
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
V = np.array([v.co[:] for v in me.vertices])
vpart = np.full(len(V), -1)
for p in me.polygons:
    for vi in p.vertices: vpart[vi] = part[p.index]
def pv(*ks): return V[np.isin(vpart, ks)]

# ------------------------------------------------------------------ joints from the Tripo body
def pca(P):
    c = P.mean(0); u, s, vt = np.linalg.svd(P - c, full_matrices=False); return c, vt
A = pv(11, 13, 12)                                   # right arm (x<0)
c, vt = pca(A); d = vt[0] if vt[0][0] < 0 else -vt[0]
t = (A - c) @ d; L = t.max() - t.min()
sh = A[t < t.min() + 0.07 * L].mean(0)
Hd = pv(12); th = (Hd - c) @ d
wr = Hd[th < th.min() + 0.15 * (th.max() - th.min())].mean(0)
tip = Hd[np.argmax(th)]
Sl = pv(11, 13); ts = (Sl - c) @ d
tm = 0.5 * (((sh - c) @ d) + ((wr - c) @ d))
el = Sl[np.abs(ts - tm) < 0.012].mean(0)
hc, hvt = pca(Hd); palm_n = hvt[2]
J = {}
for side, sx in (('R', 1), ('L', -1)):
    m = np.array([sx, 1, 1])
    J[side] = dict(sh=Vector(sh * m) + Vector((-0.01 * sx, 0, 0.015)), el=Vector(el * m), wr=Vector(wr * m), tip=Vector(tip * m), palm=Vector(palm_n * m))
# legs
P0 = pv(0)
crotch = P0[(np.abs(P0[:, 0]) < 0.012) & (P0[:, 1] < -0.02) & (P0[:, 1] > -0.2)][:, 2].min()
hip_z = crotch + 0.055
for side, thigh, boot, sx in (('L', 8, 5, 1), ('R', 9, 6, -1)):
    Tg = pv(thigh); s_ = Tg[(Tg[:, 2] > crotch - 0.07) & (Tg[:, 2] < crotch - 0.03)]
    hip = Vector((s_[:, 0].mean(), s_[:, 1].mean(), hip_z))
    B = pv(boot); shaft = B[(B[:, 2] > 0.13) & (B[:, 2] < 0.17)]
    ank = Vector((shaft[:, 0].mean(), shaft[:, 1].mean(), 0.085))
    low = B[B[:, 2] < 0.05]; toe_y = low[:, 1].min()
    toe = Vector((low[low[:, 1] < toe_y + 0.01][:, 0].mean(), toe_y + 0.01, 0.02))
    kz = ank.z + 0.54 * (hip.z - ank.z)
    LL = np.vstack([Tg, B]); ks = LL[np.abs(LL[:, 2] - kz) < 0.012]
    knee = Vector((ks[:, 0].mean(), ks[:, 1].mean() - 0.005, kz))
    toeb = Vector((ank.x * 0.3 + toe.x * 0.7, ank.y + 0.68 * (toe.y - ank.y), 0.028))
    J[side].update(hip=hip, knee=knee, ank=ank, toeb=toeb, toe=toe)
for k in ('R', 'L'):
    log('JOINTS', k, {n: [round(x, 3) for x in v] for n, v in J[k].items()})
log('crotch', round(crotch, 4))

# ------------------------------------------------------------------ VRoid import
before = set(bpy.data.objects)
bpy.ops.preferences.addon_enable(module='VRM_Addon_for_Blender-release')
bpy.ops.import_scene.vrm(filepath=VRM)
for n in ('Hair_New', 'Hair_Band', 'Ears_Elf', 'Flowers'):
    if n in bpy.data.objects: bpy.data.objects.remove(bpy.data.objects[n])
arm = bpy.data.objects['Armature']; face = bpy.data.objects['Face']; vbody = bpy.data.objects['Body.001'] if 'Body.001' in bpy.data.objects else None
if vbody is None:
    vbody = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith('Body') and o is not body][0]
vbody.name = 'Neck'
VB = {b.name: (arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local, (arm.matrix_world.to_3x3() @ b.matrix_local.to_3x3())) for b in arm.data.bones}

# head similarity transform (VRoid -> Tripo)
iris_idx = [i for i, m in enumerate(face.data.materials) if m and 'EyeIris' in m.name]
skin_idx = [i for i, m in enumerate(face.data.materials) if m and 'Face_00_SKIN' in m.name][0]
fv = face.data.vertices; fw = face.matrix_world
iv = sorted({i for p in face.data.polygons if p.material_index in iris_idx for i in p.vertices})
iv = [fw @ fv[i].co for i in iv]
eyeL = sum((v for v in iv if v.x > 0), Vector()) / len([v for v in iv if v.x > 0])
sk = [fw @ fv[i].co for p in face.data.polygons if p.material_index == skin_idx for i in p.vertices]
mean_y = sum(v.y for v in sk) / len(sk)
v_chin = min(v.z for v in sk if abs(v.x) < 0.006 and v.y < mean_y)
k_v = (T_EYE.z - T_CHIN_Z) / (eyeL.z - v_chin); k_h = T_EYE.x / eyeL.x
k = 0.5 * (k_v + k_h)
off = Vector((0, T_EYE.y, T_EYE.z)) - k * Vector((0, eyeL.y, eyeL.z))
HT = Matrix.Translation(off) @ Matrix.Scale(k, 4)
log('HEAD k_v', round(k_v, 4), 'k_h', round(k_h, 4), 'k', round(k, 4), 'off', [round(x, 4) for x in off], 'vroid eye', [round(x, 4) for x in eyeL], 'chin', round(v_chin, 4))

# neck piece from the VRoid body
bm = bmesh.new(); bm.from_mesh(vbody.data)
hb = [i for i, m in enumerate(vbody.data.materials) if m and 'HairBack' in m.name]
cut_z = 1.235
dl = [f for f in bm.faces if f.material_index not in hb and ((vbody.matrix_world @ f.calc_center_median()).z < cut_z
      or abs((vbody.matrix_world @ f.calc_center_median()).x) > 0.075)]
bmesh.ops.delete(bm, geom=dl, context='FACES'); bm.to_mesh(vbody.data); bm.free()
log('NECK faces', len(vbody.data.polygons))
# hair cap (VRoid HairBack) recoloured to the CLI hair tone so the back of the skull is covered
HAIRCAP_DARK = np.array([0.30, 0.36, 0.52]); HAIRCAP_LIGHT = np.array([0.80, 0.85, 0.95])
def _imgs(nt, seen=None):
    seen = seen or set(); out = set()
    for n in nt.nodes:
        if n.type == 'TEX_IMAGE' and n.image: out.add(n.image)
        if n.type == 'GROUP' and n.node_tree and n.node_tree.name not in seen:
            seen.add(n.node_tree.name); out |= _imgs(n.node_tree, seen)
    return out
cap_imgs = set()
for i in hb:
    m = vbody.data.materials[i]
    if m and m.node_tree: cap_imgs |= _imgs(m.node_tree)
for img in cap_imgs:   # keep the VRoid strand texture, recolour it to the CLI hair tone by luminance
    if 'nml' in img.name.lower() or 'normal' in img.name.lower() or img.name.startswith('Shader_') or img.size[0] < 16: continue
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
    lum = (0.3 * px[:, 0] + 0.59 * px[:, 1] + 0.11 * px[:, 2])
    lo, hi = np.percentile(lum, 2), np.percentile(lum, 98)
    t = np.clip((lum - lo) / max(hi - lo, 1e-4), 0, 1)[:, None]
    px[:, :3] = HAIRCAP_DARK * (1 - t) + HAIRCAP_LIGHT * t
    img.pixels[:] = px.ravel(); img.pack()
    log('HAIRCAP recolour', img.name, img.size[:])
for i in hb: vbody.data.materials[i].name = 'HairCap'
# teal iris (same recolour as the face comparison)
def tree_images(nt, seen=None):
    seen = seen or set(); out = set()
    for n in nt.nodes:
        if n.type == 'TEX_IMAGE' and n.image: out.add(n.image)
        if n.type == 'GROUP' and n.node_tree and n.node_tree.name not in seen:
            seen.add(n.node_tree.name); out |= tree_images(n.node_tree, seen)
    return out
iris_imgs = set()
for m in face.data.materials:
    if m and 'EyeIris' in m.name and m.node_tree: iris_imgs |= tree_images(m.node_tree)
for img in iris_imgs:
    if 'nml' in img.name.lower() or 'normal' in img.name.lower() or img.name.startswith('Shader_'): continue
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4); rgb = px[:, :3]
    mx = rgb.max(1); mn = rgb.min(1); v = mx; s_ = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    h = 0.47; f = h * 6 - 2; p_ = v * (1 - s_); t_ = v * (1 - (1 - f) * s_)
    rgb[:] = np.stack([p_, v, t_], 1); px[:, :3] = rgb; img.pixels[:] = px.ravel(); img.pack()
    log('IRIS teal', img.name)
# weights on bones that will not exist (old character's J_Sec) go to the head
keep_b = {b.name for b in arm.data.bones if b.name.startswith('J_Bip') or b.name.startswith('J_Adj')}
for o in (face, vbody):
    gi = {g.index: g.name for g in o.vertex_groups}
    hg = o.vertex_groups.get('J_Bip_C_Head') or o.vertex_groups.new(name='J_Bip_C_Head')
    moved = 0
    for v in o.data.vertices:
        extra = sum(g.weight for g in v.groups if gi.get(g.group) not in keep_b and gi.get(g.group) is not None)
        if extra > 0:
            hg.add([v.index], extra, 'ADD'); moved += 1
    for g in list(o.vertex_groups):
        if g.name not in keep_b: o.vertex_groups.remove(g)
    log('REWEIGHT', o.name, moved)
for o in (face, vbody):
    o.matrix_world = HT @ o.matrix_world
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True); bpy.context.view_layer.objects.active = o
    o.modifiers.clear()
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ------------------------------------------------------------------ new armature (copy of VRoid J_Bip)
bpy.ops.object.select_all(action='DESELECT')
arm.select_set(True); bpy.context.view_layer.objects.active = arm
for o in (face, vbody):
    o.parent = None
bpy.ops.object.mode_set(mode='EDIT')
eb = arm.data.edit_bones
for b in list(eb):
    if not (b.name.startswith('J_Bip') or b.name.startswith('J_Adj') or b.name == 'Root'):
        eb.remove(b)

def place(name, head, tail):
    b = eb[name]; h0, t0, M0 = VB[name]
    d0 = (t0 - h0).normalized(); d1 = (tail - head).normalized()
    Rb = d0.rotation_difference(d1).to_matrix()
    b.matrix = Matrix.Translation(head) @ (Rb @ M0).to_4x4()
    b.length = (tail - head).length
    return Rb

def place_rel(name, origin_v, origin_t, Rm, s):
    """VRoid bone mapped by a similarity (rotate Rm, scale s) around origin."""
    b = eb[name]; h0, t0, M0 = VB[name]
    h = origin_t + s * (Rm @ (h0 - origin_v)); tl = origin_t + s * (Rm @ (t0 - origin_v))
    b.matrix = Matrix.Translation(h) @ (Rm @ M0).to_4x4(); b.length = (tl - h).length

# spine: piecewise map of VRoid z between hip joint and shoulder joint
vh = VB['J_Bip_L_UpperLeg'][0].z; vs = VB['J_Bip_L_UpperArm'][0].z
th_ = hip_z; ts_ = 0.5 * (J['L']['sh'].z + J['R']['sh'].z)
yh = 0.5 * (J['L']['hip'].y + J['R']['hip'].y); ys = 0.5 * (J['L']['sh'].y + J['R']['sh'].y)
def spine_pt(vz):
    f = (vz - vh) / (vs - vh)
    return Vector((0, yh + f * (ys - yh), th_ + f * (ts_ - th_)))
neck_h = HT @ VB['J_Bip_C_Neck'][0]
head_h = HT @ VB['J_Bip_C_Head'][0]
pts = {n: spine_pt(VB[n][0].z) for n in ('J_Bip_C_Hips', 'J_Bip_C_Spine', 'J_Bip_C_Chest', 'J_Bip_C_UpperChest')}
place('J_Bip_C_Hips', pts['J_Bip_C_Hips'], spine_pt(VB['J_Bip_C_Hips'][1].z))
place('J_Bip_C_Spine', pts['J_Bip_C_Spine'], pts['J_Bip_C_Chest'])
place('J_Bip_C_Chest', pts['J_Bip_C_Chest'], pts['J_Bip_C_UpperChest'])
place('J_Bip_C_UpperChest', pts['J_Bip_C_UpperChest'], neck_h)
for n in [b.name for b in eb if b.name in ('J_Bip_C_Neck', 'J_Bip_C_Head') or b.name.startswith('J_Adj')]:
    eb[n].matrix = Matrix.Translation(HT @ VB[n][0]) @ VB[n][2].to_4x4(); eb[n].length = k * (VB[n][1] - VB[n][0]).length
for side in ('L', 'R'):
    j = J[side]; P = f'J_Bip_{side}_'
    sh_head = Vector((math.copysign(0.022, j['sh'].x), j['sh'].y + 0.01, j['sh'].z + 0.012))
    place(P + 'Shoulder', sh_head, j['sh'])
    place(P + 'UpperArm', j['sh'], j['el'])
    place(P + 'LowerArm', j['el'], j['wr'])
    # hand + fingers: similarity from VRoid hand (head -> middle tip) onto Tripo wrist -> tip, then palm twist
    vhh = VB[P + 'Hand'][0]; vtip = VB[P + 'Middle3'][1]
    d0 = (vtip - vhh).normalized(); d1 = (j['tip'] - j['wr']).normalized()
    Rm = d0.rotation_difference(d1).to_matrix()
    n_v = Rm @ (VB[P + 'Hand'][2] @ Vector((0, 0, 1)))   # VRoid hand local axis mapped
    n_t = j['palm'] if j['palm'].dot(n_v) > 0 else -j['palm']
    a = n_v - d1 * n_v.dot(d1); b_ = n_t - d1 * n_t.dot(d1)
    tw = a.normalized().rotation_difference(b_.normalized()).to_matrix() if a.length > 1e-6 and b_.length > 1e-6 else Matrix.Identity(3)
    Rm = tw @ Rm
    s_h = (j['tip'] - j['wr']).length / (vtip - vhh).length
    for b in [b.name for b in eb if b.name.startswith(P) and any(f in b.name for f in ('Hand', 'Thumb', 'Index', 'Middle', 'Ring', 'Little'))]:
        place_rel(b, vhh, j['wr'], Rm, s_h)
    place(P + 'UpperLeg', j['hip'], j['knee'])
    place(P + 'LowerLeg', j['knee'], j['ank'])
    place(P + 'Foot', j['ank'], j['toeb'])
    place(P + 'ToeBase', j['toeb'], j['toe'])
    log('HAND', side, 'scale', round(s_h, 3), 'twist deg', round(math.degrees(a.angle(b_)) if a.length > 1e-6 else 0, 1))
# connectivity: children heads follow parents' tails where VRoid had them connected
eb['J_Bip_C_Hips'].use_connect = False
for b in eb:
    if b.parent and b.use_connect:
        b.parent.tail = b.head
if 'Root' in eb:
    eb['Root'].head = Vector((0, 0, 0)); eb['Root'].tail = Vector((0, 0, 0.1))
bpy.ops.object.mode_set(mode='OBJECT')
arm.name = 'Char4_Armature'; arm.data.name = 'Char4_Armature'
for o in [o for o in bpy.data.objects if o.type == 'EMPTY']:
    bpy.data.objects.remove(o)
log('BONES', len(arm.data.bones))

# recentre: hips over the origin in y
dy = -arm.data.bones['J_Bip_C_Hips'].head_local.y
for o in (body, face, vbody):
    for v in o.data.vertices: v.co.y += dy
    if o.data.shape_keys:
        for kb in o.data.shape_keys.key_blocks:
            for d in kb.data: d.co.y += dy
bpy.ops.object.select_all(action='DESELECT'); arm.select_set(True); bpy.context.view_layer.objects.active = arm
bpy.ops.object.mode_set(mode='EDIT')
pos = {b.name: (b.head.copy(), b.tail.copy(), b.roll) for b in arm.data.edit_bones}
sh_ = Vector((0, dy, 0))
for b in arm.data.edit_bones:
    h, t_, r_ = pos[b.name]; b.head = h + sh_; b.tail = t_ + sh_; b.roll = r_
bpy.ops.object.mode_set(mode='OBJECT')
log('recentre dy', round(dy, 4))

# head + neck keep VRoid weights; parent to the new armature
for o in (face, vbody):
    o.parent = arm
    md = o.modifiers.new('Armature', 'ARMATURE'); md.object = arm
body.parent = arm

# ------------------------------------------------------------------ CLI hair on the VRoid skull
sk = [face.matrix_world @ fv[i].co for p in face.data.polygons if p.material_index == skin_idx for i in p.vertices]
top = max(v.z for v in sk); chin = min(v.z for v in sk if abs(v.x) < 0.006 * k and v.y < sum(q.y for q in sk) / len(sk))
band = [v for v in sk if v.z > top - 0.05 * k]; cy = sum(v.y for v in band) / len(band)
hair, meas = C.load_hair()
s_ = C.fit_hair(hair, meas, chin, top, cy, use='skull')
# owner (2026-11-10): forehead too wide -> hair 1 cm lower, 3% bigger around the skull top
HAIR_DROP, HAIR_GROW = 0.010, 1.03
ftop = max((face.matrix_world @ v.co).z for v in face.data.vertices)
pv_ = Vector((0, 0.01, ftop - 0.02))
hair.matrix_world = Matrix.Translation((0, 0, -HAIR_DROP)) @ Matrix.Translation(pv_) @ Matrix.Scale(HAIR_GROW, 4) @ Matrix.Translation(-pv_) @ hair.matrix_world
log('HAIR fit scale', round(s_, 4), 'top', round(top, 4), 'chin', round(chin, 4))

# ------------------------------------------------------------------ debug render (x-ray + joint markers)
mk = bpy.data.materials.new('mk'); mk.diffuse_color = (1, 0.1, 0.1, 1)
for b in arm.data.bones:
    if b.name.startswith('J_Bip') and not any(f in b.name for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Little')):
        bpy.ops.mesh.primitive_uv_sphere_add(radius=0.012, location=arm.matrix_world @ b.head_local)
        o = bpy.context.active_object; o.name = 'MK_' + b.name; o.data.materials.append(mk); o.color = (1, 0, 0, 1)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'TEXTURE'; sh.show_xray = True; sh.xray_alpha = 0.55
cam = bpy.data.objects.new('dbgcam', bpy.data.cameras.new('dbgcam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.8
sc.render.resolution_x = 1000; sc.render.resolution_y = 1100
for yaw, nm in ((0, 'front'), (90, 'side')):
    a_ = math.radians(yaw); c_ = Vector((0, 0, 0.82))
    cam.location = c_ + Vector((math.sin(a_), -math.cos(a_), 0)) * 5; cam.rotation_euler = (math.radians(90), 0, a_)
    sc.render.filepath = os.path.join(R, 'debug', f'skel_{nm}.png'); bpy.ops.render.render(write_still=True)
for o in [o for o in bpy.data.objects if o.name.startswith('MK_')]:
    bpy.data.objects.remove(o)
bpy.data.objects.remove(cam)
sh.show_xray = False
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(R, 'rig_v1.blend'))
open(os.path.join(R, 'skeleton.log'), 'w').write('\n'.join(LOG))
print('DONE')
