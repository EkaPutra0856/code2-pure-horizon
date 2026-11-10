# Contact sheet of chosen frames so moves can be judged from stills.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, os
import numpy as np
from mathutils import Vector

ROOT = ANIME_GAME_ROOT
SHOTS = [("Idle_Combat", 0), ("Attack_N1", 7), ("Attack_N2", 7), ("Attack_N3", 6), ("Attack_N3", 11), ("Attack_N4", 8), ("Attack_N4", 15),
         ("Charge_Loop", 10), ("Skill_BloomField", 12), ("Skill_Heal", 10), ("Dodge_Back", 8), ("Dodge_Left", 8),
         ("Run_F", 6), ("Jump_Loop", 0), ("Plunge_Loop", 0), ("Swap_In", 10)]
OUTNAME = "moves_sheet.png"
ULT = False
if ULT:
    ev = json.load(open(ROOT + r"\export_unreal\anim\moves.json"))["moves"]["Ultimate_EternalBloom"]["events"]
    SHOTS = [("Ultimate_EternalBloom", f) for f in ev.values()] + [("Ultimate_EternalBloom", 0), ("Ultimate_EternalBloom", 200)]
    OUTNAME = "ult_sheet.png"
arm = bpy.data.objects["Armature"]
sc = bpy.context.scene
cam, sun = bpy.data.objects["RefCam"], bpy.data.objects["KeySun"]
old = (cam.data.ortho_scale, sc.render.resolution_x, sc.render.resolution_y)
cam.data.ortho_scale = 3.4 if ULT else 2.3
sc.render.resolution_x = sc.render.resolution_y = 300
off = Vector((-1.2, -3, 0.3))
target = Vector((0, -0.1, 1.5 if ULT else 0.95))
cam.location = target + off
cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
sun.rotation_euler = (-(off + Vector((0.8, 0, 1.2)))).to_track_quat("-Z", "Y").to_euler()
tiles = []
fp = os.path.join(ROOT, "renders", "_tile.png")
for name, f in SHOTS:
    arm.animation_data.action = bpy.data.actions["A_" + name]
    sc.frame_set(int(f))
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(fp, check_existing=False)
    tiles.append(np.array(im.pixels[:], dtype=np.float32).reshape(300, 300, 4))
    bpy.data.images.remove(im)
arm.animation_data.action = None
for b in arm.pose.bones:
    b.location = (0, 0, 0)
    b.rotation_quaternion = (1, 0, 0, 0)
sc.frame_set(0)
cols = 4
while len(tiles) % cols:
    tiles.append(np.ones_like(tiles[0]) * 0.5)
rows = [np.concatenate(tiles[i:i + cols], axis=1) for i in range(0, len(tiles), cols)][::-1]
sheet = np.concatenate(rows, axis=0)
H, W = sheet.shape[:2]
im = bpy.data.images.new("sheet_tmp", W, H, alpha=True)
im.pixels.foreach_set(sheet.ravel())
im.filepath_raw = os.path.join(ROOT, "renders", OUTNAME)
im.file_format = "PNG"
im.save()
bpy.data.images.remove(im)
cam.data.ortho_scale, sc.render.resolution_x, sc.render.resolution_y = old
print("sheet done", len(SHOTS))
