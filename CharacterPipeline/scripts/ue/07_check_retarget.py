# Compares retargeted Mage clips with their sources in component space. Limb directions should
# match, feet should stay near the ground, and root motion should scale with leg length.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_check_retarget.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


L = unreal.AnimationLibrary
SRC_DIR = "/Game/MageAnimationSet/Animations/RootMotion/"
reg = unreal.AssetRegistryHelpers.get_asset_registry()
paths = {str(a.asset_name): str(a.package_name) for a in reg.get_assets_by_path("/Game/MageAnimationSet/Animations/RootMotion", recursive=True)}
SRC_B = dict(root="root", hips="pelvis", head="head", lu="upperarm_l", lh="hand_l", ru="upperarm_r", rh="hand_r", lt="thigh_l", lf="foot_l", rt="thigh_r", rf="foot_r")
TGT_B = dict(root="Root", hips="J_Bip_C_Hips", head="J_Bip_C_Head", lu="J_Bip_L_UpperArm", lh="J_Bip_L_Hand", ru="J_Bip_R_UpperArm", rh="J_Bip_R_Hand",
             lt="J_Bip_L_UpperLeg", lf="J_Bip_L_Foot", rt="J_Bip_R_UpperLeg", rf="J_Bip_R_Foot")


def world(a, bone, frame):
    path = [str(b) for b in L.find_bone_path_to_root(a, bone)]
    t = unreal.Transform()
    for b in reversed(path):
        t = L.get_bone_pose_for_frame(a, b, frame, False).multiply(t) if hasattr(t, "multiply") else L.get_bone_pose_for_frame(a, b, frame, False) * t
    return t.translation


def v(p):
    return (round(p.x, 1), round(p.y, 1), round(p.z, 1))


def unit(a, b):
    d = b - a
    n = d.length() or 1.0
    return d * (1.0 / n)


def compare(name):
    if name not in paths:
        say(name, "no source")
        return
    s = unreal.load_asset(paths[name])
    t = unreal.load_asset("/Game/Character/Mage/" + name.replace("_RM", ""))
    if not t:
        say(name, "no target")
        return
    ns, nt = L.get_num_frames(s), L.get_num_frames(t)
    say("==", name, "frames", ns, nt)
    for fr in (0.0, 0.5, 1.0):
        fs, ft = int((ns - 1) * fr), int((nt - 1) * fr)
        dots = []
        for a, b in (("lu", "lh"), ("ru", "rh"), ("lt", "lf"), ("rt", "rf"), ("hips", "head")):
            ds = unit(world(s, SRC_B[a], fs), world(s, SRC_B[b], fs))
            dt = unit(world(t, TGT_B[a], ft), world(t, TGT_B[b], ft))
            dots.append(round(ds.dot(dt), 3))
        say(" t", fr, "dir dot Larm Rarm Lleg Rleg spine", dots)
        say("   src hips", v(world(s, SRC_B["hips"], fs)), "lfoot", v(world(s, SRC_B["lf"], fs)), "rhand", v(world(s, SRC_B["rh"], fs)))
        say("   tgt hips", v(world(t, TGT_B["hips"], ft)), "lfoot", v(world(t, TGT_B["lf"], ft)), "rhand", v(world(t, TGT_B["rh"], ft)))
    say(" root end src", v(world(s, "root", ns - 1)), "tgt", v(world(t, "Root", nt - 1)))


say("names", sorted(paths)[:60])
for n in sorted(paths):
    if any(k in n for k in ("Idle", "Fireball_R", "Dodge_B", "Run_F", "GroundSlam")):
        compare(n)
say("DONE")
