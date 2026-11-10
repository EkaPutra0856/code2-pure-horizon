# Swordswoman outfit, topknot and hair ornaments on the VRoid base (sw_base.blend), saved as sw_outfit.blend.
# Palette follows the player VFX: cyan 59CCFF, ice white E6F2FF, gold FFCC4D, orange FF8C33, navy for contrast.
# Fabric motifs come from Gemini (textures/g_*.{jpg,png}) and are packed with procedural tiles into one 4x4 atlas.
# Fitted garments are clipped copies of the body surface, so they inherit its skin weights (same approach as
# scripts/10_outfit.py). Skirt and sleeve bags get J_Sec_Cloth bone chains for physics in Unreal.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, math, json, os, sys
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

ROOT = os.path.join(ANIME_GAME_ROOT, r"swordswoman")
TEX = os.path.join(ROOT, "textures")
arm = bpy.data.objects["Armature"]
body = bpy.data.objects["Body"]
hair = bpy.data.objects["Hair"]
BONES = {b.name for b in arm.data.bones}
HIPS, SPINE, CHEST, UCHEST, NECK, HEAD = ("J_Bip_C_Hips", "J_Bip_C_Spine", "J_Bip_C_Chest", "J_Bip_C_UpperChest",
                                          "J_Bip_C_Neck", "J_Bip_C_Head")

col = bpy.data.collections.get("Outfit")
if col:
    for o in list(col.objects):
        bpy.data.objects.remove(o, do_unlink=True)
else:
    col = bpy.data.collections.new("Outfit")
    bpy.context.scene.collection.children.link(col)


def hx(h):
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], dtype=np.float32)


# ---------- atlas ----------
T = 512
TILES = ["vest", "top", "robe", "skirt", "trim_navy", "trim_gold", "obi", "trim_white",
         "boot", "glove", "gold", "flower", "hair", "plate", "jade", "cord"]


def load(name):
    """Image as a top-down float RGBA array."""
    im = bpy.data.images.load(os.path.join(TEX, name), check_existing=False)
    a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)[::-1].copy()
    bpy.data.images.remove(im)
    return a


def rs(a, h, w):
    """Bilinear resample to h x w."""
    H, W = a.shape[:2]
    y = np.clip((np.arange(h) + 0.5) * H / h - 0.5, 0, H - 1)
    x = np.clip((np.arange(w) + 0.5) * W / w - 0.5, 0, W - 1)
    y0, x0 = np.floor(y).astype(int), np.floor(x).astype(int)
    y1, x1 = np.minimum(y0 + 1, H - 1), np.minimum(x0 + 1, W - 1)
    fy, fx = (y - y0)[:, None, None], (x - x0)[None, :, None]
    top = a[y0][:, x0] * (1 - fx) + a[y0][:, x1] * fx
    bot = a[y1][:, x0] * (1 - fx) + a[y1][:, x1] * fx
    return top * (1 - fy) + bot * fy


SEIG = load("g_seigaiha_navy.jpg")[:560, :560]  # a corner of it, so the waves read larger on the body
ASA = load("g_asanoha_white.jpg")
TRIMS = load("g_trims.jpg")
FLOW = load("g_flower.png")
SCALE = load("g_scales.jpg")
SCALE = np.concatenate([np.concatenate([SCALE] * 2, axis=1)] * 2, axis=0)  # 2x2, smaller scales
CLOUD = load("g_cloudhem.jpg")
BOOT = load("g_bootleather.jpg")
BAND = {"navy": TRIMS[12:246], "gold": TRIMS[268:500], "obi": TRIMS[520:766], "white": TRIMS[788:1008]}


def band_tile(b, reps):
    return rs(np.concatenate([BAND[b]] * reps, axis=1), T, T)


def solid(h):
    a = np.ones((T, T, 4), dtype=np.float32)
    a[..., :3] = hx(h)
    return a


g = (np.arange(T, dtype=np.float32) + 0.5) / T
U, V = np.meshgrid(g, g)  # V = 0 at the top row


def mixc(a, b, t):
    t = np.clip(t, 0, 1)[..., None]
    return a + (b - a) * t


def paste(dst, src, v0, v1):
    """Pastes src squeezed into rows v0..v1 (fractions) of dst."""
    r0, r1 = int(v0 * T), int(v1 * T)
    dst[r0:r1] = rs(src, r1 - r0, T)
    return dst


