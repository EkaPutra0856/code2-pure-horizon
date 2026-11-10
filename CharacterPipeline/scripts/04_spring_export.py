import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, math, os
from mathutils import Euler

ROOT = ANIME_GAME_ROOT
arm = bpy.data.objects["Armature"]
txt = bpy.data.texts["spring_bone.json"]
groups = json.loads(txt.as_string())
hair_groups = [g for g in groups if any("Hair" in b for b in g["bones"]) and "HairNew" not in "".join(g["bones"])]
colliders = hair_groups[0]["colliderGroups"] if hair_groups else []
kept = [g for g in groups if g not in hair_groups and "HairNew" not in "".join(g["bones"])]
roots = sorted(b.name for b in arm.data.bones if "HairNew" in b.name and b.name.endswith("_01"))


def grp(bones, comment, stiff, grav, drag, radius):
    return {"bones": bones, "center": "Root", "colliderGroups": colliders, "comment": comment,
            "dragForce": drag, "gravityDir": {"x": 0, "y": -1, "z": 0}, "gravityPower": grav,
            "hitRadius": radius, "stiffiness": stiff}


kept.append(grp([b for b in roots if "Back" in b], "HairNew_Back", 0.9, 0.08, 0.45, 0.025))
kept.append(grp([b for b in roots if "Lock" in b], "HairNew_Lock", 1.1, 0.06, 0.45, 0.015))
kept.append(grp([b for b in roots if "Braid" in b], "HairNew_Braid", 1.4, 0.15, 0.55, 0.02))
txt.clear()
txt.write(json.dumps(kept, indent=4))
print("spring groups", len(groups), "->", len(kept), "old hair groups removed", len(hair_groups))

# deformation check: tilt the head and swing one chain, render, then reset
pb = arm.pose.bones
for b in pb:
    b.rotation_mode = "XYZ"
pb["J_Bip_C_Head"].rotation_euler = Euler((0, 0, math.radians(18)))
pb["J_Sec_HairNew_BackL2_01"].rotation_euler = Euler((math.radians(30), 0, 0))
pb["J_Sec_HairNew_BraidR_01"].rotation_euler = Euler((0, 0, math.radians(-25)))
bpy.context.view_layer.update()
sc = bpy.context.scene
sc.render.filepath = os.path.join(ROOT, "renders", "pose_test.png")
bpy.ops.render.render(write_still=True)
for b in pb:
    b.rotation_euler = Euler((0, 0, 0))
bpy.context.view_layer.update()
bpy.ops.wm.save_mainfile()

# export
bpy.ops.object.select_all(action="DESELECT")
for o in bpy.data.objects:
    if o.name in ("Armature", "Body", "Face", "Hair_New", "Hair_Band", "Ears_Elf", "Flowers"):
        o.select_set(True)
try:
    r = bpy.ops.export_scene.vrm(filepath=os.path.join(ROOT, "karakter_final.vrm"))
    print("export", r)
except Exception as ex:
    print("EXPORT FAILED:", str(ex)[-1200:])
