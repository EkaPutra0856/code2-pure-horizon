# Measures which way the shoulders face at the start, middle and end of every Blender clip.
# 0 degrees means facing +Y like the mannequin. Lists clips that turn away from it.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import json, math, os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_facing.txt")
L = unreal.AnimationLibrary
moves = json.load(open(os.path.join(ROOT, "export_unreal", "anim", "moves.json")))["moves"]


def world(a, bone, frame):
    t = unreal.Transform()
    for b in reversed([str(x) for x in L.find_bone_path_to_root(a, bone)]):
        t = L.get_bone_pose_for_frame(a, b, frame, False).multiply(t)
    return t.translation


def yaw(a, frame):
    d = world(a, "J_Bip_L_UpperArm", frame) - world(a, "J_Bip_R_UpperArm", frame)
    return round(math.degrees(math.atan2(d.y, d.x)))


out = []
for name in moves:
    a = unreal.load_asset("/Game/Character/Anim/A_" + name)
    n = L.get_num_frames(a)
    v = [yaw(a, 0), yaw(a, n // 2), yaw(a, n - 1)]
    out.append(f"{'OFF ' if max(abs(x) for x in v) > 45 else 'ok  '}{name} {v}")
open(LOG, "w", encoding="utf-8").write("\n".join(out))