def paint(name):
    gold = hx("FFCC4D")
    if name == "vest":
        return rs(SCALE, T, T)
    if name == "top":
        return rs(ASA, T, T)
    if name == "robe":
        return rs(CLOUD, T, T)
    if name == "skirt":
        a = rs(ASA, T, T)
        a[..., :3] = mixc(a[..., :3], a[..., :3] * hx("A9DDF5"), 0.35 + V * 0.6)
        paste(a, BAND["white"], 0.86, 1.0)
        return a
    if name == "trim_navy":
        return band_tile("navy", 6)
    if name == "trim_gold":
        return band_tile("gold", 6)
    if name == "obi":
        return band_tile("obi", 1)
    if name == "trim_white":
        return band_tile("white", 6)
    if name == "boot":
        a = rs(BOOT, T, T)
        a[V < 0.05, :3] = gold
        a[(V > 0.05) & (V < 0.065), :3] = hx("59CCFF")
        a[V > 0.95, :3] = hx("0C0C10")
        return a
    if name == "glove":
        a = solid("1A2440")
        a[..., :3] = mixc(hx("22305A"), hx("161E36"), V)
        a[V < 0.12, :3] = gold
        a[(V > 0.13) & (V < 0.16), :3] = hx("59CCFF")
        a[V > 0.95, :3] = gold
        return a
    if name == "gold":
        a = solid("FFCC4D")
        a[..., :3] = mixc(hx("FFE08A"), hx("C8962E"), V)
        return a
    if name == "flower":
        a = rs(FLOW, T, T)
        lum = a[..., :3].max(axis=2)
        a[..., 3] = np.clip((lum - 0.10) / 0.12, 0, 1)
        return a
    if name == "hair":
        a = solid("1C1B22")
        s = np.maximum(0, np.sin(U * 70 + np.sin(V * 9) * 2)) ** 6
        a[..., :3] = mixc(hx("1C1B22"), hx("5A6A82"), 0.45 * s + 0.15 * (1 - V))
        return a
    if name == "plate":
        a = rs(SCALE, T, T)
        edge = (U < 0.05) | (U > 0.95) | (V < 0.06) | (V > 0.94)
        a[edge, :3] = gold
        return a
    if name == "jade":
        a = solid("3FA86A")
        n = np.sin(U * 23 + np.sin(V * 17) * 2) * np.sin(V * 19 + np.sin(U * 11) * 2)
        a[..., :3] = mixc(hx("2E8A55"), hx("8FD9A8"), 0.5 + 0.35 * n)
        return a
    if name == "cord":
        a = solid("59CCFF")
        st = np.sin((U * 14 + V * 3) * math.pi * 2) > 0.55
        a[st, :3] = hx("E6F2FF")
        return a


atlas = np.ones((4 * T, 4 * T, 4), dtype=np.float32)
for n, name in enumerate(TILES):
    c, r = n % 4, n // 4
    p = paint(name)
    atlas[r * T:(r + 1) * T, c * T:(c + 1) * T, :p.shape[2]] = p[::-1]
atlas = np.clip(atlas, 0, 1)
img = bpy.data.images.get("sw_atlas")
if img:
    bpy.data.images.remove(img)
img = bpy.data.images.new("sw_atlas", 4 * T, 4 * T, alpha=True)
img.pixels.foreach_set(atlas.ravel())
img.filepath_raw = os.path.join(TEX, "sw_atlas.png")
img.file_format = "PNG"
img.save()


