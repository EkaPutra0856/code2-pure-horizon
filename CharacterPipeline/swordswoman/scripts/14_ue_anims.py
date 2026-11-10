# Imports the main character's 47 clips (export_unreal/anim/A_*.fbx, truly cm) onto the swordswoman
# skeleton as /Game/Swordswoman/Anim. Both are VRoid skeletons with the same J_Bip names and rest pose,
# so the tracks apply directly; tracks for the other character's hair/cloth bones are ignored and the
# swordswoman's own J_Sec bones stay for the physics blueprint. Root motion flags copy moves.json.
# The reference pose of both skeletons is compared first, so a proportion mismatch shows in the log.
# Run with UnrealEditor-Cmd -run=pythonscript. Safe to rerun.
import glob, json, os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.dirname(ROOT)
ANIM = os.path.join(MAIN, "export_unreal", "anim")
LOG = os.path.join(ROOT, "renders", "_log_ue_anims.txt")
DEST = "/Game/Swordswoman/Anim"
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary
P = unreal.AnimPoseExtensions
L = unreal.AnimationLibrary
skel = unreal.load_asset("/Game/Swordswoman/sw_ue").get_editor_property("skeleton")
main = unreal.load_asset("/Game/Character/karakter_ue").get_editor_property("skeleton")
ps, pm = P.get_reference_pose(skel), P.get_reference_pose(main)
worst = (0.0, "")
for b in ("J_Bip_C_Hips", "J_Bip_C_Spine", "J_Bip_C_UpperChest", "J_Bip_C_Neck", "J_Bip_C_Head", "J_Bip_L_Shoulder", "J_Bip_L_UpperArm",
          "J_Bip_L_LowerArm", "J_Bip_L_Hand", "J_Bip_R_Hand", "J_Bip_L_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_L_Foot", "J_Bip_L_ToeBase"):
    a = P.get_ref_bone_pose(ps, b, unreal.AnimPoseSpaces.WORLD).translation
    c = P.get_ref_bone_pose(pm, b, unreal.AnimPoseSpaces.WORLD).translation
    d = (a - c).length()
    if d > worst[0]:
        worst = (d, b)
say("rest pose max difference cm", round(worst[0], 3), worst[1])

ok = 0
for f in sorted(glob.glob(os.path.join(ANIM, "A_*.fbx"))):
    name = os.path.splitext(os.path.basename(f))[0]
    o = unreal.FbxImportUI()
    o.set_editor_property("import_mesh", False)
    o.set_editor_property("import_animations", True)
    o.set_editor_property("import_as_skeletal", True)
    o.set_editor_property("skeleton", skel)
    o.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    ad = o.get_editor_property("anim_sequence_import_data")
    ad.set_editor_property("convert_scene", True)
    ad.set_editor_property("convert_scene_unit", False)
    ad.set_editor_property("import_bone_tracks", True)
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", f)
    t.set_editor_property("destination_path", DEST)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    t.set_editor_property("options", o)
    t.set_editor_property("destination_name", name)
    tools.import_asset_tasks([t])
    if unreal.load_asset(f"{DEST}/{name}"):
        ok += 1
    else:
        say("FAILED", name)
say("imported", ok)

# Keep only body tracks. The clips also carry the main character's J_Adj (eyes) and J_Sec (hair,
# skirt) tracks. Some names exist on this skeleton too (FaceEye, Skirt00..11), but their rest pose
# differs, so those tracks pushed the eyeballs into the head (eyes rendered blank) and bent the skirt.
# Without them these bones keep the swordswoman's own rest pose and the physics blueprint drives them.
stripped = 0
for f in sorted(glob.glob(os.path.join(ANIM, "A_*.fbx"))):
    a = unreal.load_asset(f"{DEST}/{os.path.splitext(os.path.basename(f))[0]}")
    if not a:
        continue
    tracks = [str(t) for t in L.get_animation_track_names(a)]
    # FName comparison is case-insensitive and the names come back lower-case (j_bip_c_hips)
    drop = [t for t in tracks if not (t.lower().startswith("j_bip_") or t.lower() == "root")]
    if stripped == 0:
        say("first clip tracks", len(tracks), "dropping", len(drop))
    # AnimationLibrary.remove_bone_animation wiped the body tracks too (T-pose), so use the data
    # controller, which removes exactly the named track.
    if len(drop) == len(tracks):
        say("ABORT strip: every track looks non-body", tracks[:6])
        raise SystemExit(1)
    ctrl = a.get_editor_property("controller")
    for t in drop:
        ctrl.remove_bone_track(t, False)
    if drop:
        lib.save_loaded_asset(a, False)
    stripped += len(drop)
say("non-body tracks removed", stripped)
a = unreal.load_asset(f"{DEST}/A_Run_F")
left = [str(t) for t in L.get_animation_track_names(a)]
n = L.get_num_frames(a)
move = 57.2958 * L.get_bone_pose_for_frame(a, "J_Bip_L_UpperLeg", 0, False).rotation.angular_distance(
    L.get_bone_pose_for_frame(a, "J_Bip_L_UpperLeg", n // 2, False).rotation)
say("Run_F tracks left", len(left), "non-body", [t for t in left if not t.lower().startswith("j_bip_") and t.lower() != "root"],
    "upper leg swing deg", round(move, 1))

moves = json.load(open(os.path.join(ANIM, "moves.json")))["moves"]
on = 0
for name, m in moves.items():
    a = unreal.load_asset(f"{DEST}/A_{name}")
    if not a:
        say("no clip for move", name)
        continue
    want = bool(m.get("root_motion"))
    a.set_editor_property("enable_root_motion", want)
    lib.save_loaded_asset(a, False)
    on += want
lib.save_directory("/Game/Swordswoman")
say("root motion on", on, "of", len(moves))
L = unreal.AnimationLibrary
for clip in ("A_Idle_Combat", "A_Run_F", "A_Dodge_Back", "A_Attack_N1"):
    a = unreal.load_asset(f"{DEST}/{clip}")
    b = unreal.load_asset(f"/Game/Character/Anim/{clip}")
    n = L.get_num_frames(a)
    hs = L.get_bone_pose_for_frame(a, "J_Bip_L_Hand", n // 2, False).translation
    hm = L.get_bone_pose_for_frame(b, "J_Bip_L_Hand", n // 2, False).translation
    say(clip, "frames", n, "root motion", a.get_editor_property("enable_root_motion"), "hand track diff vs main", round((hs - hm).length(), 4))
say("DONE")
