"""Body prep: full 4K Tripo model -> decimated, labelled by segmented part, head + tails removed,
scaled to game size (floor z=0). Saves rig/body_prep.blend. Prints per-part stats for joint fitting."""
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, os, sys
import numpy as np
from mathutils import Vector
from mathutils.kdtree import KDTree

R = os.path.join(ANIME_GAME_ROOT, r"char4\rig")
SEG = os.path.join(ANIME_GAME_ROOT, r"char4\tripo\char4_seg_v1.glb")
FULL = os.path.join(ANIME_GAME_ROOT, r"char4\tripo\char4_full_v1.glb")
S = 1.6736          # Tripo units -> metres (same total height as the VRoid trio)
RATIO = 0.05        # decimate
DROP = {3, 2, 10}   # head, twin tails

def bake(o):
    mw = o.matrix_world.copy(); o.parent = None; o.matrix_world = mw
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=SEG)
pts, lab = [], []
for o in bpy.data.objects:
    if o.type == 'MESH' and o.name.startswith('tripo_part_'):
        k = int(o.name.split('_')[-1].split('.')[0])
        for v in o.data.vertices:
            pts.append(o.matrix_world @ v.co); lab.append(k)
kd = KDTree(len(pts))
for i, p in enumerate(pts): kd.insert(p, i)
kd.balance()
lab = np.array(lab)
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)

bpy.ops.import_scene.gltf(filepath=FULL)
body = [o for o in bpy.data.objects if o.type == 'MESH'][0]
bake(body)
for o in list(bpy.data.objects):
    if o is not body: bpy.data.objects.remove(o)
body.name = 'Body'
print('FULL faces', len(body.data.polygons))
m = body.modifiers.new('dec', 'DECIMATE'); m.ratio = RATIO
bpy.ops.object.modifier_apply(modifier='dec')
print('DEC faces', len(body.data.polygons))

me = body.data
part = np.zeros(len(me.polygons), np.int32)
for p in me.polygons:
    part[p.index] = lab[kd.find(p.center)[1]]
bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[f for f in bm.faces if part[f.index] in DROP], context='FACES')
keep = [i for i in range(len(part)) if part[i] not in DROP]
bm.to_mesh(me); bm.free()
part = part[keep]
a = me.attributes.new('part', 'INT', 'FACE'); a.data.foreach_set('value', part)
# scale to metres, floor at 0
for v in me.vertices: v.co = v.co * S
me.update()
print('BODY faces', len(me.polygons), 'tris', sum(len(p.vertices) - 2 for p in me.polygons))
V = np.array([v.co[:] for v in me.vertices])
print('BODY bbox', np.round(V.min(0), 4).tolist(), np.round(V.max(0), 4).tolist())
for k in sorted(set(part.tolist())):
    vi = sorted({vi for p in me.polygons if part[p.index] == k for vi in p.vertices})
    P = V[vi]
    print('PART', k, 'faces', int((part == k).sum()), 'min', np.round(P.min(0), 3).tolist(), 'max', np.round(P.max(0), 3).tolist(),
          'mean', np.round(P.mean(0), 3).tolist())

os.makedirs(os.path.join(R, 'tex'), exist_ok=True)
for im in list(bpy.data.images):
    if im.size[0] > 0:
        p = os.path.join(R, 'tex', bpy.path.clean_name(im.name) + '.png')
        im.filepath_raw = p; im.file_format = 'PNG'; im.save(); im.source = 'FILE'; im.filepath = p
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(R, 'body_prep.blend'))
print('DONE')