def tuv(tile, u, v):
    n = TILES.index(tile)
    return ((n % 4 + 0.01 + 0.98 * min(max(u, 0), 1)) / 4, (n // 4 + 0.01 + 0.98 * (1 - min(max(v, 0), 1))) / 4)


# ---------- MToon material cloned from the VRoid hair, so it shades like the head ----------
def lin(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


SRC = "N00_000_00_HairBack_00_HAIR (Instance)"
old = bpy.data.materials.get("SW_Outfit_MToon")
if old:
    bpy.data.materials.remove(old)
MAT = bpy.data.materials[SRC].copy()
MAT.name = "SW_Outfit_MToon"
nd = MAT.node_tree.nodes
nd["Image Texture"].image = img
nd["Image Texture.001"].image = img
nd["Image Texture.002"].image = bpy.data.images["Shader_NoneNormal"]
nd["RGB"].outputs[0].default_value = (1, 1, 1, 1)
nd["RGB.001"].outputs[0].default_value = lin("BAC3DE")
MAT.use_backface_culling = False

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
W = [{gname[e.group]: e.weight for e in v.groups if gname[e.group] in BONES and e.weight > 0.001}
     for v in body.data.vertices]
DOM = [max(w, key=w.get) if w else "" for w in W]
USED = sorted({i for t in TRI for i in t})
KD = KDTree(len(USED))
for i in USED:
    KD.insert(Vector(P[i]), i)
KD.balance()


def region(words):
    idx = {i for i, d in enumerate(DOM) if any(k in d for k in words)}
    tris = [t for t in TRI if any(i in idx for i in t)]
    return BVHTree.FromPolygons([Vector(p) for p in P], tris, all_triangles=True)


BVH_ALL = BVHTree.FromPolygons([Vector(p) for p in P], TRI, all_triangles=True)
BVH_TORSO = region(["C_Hips", "C_Spine", "C_Chest", "C_UpperChest", "UpperLeg", "Bust"])


def clean(w):
    top = sorted(w.items(), key=lambda kv: -kv[1])[:4]
    t = sum(x for _, x in top) or 1
    return {b: x / t for b, x in top}


def near_w(p):
    """Skin weights of the closest body vertex."""
    return dict(W[KD.find(Vector(p))[1]])


def add_object(name, verts, faces, uv, wts):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    lay = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            lay.data[li].uv = uv[me.loops[li].vertex_index]
    me.materials.append(MAT)
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
# VRoid splits the body along UV seams; weld by position so copies cut from it have no cracks along the seams
_first = {}
CANON = [_first.setdefault(tuple(np.round(p * 1e5).astype(np.int64)), i) for i, p in enumerate(P)]


def shell(name, fn, off, tile, uvf, relax=0, floor=False, hide=True):
    """Copy of the body surface where fn > 0, cut cleanly along fn = 0 and pushed out by off."""
    f = fn(P)
    if hide:
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
        t = tuple(CANON[i] for i in t)
        if len(set(t)) < 3 or max(f[i] for i in t) <= 0:
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
        ecount = {}
        for fc in faces:
            for a, b in zip(fc, fc[1:] + fc[:1]):
                nb[a].add(b)
                nb[b].add(a)
                k = (min(a, b), max(a, b))
                ecount[k] = ecount.get(k, 0) + 1
        # open-edge vertices smooth only along the edge, so a cut line stays a clean line and doesn't fray
        rim = [set() for _ in out]
        for (a, b), c in ecount.items():
            if c == 1:
                rim[a].add(b)
                rim[b].add(a)
        nb = [rim[i] if rim[i] else nb[i] for i in range(len(out))]
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


def grid(name, rows, tile, wf, closed=True, uvf=None):
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
    return add_object(name, verts, faces, uv, ws)


def rigid(bone):
    return lambda i, k, p: {bone: 1.0}


def skin(i, k, p):
    return near_w(p)


def tube(pts, rad, sides=8, closed=False):
    """Rings around a path; rad(index, angle) gives the radius."""
    rows, n = [], len(pts)
    for i, p in enumerate(pts):
        a = pts[(i + 1) % n] if closed or i < n - 1 else p
        b = pts[i - 1] if closed or i > 0 else p
        t = (a - b).normalized()
        u = t.cross(Vector((0.13, 0.2, 1))).normalized()
        if u.length < 0.5:
            u = t.cross(Vector((1, 0, 0))).normalized()
        v = t.cross(u)
        rows.append([p + (u * math.cos(s) + v * math.sin(s)) * rad(i, s)
                     for s in (2 * math.pi * k / sides for k in range(sides))])
    return rows + rows[:1] if closed else rows


def blob(center, rx, ry, rz, n=14, m=9, wob=None):
    rows = []
    for b in np.linspace(0.02, math.pi - 0.02, m):
        row = []
        for a in (2 * math.pi * k / n for k in range(n)):
            s = 1 + (wob(a, b) if wob else 0)
            row.append(center + Vector((rx * math.sin(b) * math.cos(a) * s, ry * math.sin(b) * math.sin(a) * s,
                                        rz * math.cos(b))))
        rows.append(row)
    return rows


def ring_pts(c, axis, r, n=24):
    axis = axis.normalized()
    u = axis.cross(Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))).normalized()
    v = axis.cross(u)
    return [c + (u * math.cos(a) + v * math.sin(a)) * r for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]


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


def ring_r(z, n, bvh=BVH_TORSO):
    r = np.full(n, np.nan)
    for k in range(n):
        d = dirv(2 * math.pi * k / n)
        o = Vector((0, 0, z)) + d * 0.6
        hit = bvh.ray_cast(o, -d, 0.6)[0]
        if hit:
            r[k] = (hit - Vector((0, 0, z))).length
    ok = ~np.isnan(r)
    r = np.interp(np.arange(n), np.arange(n)[ok], r[ok], period=n)
    s = np.mean([np.roll(r, j) for j in range(-3, 4)], axis=0)
    return np.maximum(r, s)


def at(th, r, z):
    return dirv(th) * r + Vector((0, 0, z))


def front_hit(x, z):
    return BVH_ALL.ray_cast(Vector((x, -0.6, z)), Vector((0, 1, 0)), 1.0)


def smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def smax(a, b, k):
    return -smin(-a, -b, k)


def neck_cone(p, rc, zc=1.285):
    """> 0 outside a 45 degree cone round the neck. A vertical cylinder grazes the neck and a level cut grazes
    the shoulder top; both frayed the cut edge into shards. The cone crosses the neck-shoulder curve squarely,
    and it also keeps the head out."""
    x, y, z = p.T
    return (np.hypot(x, y - 0.025) - rc - (z - zc)) * 0.7071


def v_neck(p, half_width, rc):
    """> 0 on the cloth: V opening in front, round the neck behind, with the corner where they meet rounded off."""
    x, y, z = p.T
    opening = smax(np.abs(x) - half_width(z), y, 0.012)
    return smin(opening, neck_cone(p, rc), 0.02)


# ---------- inner top: white, sleeveless ----------
def uv_torso(top, bot):
    return lambda p: (math.degrees(math.atan2(abs(p.x), -(p.y + 0.02))) / 180, (top - p.z) / (top - bot))


def f_inner(p):
    x, y, z = p.T
    return np.minimum.reduce([z - 0.975, 0.152 - np.abs(x), neck_cone(p, 0.040)])


shell("SW_InnerTop", f_inner, 0.005, "top", uv_torso(1.335, 0.975), relax=8)


# ---------- kimono-cut top: ice white, V neck ----------
def vw(z):
    return np.maximum(z - 1.075, 0) * 0.42


def f_top(p):
    x, y, z = p.T
    return np.minimum.reduce([z - 0.99, 0.160 - np.abs(x), v_neck(p, vw, 0.050)])  # hem stays under the obi


TOP_OB = shell("SW_Top", f_top, 0.012, "top", uv_torso(1.335, 0.975), relax=8)


def rim_strip(name, src, keep, width, lift, tile, wrap=0.002, rows=4, step=0.004):
    """Band lying on src along its open edge (the part where keep(p) holds). Built from the edge itself, so it
    follows the cut exactly instead of guessing the opening from the body and twisting where the guesses meet."""
    me = src.data
    V = np.array([src.matrix_world @ v.co for v in me.vertices])
    polys = [list(pl.vertices) for pl in me.polygons]
    cnt = {}
    for vs in polys:
        for a, b in zip(vs, vs[1:] + vs[:1]):
            k = (min(a, b), max(a, b))
            cnt[k] = cnt.get(k, 0) + 1
    adj = {}
    for (a, b), c in cnt.items():
        if c == 1 and keep(V[a]) and keep(V[b]):
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
    seen, chains = set(), []
    for s in sorted(adj, key=lambda v: len(adj[v]) != 1):  # chain ends first
        if s in seen:
            continue
        ch, cur = [s], s
        seen.add(s)
        while True:
            nxt = [v for v in adj[cur] if v not in seen]
            if not nxt:
                break
            cur = nxt[0]
            ch.append(cur)
            seen.add(cur)
        chains.append(ch)

    def length(c):
        return float(np.linalg.norm(np.diff(V[c], axis=0), axis=1).sum())
    ch = max(chains, key=length)
    if len(ch) > 3 and ch[0] in adj[ch[-1]]:  # closed loop (e.g. round a limb)
        ch = ch + [ch[0]]
    C = V[ch]
    seg = np.r_[0, np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))]
    n = max(8, int(seg[-1] / step))
    C = np.stack([np.interp(np.linspace(0, seg[-1], n), seg, C[:, i]) for i in range(3)], axis=1)
    for _ in range(8):
        C[1:-1] = C[1:-1] * 0.5 + (C[:-2] + C[2:]) * 0.25
    bvh = BVHTree.FromPolygons([Vector(p) for p in V], polys)

    def proj(p):
        loc, nr, _, _ = bvh.find_nearest(Vector(p))
        if nr.dot(loc - BVH_ALL.find_nearest(loc)[0]) < 0:
            nr = -nr
        return loc, nr
    base = [proj(p) for p in C]
    D = [nr.cross(Vector(t)).normalized() for (loc, nr), t in zip(base, np.gradient(C, axis=0))]
    # the cloth side projects back onto itself; the hole side lands on the edge
    votes = 0
    for (loc, nr), d in zip(base, D):
        a, b = loc + d * 0.006, loc - d * 0.006
        votes += 1 if (proj(a)[0] - a).length < (proj(b)[0] - b).length else -1
    D = [d * (1 if votes >= 0 else -1) for d in D]
    for _ in range(4):
        D = [D[0]] + [(D[i - 1] + D[i] * 2 + D[i + 1]).normalized() for i in range(1, len(D) - 1)] + [D[-1]]
    out = []
    for j in range(rows):
        off = -wrap + (width + wrap) * j / (rows - 1)
        h = lift * (0.55 + 0.45 * math.sin(math.pi * j / (rows - 1)))  # slightly rounded piping
        row = []
        for (loc, nr), d in zip(base, D):
            p, m = loc + d * min(off, 0), nr
            for _ in range(3 if off > 0 else 0):
                p, m = proj(p + d * (off / 3))
            row.append(p + m * h)
        out.append(row)
    print("RIM", name, "chains", len(chains), "points", n, "length", round(seg[-1], 3),
          "ends", [tuple(round(float(c), 3) for c in C[i]) for i in (0, -1)], "votes", votes)
    return grid(name, out, tile, skin, closed=False, uvf=lambda i, k: (k / (n - 1), i / (rows - 1)))


