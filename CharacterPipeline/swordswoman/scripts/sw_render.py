# Shared preview rendering for the swordswoman: ortho four-view sheet (front, left, right, back).
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import bpy
import numpy as np
from mathutils import Vector

ROOT = os.path.join(ANIME_GAME_ROOT, r"swordswoman")


def setup():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.13, 0.13, 0.13, 1)
    bg.inputs[1].default_value = 1.6
    sun = bpy.data.objects.get("KeySun")
    if not sun:
        sd = bpy.data.lights.new("KeySun", "SUN")
        sd.energy = 2.2
        sun = bpy.data.objects.new("KeySun", sd)
        sc.collection.objects.link(sun)
    cam = bpy.data.objects.get("RefCam")
    if not cam:
        cd = bpy.data.cameras.new("RefCam")
        cd.type = "ORTHO"
        cam = bpy.data.objects.new("RefCam", cd)
        sc.collection.objects.link(cam)
    sc.camera = cam
    return cam, sun


def sheet(name, target=(0, 0.02, 0.84), scale=1.8, res=700,
          views=("front", "left", "right", "back")):
    """Renders the listed views and tiles them side by side into renders/<name>.png."""
    cam, sun = setup()
    sc = bpy.context.scene
    sc.render.resolution_x = sc.render.resolution_y = res
    cam.data.ortho_scale = scale
    t = Vector(target)
    offs = {"front": Vector((0, -3, 0)), "left": Vector((-3, 0, 0)), "right": Vector((3, 0, 0)),
            "back": Vector((0, 3, 0)), "q34": Vector((-2.1, -2.1, 0.4)),
            "q34l": Vector((2.1, -2.1, 0.4)), "back_l": Vector((2.1, 2.1, 0.4)), "back_r": Vector((-2.1, 2.1, 0.4)),
            "top": Vector((0, -0.6, 3)), "low_l": Vector((2.4, -1.2, -1.2))}
    out = os.path.join(ROOT, "renders")
    os.makedirs(out, exist_ok=True)
    tiles = []
    for v in views:
        off = offs[v]
        cam.location = t + off
        cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
        sun.rotation_euler = (-(off + Vector((0.8, 0, 1.2)))).to_track_quat("-Z", "Y").to_euler()
        fp = os.path.join(out, "_tmp_" + v + ".png")
        sc.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(fp, check_existing=False)
        tiles.append(np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4))
        bpy.data.images.remove(im)
        os.remove(fp)
    s = np.concatenate(tiles, axis=1)
    im = bpy.data.images.new(name, s.shape[1], s.shape[0], alpha=True)
    im.pixels.foreach_set(s.ravel())
    fp = os.path.join(out, name + ".png")
    im.filepath_raw = fp
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)
    return fp
