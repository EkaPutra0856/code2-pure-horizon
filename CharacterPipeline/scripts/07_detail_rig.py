# Pink gradient plus detailed hair rig. Bones follow the real lock centerlines and
# weights run along each lock's length, so strands bend smoothly instead of tearing.
# Vertex layout comes from build_hair.py: every lock is n rings of 8 verts, in build order.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, math, json
import numpy as np
from mathutils import Vector

arm = bpy.data.objects["Armature"]
hair = bpy.data.objects["Hair_New"]
HEAD = "J_Bip_C_Head"
K = 8


# ---------- pink gradient ----------
def hexc(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)])


img = bpy.data.images["hair_gradient"]
W, H = img.size
silver, pale, mid, deep = hexc("E4E6E5"), hexc("F4D9E2"), hexc("F2A9C4"), hexc("E2739F")
px = np.zeros((H, W, 4), dtype=np.float32)
for y in range(H):
    v = y / (H - 1)
    if v < 0.35:
        c = silver + (pale - silver) * (v / 0.35)
    elif v < 0.75:
        c = pale + (mid - pale) * ((v - 0.35) / 0.4)
    else:
        c = mid + (deep - mid) * ((v - 0.75) / 0.25)
    for x in range(W):
        e = abs(x / (W - 1) - 0.5) * 2
        s = 1.0 - 0.30 * max(0.0, (e - 0.82) / 0.18) ** 1.5
        s *= 1.0 - 0.14 * math.exp(-((e - 0.5) / 0.05) ** 2) - 0.08 * math.exp(-((e - 0.25) / 0.04) ** 2)
        px[y, x, :3] = c * s
        px[y, x, 3] = 1
img.pixels.foreach_set(px.ravel())
img["gamma_fixed"] = 1
img.save()

# ---------- locate locks ----------
locks = []
off = 0


def take(kind, n, **meta):
    global off
    locks.append(dict(kind=kind, start=off, n=n, **meta))
    off += n * K


for _ in range(32):
    take("shell", 18)
for layer, count in enumerate((16, 14, 10)):
    for s in (1, -1):
        for i in range(count):
            take("back", 70, s=s, f=i / (count - 1), layer=layer)
for s in (1, -1):
    for b in range(4):
        take("bang", 30, s=s, b=b)
    for a in range(3):
        take("accent", 24, s=s, a=a)
for i in range(3):
    take("lock", 36, i=i)
for i in range(3):
    take("braid", 110, i=i)
for i in range(3):
    take("tassel", 16, i=i)
assert off == len(hair.data.vertices), (off, len(hair.data.vertices))

mw = hair.matrix_world
co = np.array([v.co[:] for v in hair.data.vertices])
for L in locks:
    ring = co[L["start"]:L["start"] + L["n"] * K].reshape(L["n"], K, 3)
    L["c"] = [mw @ Vector(p) for p in ring.mean(axis=1)]


def r0_of(L, zs):
    for r, p in enumerate(L["c"]):
        if p.z < zs:
            return r
    return 0


def sample(L, r0, u):
    x = r0 + u * (L["n"] - 1 - r0)
    i = min(int(x), L["n"] - 2)
    return L["c"][i].lerp(L["c"][i + 1], x - i)


# ---------- chain definitions ----------
ZS = {"back": 1.43, "bang": 1.56, "accent": 1.56, "lock": 1.50, "braid": 1.46}
for L in locks:
    if L["kind"] in ZS:
        L["r0"] = r0_of(L, ZS[L["kind"]])

chains = {}  # name -> dict(pts, parent)


def avg_chain(name, members, bones, parent=HEAD):
    pts = []
    for j in range(bones + 1):
        acc, tw = Vector((0, 0, 0)), 0.0
        for L, w in members:
            acc += sample(L, L["r0"], j / bones) * w
            tw += w
        pts.append(acc / tw)
    chains[name] = dict(pts=pts, parent=parent, bones=bones)


NB = 8  # back chains per side
for s, tag in ((1, "L"), (-1, "R")):
    side = [L for L in locks if L["kind"] == "back" and L["s"] == s]
    for L in side:
        L["cpos"] = L["f"] * (NB - 1)
    for c in range(NB):
        mem = [(L, 1 - abs(L["cpos"] - c)) for L in side if abs(L["cpos"] - c) < 1]
        avg_chain(f"Back{tag}{c}", mem, 6)
    for b in range(4):
        L = next(x for x in locks if x["kind"] == "bang" and x["s"] == s and x["b"] == b)
        avg_chain(f"Bang{tag}{b}", [(L, 1)], 3)
for i in range(3):
    L = next(x for x in locks if x["kind"] == "lock" and x["i"] == i)
    avg_chain(f"Lock{i}", [(L, 1)], 5)
braids = [L for L in locks if L["kind"] == "braid"]
avg_chain("Braid", [(L, 1) for L in braids], 8)
for i, L in enumerate([x for x in locks if x["kind"] == "tassel"]):
    L["r0"] = 0
    avg_chain(f"Tassel{i}", [(L, 1)], 2, parent="Braid")

# ---------- bones ----------
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
for b in [b for b in eb if "HairNew" in b.name]:
    eb.remove(b)
inv = arm.matrix_world.inverted()
names = {}
for cname, C in chains.items():
    if C["parent"] == "Braid":
        continue
    parent, names[cname] = eb[HEAD], []
    for i in range(C["bones"]):
        b = eb.new(f"J_Sec_HairNew_{cname}_{i + 1:02d}")
        b.head, b.tail = inv @ C["pts"][i], inv @ C["pts"][i + 1]
        b.parent, b.use_connect = parent, i > 0
        parent = b
        names[cname].append(b.name)
