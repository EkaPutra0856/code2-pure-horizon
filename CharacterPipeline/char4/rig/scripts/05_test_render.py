"""Test renders of rig_v3: bone overview (x-ray), toon renders of poses with cloth/hair sway, face expressions."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys, math
from mathutils import Vector, Quaternion
sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"char4\face_compare\scripts"))
import common as C

R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
OUT = os.path.join(R, 'renders'); os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v3.blend'))
arm = bpy.data.objects['Char4_Armature']; body = bpy.data.objects['Body']; face = bpy.data.objects['Face']
PB = arm.pose.bones

# toon material for the Tripo body
img = None
for m in body.data.materials:
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].links:
            img = n.inputs['Base Color'].links[0].from_node.image
body.data.materials.clear(); body.data.materials.append(C.toon_from_image('Toon_Body', img, (0.80, 0.74, 0.80, 1)))
for p in body.data.polygons: p.use_smooth = True
# hair cap: toon in the CLI hair tone (Principled stays in the rig file for the UE export)
capimg = bpy.data.images.new('haircap_tone', 4, 4); capimg.pixels[:] = [0.58, 0.65, 0.80, 1.0] * 16
neck = bpy.data.objects['Neck']
for i, m in enumerate(neck.data.materials):
    if m and m.name.startswith('HairCap'):
        def _imgs(nt, seen=None):
            seen = seen or set(); out = []
            for n in nt.nodes:
                if n.type == 'TEX_IMAGE' and n.image: out.append(n.image)
                if n.type == 'GROUP' and n.node_tree and n.node_tree.name not in seen:
                    seen.add(n.node_tree.name); out += _imgs(n.node_tree, seen)
            return out
        lit = [im for im in _imgs(m.node_tree) if 'nml' not in im.name.lower() and im.size[0] >= 8]
        neck.data.materials[i] = C.toon_from_image('Toon_HairCap', lit[0] if lit else capimg, (0.62, 0.66, 0.85, 1))

def rot_world(pb, axis, deg):
    pb.rotation_mode = 'QUATERNION'
    M = arm.matrix_world.to_3x3() @ pb.bone.matrix_local.to_3x3()
    ax = (M.inverted() @ Vector(axis)).normalized()
    pb.rotation_quaternion = Quaternion(ax, math.radians(deg)) @ pb.rotation_quaternion

keys = face.data.shape_keys.key_blocks
def reset():
    for pb in PB:
        pb.rotation_mode = 'QUATERNION'; pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0)
    for k in keys:
        if k.name != 'Basis': k.value = 0

def chains(prefix):
    return sorted({b.name.rsplit('_', 1)[0] for b in arm.data.bones if b.name.startswith(prefix)})

def sway(prefix, axis, degs):
    for ch in chains(prefix):
        for i, d in enumerate(degs, 1):
            n = f'{ch}_{i}'
            if n in PB: rot_world(PB[n], axis, d)

def skirt_side(sign, axis, deg):
    """swing the skirt chains on one side (sign of x) of the body"""
    for ch in chains('J_Sec_Skirt'):
        h = arm.data.bones[ch + '_1'].head_local
        if h.x * sign > 0.02:
            rot_world(PB[ch + '_1'], axis, deg)

POSES = {
    'idle': [],
    'run': dict(b=[('J_Bip_L_UpperLeg', (-1, 0, 0), 55), ('J_Bip_L_LowerLeg', (1, 0, 0), 80), ('J_Bip_R_UpperLeg', (1, 0, 0), 30),
                   ('J_Bip_R_LowerLeg', (1, 0, 0), 60), ('J_Bip_C_Spine', (1, 0, 0), 12),
                   ('J_Bip_L_UpperArm', (1, 0, 0), 40), ('J_Bip_L_LowerArm', (-1, 0, 0), 60),
                   ('J_Bip_R_UpperArm', (-1, 0, 0), 45), ('J_Bip_R_LowerArm', (-1, 0, 0), 70)],
                cloth=lambda: (skirt_side(1, (-1, 0, 0), 30), skirt_side(-1, (1, 0, 0), 15),
                               sway('Hair_Tail', (1, 0, 0), [12, 10, 8, 6, 4, 3]), sway('J_Sec_Cape', (1, 0, 0), [15, 10]),
                               sway('J_Sec_Hood', (1, 0, 0), [10, 10]))),
    'bow_draw': dict(b=[('J_Bip_L_UpperArm', (0, -1, 0), 52), ('J_Bip_L_UpperArm', (0, 0, -1), 65),
                        ('J_Bip_R_UpperArm', (0, 1, 0), 55), ('J_Bip_R_UpperArm', (0, 0, 1), 55), ('J_Bip_R_LowerArm', (0, 0, 1), 125),
                        ('J_Bip_C_Spine', (0, 0, 1), 25), ('J_Bip_C_Neck', (0, 0, 1), -30),
                        ('J_Bip_L_UpperLeg', (0, -1, 0), 8), ('J_Bip_R_UpperLeg', (0, 1, 0), 8)],
                     cloth=lambda: sway('Hair_Tail', (0, 0, 1), [8, 6, 4, 3, 2, 2])),
    'heal_cast': dict(b=[('J_Bip_L_UpperArm', (1, 0, 0), -70), ('J_Bip_L_UpperArm', (0, -1, 0), 20),
                         ('J_Bip_R_UpperArm', (1, 0, 0), -70), ('J_Bip_R_UpperArm', (0, 1, 0), 20),
                         ('J_Bip_L_LowerArm', (1, 0, 0), -15), ('J_Bip_R_LowerArm', (1, 0, 0), -15),
                         ('J_Bip_C_Chest', (1, 0, 0), -8), ('J_Bip_C_Head', (1, 0, 0), -10)],
                      cloth=lambda: (sway('Hair_Tail', (0, 0, 0.0001), [0]), sway('J_Sec_Skirt', (0, 0, 1), [6, 4, 3]),
                                     sway('Hair_Tail', (-1, 0, 0), [-15, -10, -8, -6, -4, -3]))),
    'jump': dict(b=[('J_Bip_L_UpperLeg', (-1, 0, 0), 70), ('J_Bip_L_LowerLeg', (1, 0, 0), 110), ('J_Bip_R_UpperLeg', (-1, 0, 0), 30),
                    ('J_Bip_R_LowerLeg', (1, 0, 0), 90), ('J_Bip_L_UpperArm', (0, -1, 0), 35), ('J_Bip_R_UpperArm', (0, 1, 0), 35)],
                 cloth=lambda: (sway('J_Sec_Skirt', (1, 0, 0), [0]), [rot_world(PB[c + '_1'], Vector((math.sin(math.radians(a)), -math.cos(math.radians(a)), 0)).cross(Vector((0, 0, 1))), -25)
                                for c, a in [(c, math.degrees(math.atan2(arm.data.bones[c + '_1'].head_local.x, -arm.data.bones[c + '_1'].head_local.y))) for c in chains('J_Sec_Skirt')]],
                                sway('Hair_Tail', (-1, 0, 0), [-25, -15, -10, -5, -3, -2]), sway('J_Sec_Cape', (0, 0, 0.0001), [0]))),
}

cam = C.setup_render(res=(700, 1000))
sc = bpy.context.scene
for name, P in POSES.items():
    reset()
    if P:
        for b, ax, d in P['b']: rot_world(PB[b], ax, d)
        P['cloth']()
    bpy.context.view_layer.update()
    for yaw, tag in ((0, 'f'), (-35, 'q'), (150, 'b')):
        if name != 'idle' and tag == 'b': continue
        C.aim(cam, Vector((0, 0, 0.80)), 1.75, yaw)
        sc.render.filepath = os.path.join(OUT, f'pose_{name}_{tag}.png'); bpy.ops.render.render(write_still=True)

# expressions (VRoid shape keys), head close-up
reset(); bpy.context.view_layer.update()
hz = arm.data.bones['J_Bip_C_Head'].head_local.z
sc.render.resolution_x = 560; sc.render.resolution_y = 560
for nm, kv in [('neutral', {}), ('joy', {'Fcl_ALL_Joy': 1}), ('angry', {'Fcl_ALL_Angry': 1}), ('sorrow', {'Fcl_ALL_Sorrow': 1}),
               ('surprised', {'Fcl_ALL_Surprised': 1}), ('blink', {'Fcl_EYE_Close': 1}), ('mouth_A', {'Fcl_MTH_A': 1}), ('fun', {'Fcl_ALL_Fun': 1})]:
    reset()
    for k, v in kv.items():
        if k in keys: keys[k].value = v
    bpy.context.view_layer.update()
    C.aim(cam, Vector((0, 0, hz + 0.08)), 0.36, -15)
    sc.render.filepath = os.path.join(OUT, f'face_{nm}.png'); bpy.ops.render.render(write_still=True)

# bone overview: workbench x-ray + coloured sticks
reset(); bpy.context.view_layer.update()
cols = {'J_Bip': (0.9, 0.1, 0.1, 1), 'J_Sec_Skirt': (0.1, 0.3, 1, 1), 'J_Sec_Cape': (0.1, 0.8, 0.2, 1), 'J_Sec_Hood': (0.1, 0.8, 0.2, 1),
        'J_Sec_Pendant': (1, 0.5, 0, 1), 'Hair_': (1, 0.85, 0, 1), 'J_Adj': (1, 0, 1, 1)}
for b in arm.data.bones:
    c = next((v for k, v in cols.items() if b.name.startswith(k)), None)
    if not c: continue
    h, t = b.head_local, b.tail_local; d = t - h
    if d.length < 1e-4: continue
    bpy.ops.mesh.primitive_cylinder_add(radius=0.0045, depth=d.length, location=(h + t) / 2)
    o = bpy.context.active_object; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d)
    o.color = c; o.name = 'BN_' + b.name
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.008, location=h); s_ = bpy.context.active_object; s_.color = c; s_.name = 'BJ_' + b.name
sc.render.engine = 'BLENDER_WORKBENCH'
sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'OBJECT'; sh.show_xray = True; sh.xray_alpha = 0.35
for o in bpy.data.objects:
    if o.type == 'MESH' and not o.name.startswith(('BN_', 'BJ_')): o.color = (0.85, 0.85, 0.88, 1)
sc.render.resolution_x = 900; sc.render.resolution_y = 1100
for yaw, tag in ((0, 'f'), (90, 's')):
    C.aim(cam, Vector((0, 0, 0.80)), 1.75, yaw)
    sc.render.filepath = os.path.join(OUT, f'bones_{tag}.png'); bpy.ops.render.render(write_still=True)
print('DONE')