rim_strip("SW_Collar", TOP_OB, lambda p: p[2] > 1.10 and abs(p[0]) < 0.15, 0.024, 0.003, "trim_white")


# ---------- scale vest over the top, wide V, gold edge ----------
def vvw(z):
    return 0.010 + np.maximum(z - 1.12, 0) * 0.58


def f_vest(p):
    x, y, z = p.T
    return np.minimum.reduce([z - 0.972, 0.176 - np.abs(x), v_neck(p, vvw, 0.078)])


VEST_OB = shell("SW_Vest", f_vest, 0.024, "vest", uv_torso(1.318, 0.972), relax=8, hide=False)
rim_strip("SW_VestTrim", VEST_OB, lambda p: p[2] > 1.0 and abs(p[0]) < 0.16, 0.014, 0.003, "gold")

# ---------- obi sash with a cyan cord, knots front and back ----------
NB = 72
OZ = np.linspace(1.08, 0.962, 6)
rings = np.array([ring_r(z, NB) for z in OZ])
RO = rings.max(axis=0) + 0.030
rows = [[at(2 * math.pi * k / NB, RO[k] + 0.002 * math.sin(i), z) for k in range(NB)] for i, z in enumerate(OZ)]
grid("SW_Obi", rows, "obi", skin)
cord = [at(2 * math.pi * k / NB, RO[k] + 0.0115, 1.020 + 0.004 * math.sin(2 * math.pi * k / NB)) for k in range(NB)]
grid("SW_ObiCord", tube(cord, lambda i, a: 0.0055, 6, closed=True), "cord", skin)


def knot(tag, th, tails):
    kc = at(th, RO[int(th / (2 * math.pi) * NB) % NB] + 0.040, 1.025)  # clear of the cord (RO + 0.017)
    out = dirv(th)
    side = Vector((math.cos(th), math.sin(th), 0))
    grid(f"SW_Knot{tag}", blob(kc, 0.028, 0.022, 0.032), "obi", skin)
    for s in (1, -1):
        grid(f"SW_Bow{tag}{s:+d}", blob(kc + side * (s * 0.058) - out * 0.006, 0.046, 0.016, 0.036,
                                        wob=lambda a, b: 0.12 * math.cos(2 * a)), "obi", skin)
    for j, (dx, L, swing) in enumerate(tails):
        pts = [kc + side * (dx + swing * t) + out * (0.03 + 0.07 * t) + Vector((0, 0, -0.03 - L * t))
               for t in np.linspace(0, 1, 12)]
        bones = chain(f"Tail{tag}{j}", [pts[0], pts[4], pts[8], pts[11]], HIPS)
        rows = [[p + side * (sx * 0.024) for p in pts] for sx in (-1, 1)]
        grid(f"SW_Tail{tag}{j}", rows, "obi", lambda i, k, p, b=bones: cloth([(b, 1.0)], k / 11, HIPS, 0.1),
             closed=False, uvf=lambda i, k: (i, k / 11))


