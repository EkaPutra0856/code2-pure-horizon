# Builds the outfit from referensi/outfit_ref.webp. Safe to rerun: it replaces the Outfit
# collection and the J_Sec_Cloth bones. Fitted garments are clipped copies of the body surface,
# so they inherit its skin weights. Loose parts get their own bone chains for physics in Unreal.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, math, json, os
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = ANIME_GAME_ROOT
arm = bpy.data.objects["Armature"]
body = bpy.data.objects["Body"]
BONES = {b.name for b in arm.data.bones}
HIPS, CHEST = "J_Bip_C_Hips", "J_Bip_C_UpperChest"

col = bpy.data.collections.get("Outfit")
if col:
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    col = bpy.data.collections.new("Outfit")
    bpy.context.scene.collection.children.link(col)


def hx(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


# ---------- texture atlas: 4x4 tiles, one image for the whole outfit ----------
TILES = ["corset", "bolero", "sleeve", "stocking", "boot", "petal", "pleat", "belt",
         "leaf", "gold", "fur", "gem", "pouch", "cuff", "cape", "flap"]
T = 512


def mixc(a, b, t):
    return a + (b - a) * np.clip(t, 0, 1)[..., None]


def band(v, c, w):
    return np.clip(1 - np.abs(v - c) / w, 0, 1) > 0


def paint(name, U, V):
    gold = hx("D9B44A")
    if name == "corset":
        c = mixc(hx("F6CBD6"), hx("EDA9BE"), V)
        c = c * (1 - 0.10 * (np.abs(np.sin(U * math.pi * 7)) < 0.05))[..., None]
        trim = (V < 0.035) | (V > 0.965) | band(U, 0.0, 0.012) | band(U, 0.32, 0.01)
        c[trim] = gold
        return c
    if name == "bolero":
        c = np.broadcast_to(hx("3E7A48"), U.shape + (3,)).copy()
        swirl = np.abs(np.sin(U * 42 + 3.2 * np.sin(V * 15))) < 0.10
        c[swirl & (U < 0.34) & (V > 0.08)] = gold
        c[(V > 0.94) | (U < 0.03)] = gold
        return c
    if name == "sleeve":
        return mixc(hx("FBF8F2"), hx("E6E0D8"), 0.5 + 0.5 * np.sin(U * 40 + V * 5))
    if name == "stocking":
        c = np.broadcast_to(hx("F7F4EE"), U.shape + (3,)).copy()
        vine = 0.5 + 0.17 * np.sin(V * math.pi * 7)
        c[np.abs(U - vine) < 0.012] = hx("6C9A58")
        leaf = np.hypot((U - vine - 0.05 * np.sign(np.sin(V * 44))) * 1.1, ((V * 22) % 1 - 0.5) / 22 * 2) < 0.028
        c[leaf] = hx("7FAE68")
        c[V < 0.02] = gold
        return c
    if name == "boot":
        c = mixc(hx("6E4A30"), hx("5A3B26"), V)
        c[V > 0.80] = hx("4F8048")
        c[band(V, 0.80, 0.012) | band(V, 0.35, 0.010) | band(V, 0.55, 0.010) | (V < 0.02)] = gold
        return c
    if name == "petal":
        c = mixc(hx("6FA465"), hx("F3DCD6"), V / 0.42)
        c = np.where((V > 0.42)[..., None], mixc(hx("F3DCD6"), hx("EE9DBA"), (V - 0.42) / 0.5), c)
        vein = (np.abs(U - 0.5) < 0.012) | (np.abs(np.sin((U - 0.5) * 34 + V * 12)) < 0.04)
        return c * (1 - 0.10 * vein)[..., None]
    if name == "pleat":
        return mixc(hx("FAF7F1"), hx("EDE7DF"), V)
    if name == "belt":
        c = np.broadcast_to(hx("7A4E2D"), U.shape + (3,)).copy()
        c[band(V, 0.12, 0.02) | band(V, 0.88, 0.02)] = hx("B98B5C")
        return c
    if name == "leaf":
        c = mixc(hx("6FA052"), hx("3F7A3E"), V)
        vein = (np.abs(U - 0.5) < 0.014) | (np.abs(np.sin((np.abs(U - 0.5) * 2 + V) * 30)) < 0.05)
        c[vein] = hx("9CC27A")
        return c
    if name == "gold":
        return mixc(hx("E7C862"), hx("B98F34"), V)
    if name == "fur":
        n = np.sin(U * 90 + np.sin(V * 40) * 3) * np.sin(V * 70 + np.sin(U * 50) * 3)
        return mixc(hx("EFE9E1"), hx("FFFDF9"), 0.5 + 0.5 * n)
    if name == "gem":
        return mixc(hx("F7A3C0"), hx("D94F85"), V)
    if name == "pouch":
        c = mixc(hx("7B4F31"), hx("5F3C25"), V)
        c[(V < 0.03) | (V > 0.97)] = hx("B98B5C")
        return c
    if name == "flap":
        return mixc(hx("8A5A38"), hx("6E4629"), V)
    if name == "cuff":
        return mixc(hx("F8C4D4"), hx("EA8FB0"), V)
    if name == "cape":
        c = mixc(hx("FBF3F2"), hx("F4C6D4"), V)
        a = 0.26 + 0.20 * V ** 2 + 0.22 * (V > 0.975)
        return np.dstack([c, a])


atlas = np.ones((4 * T, 4 * T, 4), dtype=np.float32)
g = (np.arange(T, dtype=np.float32) + 0.5) / T
U, V = np.meshgrid((g - 0.01) / 0.98, (g - 0.01) / 0.98)
for n, name in enumerate(TILES):
    c, r = n % 4, n // 4
    p = paint(name, np.clip(U, 0, 1), np.clip(V, 0, 1))
    atlas[r * T:(r + 1) * T, c * T:(c + 1) * T, :p.shape[2]] = p[::-1]
img = bpy.data.images.get("outfit_atlas")
if img:
    bpy.data.images.remove(img)
img = bpy.data.images.new("outfit_atlas", 4 * T, 4 * T, alpha=True)
img.pixels.foreach_set(atlas.ravel())
img.filepath_raw = os.path.join(ROOT, "textures", "outfit_atlas.png")
img.file_format = "PNG"
img.save()


def tuv(tile, u, v):
    n = TILES.index(tile)
    return ((n % 4 + 0.01 + 0.98 * min(max(u, 0), 1)) / 4, (n // 4 + 0.01 + 0.98 * (1 - min(max(v, 0), 1))) / 4)


def material(name, blend=False):
    m = bpy.data.materials.get(name)
    if m:
        bpy.data.materials.remove(m)
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.75
    bsdf.inputs["Specular IOR Level"].default_value = 0.2
    m.use_backface_culling = False
    if blend:
        nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
        m.blend_method = "BLEND"
        m.shadow_method = "NONE"
        m.show_transparent_back = False
    return m


M_MAIN, M_CAPE = material("M_Outfit"), material("M_Outfit_Cape", True)


# ---------- body data ----------
bm = bmesh.new()
bm.from_mesh(body.data)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
TRI = [tuple(v.index for v in f.verts) for f in bm.faces if f.material_index == 0]
bm.free()
mw = body.matrix_world
P = np.array([mw @ v.co for v in body.data.vertices])
NRM = [(mw.to_3x3() @ v.normal).normalized() for v in body.data.vertices]
gname = {gr.index: gr.name for gr in body.vertex_groups}
W = []
for v in body.data.vertices:
    W.append({gname[e.group]: e.weight for e in v.groups if gname[e.group] in BONES and e.weight > 0.001})
DOM = [max(w, key=w.get) if w else "" for w in W]


def region(words):
    idx = {i for i, d in enumerate(DOM) if any(k in d for k in words)}
    tris = [t for t in TRI if any(i in idx for i in t)]
    return BVHTree.FromPolygons([Vector(p) for p in P], tris, all_triangles=True), idx


BVH_ALL = BVHTree.FromPolygons([Vector(p) for p in P], TRI, all_triangles=True)
BVH_TORSO, _ = region(["C_Hips", "C_Spine", "C_Chest", "C_UpperChest", "UpperLeg", "Bust"])


def clean(w):
    top = sorted(w.items(), key=lambda kv: -kv[1])[:4]
    t = sum(x for _, x in top) or 1
    return {b: x / t for b, x in top}


def add_object(name, verts, faces, uv, wts, mat=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    lay = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            lay.data[li].uv = uv[me.loops[li].vertex_index]
    me.materials.append(mat or M_MAIN)
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    me.update()
    ob = bpy.data.objects.new(name, me)
    col.objects.link(ob)
    ob.parent = arm
    ob.modifiers.new("Armature", "ARMATURE").object = arm
    groups = {}
    for i, w in enumerate(wts):
        for b, x in clean(w).items():
            gr = groups.get(b) or ob.vertex_groups.new(name=b)
            groups[b] = gr
            gr.add([i], x, "REPLACE")
    return ob


HIDDEN = np.zeros(len(P), dtype=bool)


def shell(name, fn, off, tile, uvf, relax=0, floor=False):
    """Copy of the body surface where fn > 0, cut cleanly along fn = 0 and pushed out by off."""
    f = fn(P)
    HIDDEN[f > 0.012] = True
    index, vs, ns, ws, faces = {}, [], [], [], []

    def keep(i):
        if i not in index:
            index[i] = len(vs)
            vs.append(Vector(P[i]))
            ns.append(NRM[i])
            ws.append(dict(W[i]))
        return index[i]

    def cut(a, b):
        k = (min(a, b), max(a, b))
        if k not in index:
            t = f[a] / (f[a] - f[b])
            index[k] = len(vs)
            vs.append(Vector(P[a]).lerp(Vector(P[b]), t))
            ns.append(NRM[a].lerp(NRM[b], t).normalized())
            w = {n: x * (1 - t) for n, x in W[a].items()}
            for n, x in W[b].items():
                w[n] = w.get(n, 0) + x * t
            ws.append(w)
        return index[k]

    for t in TRI:
        if max(f[i] for i in t) <= 0:
            continue
        poly = []
        for q in range(3):
            a, b = t[q], t[(q + 1) % 3]
            if f[a] > 0:
                poly.append(keep(a))
            if (f[a] > 0) != (f[b] > 0):
                poly.append(cut(a, b))
        if len(poly) >= 3:
            faces.append(poly)
    out = [v + n * off for v, n in zip(vs, ns)]
    if relax:
        nb = [set() for _ in out]
        for fc in faces:
            for a, b in zip(fc, fc[1:] + fc[:1]):
                nb[a].add(b)
                nb[b].add(a)
        for _ in range(relax):  # lets the cloth bridge hollows instead of hugging them
            out = [sum((out[j] for j in nb[i]), Vector()) / len(nb[i]) * 0.5 + out[i] * 0.5 if nb[i] else out[i]
                   for i in range(len(out))]
            for i, p in enumerate(out):
                loc, nr, _, _ = BVH_ALL.find_nearest(p)
                if (p - loc).dot(nr) < off:
                    out[i] = loc + nr * off
    if floor:
        for p in out:
            p.z = max(p.z, 0.0)
    return add_object(name, out, faces, [tuv(tile, *uvf(p)) for p in vs], ws)


def grid(name, rows, tile, wf, closed=True, mat=None, uvf=None):
    """Mesh from rows of points; wf(row, col, point) returns that vertex's bone weights."""
    R, N = len(rows), len(rows[0])
    verts = [p for r in rows for p in r]
    faces = []
    for i in range(R - 1):
        for k in range(N if closed else N - 1):
            k2 = (k + 1) % N
            faces.append([i * N + k, i * N + k2, (i + 1) * N + k2, (i + 1) * N + k])
    uv, ws = [], []
    for i in range(R):
        for k in range(N):
            u = 1 - abs(2 * k / N - 1) if closed else k / (N - 1)
            v = i / (R - 1)
            uv.append(tuv(tile, *(uvf(i, k) if uvf else (u, v))))
            ws.append(wf(i, k, rows[i][k]))
    return add_object(name, verts, faces, uv, ws, mat)


def rigid(bone):
    return lambda i, k, p: {bone: 1.0}


def tube(pts, rad, sides=8, closed=False):
    """Rings around a path; rad(index, angle) gives the radius."""
    rows, n = [], len(pts)
    for i, p in enumerate(pts):
        a = pts[(i + 1) % n] if closed or i < n - 1 else p
        b = pts[i - 1] if closed or i > 0 else p
        t = (a - b).normalized()
        u = t.cross(Vector((0.13, 0.2, 1))).normalized()
        v = t.cross(u)
        rows.append([p + (u * math.cos(s) + v * math.sin(s)) * rad(i, s)
                     for s in (2 * math.pi * k / sides for k in range(sides))])
    return rows + rows[:1] if closed else rows


# ---------- bone chains ----------
CHAINS = {}


def chain(name, pts, parent):
    CHAINS[name] = dict(pts=pts, parent=parent, bones=[f"J_Sec_Cloth_{name}_{i + 1:02d}" for i in range(len(pts) - 1)])
    return CHAINS[name]["bones"]


def along(bones, u):
    x = u * len(bones) - 0.5
    i = math.floor(x)
    if i < 0:
        return {bones[0]: 1.0}
    if i >= len(bones) - 1:
        return {bones[-1]: 1.0}
    return {bones[i]: 1 - (x - i), bones[i + 1]: x - i}


def cloth(mix, u, root, ramp=0.12):
    """Weights at length u (0..1) over one or two chains, easing in from the root bone."""
    if u <= 0:
        return {root: 1.0}
    hw = max(0.0, 1 - u / ramp)
    out = {root: hw} if hw else {}
    for bones, m in mix:
        for b, x in along(bones, u).items():
            out[b] = out.get(b, 0) + x * m * (1 - hw)
    return out


# ---------- rings around the pelvis ----------
def dirv(th):
    return Vector((math.sin(th), -math.cos(th), 0))


def ring_r(z, n):
    r = np.full(n, np.nan)
    for k in range(n):
        d = dirv(2 * math.pi * k / n)
        o = Vector((0, 0, z)) + d * 0.6
        hit = BVH_TORSO.ray_cast(o, -d, 0.6)[0]
        if hit:
            r[k] = (hit - Vector((0, 0, z))).length
    ok = ~np.isnan(r)
    r = np.interp(np.arange(n), np.arange(n)[ok], r[ok], period=n)
    s = np.mean([np.roll(r, j) for j in range(-3, 4)], axis=0)
    return np.maximum(r, s)


def at(th, r, z):
    return dirv(th) * r + Vector((0, 0, z))


# ---------- fitted garments ----------
def polar(p):
    return np.degrees(np.arctan2(np.abs(p[:, 0]), -(p[:, 1] + 0.02)))


def corset_top(d):
    return np.interp(d, [0, 12, 30, 90, 180], [1.200, 1.218, 1.222, 1.195, 1.160])


def corset_bot(d):
    return np.interp(d, [0, 25, 90, 180], [0.905, 0.925, 0.940, 0.945])


def f_corset(p):
    d = polar(p)
    return np.minimum.reduce([p[:, 2] - corset_bot(d), corset_top(d) - p[:, 2], 0.17 - np.abs(p[:, 0])])


def uv_corset(p):
    d = math.degrees(math.atan2(abs(p.x), -(p.y + 0.02)))
    b, t = float(corset_bot(d)), float(corset_top(d))
    return d / 180, (t - p.z) / (t - b)


shell("Outfit_Corset", f_corset, 0.006, "corset", uv_corset, relax=10)


def f_bolero(p):
    x, y, z = p.T
    opening = np.maximum(np.abs(x) - (0.04 + (1.30 - z) * 0.33), y + 0.01)
    neck = np.hypot(x, y - 0.03) - 0.075
    return np.minimum.reduce([z - 1.125, 0.25 - np.abs(x), opening, neck, 1.36 - z])


def uv_bolero(p):
    return math.degrees(math.atan2(abs(p.x), -(p.y + 0.02))) / 180, (1.33 - p.z) / 0.205


shell("Outfit_Bolero", f_bolero, 0.012, "bolero", uv_bolero, relax=3)


def leg_uv(p, top):
    a = math.atan2(abs(p.x) - 0.083, -(p.y - 0.03))
    return abs(a) / math.pi, (top - p.z) / top


shell("Outfit_Stockings", lambda p: np.minimum(0.62 - p[:, 2], p[:, 2] - 0.36), 0.0045, "stocking",
      lambda p: leg_uv(p, 0.62))


def uv_boot(p):
    toe = min(max((0.11 - p.z) / 0.05, 0), 1) * min(max((0.03 - p.y) / 0.06, 0), 1)
    return leg_uv(p, 0.41)[0], (0.41 - p.z) / 0.41 * 0.78 + 0.2 * toe


shell("Outfit_Boots", lambda p: 0.41 - p[:, 2], 0.012, "boot", uv_boot, relax=2, floor=True)

# ---------- sleeves ----------
for s, tag in ((1, "L"), (-1, "R")):
    up, low, hand = f"J_Bip_{tag}_UpperArm", f"J_Bip_{tag}_LowerArm", f"J_Bip_{tag}_Hand"

    def arm_w(i, k, p):
        t = min(max((abs(p.x) - 0.30) / 0.06, 0), 1)
        return {up: 1 - t, low: t} if t < 1 else {low: 1.0}

    xs = np.linspace(0.245, 0.528, 22)
    prof = np.interp(xs, [0.245, 0.40, 0.47, 0.51, 0.528], [0.047, 0.056, 0.062, 0.050, 0.043])
    rows = []
    for x, r in zip(xs, prof):
        fold = 0.05 * min((x - 0.245) / 0.1, 1)
        rows.append([Vector((s * x, 0.025 + math.cos(a) * r * (1 + fold * math.sin(5 * a + x * 30)),
                             1.258 + math.sin(a) * r * (1 + fold * math.sin(5 * a + x * 30))))
                     for a in (2 * math.pi * k / 28 for k in range(28))])
    grid(f"Outfit_Sleeve_{tag}", rows, "sleeve", arm_w)

    def cuff_w(i, k, p):
        return {low: 0.5, hand: 0.5} if i else {low: 1.0}

    rows = []
    for j in range(7):
        t = j / 6
        r = 0.042 + 0.030 * t ** 0.8
        rows.append([Vector((s * (0.524 + 0.052 * t + 0.012 * t * math.sin(6 * a)),
                             0.025 + math.cos(a) * r, 1.258 + math.sin(a) * r))
                     for a in (2 * math.pi * k / 36 for k in range(36))])
    grid(f"Outfit_Cuff_{tag}", rows, "cuff", cuff_w)
    for nm, x, r, w, bone in (("Armband", 0.25, 0.054, 0.014, up), ("Bracelet", 0.526, 0.047, 0.010, low)):
        rows = [[Vector((s * (x + dx), 0.025 + math.cos(a) * rr, 1.258 + math.sin(a) * rr))
                 for a in (2 * math.pi * k / 28 for k in range(28))]
                for dx, rr in ((-w, r - 0.003), (-w * 0.6, r), (w * 0.6, r), (w, r - 0.003))]
        grid(f"Outfit_{nm}_{tag}", rows, "gold", rigid(bone))

# ---------- boot cuffs ----------
for s, tag in ((1, "L"), (-1, "R")):
    c0 = Vector((s * 0.083, 0.04, 0.395))
    for j in range(6):
        a = 2 * math.pi * j / 6 + 0.3
        d, side = Vector((math.sin(a), -math.cos(a), 0)), Vector((math.cos(a), math.sin(a), 0))
        rows = []
        for i in range(10):
            t = i / 9
            w = 0.040 * (t + 0.25) ** 0.4 * max(1 - t, 0.0) ** 0.55 * 1.5
            c = c0 + d * (0.062 + 0.034 * t ** 1.5) + Vector((0, 0, 0.09 * t))
            rows.append([c + side * (w * q) - d * (0.3 * w * q * q) for q in np.linspace(-1, 1, 7)])
        grid(f"Outfit_BootPetal_{tag}{j}", rows, "cuff", rigid(f"J_Bip_{tag}_LowerLeg"), closed=False)

# ---------- collar and brooch ----------
pts, N = [], 96
for i in range(N):
    a = 2 * math.pi * i / N
    pts.append(Vector((0.098 * math.sin(a), 0.015 - 0.092 * math.cos(a), 1.2925 - 0.0225 * math.cos(a))))
rows = tube(pts, lambda i, a: 0.031 * (1 + 0.20 * math.sin(i * 0.85 + 3 * a) * math.sin(2 * a + i * 0.33)), 12, closed=True)
grid("Outfit_Collar", rows, "fur", rigid(CHEST))


def blob(center, rx, ry, rz, n=14):
    return [[center + Vector((rx * math.sin(b) * math.cos(a), ry * math.cos(b), rz * math.sin(b) * math.sin(a)))
             for a in (2 * math.pi * k / n for k in range(n))] for b in np.linspace(0.02, math.pi - 0.02, 9)]


front = BVH_TORSO.ray_cast(Vector((0, -0.6, 1.195)), Vector((0, 1, 0)), 1.0)[0]
grid("Outfit_Brooch_Gem", blob(front + Vector((0, -0.024, 0)), 0.017, 0.010, 0.020), "gem", rigid(CHEST))
ringp = [front + Vector((0.024 * math.cos(a), -0.018, 0.027 * math.sin(a))) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
grid("Outfit_Brooch_Gold", tube(ringp, lambda i, a: 0.0055, 6, closed=True), "gold", rigid(CHEST))

# ---------- pleated skirt ----------
NS, SK = 96, 12
Z0, ZH = 0.95, 0.70
zs = np.linspace(Z0, ZH, 16)
base = ring_r(0.84, NS) + 0.012
ringz = {}
for z in zs:
    ringz[z] = ring_r(z, NS) + (0.003 if z >= 0.925 else 0.012) if z >= 0.84 else base + (0.84 - z) * 0.22


def tri_wave(t):
    return 2 * abs((t % 1) - 0.5) * 2 - 1


rows = []
for z in zs:
    amp = 0.003 + 0.009 * (Z0 - z) / (Z0 - ZH)
    rows.append([at(2 * math.pi * k / NS, ringz[z][k] + amp * tri_wave(k / 4), z) for k in range(NS)])
sk = []
for c in range(SK):
    k = c * NS // SK
    th = 2 * math.pi * k / NS
    p = []
    for z in (0.90, 0.83, 0.765, 0.70):
        rr = ring_r(z, NS)[k] + 0.012 if z >= 0.84 else base[k] + (0.84 - z) * 0.22
        p.append(at(th, rr, z))
    sk.append(chain(f"Skirt{c:02d}", p, HIPS))


def skirt_w(i, k, p):
    c = k / NS * SK
    a = int(c) % SK
    t = c - int(c)
    return cloth([(sk[a], 1 - t), (sk[(a + 1) % SK], t)], (0.90 - zs[i]) / 0.20, HIPS, 0.15)


grid("Outfit_Skirt", rows, "pleat", skirt_w)

# ---------- petals and leaves ----------
RH = ring_r(0.93, 180)


def petal_rows(th, r0, z0, L, Wd, flare, n=18, m=9):
    d, side = dirv(th), Vector((math.cos(th), math.sin(th), 0))
    rows = []
    for i in range(n):
        s = i / (n - 1)
        w = Wd * 1.6 * (s + 0.12) ** 0.45 * max(1 - s, 0.0) ** 0.6
        c = d * (r0 + 0.035 * min(s / 0.2, 1) + flare * s ** 1.3) + Vector((0, 0, z0 - L * s))
        rows.append([c + side * (w * j) - d * (0.15 * w * j * j)
                     for j in np.linspace(-1, 1, m)])
    return rows


def centre(th, r0, z0, L, flare, s):
    return dirv(th) * (r0 + 0.035 * min(s / 0.2, 1) + flare * s ** 1.3) + Vector((0, 0, z0 - L * s))


def petal(name, deg, L, Wd, flare, z0, pad, tile, us):
    th = math.radians(deg)
    r0 = float(RH[int(deg % 360) // 2]) + pad
    bones = chain(name, [centre(th, r0, z0, L, flare, s) for s in us], HIPS)
    n = 18 if tile == "petal" else 11

    def w(i, k, p):
        return cloth([(bones, 1.0)], (i / (n - 1) - us[0]) / (1 - us[0]), HIPS, 0.1)

    grid(f"Outfit_{name}", petal_rows(th, r0, z0, L, Wd, flare, n), tile, w, closed=False)


SPEC = [(45, 0.46, 0.105, 0.20), (80, 0.52, 0.125, 0.24), (115, 0.54, 0.125, 0.22), (150, 0.54, 0.125, 0.16)]
for deg, L, Wd, fl in SPEC:
    petal(f"PetalL{deg}", deg, L, Wd, fl, 0.925, 0.016, "petal", (0.12, 0.35, 0.6, 0.82, 1.0))
    petal(f"PetalR{deg}", -deg, L, Wd, fl, 0.925, 0.016, "petal", (0.12, 0.35, 0.6, 0.82, 1.0))
petal("PetalBack", 180, 0.54, 0.125, 0.14, 0.925, 0.022, "petal", (0.12, 0.35, 0.6, 0.82, 1.0))
for i, (deg, L) in enumerate(((-20, 0.20), (5, 0.22), (22, 0.18), (38, 0.15))):
    petal(f"Leaf{i}", deg, L, 0.05, 0.05, 0.915, 0.036, "leaf", (0.15, 0.55, 1.0))

# ---------- belt, buckle, pouch ----------
NB = 64


def belt_z(th):
    return 0.93 + 0.024 * math.sin(th)


RB = {dz: ring_r(0.93 + dz, NB) for dz in (-0.02, 0.0, 0.02)}
rows = [[at(2 * math.pi * k / NB, RB[dz][k] + 0.03, belt_z(2 * math.pi * k / NB) + dz) for k in range(NB)]
        for dz in (0.02, 0.0, -0.02)]
grid("Outfit_Belt", rows, "belt", rigid(HIPS))
bc = at(0, float(RB[0.0][0]) + 0.037, belt_z(0))
sq = [bc + Vector((0.030 * np.sign(math.cos(a)) * abs(math.cos(a)) ** 0.5, 0, 0.024 * np.sign(math.sin(a)) * abs(math.sin(a)) ** 0.5))
      for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
grid("Outfit_Buckle", tube(sq, lambda i, a: 0.0055, 6, closed=True), "gold", rigid(HIPS))
grid("Outfit_Buckle_Pin", tube([bc + Vector((-0.03, -0.003, 0)), bc + Vector((0.03, -0.003, 0))], lambda i, a: 0.003, 6), "gold", rigid(HIPS))


def box(c, hx_, hy, hz, n=16, m=9):
    def sp(v, e):
        return math.copysign(abs(v) ** e, v)
    rows = []
    for b in np.linspace(-math.pi / 2 + 0.02, math.pi / 2 - 0.02, m):
        rows.append([c + Vector((hx_ * sp(math.cos(b), 0.4) * sp(math.cos(a), 0.4),
                                 hy * sp(math.cos(b), 0.4) * sp(math.sin(a), 0.4), hz * sp(math.sin(b), 0.4)))
                     for a in (2 * math.pi * k / n for k in range(n))])
    return rows[::-1]


th = math.radians(-72)
pc = at(th, float(RB[0.0][int(-72 % 360 / 360 * NB)]) + 0.05, 0.855)
pb = chain("Pouch", [pc + Vector((0, 0, 0.06)), pc, pc + Vector((0, 0, -0.055))], HIPS)
grid("Outfit_Pouch", box(pc, 0.052, 0.030, 0.050), "pouch", rigid(pb[0]))
grid("Outfit_Pouch_Flap", box(pc + Vector((0, -0.006, 0.028)), 0.056, 0.031, 0.026), "flap", rigid(pb[0]))
grid("Outfit_Pouch_Button", blob(pc + Vector((0, -0.038, 0.012)), 0.010, 0.006, 0.010), "gold", rigid(pb[0]))

# ---------- cape ----------
NC, RC, CC = 25, 26, 7


def cape_p(c, s):
    x = c * (0.17 + 0.20 * s ** 0.8)
    y = 0.088 + 0.30 * s ** 1.5 - 0.10 * c * c * s + 0.012 * s * math.sin(7 * c + 1)
    z = 1.27 - 0.87 * s + 0.03 * s * math.sin(c * 6)
    return Vector((x, y, z))


cols = np.linspace(-1, 1, CC)
ss = (0.05, 0.22, 0.40, 0.58, 0.76, 0.90, 1.0)
cp = [chain(f"Cape{i}", [cape_p(float(c), s) for s in ss], CHEST) for i, c in enumerate(cols)]
rows = [[cape_p(c, s) for c in np.linspace(-1, 1, NC)] for s in np.linspace(0, 1, RC)]


def cape_w(i, k, p):
    x = k / (NC - 1) * (CC - 1)
    a = min(int(x), CC - 2)
    t = x - a
    return cloth([(cp[a], 1 - t), (cp[a + 1], t)], (i / (RC - 1) - 0.05) / 0.95, CHEST, 0.08)


grid("Outfit_Cape", rows, "cape", cape_w, closed=False, mat=M_CAPE)

# ---------- bones ----------
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
for b in [b for b in eb if "J_Sec_Cloth" in b.name]:
    eb.remove(b)
for C in CHAINS.values():
    parent = eb[C["parent"]]
    for i, name in enumerate(C["bones"]):
        b = eb.new(name)
        b.head, b.tail = C["pts"][i], C["pts"][i + 1]
        b.parent, b.use_connect = parent, i > 0
        parent = b
bpy.ops.object.mode_set(mode="OBJECT")

# ---------- hide skin under the clothes (keeps the body mesh itself intact) ----------
x = np.abs(P[:, 0])
HIDDEN |= (x > 0.27) & (x < 0.52) & (P[:, 2] > 1.1)
gr = body.vertex_groups.get("Outfit_Hidden") or body.vertex_groups.new(name="Outfit_Hidden")
gr.remove(list(range(len(P))))
gr.add(np.nonzero(HIDDEN)[0].tolist(), 1.0, "REPLACE")
mask = body.modifiers.get("Outfit_Mask") or body.modifiers.new("Outfit_Mask", "MASK")
mask.vertex_group = "Outfit_Hidden"
mask.invert_vertex_group = True
while body.modifiers[0] != mask:
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_move_up(modifier=mask.name)

with open(os.path.join(ROOT, "scripts", "_bridge", "cloth_chains.json"), "w") as fh:
    json.dump({k: dict(bones=v["bones"], parent=v["parent"]) for k, v in CHAINS.items()}, fh, indent=1)
print("objects", len(col.objects), "verts", sum(len(o.data.vertices) for o in col.objects),
      "chains", len(CHAINS), "bones", sum(len(c["bones"]) for c in CHAINS.values()), "hidden", int(HIDDEN.sum()))
bpy.ops.wm.save_mainfile()
