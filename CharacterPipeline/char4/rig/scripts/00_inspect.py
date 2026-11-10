"""Inspect Tripo body pose/proportions vs VRoid J_Bip skeleton; front/side renders of both."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, sys, math
import numpy as np
from mathutils import Vector
R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
os.makedirs(os.path.join(R, 'debug'), exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.preferences.addon_enable(module='VRM_Addon_for_Blender-release')
bpy.ops.import_scene.vrm(filepath=os.path.join(ANIME_GAME_ROOT, r"karakter_final.vrm"))
arm = bpy.data.objects['Armature']
for n in ('Hips', 'Spine', 'Chest', 'UpperChest', 'Neck', 'Head', 'L_UpperArm', 'L_LowerArm', 'L_Hand', 'L_UpperLeg', 'L_LowerLeg', 'L_Foot', 'L_Shoulder'):
    for b in arm.data.bones:
        if b.name.endswith('_' + n) and b.name.startswith('J_Bip'):
            h = arm.matrix_world @ b.head_local; t = arm.matrix_world @ b.tail_local
            print('VBONE', b.name, [round(v, 4) for v in h], [round(v, 4) for v in t])
vm = [o for o in bpy.data.objects if o.type == 'MESH']
for o in vm:
    P = np.array([o.matrix_world @ v.co for v in o.data.vertices])
    print('VMESH', o.name, len(P), np.round(P.min(0), 3).tolist(), np.round(P.max(0), 3).tolist())
print('VBONES total', len(arm.data.bones), sorted(b.name for b in arm.data.bones if not b.name.startswith('J_Bip') and not b.name.startswith('J_Sec'))[:40])

before = set(bpy.data.objects)
bpy.ops.import_scene.gltf(filepath=os.path.join(ANIME_GAME_ROOT, r"char4\tripo\char4_full_v1.glb"))
new = [o for o in bpy.data.objects if o not in before]
t = [o for o in new if o.type == 'MESH'][0]
mw = t.matrix_world.copy()
P = np.array([mw @ v.co for v in t.data.vertices])
print('TRIPO verts', len(P), 'min', np.round(P.min(0), 4).tolist(), 'max', np.round(P.max(0), 4).tolist())
# silhouette width per height band
zmin, zmax = P[:, 2].min(), P[:, 2].max()
for k in range(40):
    z0 = zmin + (zmax - zmin) * k / 40; z1 = z0 + (zmax - zmin) / 40
    s = P[(P[:, 2] >= z0) & (P[:, 2] < z1)]
    if len(s):
        print('BAND', round(z0, 3), 'x', round(s[:, 0].min(), 3), round(s[:, 0].max(), 3), 'y', round(s[:, 1].min(), 3), round(s[:, 1].max(), 3), 'n', len(s))
# shift tripo beside VRoid for a combined render (scale to VRoid height)
vh = max(np.array([o.matrix_world @ v.co for v in bpy.data.objects['Body'].data.vertices])[:, 2])
s = vh / (zmax - zmin)
print('SCALE to vroid height', round(s, 4), 'vroid height', round(vh, 4))
for o in new:
    if o.parent is None:
        o.scale = o.scale * s
        o.location = (0.9, 0, -zmin * s)
sc = bpy.context.scene
sc.render.engine = 'BLENDER_WORKBENCH'
sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'TEXTURE'
cam = bpy.data.objects.new('cam', bpy.data.cameras.new('cam')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'; cam.data.ortho_scale = 2.0
sc.render.resolution_x = 1400; sc.render.resolution_y = 1100
for yaw, nm in ((0, 'front'), (90, 'side')):
    a = math.radians(yaw)
    c = Vector((0.45, 0, 0.85))
    cam.location = c + Vector((math.sin(a), -math.cos(a), 0)) * 5; cam.rotation_euler = (math.radians(90), 0, a)
    sc.render.filepath = os.path.join(R, 'debug', f'inspect_{nm}.png'); bpy.ops.render.render(write_still=True)
print('DONE')
