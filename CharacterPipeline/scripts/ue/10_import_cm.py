# Imports the centimetre mesh and all clips. Both FBX types are truly in cm, so neither uses
# scene-unit conversion. Reports reference pose values that must read in centimetres, scale 1.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import glob, os
import unreal

ROOT = ANIME_GAME_ROOT
EXP = os.path.join(ROOT, "export_unreal")
LOG = os.path.join(ROOT, "scripts", "ue", "report_import_cm.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary


def run(path, dest, opts, name=None):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", dest)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", opts)
    if name:
        t.set_editor_property("destination_name", name)
    tools.import_asset_tasks([t])


o = unreal.FbxImportUI()
o.set_editor_property("import_as_skeletal", True)
o.set_editor_property("import_mesh", True)
o.set_editor_property("import_animations", False)
o.set_editor_property("import_materials", True)
o.set_editor_property("import_textures", True)
o.set_editor_property("create_physics_asset", True)
o.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
sm = o.get_editor_property("skeletal_mesh_import_data")
sm.set_editor_property("import_morph_targets", True)
sm.set_editor_property("convert_scene", True)
sm.set_editor_property("convert_scene_unit", False)
run(os.path.join(EXP, "karakter_ue.fbx"), "/Game/Character", o)
mesh = unreal.load_asset("/Game/Character/karakter_ue")
skeleton = mesh.get_editor_property("skeleton")
lib.save_directory("/Game/Character")
b = mesh.get_bounds()
say("extent", b.box_extent, "origin", b.origin, "morphs", len(mesh.get_editor_property("morph_targets")), "materials", len(mesh.get_editor_property("materials")))
pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
for bone in ("Root", "J_Bip_C_Hips", "J_Bip_L_LowerLeg", "J_Bip_L_Foot", "J_Bip_L_Hand"):
    loc = unreal.AnimPoseExtensions.get_ref_bone_pose(pose, bone, unreal.AnimPoseSpaces.LOCAL)
    wor = unreal.AnimPoseExtensions.get_ref_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)
    say(bone, "local", loc.translation, "scale", loc.scale3d, "world", wor.translation)

ok = 0
for f in sorted(glob.glob(os.path.join(EXP, "anim", "A_*.fbx"))):
    name = os.path.splitext(os.path.basename(f))[0]
    a = unreal.FbxImportUI()
    a.set_editor_property("import_mesh", False)
    a.set_editor_property("import_animations", True)
    a.set_editor_property("import_as_skeletal", True)
    a.set_editor_property("skeleton", skeleton)
    a.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    d = a.get_editor_property("anim_sequence_import_data")
    d.set_editor_property("convert_scene", True)
    d.set_editor_property("convert_scene_unit", False)
    d.set_editor_property("import_bone_tracks", True)
    run(f, "/Game/Character/Anim", a, name)
    ok += 1
lib.save_directory("/Game/Character")
say("clips", ok)
L = unreal.AnimationLibrary
c = unreal.load_asset("/Game/Character/Anim/A_Dodge_Back")
n = L.get_num_frames(c)
say("dodge hips", L.get_bone_pose_for_frame(c, "J_Bip_C_Hips", 0, False).translation, "root end", L.get_bone_pose_for_frame(c, "Root", n - 1, False).translation,
    "root scale", L.get_bone_pose_for_frame(c, "Root", 0, False).scale3d)
phys = [str(p) for p in lib.list_assets("/Game/Character", recursive=False, include_folder=False)]
say("assets", len(phys), [p.split(".")[-1] for p in phys if "Physics" in p or "Skeleton" in p])
say("DONE")
