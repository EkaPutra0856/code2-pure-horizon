# Measures the swordswoman's body for the cloth / hair collision capsules used in Unreal (23_bf_cloth.py).
# Run on sw_outfit_v4.blend (headless, nothing saved). Capsules sit INSIDE the skin (Body / Face mesh only,
# moderate percentiles), so a strand that rests against the outfit is never swallowed by one; the solver
# then keeps each particle's rest gap (bRestRadius). A round capsule cannot fit a flat torso, so the chest
# and the pelvis use two capsules side by side / one across the hips; the pauldrons get spheres of their own.
# Also lists every physics chain (root to tip) with its rest positions.
# Writes export_unreal/sw_colliders.json in centimetres, Blender armature space (x left->right of the
# character is -x, y back, z up; Unreal mapping is checked in 23_bf_cloth.py).
import bpy, json, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
arm = bpy.data.objects["Armature"]
bones = arm.data.bones
M = arm.matrix_world
S = 100.0  # m -> cm


def head(b):
    return np.array(M @ bones[b].head_local) * S


def tail(b):
    return np.array(M @ bones[b].tail_local) * S


def verts(names):
    P, O = [], []
    for name in names:
        ob = bpy.data.objects[name]
        vg = {g.index: g.name for g in ob.vertex_groups}
        for v in ob.data.vertices:
            if v.groups:
                g = max(v.groups, key=lambda x: x.weight)
                P.append(np.array(ob.matrix_world @ v.co) * S)
                O.append(vg.get(g.group, ""))
    return np.array(P), np.array(O)


# Body skin under the outfit was deleted, so the tight layers stand in for it (their surface is the body plus
# a thin cloth); loose parts (pauldrons, medallion, trims, the physics cloth itself) are left out.
skin, skin_o = verts(["Body", "Face", "SW_InnerTop", "SW_Top", "SW_Vest", "SW_Collar", "SW_Obi", "SW_Boots", "SW_Gloves",
                      "SW_UnderSleeve", "SW_Vambrace"])
print("RESULT skin verts", len(skin))


def seg_dist(P, A, B):
    AB = B - A
    t = np.clip(((P - A) @ AB) / max(AB @ AB, 1e-9), 0, 1)
    return np.linalg.norm(P - (A + t[:, None] * AB), axis=1), t


def sel(owners):
    return skin[np.isin(skin_o, owners)]


C = []


def add(name, bone, end, a, b, r, n):
    C.append(dict(name=name, bone=bone, end=end, a=np.round(a, 2).tolist(), b=np.round(b, 2).tolist(),
                  bone_a=np.round(head(bone), 2).tolist(), bone_b=np.round(head(end), 2).tolist(), radius=round(float(r), 2), verts=int(n)))


def limb(name, owners, b0, b1, pct=60):
    P = sel(owners)
    A, B = head(b0), head(b1)
    AB = (B - A) / np.linalg.norm(B - A)
    c = P.mean(0)
    off = (c - A) - ((c - A) @ AB) * AB  # centre the axis on the flesh
    d, t = seg_dist(P, A + off, B + off)
    keep = (t > 0.05) & (t < 0.95)
    add(name, b0, b1, A + off, B + off, np.percentile(d[keep], pct), len(P))


# head: sphere on the skull centre (face + head skin)
H = sel(["J_Bip_C_Head", "J_Adj_L_FaceEye", "J_Adj_R_FaceEye"])
hc = H.mean(0)
add("head", "J_Bip_C_Head", "J_Bip_C_Head", hc - [0, 0, 2], hc + [0, 0, 2], np.percentile(np.linalg.norm(H - hc, axis=1), 50), len(H))
limb("neck", ["J_Bip_C_Neck"], "J_Bip_C_Neck", "J_Bip_C_Head", 55)

# torso: two upright capsules, one per side, as deep as the chest and spread to its width
T = sel(["J_Bip_C_Chest", "J_Bip_C_UpperChest", "J_Bip_C_Spine"])
T = T[(T[:, 2] > head("J_Bip_C_Spine")[2]) & (T[:, 2] < head("J_Bip_C_Neck")[2])]
A, B = head("J_Bip_C_Spine"), head("J_Bip_C_Neck") - [0, 0, 4]
c = T.mean(0)
half_w = np.percentile(np.abs(T[:, 0] - c[0]), 85)
half_d = np.percentile(np.abs(T[:, 1] - c[1]), 85)
r = half_d * 0.95
spread = max(0.0, half_w - r)
for side, sx in (("l", 1), ("r", -1)):
    o = np.array([c[0] + sx * spread - A[0], c[1] - A[1], 0])
    add("torso_" + side, "J_Bip_C_Spine", "J_Bip_C_UpperChest" if "J_Bip_C_UpperChest" in bones else "J_Bip_C_Chest",
        A + o, B + o, r, len(T))
