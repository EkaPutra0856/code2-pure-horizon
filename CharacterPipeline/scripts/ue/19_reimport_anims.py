# Reimports every clip from the centimetre FBX files into the existing skeleton. Run 12_notifies and 15_root_motion after this.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import glob, os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_anims.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary
skeleton = unreal.load_asset("/Game/Character/karakter_ue").get_editor_property("skeleton")
say("skeleton", skeleton)
ok = 0
for f in sorted(glob.glob(os.path.join(ROOT, "export_unreal", "anim", "A_*.fbx"))):
    name = os.path.splitext(os.path.basename(f))[0]
    o = unreal.FbxImportUI()
    o.set_editor_property("import_mesh", False)
    o.set_editor_property("import_animations", True)
    o.set_editor_property("import_as_skeletal", True)
    o.set_editor_property("skeleton", skeleton)
    o.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    ad = o.get_editor_property("anim_sequence_import_data")
    ad.set_editor_property("convert_scene", True)
    ad.set_editor_property("convert_scene_unit", False)
    ad.set_editor_property("import_bone_tracks", True)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", f)
    t.set_editor_property("destination_path", "/Game/Character/Anim")
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", o)
    t.set_editor_property("destination_name", name)
    tools.import_asset_tasks([t])
    ok += 1
lib.save_directory("/Game/Character")
say("imported", ok)
L = unreal.AnimationLibrary
for clip in ("A_Dodge_Back", "A_Ultimate_EternalBloom", "A_Run_F"):
    a = unreal.load_asset("/Game/Character/Anim/" + clip)
    n = L.get_num_frames(a)
    p = lambda b, f: L.get_bone_pose_for_frame(a, b, f, False).translation
    say(clip, "frames", n, "length", a.get_editor_property("sequence_length"), "hips", p("J_Bip_C_Hips", 0), "arm", p("J_Bip_L_UpperArm", 0),
        "root mid", p("Root", n // 2), "root end", p("Root", n - 1))
say("DONE")