knot("Back", math.pi, ((0.018, 0.20, 0.02), (-0.018, 0.17, -0.02)))
knot("Front", 0.0, ((0.016, 0.30, 0.01), (-0.020, 0.24, -0.03)))

# ---------- short pleated skirt (pale blue, white cloud hem) ----------
NS, SK = 96, 12
Z0, ZH = 0.985, 0.66
zsk = np.linspace(Z0, ZH, 18)
R = None
radii = []
for z in zsk:
    r = ring_r(max(z, 0.80), NS) + 0.016
    R = r if R is None else np.maximum(R, r)
    radii.append(R + max(0.0, 0.80 - z) * 0.30)
RAD = np.array(radii)  # [z index, angle index]


def rsk(th, z):
    """Skirt radius at angle th and height z, extended as a gentle cone below its hem."""
    k = (th % (2 * math.pi)) / (2 * math.pi) * NS
    k0 = int(k) % NS
    t = k - int(k)
    col = RAD[:, k0] * (1 - t) + RAD[:, (k0 + 1) % NS] * t
    if z >= ZH:
        return float(np.interp(z, zsk[::-1], col[::-1]))
    return float(col[-1]) + (ZH - z) * 0.16


def tri_wave(t):
    return 2 * abs((t % 1) - 0.5) * 2 - 1


rows = []
for z, rr in zip(zsk, radii):
    amp = 0.002 + 0.010 * (Z0 - z) / (Z0 - ZH)
    rows.append([at(2 * math.pi * k / NS, rr[k] + amp * tri_wave(k / 4), z) for k in range(NS)])
sk = []
for c in range(SK):
    th = 2 * math.pi * c / SK
    sk.append(chain(f"Skirt{c:02d}", [at(th, rsk(th, z), z) for z in (0.93, 0.85, 0.75, 0.66)], HIPS))


def skirt_at(th, z):
    c = (th % (2 * math.pi)) / (2 * math.pi) * SK
    a = int(c) % SK
    t = c - int(c)
    return cloth([(sk[a], 1 - t), (sk[(a + 1) % SK], t)], (0.93 - z) / 0.27, HIPS, 0.15)


grid("SW_Skirt", rows, "skirt", lambda i, k, p: skirt_at(2 * math.pi * k / NS, zsk[i]))

# ---------- front tassets: scale panels over the skirt ----------
for s in (1, -1):
    rows = []
    zt = np.linspace(0.975, 0.70, 12)
    for z in zt:
        rows.append([at(math.radians(s * c), rsk(math.radians(s * c), max(z, ZH)) + 0.016 + 0.05 * (0.975 - z), z)
                     for c in np.linspace(6, 40, 9)])
    grid(f"SW_Tasset{'L' if s > 0 else 'R'}", rows, "plate",
         lambda i, k, p, s=s: skirt_at(math.atan2(p.x, -p.y), p.z), closed=False,
         uvf=lambda i, k: (k / 8, i / 11))

# ---------- long over-robe, open at the front, ankle length at the back ----------
NR, RC, NCH = 64, 24, 12


def hem(th):
    d = abs(math.degrees(math.atan2(math.sin(th), math.cos(th))))
    return float(np.interp(d, [40, 90, 140, 180], [0.36, 0.22, 0.11, 0.08]))


def robe_p(c, s):
    """c in 0..1 across the robe (left front edge to right front edge), s in 0..1 from waist to hem."""
    oa = math.radians(44 + 20 * s ** 1.5)
    th = oa + (2 * math.pi - 2 * oa) * c
    z = 0.985 - s * (0.985 - hem(th))
    r = max(rsk(th, z) + 0.034, float(RO[int(th / (2 * math.pi) * NB) % NB]) - 0.004 if z > 0.95 else 0)
    r += 0.03 * s + 0.010 * s * math.sin(c * 40)
    return at(th, r, z)


rows = [[robe_p(c, s) for c in np.linspace(0, 1, NR)] for s in np.linspace(0, 1, RC)]
rc = [chain(f"Robe{j:02d}", [robe_p(c, s) for s in (0.08, 0.3, 0.52, 0.76, 1.0)], HIPS)
      for j, c in enumerate(np.linspace(0, 1, NCH))]


def robe_w(i, k, p):
    x = k / (NR - 1) * (NCH - 1)
    a = min(int(x), NCH - 2)
    t = x - a
    return cloth([(rc[a], 1 - t), (rc[a + 1], t)], i / (RC - 1), HIPS, 0.1)


grid("SW_Robe", rows, "robe", robe_w, closed=False,
     uvf=lambda i, k: (abs((k / (NR - 1) * 3) % 2 - 1), i / (RC - 1)))

# ---------- short bell sleeves to the elbow: pale blue outside, navy lining, gold cuff ----------
# (owner's call: short open sleeves over a fitted dark undersleeve, armoured forearms)
SL_X0, SL_X1 = 0.168, 0.375


def sleeve_ring(x, s, inset=0.0):
    t = (x - SL_X0) / (SL_X1 - SL_X0)
    rt = 0.050 + 0.024 * t ** 1.5 - inset
    ry = 0.052 + 0.040 * t ** 1.5 - inset
    rb = 0.050 + 0.085 * t ** 1.3 - inset
    row = []
    for a in (2 * math.pi * k / 36 for k in range(36)):
        ca, sa = math.cos(a), math.sin(a)
        z = 1.26 + (ca * rt if ca >= 0 else -rb * abs(ca) ** 0.45)
        y = 0.025 + sa * ry * (1 + 0.2 * max(0, -ca) * t)
        row.append(Vector((s * (x + 0.03 * t * max(0, -ca)), y, z)))
    return row


