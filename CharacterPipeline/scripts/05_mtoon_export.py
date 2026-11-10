# Moves the new parts onto MToon materials cloned from the VRoid hair material,
# so colors and the gradient survive VRM export, then renders and exports.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os
import numpy as np
from mathutils import Vector

ROOT = ANIME_GAME_ROOT
SRC = "N00_000_00_HairBack_00_HAIR (Instance)"


def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


# gradient was stored as linear values in an sRGB image; correct it once
img = bpy.data.images["hair_gradient"]
if not img.get("gamma_fixed"):
    px = np.array(img.pixels[:], dtype=np.float32).reshape(-1, 4)
    px[:, :3] = np.power(np.clip(px[:, :3], 0, 1), 1 / 2.2)
    img.pixels.foreach_set(px.ravel())
    img["gamma_fixed"] = 1
    img.save()
none_nrm = bpy.data.images.get("Shader_NoneNormal")


def flat_image(name, hexcol):
    im = bpy.data.images.get(name) or bpy.data.images.new(name, 4, 4, alpha=False)
    c = [int(hexcol[i:i + 2], 16) / 255 for i in (0, 2, 4)] + [1.0]
    im.pixels.foreach_set(np.tile(np.array(c, dtype=np.float32), 16))
    im.filepath_raw = os.path.join(ROOT, "textures", name + ".png")
    im.file_format = "PNG"
    im.save()
    return im


def toon(name, image, shade_hex):
    new = name + "_MToon"
    old = bpy.data.materials.get(new)
    if old:
        bpy.data.materials.remove(old)
    m = bpy.data.materials[SRC].copy()
    m.name = new
    n = m.node_tree.nodes
    n["Image Texture"].image = image
    n["Image Texture.001"].image = image
    n["Image Texture.002"].image = none_nrm
    n["RGB"].outputs[0].default_value = (1, 1, 1, 1)
    n["RGB.001"].outputs[0].default_value = lin(shade_hex)
    return m


plan = {
    "Hair_New": [toon("Hair_New", img, "DCCFD6")],
    "Hair_Band": [toon("Hair_Tie", flat_image("tie", "C9A24A"), "A8853A")],
    "Ears_Elf": [toon("Ear_Skin", flat_image("ear", "FAEBDE"), "EFBAA3")],
    "Flowers": [toon("Petal_Pink", flat_image("petal_pink", "F2B6C0"), "D98CA0"),
                toon("Petal_White", flat_image("petal_white", "F9DDE0"), "E8B4BE"),
                toon("Bud_Yellow", flat_image("bud_yellow", "E9C44E"), "C89A30"),
                toon("Leaf_Green", flat_image("leaf_green", "5E9A4E"), "3F7A3E"),
                toon("Stamen", flat_image("stamen", "C98A2B"), "A06A1C")],
}
for ob, mats in plan.items():
    data = bpy.data.objects[ob].data
    for i, m in enumerate(mats):
        data.materials[i] = m
for name in ("Hair_New", "Hair_Tie", "Ear_Skin", "Petal_Pink", "Petal_White", "Bud_Yellow",
             "Leaf_Green", "Stamen"):
    m = bpy.data.materials.get(name)
    if m and m.users == 0:
        bpy.data.materials.remove(m)

# four-view sheet
sc = bpy.context.scene
cam, sun = bpy.data.objects["RefCam"], bpy.data.objects["KeySun"]
target = Vector((0, 0.02, 1.33))
views = (("front", Vector((0, -2, 0))), ("left", Vector((-2, 0, 0))),
         ("right", Vector((2, 0, 0))), ("back", Vector((0, 2, 0))))
tiles = {}
for name, off in views:
    cam.location = target + off
    cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
    sun.rotation_euler = (-(off + Vector((0.8, 0, 1.2)))).to_track_quat("-Z", "Y").to_euler()
    fp = os.path.join(ROOT, "renders", name + ".png")
    sc.render.filepath = fp
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(fp, check_existing=False)
    tiles[name] = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
    bpy.data.images.remove(im)
sheet = np.concatenate([np.concatenate([tiles["right"], tiles["back"]], axis=1),
                        np.concatenate([tiles["front"], tiles["left"]], axis=1)], axis=0)
H, W = sheet.shape[:2]
im = bpy.data.images.new("sheet", W, H, alpha=True)
im.pixels.foreach_set(sheet.ravel())
im.filepath_raw = os.path.join(ROOT, "renders", "sheet.png")
im.file_format = "PNG"
im.save()
bpy.data.images.remove(im)

bpy.ops.wm.save_mainfile()
r = bpy.ops.export_scene.vrm(filepath=os.path.join(ROOT, "karakter_final.vrm"))
print("export", r)
