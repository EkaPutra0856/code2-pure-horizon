"""Debug: bow_draw right shoulder close-up, toon + part-colour views."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys, math
from mathutils import Vector, Quaternion
sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"char4\face_compare\scripts"))
import common as C
R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
TAG = sys.argv[-1]; POSE = sys.argv[-2] if len(sys.argv) > 2 and sys.argv[-2] != '--' else 'bow_draw'
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v3.blend'))
arm = bpy.data.objects['Char4_Armature']; PB = arm.pose.bones; body = bpy.data.objects['Body']
src = open(os.path.join(R, 'scripts', '07_collide_check.py')).read()
ns = {}; exec(src[src.index('POSES = {'):src.index('GROUPS = ')], {}, ns); POSES = ns['POSES']
img = None
for m in body.data.materials:
    for n in m.node_tree.nodes:
        if n.type == 'BSDF_PRINCIPLED' and n.inputs['Base Color'].links: img = n.inputs['Base Color'].links[0].from_node.image
toon = C.toon_from_image('T', img)
PAL = {0: (0.2, 0.4, 1), 1: (0.1, 0.8, 0.2), 4: (1, 0.6, 0.1), 7: (1, 0.1, 0.1), 11: (1, 0.1, 0.8), 12: (0.9, 0.9, 0.2), 13: (0.5, 0.2, 1), 14: (0, 1, 1)}
pm = [C.flat_color(f'P{k}', (*c, 1)) for k, c in PAL.items()]
body.data.materials.clear(); body.data.materials.append(toon)
for m in pm: body.data.materials.append(m)
keys = list(PAL)
import numpy as np
part = np.zeros(len(body.data.polygons), np.int32); body.data.attributes['part'].data.foreach_get('value', part)
def rot_world(pb, axis, deg):
    pb.rotation_mode = 'QUATERNION'; M = pb.bone.matrix_local.to_3x3(); ax = (M.inverted() @ Vector(axis)).normalized()
    pb.rotation_quaternion = Quaternion(ax, math.radians(deg)) @ pb.rotation_quaternion
for b, ax, d in POSES[POSE]: rot_world(PB[b], ax, d)
bpy.context.view_layer.update()
cam = C.setup_render(res=(700, 700)); sc = bpy.context.scene
hair = bpy.data.objects['Hair']
for mode in ('toon', 'parts'):
    for p in body.data.polygons:
        p.material_index = 0 if mode == 'toon' else 1 + keys.index(part[p.index]) if part[p.index] in keys else 0
    hair.hide_render = (mode == 'parts')
    for i, (c, s, y) in enumerate((((-0.17, 0, 1.13), 0.3, -30), ((-0.17, 0, 1.13), 0.3, -80), ((-0.17, 0, 1.13), 0.3, 20))):
        C.aim(cam, Vector(c), s, y); sc.render.filepath = os.path.join(R, 'debug', 'shoulder', f'{TAG}_{mode}_{i}.png'); bpy.ops.render.render(write_still=True)
# no-sleeve view: torso coloured by R UpperArm weight (red = 1)
import bmesh
gi = body.vertex_groups['J_Bip_R_UpperArm'].index
wv = np.array([next((g.weight for g in v.groups if g.group == gi), 0.0) for v in body.data.vertices])
ca = body.data.color_attributes.new('W', 'FLOAT_COLOR', 'POINT')
for i, w in enumerate(wv): ca.data[i].color = (w, 0.2, 1 - w, 1)
wm = bpy.data.materials.new('WM'); wm.use_nodes = True; nt = wm.node_tree
at = nt.nodes.new('ShaderNodeVertexColor'); at.layer_name = 'W'; em = nt.nodes.new('ShaderNodeEmission')
nt.links.new(at.outputs['Color'], em.inputs['Color']); nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs[0])
body.data.materials.append(wm); wi = len(body.data.materials) - 1
for p in body.data.polygons:
    p.material_index = wi if part[p.index] == 4 else 1 + keys.index(part[p.index]) if part[p.index] in keys else 0
bm = bmesh.new(); bm.from_mesh(body.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if part[f.index] in (11, 12, 13, 1)], context='FACES_ONLY'); bm.to_mesh(body.data); bm.free()
bpy.context.view_layer.update()
for i, (c, s, y) in enumerate((((-0.17, 0, 1.13), 0.3, -30), ((-0.17, 0, 1.13), 0.3, -80), ((-0.17, 0, 1.13), 0.3, 20))):
    C.aim(cam, Vector(c), s, y); sc.render.filepath = os.path.join(R, 'debug', 'shoulder', f'{TAG}_nos_{i}.png'); bpy.ops.render.render(write_still=True)
