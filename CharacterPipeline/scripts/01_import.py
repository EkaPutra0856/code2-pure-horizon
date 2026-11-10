import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import addon_utils
print(addon_utils.enable('VRM_Addon_for_Blender-release', default_set=False))
import bpy, json
from mathutils import Vector

for name in ("Cube", "Light", "Camera"):
    o = bpy.data.objects.get(name)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)

bpy.ops.import_scene.vrm(filepath=os.path.join(ANIME_GAME_ROOT, r"karakter_uji.vrm"))
bpy.context.view_layer.update()

info = {"objects": []}
for o in bpy.data.objects:
    d = {"name": o.name, "type": o.type, "parent": o.parent.name if o.parent else None}
    if o.type == "MESH":
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        d["min"] = [round(min(v[i] for v in bb), 4) for i in range(3)]
        d["max"] = [round(max(v[i] for v in bb), 4) for i in range(3)]
        d["verts"] = len(o.data.vertices)
        d["mats"] = [m.name for m in o.data.materials if m]
        d["shapekeys"] = len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0
    info["objects"].append(d)

arm = next(o for o in bpy.data.objects if o.type == "ARMATURE")
bones = arm.data.bones
info["bone_count"] = len(bones)
info["hair_bones"] = len([b for b in bones if "Hair" in b.name])
info["key_bones"] = {
    b.name: [round(x, 4) for x in (arm.matrix_world @ b.head_local)]
    for b in bones
    if any(k in b.name for k in ("Head", "Neck", "Eye", "Hips", "UpperChest"))
    and "Hair" not in b.name
}
print(json.dumps(info, indent=0))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ANIME_GAME_ROOT, r"karakter_rambut.blend"))

