# Run in a background Blender. Unreal does not convert units on child bone tracks of an
# animation FBX, so this writes every clip with the skeleton truly in centimetres.
# Nothing is saved back to the .blend.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os

ROOT = ANIME_GAME_ROOT
OUT = os.path.join(ROOT, "export_unreal", "anim")
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "karakter_rambut.blend"))
arm = bpy.data.objects["Armature"]
sc = bpy.context.scene
sc.render.fps = 30
for o in list(bpy.data.objects):
    if o.type != "ARMATURE":
        bpy.data.objects.remove(o, do_unlink=True)
ad = arm.animation_data
ad.action = None
for t in list(ad.nla_tracks):
    ad.nla_tracks.remove(t)

sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.01
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
arm.scale = (100, 100, 100)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

acts = [a for a in bpy.data.actions if a.name.startswith("A_")]
for act in acts:
    for fc in act.fcurves:
        if fc.data_path.endswith(".location"):
            for k in fc.keyframe_points:
                k.co.y *= 100
            fc.update()
for act in acts:
    ad.action = act
    f0, f1 = act.frame_range
    sc.frame_start, sc.frame_end = int(f0), int(f1)
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, act.name + ".fbx"), object_types={"ARMATURE"}, add_leaf_bones=False,
        primary_bone_axis="Y", secondary_bone_axis="X", axis_forward="-Y", axis_up="Z",
        apply_scale_options="FBX_SCALE_NONE", apply_unit_scale=True, global_scale=1.0,
        bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, bake_anim_step=1.0)
print("RESULT exported", len(acts))
