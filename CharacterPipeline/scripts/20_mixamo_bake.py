# Run in a background Blender. Converts every Mixamo FBX into rotations for the VRoid skeleton:
# each bone's world rotation change from T-pose is reapplied on the matching target bone.
# Output is one .npz per clip in mixamo/baked, so later steps can edit clips without Blender.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, os, glob, re
import numpy as np
from mathutils import Quaternion, Vector

ROOT = ANIME_GAME_ROOT
OUT = os.path.join(ROOT, "mixamo", "baked")
os.makedirs(OUT, exist_ok=True)

MAP = {"Hips": "C_Hips", "Spine": "C_Spine", "Spine1": "C_Chest", "Spine2": "C_UpperChest", "Neck": "C_Neck", "Head": "C_Head"}
for side, t in (("Left", "L"), ("Right", "R")):
    MAP.update({f"{side}Shoulder": f"{t}_Shoulder", f"{side}Arm": f"{t}_UpperArm", f"{side}ForeArm": f"{t}_LowerArm",
                f"{side}Hand": f"{t}_Hand", f"{side}UpLeg": f"{t}_UpperLeg", f"{side}Leg": f"{t}_LowerLeg",
                f"{side}Foot": f"{t}_Foot", f"{side}ToeBase": f"{t}_ToeBase"})
    for src, dst in (("Thumb", "Thumb"), ("Index", "Index"), ("Middle", "Middle"), ("Ring", "Ring"), ("Pinky", "Little")):
        for i in (1, 2, 3):
            MAP[f"{side}Hand{src}{i}"] = f"{t}_{dst}{i}"
MAP = {k: "J_Bip_" + v for k, v in MAP.items()}

# target rest pose
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "karakter_rambut.blend"))
arm = bpy.data.objects["Armature"]
REST, PARENT = {}, {}
for b in arm.data.bones:
    if b.name in MAP.values():
        REST[b.name] = b.matrix_local.to_quaternion()
        PARENT[b.name] = b.parent.name if b.parent and b.parent.name in MAP.values() else None
HIP_H = (arm.matrix_world @ arm.data.bones["J_Bip_C_Hips"].head_local).z
with open(os.path.join(ROOT, "mixamo", "target_rest.json"), "w") as fh:
    json.dump({"rest": {k: list(v) for k, v in REST.items()}, "parent": PARENT, "hip_height": HIP_H}, fh, indent=0)


def load(path):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=path)
    return next(o for o in bpy.data.objects if o.type == "ARMATURE")


def short(n):
    return n.split(":")[-1]


# source rest pose comes from the skinned T-pose file
ybot = load(os.path.join(ROOT, "mixamo", "pack", "Y Bot.fbx"))
SRC = {}
for b in ybot.data.bones:
    if short(b.name) in MAP:
        m = ybot.matrix_world @ b.matrix_local
        SRC[short(b.name)] = m.to_quaternion().normalized()
hb = next(b for b in ybot.data.bones if short(b.name) == "Hips")
HIP0 = (ybot.matrix_world @ hb.head_local).copy()
SCALE = HIP_H / HIP0.z
print("source bones", len(SRC), "of", len(MAP), "hip", tuple(round(x, 3) for x in HIP0))

files = sorted(glob.glob(os.path.join(ROOT, "mixamo", "pack", "*.fbx")) + glob.glob(os.path.join(ROOT, "mixamo", "raw", "*.fbx")))
order = [t for t in MAP.values()]
inv = {v: k for k, v in MAP.items()}
for path in files:
    name = re.sub(r"[^a-z0-9]+", "_", os.path.splitext(os.path.basename(path))[0].lower()).strip("_")
    if name == "y_bot":
        continue
    a = load(path)
    act = a.animation_data.action if a.animation_data else None
    if not act:
        print("no action", name)
        continue
    f0, f1 = (int(x) for x in act.frame_range)
    pose = {short(p.name): p for p in a.pose.bones}
    sc = bpy.context.scene
    Q = np.zeros((f1 - f0 + 1, len(order), 4), dtype=np.float32)
    H = np.zeros((f1 - f0 + 1, 3), dtype=np.float32)
    mw = a.matrix_world
    for i, f in enumerate(range(f0, f1 + 1)):
        sc.frame_set(f)
        D = {}
        for s, t in MAP.items():
            if s in pose and s in SRC:
                w = (mw @ pose[s].matrix).to_quaternion().normalized()
                D[t] = w @ SRC[s].inverted()
            else:
                D[t] = None
        for j, t in enumerate(order):
            d = D[t]
            if d is None:
                Q[i, j] = (1, 0, 0, 0)
                continue
            p = PARENT[t]
            dp = D[p] if p and D[p] is not None else Quaternion()
            q = REST[t].inverted() @ dp.inverted() @ d @ REST[t]
            Q[i, j] = q.normalized()
        H[i] = ((mw @ pose["Hips"].matrix).translation - HIP0) * SCALE
    np.savez_compressed(os.path.join(OUT, name + ".npz"), q=Q, hips=H, bones=np.array(order))
    print("baked", name, Q.shape[0], "frames, travel", np.round(H[-1] - H[0], 2).tolist())
print("ALL DONE")