# the second bone is UpperChest, so its offset is from that bone's head
for cc in C[-2:]:
    cc["bone_b"] = np.round(head(cc["end"]), 2).tolist()
print("RESULT torso half width", round(half_w, 1), "half depth", round(half_d, 1))

# pelvis: one capsule across the hips between the hip joints, as deep as the pelvis
Pv = sel(["J_Bip_C_Hips"])
lh, rh = head("J_Bip_L_UpperLeg"), head("J_Bip_R_UpperLeg")
pc = Pv.mean(0)
lift = np.array([0, pc[1] - (lh[1] + rh[1]) / 2, max(0.0, pc[2] - (lh[2] + rh[2]) / 2)])
add("pelvis", "J_Bip_L_UpperLeg", "J_Bip_R_UpperLeg", lh + lift, rh + lift, np.percentile(np.abs(Pv[:, 1] - pc[1]), 80), len(Pv))
for s, side in (("L", "l"), ("R", "r")):
    limb("thigh_" + side, [f"J_Bip_{s}_UpperLeg"], f"J_Bip_{s}_UpperLeg", f"J_Bip_{s}_LowerLeg", 60)
    limb("calf_" + side, [f"J_Bip_{s}_LowerLeg"], f"J_Bip_{s}_LowerLeg", f"J_Bip_{s}_Foot", 60)
    limb("upperarm_" + side, [f"J_Bip_{s}_UpperArm"], f"J_Bip_{s}_UpperArm", f"J_Bip_{s}_LowerArm", 60)
    limb("forearm_" + side, [f"J_Bip_{s}_LowerArm"], f"J_Bip_{s}_LowerArm", f"J_Bip_{s}_Hand", 60)
    # boots are wider than the foot skin; the robe hem brushes them
    Bt, Bo = verts(["SW_Boots"])
    fb = Bt[np.isin(Bo, [f"J_Bip_{s}_Foot", f"J_Bip_{s}_ToeBase"])]
    A, B = head(f"J_Bip_{s}_Foot"), head(f"J_Bip_{s}_ToeBase")
    d, t = seg_dist(fb, A, B)
    add("foot_" + side, f"J_Bip_{s}_Foot", f"J_Bip_{s}_ToeBase", A, B, np.percentile(d, 55), len(fb))
    # pauldron: a sphere on the shell's centre, radius to its outer surface (hair lies on top of it)
    pv = np.array([np.array(bpy.data.objects[f"SW_Pauldron_{s}"].matrix_world @ v.co) * S for v in bpy.data.objects[f"SW_Pauldron_{s}"].data.vertices])
    pc2 = pv.mean(0)
    add("pauldron_" + side, f"J_Bip_{s}_UpperArm", f"J_Bip_{s}_UpperArm", pc2, pc2, np.percentile(np.linalg.norm(pv - pc2, axis=1), 60), len(pv))

for c in C:
    print("RESULT collider", c["name"], "r", c["radius"], "verts", c["verts"])

setup = json.load(open(os.path.join(ROOT, "export_unreal", "ue_physics_setup.json")))
chains = {}
for gname, g in setup["groups"].items():
    for r in g["root_bones"]:
        ch, b = [r], bones[r]
        while b.children:
            b = b.children[0]
            ch.append(b.name)
        grp = "hair_front" if gname == "hair" and len(ch) <= 3 else gname
        chains[r] = dict(group=grp, bones=ch, rest=[head(x).round(2).tolist() for x in ch], tip=tail(ch[-1]).round(2).tolist())

# rest clearance report: how deep each chain's particles sit inside each capsule at rest
for r, ch in chains.items():
    worst = []
    for p in ch["rest"]:
        for c in C:
            d, _ = seg_dist(np.array([p]), np.array(c["a"]), np.array(c["b"]))
            if d[0] < c["radius"]:
                worst.append((c["name"], round(c["radius"] - float(d[0]), 1)))
    if worst:
        print("RESULT inside", ch["group"], r, sorted(worst, key=lambda x: -x[1])[:3])
json.dump(dict(units="cm", space="blender armature, x = character's left is +x, y back, z up", colliders=C, chains=chains),
          open(os.path.join(ROOT, "export_unreal", "sw_colliders.json"), "w"), indent=1)
print("RESULT written")
