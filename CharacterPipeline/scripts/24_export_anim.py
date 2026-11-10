# Run in a background Blender. Writes one skeleton-only FBX per move for Unreal, then reimports
# a sample of them to confirm bones, length and root motion survived.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, os

ROOT = ANIME_GAME_ROOT
OUT = os.path.join(ROOT, "export_unreal", "anim")
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "karakter_rambut.blend"))
arm = bpy.data.objects["Armature"]
sc = bpy.context.scene
sc.render.fps = 30
for o in list(bpy.data.objects):
    if o.type != "ARMATURE":
        bpy.data.objects.remove(o, do_unlink=True)
if not arm.animation_data:
    arm.animation_data_create()
acts = [a for a in bpy.data.actions if a.name.startswith("A_")]
for act in acts:
    arm.animation_data.action = act
    f0, f1 = act.frame_range
    sc.frame_start, sc.frame_end = int(f0), int(f1)
    bpy.ops.export_scene.fbx(
        filepath=os.path.join(OUT, act.name + ".fbx"), object_types={"ARMATURE"}, add_leaf_bones=False,
        primary_bone_axis="Y", secondary_bone_axis="X", axis_forward="-Y", axis_up="Z",
        apply_scale_options="FBX_SCALE_ALL", apply_unit_scale=True, global_scale=1.0,
        bake_anim=True, bake_anim_use_all_actions=False, bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True, bake_anim_simplify_factor=0.0, bake_anim_step=1.0)
print("RESULT exported", len(acts))
moves = json.load(open(os.path.join(OUT, "moves.json")))["moves"]
for name in ("Attack_N3", "Dodge_Back", "Ultimate_EternalBloom", "Run_F"):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=os.path.join(OUT, f"A_{name}.fbx"))
    a = next(o for o in bpy.data.objects if o.type == "ARMATURE")
    act = a.animation_data.action
    sc = bpy.context.scene
    f0, f1 = (int(x) for x in act.frame_range)
    root = a.pose.bones["Root"]
    pts = []
    for f in (f0, (f0 + f1) // 2, f1):
        sc.frame_set(f)
        pts.append(tuple(round(x, 2) for x in (a.matrix_world @ root.matrix).translation))
    print("RESULT", name, "bones", len(a.data.bones), "frames", f1 - f0 + 1, "expected", moves[name]["frames"], "root", pts)