for s, tag in ((1, "L"), (-1, "R")):
    up, low = f"J_Bip_{tag}_UpperArm", f"J_Bip_{tag}_LowerArm"
    xs = np.linspace(SL_X0, SL_X1, 16)
    sb = chain(f"Sleeve{tag}", [Vector((s * 0.33, 0.025, 1.205)), Vector((s * 0.345, 0.025, 1.18)),
                               Vector((s * 0.36, 0.025, 1.15)), Vector((s * 0.37, 0.025, 1.125))], up)

    def sleeve_w(i, k, p, up=up, low=low, sb=sb):
        t = min(max((abs(p.x) - 0.33) / 0.07, 0), 1)
        base = {up: 1 - t, low: t} if 0 < t < 1 else ({low: 1.0} if t >= 1 else {up: 1.0})
        m = min(max((1.215 - p.z) / 0.05, 0), 1) * min(max((abs(p.x) - 0.24) / 0.08, 0), 1)
        if m <= 0:
            return base
        out = {b: x * (1 - m) for b, x in base.items()}
        for b, x in along(sb, min(max((1.215 - p.z) / 0.09, 0), 1)).items():
            out[b] = out.get(b, 0) + x * m
        return out

    rows = [sleeve_ring(x, s) for x in xs]
    grid(f"SW_Sleeve_{tag}", rows, "robe", sleeve_w,
         uvf=lambda i, k, rows=rows: ((abs(rows[i][k].x) - SL_X0) / 0.21,
                                      min(0.97, max(0.0, (1.338 - rows[i][k].z) / 0.25))))
    # navy lining just inside, stopping short of the cuff so the gold trim covers its edge
    lin_rows = [sleeve_ring(x, s, 0.007) for x in np.linspace(0.20, SL_X1 - 0.003, 13)]
    grid(f"SW_SleeveLining_{tag}", lin_rows, "glove", sleeve_w,
         uvf=lambda i, k: (k / 36, 0.5))
    # gold cuff: outside band, over the edge, a little way inside
    end, prev = rows[-1], rows[-2]
    trim = [[], [], []]
    for pe, pp in zip(end, prev):
        d = (pe - pp).normalized()
        r = Vector((0, pe.y - 0.025, pe.z - 1.26)).normalized()
        trim[0].append(pe - d * 0.014 + r * 0.0025)
        trim[1].append(pe + d * 0.002 + r * 0.0005)
        trim[2].append(pe - d * 0.010 - r * 0.0035)
    grid(f"SW_SleeveTrim_{tag}", trim, "gold", sleeve_w)

# fitted navy undersleeve on the upper arm, armoured forearm guard from elbow to glove
shell("SW_UnderSleeve", lambda p: np.minimum.reduce([np.abs(p[:, 0]) - 0.172, 0.392 - np.abs(p[:, 0]), p[:, 2] - 1.10]),
      0.004, "glove", lambda p: (abs(math.atan2(p.z - 1.26, p.y - 0.025)) / math.pi, 0.5))
VAMB = shell("SW_Vambrace", lambda p: np.minimum.reduce([np.abs(p[:, 0]) - 0.392, 0.482 - np.abs(p[:, 0]),
                                                        p[:, 2] - 1.10]),
             0.009, "plate", lambda p: (abs(math.atan2(p.z - 1.26, p.y - 0.025)) / math.pi, (abs(p.x) - 0.392) / 0.09),
             relax=2)
for s, tag in ((1, "L"), (-1, "R")):
    rim_strip(f"SW_VambraceRimA_{tag}", VAMB, lambda p, s=s: s * p[0] > 0 and abs(p[0]) < 0.42, 0.007, 0.002, "gold")
    rim_strip(f"SW_VambraceRimB_{tag}", VAMB, lambda p, s=s: s * p[0] > 0 and abs(p[0]) > 0.45, 0.007, 0.002, "gold")


# ---------- fingerless gloves ----------
shell("SW_Gloves", lambda p: np.minimum.reduce([np.abs(p[:, 0]) - 0.470, 0.588 - np.abs(p[:, 0]), p[:, 2] - 1.10]),
      0.004, "glove", lambda p: (abs(math.atan2(p.z - 1.26, p.y - 0.025)) / math.pi, (abs(p.x) - 0.47) / 0.118))


# ---------- knee-high boots, black with gold filigree ----------
def leg_uv(p, top, bot=0.0):
    a = math.atan2(abs(p.x) - 0.077, -(p.y - 0.03))
    return abs(a) / math.pi, (top - p.z) / (top - bot)


def uv_boot(p):
    toe = min(max((0.08 - p.z) / 0.05, 0), 1) * min(max((0.0 - p.y) / 0.08, 0), 1)
    return leg_uv(p, 0.475)[0], (0.475 - p.z) / 0.475 * 0.92 + 0.06 * toe


shell("SW_Boots", lambda p: 0.475 - p[:, 2], 0.012, "boot", uv_boot, relax=2, floor=True)
for s in (1, -1):
    rim = [Vector((s * 0.077, 0.03, 0.475)) + Vector((math.sin(a) * rx, -math.cos(a) * ry, 0.012 * math.cos(a)))
           for a, rx, ry in ((a, 0.060, 0.062) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False))]
    hits = []
    for p in rim:
        loc, nr, _, _ = BVH_ALL.find_nearest(p)
        hits.append(loc + nr * 0.016)
    grid(f"SW_BootRim{'L' if s > 0 else 'R'}", tube(hits, lambda i, a: 0.005, 6, closed=True), "gold", skin)

