# Deformation check: head tilt plus every hair chain curled, front and back renders.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, math, os
from mathutils import Euler, Vector

ROOT = ANIME_GAME_ROOT
arm = bpy.data.objects["Armature"]
names = json.load(open(os.path.join(ROOT, "scripts", "_bridge", "chains.json")))
pb = arm.pose.bones
for b in pb:
    b.rotation_mode = "XYZ"
pb["J_Bip_C_Head"].rotation_euler = Euler((0, 0, math.radians(15)))
for cname, bones in names.items():
    for i, b in enumerate(bones):
        a = math.radians(11 if cname.startswith(("Back", "Lock", "Braid")) else 7)
        pb[b].rotation_euler = Euler((a * math.sin(i * 1.3 + len(cname)), 0, a * math.cos(i * 1.1)))
bpy.context.view_layer.update()
sc = bpy.context.scene
cam, sun = bpy.data.objects["RefCam"], bpy.data.objects["KeySun"]
target = Vector((0, 0.02, 1.33))
for name, off in (("pose_front", Vector((0, -2, 0))), ("pose_back", Vector((0, 2, 0)))):
    cam.location = target + off
    cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
    sun.rotation_euler = (-(off + Vector((0.8, 0, 1.2)))).to_track_quat("-Z", "Y").to_euler()
    sc.render.filepath = os.path.join(ROOT, "renders", name + ".png")
    bpy.ops.render.render(write_still=True)
for b in pb:
    b.rotation_euler = Euler((0, 0, 0))
bpy.context.view_layer.update()
bpy.ops.wm.save_mainfile()
print("pose done")