for cname, C in chains.items():
    if C["parent"] != "Braid":
        continue
    parent, names[cname] = eb[names["Braid"][-1]], []
    for i in range(C["bones"]):
        b = eb.new(f"J_Sec_HairNew_{cname}_{i + 1:02d}")
        b.head, b.tail = inv @ C["pts"][i], inv @ C["pts"][i + 1]
        b.parent = parent
        parent = b
        names[cname].append(b.name)
bpy.ops.object.mode_set(mode="OBJECT")


# ---------- weights ----------
def along(u, chain):
    """Weights of the chain's bones at position u (0..1), blended across joints."""
    bl = names[chain]
    x = u * len(bl) - 0.5
    i = int(math.floor(x))
    f = x - i
    if i < 0:
        return {bl[0]: 1.0}
    if i >= len(bl) - 1:
        return {bl[-1]: 1.0}
    return {bl[i]: 1 - f, bl[i + 1]: f}


def ring_weights(L, r, mix, root_bone=HEAD, ramp=0.12):
    u = (r - L["r0"]) / max(1, L["n"] - 1 - L["r0"])
    if r <= L["r0"]:
        return {root_bone: 1.0}
    out = {}
    hw = max(0.0, 1 - u / ramp)
    for chain, w in mix:
        for b, bw in along(u, chain).items():
            out[b] = out.get(b, 0) + bw * w * (1 - hw)
    if hw > 0:
        out[root_bone] = out.get(root_bone, 0) + hw
    return out


hair.vertex_groups.clear()
groups = {}
buckets = {}


def put(v0, wts):
    top = sorted(wts.items(), key=lambda kv: -kv[1])[:4]  # VRM allows 4 influences
    tot = sum(w for _, w in top)
    for b, w in top:
        buckets.setdefault((b, round(w / tot, 3)), []).extend(range(v0, v0 + K))


for L in locks:
    k = L["kind"]
    for r in range(L["n"]):
        v0 = L["start"] + r * K
        if k == "shell":
            put(v0, {HEAD: 1.0})
            continue
        if k == "back":
            tag = "L" if L["s"] > 0 else "R"
            a = min(int(L["cpos"]), NB - 2)
            wb = L["cpos"] - a
            mix = [(f"Back{tag}{a}", 1 - wb), (f"Back{tag}{a + 1}", wb)]
            put(v0, ring_weights(L, r, [m for m in mix if m[1] > 0]))
        elif k == "bang":
            put(v0, ring_weights(L, r, [(f"Bang{'L' if L['s'] > 0 else 'R'}{L['b']}", 1.0)], ramp=0.2))
        elif k == "accent":
            tag = "L" if L["s"] > 0 else "R"
            tip = L["c"][-1]
            near = sorted(range(4), key=lambda b: (chains[f"Bang{tag}{b}"]["pts"][-1] - tip).length)[:2]
            d = [(chains[f"Bang{tag}{b}"]["pts"][-1] - tip).length + 1e-4 for b in near]
            w0 = d[1] / (d[0] + d[1])
            put(v0, ring_weights(L, r, [(f"Bang{tag}{near[0]}", w0), (f"Bang{tag}{near[1]}", 1 - w0)], ramp=0.2))
        elif k == "lock":
            put(v0, ring_weights(L, r, [(f"Lock{L['i']}", 1.0)]))
        elif k == "braid":
            put(v0, ring_weights(L, r, [("Braid", 1.0)], ramp=0.08))
        elif k == "tassel":
            put(v0, ring_weights(L, r, [(f"Tassel{L['i']}", 1.0)], root_bone=names["Braid"][-1], ramp=0.25))

for (b, w), idx in buckets.items():
    g = groups.get(b) or hair.vertex_groups.new(name=b)
    groups[b] = g
    g.add(idx, w, "REPLACE")

band = bpy.data.objects["Hair_Band"]
band.vertex_groups.clear()
band.vertex_groups.new(name=names["Braid"][-1]).add(list(range(len(band.data.vertices))), 1.0, "REPLACE")

# ---------- spring bones ----------
txt = bpy.data.texts["spring_bone.json"]
data = json.loads(txt.as_string())
colliders = next(g["colliderGroups"] for g in data if "HairNew" in g["comment"])
data = [g for g in data if "HairNew" not in g["comment"]]


def spring(comment, chs, stiff, grav, drag, radius):
    data.append({"bones": [names[c][0] for c in chs], "center": "Root", "colliderGroups": colliders,
                 "comment": comment, "dragForce": drag, "gravityDir": {"x": 0, "y": -1, "z": 0},
                 "gravityPower": grav, "hitRadius": radius, "stiffiness": stiff})


spring("HairNew_Back", [c for c in names if c.startswith("Back")], 0.8, 0.10, 0.45, 0.022)
spring("HairNew_Bangs", [c for c in names if c.startswith("Bang")], 2.2, 0.0, 0.65, 0.010)
spring("HairNew_SideLock", [c for c in names if c.startswith("Lock")], 1.1, 0.06, 0.5, 0.012)
spring("HairNew_Braid", ["Braid"], 1.4, 0.15, 0.55, 0.018)  # tassels ride along as its children
txt.clear()
txt.write(json.dumps(data, indent=4))

nb = sum(len(v) for v in names.values())
print("chains", len(names), "hair bones", nb, "armature bones", len(arm.data.bones), "vgroups", len(hair.vertex_groups))
print("spring", [(g["comment"], len(g["bones"])) for g in data])
with open(os.path.join(ANIME_GAME_ROOT, r"scripts\_bridge\chains.json"), "w") as fh:
    json.dump(names, fh)
bpy.ops.wm.save_mainfile()