# ---------- scabbard holder on the left hip ----------
hip = at(math.radians(95), float(RO[int(95 / 360 * NB)]) + 0.022, 0.985)
d = Vector((0.10, 0.85, -0.52)).normalized()
for j, t in enumerate((-0.045, 0.06)):
    c = hip + d * t + Vector((0.018, 0, -0.01))
    grid(f"SW_Holder{j}", tube(ring_pts(c, d, 0.024, 20), lambda i, a: 0.0055, 6, closed=True), "boot", skin)
strap = [hip + Vector((0, -0.05, 0.03)), hip + Vector((0.006, -0.02, 0.0)), hip + Vector((0.012, 0.03, -0.03)),
         hip + Vector((0.016, 0.07, -0.05))]
grid("SW_HolderStrap", [[p + Vector((0, 0, dz)) for p in strap] for dz in (-0.012, 0.012)], "boot", skin,
     closed=False, uvf=lambda i, k: (k / 3, i))

# ---------- jade bi pendant with an orange tassel, hanging at the front right ----------
th = math.radians(-52)  # clear of the Tripo obi medallion (scripts/06_tripo.py)
out = dirv(th)
side = Vector((math.cos(th), math.sin(th), 0))
top = at(th, float(RO[int((th % (2 * math.pi)) / (2 * math.pi) * NB)]) + 0.012, 0.962)
dc = top + out * 0.020 + Vector((0, 0, -0.075))
pb = chain("Pendant", [top, dc + Vector((0, 0, 0.03)), dc + Vector((0, 0, -0.04)), dc + Vector((0, 0, -0.15))], HIPS)


def pend_w(i, k, p):
    return cloth([(pb, 1.0)], min(max((top.z - p.z) / 0.23, 0), 1), HIPS, 0.05)


grid("SW_PendantCord", tube([top.lerp(dc + Vector((0, 0, 0.028)), t) + out * (0.006 * math.sin(t * math.pi))
                             for t in np.linspace(0, 1, 6)], lambda i, a: 0.0025, 6), "cord", pend_w)
rows = []
for f in np.linspace(0, 2 * math.pi, 29):
    radial = side * math.cos(f) + Vector((0, 0, math.sin(f)))
    rows.append([dc + radial * (0.0185 + 0.0095 * math.cos(q)) + out * (0.0045 * math.sin(q))
                 for q in np.linspace(0, 2 * math.pi, 12, endpoint=False)])
grid("SW_Jade", rows, "jade", pend_w)
grid("SW_JadeCap", blob(dc + Vector((0, 0, 0.030)), 0.008, 0.008, 0.007, n=10, m=6), "gold", pend_w)
grid("SW_TasselCap", blob(dc + Vector((0, 0, -0.033)), 0.007, 0.007, 0.008, n=10, m=6), "gold", pend_w)
grid("SW_Tassel", blob(dc + Vector((0, 0, -0.085)), 0.013, 0.013, 0.052, n=12, m=9,
                       wob=lambda a, b: 0.10 * math.cos(6 * a) * (b / math.pi)), "obi", pend_w)

# ---------- topknot bun at the crown, hairpins, red flowers, gold dangles ----------
hb = bmesh.new()
hb.from_mesh(hair.data)
hb.transform(hair.matrix_world)
HBVH = BVHTree.FromBMesh(hb)
hb.free()
crown = None
for y in (0.05, 0.04, 0.06, 0.03, 0.07):
    hit = HBVH.ray_cast(Vector((0, y, 2.0)), Vector((0, 0, -1)), 1.0)[0]
    if hit:
        crown = hit
        break
bun = crown + Vector((0, 0.008, 0.030))
grid("SW_Bun", blob(bun, 0.048, 0.044, 0.036, n=24, m=12,
                    wob=lambda a, b: 0.07 * math.sin(3 * a + 4 * b)), "hair", rigid(HEAD))
grid("SW_BunTop", blob(bun + Vector((0, 0.004, 0.026)), 0.028, 0.026, 0.020, n=18, m=9,
                       wob=lambda a, b: 0.08 * math.sin(4 * a - 3 * b)), "hair", rigid(HEAD))
band = [bun + Vector((math.cos(a) * 0.040, math.sin(a) * 0.037, -0.026)) for a in np.linspace(0, 2 * math.pi, 28, endpoint=False)]
grid("SW_BunBand", tube(band, lambda i, a: 0.006, 6, closed=True), "gold", rigid(HEAD))
for nm, a0, a1 in (("PinA", Vector((-0.085, 0.020, -0.008)), Vector((0.095, -0.010, 0.030))),
                   ("PinB", Vector((-0.080, -0.015, 0.025)), Vector((0.090, 0.025, -0.010)))):
    pts = [bun + a0.lerp(a1, t) for t in np.linspace(0, 1, 10)]
    grid(f"SW_{nm}", tube(pts, lambda i, a: 0.0035 if 0 < i < 9 else 0.0015, 6), "gold", rigid(HEAD))
    grid(f"SW_{nm}Knob", blob(bun + a1, 0.008, 0.008, 0.008, n=10, m=6), "gold", rigid(HEAD))


def card(name, c, n, size, rot=0.0):
    n = n.normalized()
    u = n.cross(Vector((0, 0, 1))).normalized()
    v = u.cross(n)
    m = Matrix.Rotation(rot, 3, n)
    u, v = m @ u, m @ v
    rows = [[c + (u * (x - 0.5) + v * (0.5 - y)) * size for x in (0, 1)] for y in (0, 1)]
    return grid(name, rows, "flower", rigid(HEAD), closed=False, uvf=lambda i, k: (k, i))


