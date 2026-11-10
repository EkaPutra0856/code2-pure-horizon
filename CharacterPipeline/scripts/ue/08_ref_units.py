# Prints local translations of a leg and arm chain from the mesh reference pose, a Blender clip
# and a retargeted clip, to find which of them holds bone offsets in the wrong unit.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_ref_units.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


L = unreal.AnimationLibrary
BONES = ["Root", "J_Bip_C_Hips", "J_Bip_C_Spine", "J_Bip_L_UpperLeg", "J_Bip_L_LowerLeg", "J_Bip_L_Foot", "J_Bip_L_UpperArm", "J_Bip_L_LowerArm", "J_Bip_L_Hand"]


def v(p):
    return (round(p.x, 3), round(p.y, 3), round(p.z, 3))


mesh = unreal.load_asset("/Game/Character/karakter_ue")
say("bounds", mesh.get_bounds().box_extent if hasattr(mesh, "get_bounds") else "n/a")
for label, getter in (("mesh ref", lambda: mesh.get_editor_property("skeleton").get_reference_pose()),):
    try:
        rp = getter()
        say(label, type(rp).__name__, [m for m in dir(rp) if not m.startswith("_")][:30])
        for b in BONES:
            say(" ", b, v(rp.get_ref_bone_pose(b, unreal.AnimPoseSpaces.LOCAL).translation) if hasattr(rp, "get_ref_bone_pose") else "n/a")
    except Exception as e:
        say(label, "failed", e)
try:
    ap = unreal.AnimPoseExtensions
    pose = ap.get_reference_pose(mesh.get_editor_property("skeleton"))
    for b in BONES:
        say("animpose local", b, v(ap.get_ref_bone_pose(pose, b, unreal.AnimPoseSpaces.LOCAL).translation),
            "world", v(ap.get_ref_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation))
except Exception as e:
    say("animpose failed", e)

for path in ("/Game/Character/Anim/A_Run_F", "/Game/Character/Mage/Mage_Idle"):
    a = unreal.load_asset(path)
    say("clip", path, "tracks", len(L.get_animation_track_names(a)))
    for b in BONES:
        say(" ", b, v(L.get_bone_pose_for_frame(a, b, 0, False).translation))

rtg = unreal.load_asset("/Game/Character/Retarget/RTG_Mage_To_Karakter")
c = unreal.IKRetargeterController.get_controller(rtg)
say("ops", [str(c.get_op_name(i)) for i in range(c.get_num_retarget_ops())])
say("controller", [m for m in dir(c) if "pose" in m.lower() or "setting" in m.lower() or "scale" in m.lower()])
say("DONE")
