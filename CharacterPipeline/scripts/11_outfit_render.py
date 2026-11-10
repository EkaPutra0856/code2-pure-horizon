# Full-body four-view sheet, plus an optional test pose that swings arms and legs.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, math, os
import numpy as np
from mathutils import Euler, Vector

ROOT = ANIME_GAME_ROOT
POSE = False
arm = bpy.data.objects["Armature"]
sc = bpy.context.scene
cam, sun = bpy.data.objects["RefCam"], bpy.data.objects["KeySun"]
old_scale, old_res = cam.data.ortho_scale, sc.render.resolution_x
cam.data.ortho_scale = 1.8
sc.render.resolution_x = sc.render.resolution_y = 760
if POSE:
    for tag, s in (("L", 1), ("R", -1)):
        pb = arm.pose.bones
        pb[f"J_Bip_{tag}_UpperArm"].rotation_mode = "XYZ"
        pb[f"J_Bip_{tag}_UpperArm"].rotation_euler = Euler((0, 0, math.radians(-55 * s)))
        pb[f"J_Bip_{tag}_UpperLeg"].rotation_mode = "XYZ"
        pb[f"J_Bip_{tag}_UpperLeg"].rotation_euler = Euler((math.radians(25 * s), 0, 0))
    bpy.context.view_layer.update()
target = Vector((0, 0.02, 0.84))
views = (("front", Vector((0, -3, 0))), ("left", Vector((-3, 0, 0))), ("right", Vector((3, 0, 0))), ("back", Vector((0, 3, 0))))
tiles = {}
for name, off in views:
    cam.location = target + off
    cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
    sun.rotation_euler = (-(off + Vector((0.8, 0, 1.2)))).to_track_quat("-Z", "Y").to_euler()
    fp = os.path.join(ROOT, "renders", "outfit_" + name + ".png")
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(fp, check_existing=False)
    tiles[name] = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
    bpy.data.images.remove(im)
sheet = np.concatenate([np.concatenate([tiles["right"], tiles["back"]], axis=1),
                        np.concatenate([tiles["front"], tiles["left"]], axis=1)], axis=0)
H, Wd = sheet.shape[:2]
im = bpy.data.images.new("outfit_sheet", Wd, H, alpha=True)
im.pixels.foreach_set(sheet.ravel())
im.filepath_raw = os.path.join(ROOT, "renders", "outfit_pose_sheet.png" if POSE else "outfit_sheet.png")
im.file_format = "PNG"
im.save()
bpy.data.images.remove(im)
for b in arm.pose.bones:
    if b.rotation_mode == "XYZ":
        b.rotation_euler = Euler((0, 0, 0))
cam.data.ortho_scale = old_scale
sc.render.resolution_x = sc.render.resolution_y = old_res
bpy.context.view_layer.update()
print("render done")
