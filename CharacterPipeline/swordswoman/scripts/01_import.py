# Imports the VRoid base (head, body, hair, no outfit) and saves sw_base.blend, then renders a body check sheet.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import sys, json
sys.path.insert(0, os.path.join(ANIME_GAME_ROOT, r"swordswoman\scripts"))
import addon_utils
addon_utils.enable('VRM_Addon_for_Blender-release', default_set=False)
import bpy
from mathutils import Vector
import sw_render

for name in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.import_scene.vrm(filepath=os.path.join(ANIME_GAME_ROOT, r"swordswoman\sw_base.vrm"))
bpy.context.view_layer.update()

info = []
for o in bpy.data.objects:
    if o.type == "MESH":
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        info.append({"name": o.name, "verts": len(o.data.vertices),
                     "min": [round(min(v[i] for v in bb), 3) for i in range(3)],
                     "max": [round(max(v[i] for v in bb), 3) for i in range(3)],
                     "mats": [m.name for m in o.data.materials if m]})
    elif o.type == "ARMATURE":
        b = o.data.bones
        info.append({"armature": o.name, "bones": len(b),
                     "head": [round(x, 3) for x in (o.matrix_world @ b["J_Bip_C_Head"].head_local)]})
print("INFO", json.dumps(info))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ANIME_GAME_ROOT, r"swordswoman\sw_base.blend"))
print("SHEET", sw_render.sheet("base_body"))
print("SHEET", sw_render.sheet("base_head", target=(0, 0.02, 1.35), scale=0.6, res=500))