flowers = [(Vector((0.060, -0.004, 0.006)), Vector((1, -0.35, 0.25)), 0.052, 0.3),
           (Vector((0.052, 0.034, -0.016)), Vector((0.9, 0.3, 0.1)), 0.042, 1.1),
           (Vector((0.040, -0.026, 0.034)), Vector((0.7, -0.6, 0.5)), 0.036, 2.0),
           (Vector((-0.058, -0.006, 0.012)), Vector((-1, -0.3, 0.25)), 0.044, 0.7)]
for j, (o, n, sz, rot) in enumerate(flowers):
    card(f"SW_Flower{j}", bun + o + n.normalized() * 0.004, n, sz, rot)
    card(f"SW_FlowerB{j}", bun + o - n.normalized() * 0.001, -n, sz, -rot)
for j, (dx, dy, L) in enumerate(((0.072, -0.012, 0.085), (0.070, 0.006, 0.105), (0.066, 0.024, 0.075))):
    top = bun + Vector((dx, dy, -0.010))
    for q in range(int(L / 0.014)):
        grid(f"SW_Bead{j}_{q}", blob(top + Vector((0.002 * q, 0, -0.014 * q)), 0.0042, 0.0042, 0.0050, n=8, m=5),
             "gold", rigid(HEAD))
    tip = top + Vector((0.002 * int(L / 0.014), 0, -0.014 * int(L / 0.014) - 0.004))
    grid(f"SW_Tassel{j}", blob(tip, 0.009, 0.004, 0.013, n=10, m=7,
                               wob=lambda a, b: 0.15 * math.cos(2 * a)), "gold", rigid(HEAD))

# ---------- green eyes: hue-shift the VRoid iris texture ----------
iris = bpy.data.materials["N00_000_00_EyeIris_00_EYE (Instance)"]
src = iris.node_tree.nodes["Image Texture"].image
if not src.get("sw_green"):
    a = np.array(src.pixels[:], dtype=np.float32).reshape(-1, 4)
    rgb = a[:, :3]
    mx, mn = rgb.max(1), rgb.min(1)
    dl = mx - mn + 1e-6
    h = np.where(mx == rgb[:, 0], ((rgb[:, 1] - rgb[:, 2]) / dl) % 6,
                 np.where(mx == rgb[:, 1], (rgb[:, 2] - rgb[:, 0]) / dl + 2, (rgb[:, 0] - rgb[:, 1]) / dl + 4)) / 6
    sat = np.where(mx > 0, dl / (mx + 1e-6), 0)
    h = np.where(sat > 0.08, 0.40 + (h - 0.62) * 0.4, h) % 1.0
    sat = np.where(sat > 0.08, np.clip(sat * 1.05, 0, 1), sat)
    i6 = np.floor(h * 6).astype(int) % 6
    f6 = h * 6 - np.floor(h * 6)
    p_ = mx * (1 - sat)
    q_ = mx * (1 - f6 * sat)
    t_ = mx * (1 - (1 - f6) * sat)
    sel = [(p_ * 0 + mx, t_, p_), (q_, mx, p_), (p_, mx, t_), (p_, q_, mx), (t_, p_, mx), (mx, p_, q_)]
    out = np.zeros_like(rgb)
    for k in range(6):
        m = i6 == k
        for ch in range(3):
            out[m, ch] = sel[k][ch][m]
    a[:, :3] = out
    green = bpy.data.images.new("iris_green", src.size[0], src.size[1], alpha=True)
    green.pixels.foreach_set(a.ravel())
    green.filepath_raw = os.path.join(TEX, "iris_green.png")
    green.file_format = "PNG"
    green.save()
    green["sw_green"] = 1
    iris.node_tree.nodes["Image Texture"].image = green
    iris.node_tree.nodes["Image Texture.001"].image = green

# ---------- bones ----------
bpy.context.view_layer.objects.active = arm
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
for b in [b for b in eb if "J_Sec_Cloth" in b.name]:
    eb.remove(b)
for C in CHAINS.values():
    parent = eb[C["parent"]]
    for i, name in enumerate(C["pts"][:-1]):
        b = eb.new(C["bones"][i])
        b.head, b.tail = C["pts"][i], C["pts"][i + 1]
        b.parent, b.use_connect = parent, i > 0
        parent = b
bpy.ops.object.mode_set(mode="OBJECT")

# ---------- hide skin under the clothes (keeps the body mesh itself intact) ----------
gr = body.vertex_groups.get("Outfit_Hidden") or body.vertex_groups.new(name="Outfit_Hidden")
gr.remove(list(range(len(P))))
gr.add(np.nonzero(HIDDEN)[0].tolist(), 1.0, "REPLACE")
mask = body.modifiers.get("Outfit_Mask") or body.modifiers.new("Outfit_Mask", "MASK")
mask.vertex_group = "Outfit_Hidden"
mask.invert_vertex_group = True
mask.threshold = 0.5
while body.modifiers[0] != mask:
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = body
    bpy.ops.object.modifier_move_up(modifier=mask.name)

with open(os.path.join(ROOT, "cloth_chains.json"), "w") as fh:
    json.dump({k: dict(bones=v["bones"], parent=v["parent"]) for k, v in CHAINS.items()}, fh, indent=1)
print("OUTFIT objects", len(col.objects), "verts", sum(len(o.data.vertices) for o in col.objects),
      "chains", len(CHAINS), "hidden", int(HIDDEN.sum()), "crown", tuple(round(x, 3) for x in crown))
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "sw_outfit.blend"))

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import sw_render
print("SHEET", sw_render.sheet("outfit_v3b"))
print("SHEET", sw_render.sheet("outfit_v3b_head", target=(0, 0.02, 1.40), scale=0.55, res=520,
                               views=("front", "left", "back", "q34")))
