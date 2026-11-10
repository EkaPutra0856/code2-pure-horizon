import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys, math, bmesh, numpy as np
from mathutils import Vector, Quaternion
sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"char4\face_compare\scripts"))
import common as C
R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
bpy.ops.wm.open_mainfile(filepath=os.path.join(R, 'rig_v3.blend'))
arm = bpy.data.objects['Char4_Armature']; PB = arm.pose.bones; body = bpy.data.objects['Body']; me = body.data
src = open(os.path.join(R, 'scripts', '07_collide_check.py')).read()
ns = {}; exec(src[src.index('POSES = {'):src.index('GROUPS = ')], {}, ns); POSES = ns['POSES']
part = np.zeros(len(me.polygons), np.int32); me.attributes['part'].data.foreach_get('value', part)
for o in bpy.data.objects:
    if o.type == 'MESH' and o != body: o.hide_render = True
# front = green, back = red (backface via geometry node 'Backfacing')
m = bpy.data.materials.new('BF'); m.use_nodes = True; nt = m.node_tree
g = nt.nodes.new('ShaderNodeNewGeometry'); mix = nt.nodes.new('ShaderNodeMixRGB'); em = nt.nodes.new('ShaderNodeEmission')
mix.inputs[1].default_value = (0.9, 0.9, 0.6, 1); mix.inputs[2].default_value = (1, 0, 0, 1)
nt.links.new(g.outputs['Backfacing'], mix.inputs[0]); nt.links.new(mix.outputs[0], em.inputs[0]); nt.links.new(em.outputs[0], nt.nodes['Material Output'].inputs[0])
m.use_backface_culling = False
me.materials.clear(); me.materials.append(m)
bm = bmesh.new(); bm.from_mesh(me)
bmesh.ops.delete(bm, geom=[f for f in bm.faces if part[f.index] not in (11, 13, 12)], context='FACES_ONLY'); bm.to_mesh(me); bm.free()
def rot_world(pb, axis, deg):
    pb.rotation_mode = 'QUATERNION'; M = pb.bone.matrix_local.to_3x3(); ax = (M.inverted() @ Vector(axis)).normalized()
    pb.rotation_quaternion = Quaternion(ax, math.radians(deg)) @ pb.rotation_quaternion
pose = sys.argv[-1]
for b, ax, d in POSES[pose]: rot_world(PB[b], ax, d)
bpy.context.view_layer.update()
cam = C.setup_render(res=(700, 700)); sc = bpy.context.scene
for i, (c, s, y) in enumerate((((-0.17, 0, 1.13), 0.3, -30), ((-0.20, 0, 1.08), 0.4, -100), ((-0.20, 0, 1.08), 0.4, 150))):
    C.aim(cam, Vector(c), s, y); sc.render.filepath = os.path.join(R, 'debug', 'shoulder', f'sl_{pose}_{i}.png'); bpy.ops.render.render(write_still=True)
