# Fits the Tripo props (tripo/*_lo.blend from 05_tripo_probe.py) onto the outfit from 04_outfit.py and resolves
# the intersections so nothing pokes through in the rest pose:
#  - placement is measured against the real surfaces (ray casts / nearest points) instead of guessed;
#  - rigid pieces (pauldrons, medallion disc, pendant, scabbard, sword) move clear as a whole, soft parts (bow
#    wings, knot tails, pauldron lames, straps) bend, and cloth / hair is pushed over or under the props;
#  - the sheathed sword keeps only the hilt; the blade would sit inside the scabbard (the full sword stays in
#    tripo/E_sword_lo.blend for the game's weapon actor).
# Knee guards, bracers and earrings are not used: the reference (images/12.png) has none of them.
# Saves sw_outfit_v4.blend and renders/fit_log.txt. Check with 07_check.py, close-ups with 08_review.py.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, math, os, sys, importlib
import numpy as np
from mathutils import Vector, Matrix
from mathutils.kdtree import KDTree
from mathutils.bvhtree import BVHTree

ROOT = os.path.join(ANIME_GAME_ROOT, r"swordswoman")
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import fitlib
importlib.reload(fitlib)
from fitlib import (Surf, Multi, verts, set_verts, xform, rigid_clear, soft_push, trim_inside, frame_rot,
                    mirror_plane, drop)

TDIR = os.path.join(ROOT, "tripo")
TEXO = os.path.join(ROOT, "textures", "tripo")
os.makedirs(TEXO, exist_ok=True)
arm = bpy.data.objects["Armature"]
body = bpy.data.objects["Body"]
hair = bpy.data.objects["Hair"]
col = bpy.data.collections["Outfit"]
BONES = {b.name for b in arm.data.bones}
HIPS, HEAD = "J_Bip_C_Hips", "J_Bip_C_Head"
MAT = bpy.data.materials["SW_Outfit_MToon"]
TILES = ["vest", "top", "robe", "skirt", "trim_navy", "trim_gold", "obi", "trim_white",
         "boot", "glove", "gold", "flower", "hair", "plate", "jade", "cord"]
LOG = []


def log(*a):
    LOG.append(" ".join(str(x) for x in a))
    print("FIT", *a)


def ob(n):
    return bpy.data.objects[n]


def tuv(tile, u, v):
    n = TILES.index(tile)
    return ((n % 4 + 0.01 + 0.98 * min(max(u, 0), 1)) / 4, (n // 4 + 0.01 + 0.98 * (1 - min(max(v, 0), 1))) / 4)


def dirv(th):
    return Vector((math.sin(th), -math.cos(th), 0))


def load(sheet, idx):
    path = os.path.join(TDIR, sheet + "_lo.blend")
    names = ["%s_%02d" % (sheet, i) for i in idx]
    with bpy.data.libraries.load(path) as (src, dst):
        dst.objects = names
    for o in dst.objects:
        col.objects.link(o)
        o.matrix_world = Matrix()
    return dst.objects


def box(o):
    v = verts(o)
    return v.min(0), v.max(0)


def fit(o, axis, size, anchor, at):
    """Uniform scale so bbox side `axis` = size, then bbox point `anchor` (0..1 per axis) -> `at`."""
    lo, hi = box(o)
    s = size / (hi - lo)[axis]
    a = lo * s + (hi - lo) * s * np.array(anchor)
    xform(o, Matrix.Translation(Vector(at) - Vector(a)) @ Matrix.Scale(s, 4))
    return s


def about(o, c, M3):
    xform(o, Matrix.Translation(c) @ M3.to_4x4() @ Matrix.Translation(-Vector(c)))


def clean(w):
    top = sorted(((b, x) for b, x in w.items() if b in BONES and x > 0.001), key=lambda kv: -kv[1])[:4]
    t = sum(x for _, x in top) or 1
    return {b: x / t for b, x in top}


def bind(o, wfun, name):
    o.name = name
    o.data.name = name
    o.parent = arm
    o.matrix_parent_inverse = Matrix()
    for m in list(o.modifiers):
        o.modifiers.remove(m)
    o.modifiers.new("Armature", "ARMATURE").object = arm
    o.vertex_groups.clear()
    groups = {}
    for v in o.data.vertices:
        for b, x in clean(wfun(Vector(v.co))).items():
            g = groups.get(b) or o.vertex_groups.new(name=b)
            groups[b] = g
            g.add([v.index], x, "REPLACE")
    for p in o.data.polygons:
        p.use_smooth = True
    return o


def rigid(bone):
    return lambda p: {bone: 1.0}


def weights_of(objs):
    pts, ws = [], []
    for o in objs:
        gn = {g.index: g.name for g in o.vertex_groups}
        for v in o.data.vertices:
            pts.append(o.matrix_world @ v.co)
            ws.append({gn[e.group]: e.weight for e in v.groups})
    kd = KDTree(len(pts))
    for i, p in enumerate(pts):
        kd.insert(p, i)
    kd.balance()
    return lambda p: dict(ws[kd.find(p)[1]])


def remove(names):
    for n in names:
        o = bpy.data.objects.get(n)
        if o:
            bpy.data.objects.remove(o, do_unlink=True)


def delete_verts(o, sel):
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in np.nonzero(sel)[0]], context="VERTS")
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def add_mesh(name, V, F, UV, tile):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in V], [], F)
    lay = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            lay.data[li].uv = tuv(tile, *UV[me.loops[li].vertex_index])
    me.materials.append(MAT)
    me.update()
    o = bpy.data.objects.new(name, me)
    col.objects.link(o)
    return o


def strap(name, pts, wdir, width=0.014, thick=0.004, tile="boot"):
    """Flat leather strap along pts (closed box section); wdir gives the width direction."""
    V, UV, F = [], [], []
    n_ = len(pts)
    for i, p in enumerate(pts):
        t = (Vector(pts[min(i + 1, n_ - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        s = (Vector(wdir) - t * t.dot(Vector(wdir))).normalized()
        n = t.cross(s)
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            V.append(Vector(p) + s * (a * width / 2) + n * (b * thick / 2))
            UV.append(((a + 1) / 2, i / (n_ - 1)))
    for i in range(n_ - 1):
        for k in range(4):
            F.append([i * 4 + k, i * 4 + (k + 1) % 4, (i + 1) * 4 + (k + 1) % 4, (i + 1) * 4 + k])
    F.append([3, 2, 1, 0])
    m = (n_ - 1) * 4
    F.append([m, m + 1, m + 2, m + 3])
    return add_mesh(name, V, F, UV, tile)


# ---------- surfaces ----------
BODYR = Surf([body], raw=True)  # whole body, ignores Outfit_Mask
BODYW = weights_of([body])


def cloth(*names):
    """One Surf per cloth layer (normals away from the body); Multi reports the deepest violation."""
    return Multi(*[Surf([ob(n)], away_from=BODYR) for n in names if bpy.data.objects.get(n)])


def closed(*objs):
    return Multi(*[Surf([o]) for o in objs])


def flat(s):
    return sum((flat(x) for x in s.surfs), []) if isinstance(s, Multi) else [s]


def blame(tag, o, surf, maxd=0.06, mask=None):
    """Logs, per surface, how deep the object's vertices sit inside it (to see what drives a push)."""
    P = verts(o) if mask is None else verts(o)[mask]
    P = P[::max(1, len(P) // 1500)]
    out = []
    for s in flat(surf):
        w = 0.0
        for p in P:
            r = s.sd(Vector(p), maxd)
            if r is not None:
                w = min(w, r[0])
        if w < -0.001:
            out.append((s.objs[0], round(w, 4)))
    log("blame", tag, out)


# ---------- placeholders out (weights of the ones that carry cloth-chain bones are kept) ----------
front_old = [ob(n) for n in ("SW_KnotFront", "SW_BowFront+1", "SW_BowFront-1", "SW_TailFront0", "SW_TailFront1")]
KNOT_W = weights_of(front_old)
lo_c, hi_c = box(ob("SW_PendantCord"))
PEND_TOP_OLD = Vector(((lo_c[0] + hi_c[0]) / 2, (lo_c[1] + hi_c[1]) / 2, hi_c[2]))
pend_old = [ob(n) for n in ("SW_PendantCord", "SW_Jade", "SW_JadeCap", "SW_TasselCap", "SW_Tassel")]
PEND_W = weights_of(pend_old)
remove([o.name for o in front_old + pend_old])
remove(["SW_Holder0", "SW_Holder1", "SW_HolderStrap", "SW_Tassel0", "SW_Tassel1", "SW_Tassel2"])
remove([o.name for o in list(col.objects) if o.name.startswith(("SW_Bun", "SW_Pin", "SW_Flower", "SW_Bead",
                                                                 "SW_Guard", "SW_Armband"))])

# ---------- cloth-on-cloth fixes in the base outfit ----------
VEST = cloth("SW_Vest")
for tag in ("L", "R"):
    sl = ob(f"SW_Sleeve_{tag}")
    P = verts(sl)
    log("sleeve root under vest", tag, soft_push(sl, VEST, 0.002, side=-1, maxd=0.02, smooth=2,
                                                  mask=(np.abs(P[:, 0]) < 0.20).astype(float)))
# The sleeve's root ring sits right at the vest's armhole edge, where the nearest-surface push above gives up
# (open-sheet border). Measure the vest along rays from the arm axis instead: tuck the root under it and, past the
# vest's edge, let the sleeve rise back over 2 cm so no face climbs out through the edge.
_vv = verts(ob("SW_Vest"))
VEST_BVH = BVHTree.FromPolygons([Vector(p) for p in _vv], [list(p.vertices) for p in ob("SW_Vest").data.polygons])
for tag, s in (("L", 1), ("R", -1)):
    sl = ob(f"SW_Sleeve_{tag}")
    P = verts(sl)
    moved = 0
    for i in np.nonzero(np.abs(P[:, 0]) < 0.215)[0]:
        d = Vector((0, P[i, 1] - 0.025, P[i, 2] - 1.26))
        r = d.length
        d.normalize()
        edge = None
        for back in (0.0, 0.004, 0.008, 0.012, 0.016, 0.020, 0.024, 0.030, 0.036, 0.044):
            x = P[i, 0] - s * back
            hit = VEST_BVH.ray_cast(Vector((x, 0.025, 1.26)), d, 0.2)
            if hit[0] is not None:
                edge = (back, hit[3])
                break
        if edge is None:
            continue
        back, rv = edge
        want = rv - 0.003
        want += (r - want) * min(max((back - 0.002) / 0.02, 0.0), 1.0) if r > want else 0.0
        if r > want:
            P[i, 1:] = np.array([0.025, 1.26]) + np.array(d[1:]) * want
            moved += 1
    set_verts(sl, P)
    log("sleeve root tucked under vest edge", tag, moved)
OBI = cloth("SW_Obi")
for n in ("SW_VestTrim", "SW_TassetL", "SW_TassetR"):
    o = ob(n)
    P = verts(o)
    m = ((P[:, 2] > 0.94) & (P[:, 2] < 1.10)).astype(float)
    log("under obi", n, soft_push(o, OBI, 0.002, side=-1, mask=m, maxd=0.02, smooth=2))
for tag in ("L", "R"):
    sl = ob(f"SW_Sleeve_{tag}")
    P = verts(sl)
    m = ((np.abs(P[:, 0]) < 0.26) & (P[:, 2] < 1.30)).astype(float)
    log("sleeve root off armpit", tag, soft_push(sl, BODYR, 0.002, mask=m, maxd=0.02, smooth=2))
# layer order at the neck: body < inner top < top < collar < vest; the collar's outer edge runs just under the vest
for n, over in (("SW_Collar", ("SW_Vest",)),):
    o = ob(n)
    P = verts(o)
    log("under", over, n, soft_push(o, cloth(*over), 0.002, side=-1, mask=(P[:, 2] > 1.12).astype(float), maxd=0.02,
                                     smooth=2))
BOOTS = cloth("SW_Boots")
for n in ("SW_BootRimL", "SW_BootRimR"):
    log("rim over boot", n, soft_push(ob(n), BOOTS, 0.003, maxd=0.03, smooth=2))
SKIRT = cloth("SW_Skirt")
for n in ("SW_TassetL", "SW_TassetR"):
    o = ob(n)
    P = verts(o)
    m = np.clip((0.985 - P[:, 2]) / 0.02, 0, 1)
    log("tasset over skirt", n, soft_push(o, SKIRT, 0.0015, mask=m, maxd=0.02, smooth=2))

# ---------- pauldrons: small caps on the shoulder points, lames along the T-pose arm ----------
def heightmap(objs, x0, x1, y0, y1, step=0.0025):
    """Top surface z of objs on an xy grid (rays from above); nan where nothing is below."""
    V, T, base = [], [], 0
    for o in objs:
        V.append(verts(o))
        T += [[base + i for i in p.vertices] for p in o.data.polygons]
        base += len(V[-1])
    bvh = BVHTree.FromPolygons([Vector(p) for p in np.concatenate(V)], T)
    xs, ys = np.arange(x0, x1 + 1e-9, step), np.arange(y0, y1 + 1e-9, step)
    H = np.full((len(xs), len(ys)), np.nan)
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            hit = bvh.ray_cast(Vector((x, y, 2.0)), Vector((0, 0, -1)), 3.0)
            if hit[0] is not None:
                H[i, j] = hit[0].z
    return xs, ys, H


def h_at(hm, xy):
    xs, ys, H = hm
    i = np.clip(np.round((xy[:, 0] - xs[0]) / (xs[1] - xs[0])).astype(int), 0, len(xs) - 1)
    j = np.clip(np.round((xy[:, 1] - ys[0]) / (ys[1] - ys[0])).astype(int), 0, len(ys) - 1)
    out = H[i, j]
    out[(xy[:, 0] < xs[0]) | (xy[:, 0] > xs[-1]) | (xy[:, 1] < ys[0]) | (xy[:, 1] > ys[-1])] = np.nan
    return out


def underside(P, cell=0.005):
    """Lowest vertex in each xy cell: (cell keys, their points)."""
    key = np.floor(P[:, :2] / cell).astype(np.int64)
    order = np.lexsort((P[:, 2], key[:, 1], key[:, 0]))
    k = key[order]
    first = np.r_[True, np.any(k[1:] != k[:-1], axis=1)]
    return k[first], P[order[first]]


def settle(o, hm, margin, pitch=range(-40, 41, 4), roll=range(-20, 21, 5)):
    """Rigid tilt (about x, then y) plus drop that leaves the least air between o's underside and what's below.
    A cap resting on its two lowest points with its middle in the air is what reads as 'floating'."""
    P0 = verts(o)
    lo, hi = P0.min(0), P0.max(0)
    c = (lo + hi) / 2
    best = None
    for a in pitch:
        for b in roll:
            M = np.array(Matrix.Rotation(math.radians(b), 3, "Y") @ Matrix.Rotation(math.radians(a), 3, "X"))
            _, U = underside((P0 - c) @ M.T + c)
            g = U[:, 2] - h_at(hm, U)
            ok = ~np.isnan(g)
            if ok.mean() < 0.6:
                continue
            g = g[ok]
            air = float(np.mean(g - g.min())) + 0.00005 * (abs(a) + abs(b))
            if best is None or air < best[0]:
                best = (air, a, b, float(g.min()))
    air, a, b, gmin = best
    about(o, Vector(c), Matrix.Rotation(math.radians(b), 3, "Y") @ Matrix.Rotation(math.radians(a), 3, "X"))
    set_verts(o, verts(o) - np.array([0, 0, gmin - margin]))
    return a, b, round(gmin - margin, 4), round(air, 4)


def conform(o, hm, margin, cap=0.015, cell=0.005):
    """Lets each column of o sink onto the surface below by its own gap (smoothed, at most cap), so the cap's
    underside follows the shoulder instead of bridging over it. Whole columns move, so the plates keep their
    thickness."""
    P = verts(o)
    keys, U = underside(P, cell)
    g = U[:, 2] - h_at(hm, U) - margin
    k0 = keys.min(0)
    G = np.full(tuple(keys.max(0) - k0 + 1), np.nan)
    G[tuple((keys - k0).T)] = np.clip(g, 0, cap)
    for _ in range(G.size):  # holes (no surface below) take their neighbours' value
        if not np.isnan(G).any():
            break
        Pd = np.pad(G, 1, constant_values=np.nan)
        nb = np.stack([Pd[1 + dx:Pd.shape[0] - 1 + dx, 1 + dy:Pd.shape[1] - 1 + dy]
                       for dx in (-1, 0, 1) for dy in (-1, 0, 1)])
        fill = np.nanmean(np.where(np.isnan(nb), np.nan, nb), axis=0) if (~np.isnan(nb)).any() else G
        G = np.where(np.isnan(G), fill, G)
    G = np.nan_to_num(G)
    for _ in range(2):  # erode first so the blur doesn't sink a column below its own gap
        Pd = np.pad(G, 1, mode="edge")
        G = np.min([Pd[1 + dx:Pd.shape[0] - 1 + dx, 1 + dy:Pd.shape[1] - 1 + dy]
                    for dx in (-1, 0, 1) for dy in (-1, 0, 1)], axis=0)
    for _ in range(3):
        Pd = np.pad(G, 1, mode="edge")
        G = np.mean([Pd[1 + dx:Pd.shape[0] - 1 + dx, 1 + dy:Pd.shape[1] - 1 + dy]
                     for dx in (-1, 0, 1) for dy in (-1, 0, 1)], axis=0)
    # bilinear lookup at cell centres
    f = P[:, :2] / cell - 0.5 - k0
    i0 = np.clip(np.floor(f).astype(int), 0, np.array(G.shape) - 1)
    i1 = np.clip(i0 + 1, 0, np.array(G.shape) - 1)
    t = np.clip(f - i0, 0, 1)
    d = (G[i0[:, 0], i0[:, 1]] * (1 - t[:, 0]) * (1 - t[:, 1]) + G[i1[:, 0], i0[:, 1]] * t[:, 0] * (1 - t[:, 1]) +
         G[i0[:, 0], i1[:, 1]] * (1 - t[:, 0]) * t[:, 1] + G[i1[:, 0], i1[:, 1]] * t[:, 0] * t[:, 1])
    P[:, 2] -= d
    set_verts(o, P)
    return round(float(d.max()), 4), round(float(np.nanmean(np.clip(g, 0, None))), 4)


# (the neckline trim and collar end at |x| 0.123, inside the pauldrons' reach; their thin ends give false depths)
UNDER_SH = Multi(BODYR, cloth("SW_InnerTop", "SW_Top", "SW_Vest", "SW_Sleeve_L", "SW_Sleeve_R"))
SH_OBJS = [ob(n) for n in ("Body", "SW_InnerTop", "SW_Top", "SW_Vest", "SW_Sleeve_L", "SW_Sleeve_R")]
pl, pr = load("A_props", [0, 1])
for o, s, tag in ((pl, 1, "L"), (pr, -1, "R")):
    lo, hi = box(o)
    # modelled for arms hanging ~45 deg (lames run down-out); turn so the lames follow the horizontal arm
    about(o, Vector((lo + hi) / 2), Matrix.Rotation(math.radians(-40 * s), 3, "Y"))
    fit(o, 0, 0.165, (0.5, 0.5, 0.0), (s * 0.225, 0.025, 1.45))  # broad: covers the shoulder cap  # above the shoulder, then set down onto it
    lo, hi = box(o)
    about(o, Vector((lo + hi) / 2), Matrix.Diagonal((1, max(1.0, 0.14 / (hi[1] - lo[1])), 0.60)))  # low profile: a cap, not a cuff
    hm = heightmap(SH_OBJS, *sorted((s * 0.10, s * 0.38)), -0.12, 0.18)
    log("pauldron", tag, "settle pitch/roll/drop/air", settle(o, hm, 0.006))
    log("pauldron", tag, "conform max/mean gap", conform(o, hm, 0.005, cap=0.05))
    down = drop(o, UNDER_SH, (0, 0, -1), 0.004, travel=0.03)
    blame("pauldron " + tag, o, UNDER_SH)
    up = rigid_clear(o, UNDER_SH, (s * 0.3, 0, 1), 0.004, maxd=0.06)
    P = verts(o)
    m = np.clip((P[:, 2].max() - 0.025 - P[:, 2]) / 0.03, 0, 1)  # the lower lame edges may flex
    moved, worst = soft_push(o, UNDER_SH, 0.003, mask=m, maxd=0.04, smooth=4)
    lo, hi = box(o)
    log("pauldron", tag, "drop", round(down, 4), "lift", round(up, 4), "flexed", moved, "worst", round(worst, 4), "box", np.round(lo, 3),
        np.round(hi, 3))

    def guard_w(p, tag=tag):
        t = min(max((abs(p.x) - 0.11) / 0.05, 0), 1)
        return {f"J_Bip_{tag}_Shoulder": 1 - t, f"J_Bip_{tag}_UpperArm": t}
    bind(o, guard_w, f"SW_Pauldron_{tag}")
PAUL = closed(pl, pr)

# ---------- obi medallion with its orange bow and tails, wrapped onto the obi curve ----------
ZC = 1.035
h0 = OBI.ray((0, -1.0, ZC), (0, 1, 0))
yo = h0[0].y if h0 else -0.145
h1 = OBI.ray((0.09, -1.0, ZC), (0, 1, 0))
dy = (h1[0].y - yo) if h1 else 0.025
R0 = (0.09 ** 2 + dy ** 2) / (2 * max(dy, 1e-3))
(md,) = load("B_armor", [0])
MW = 0.17
# the cord runs under the medallion: flatten it onto the sash there so the plate can lie flat over it
cd = ob("SW_ObiCord")
C = verts(cd)
wc = np.clip((MW / 2 + 0.010 - np.abs(C[:, 0])) / 0.018, 0, 1) * (C[:, 1] < -0.05)
for i in np.nonzero(wc > 0)[0]:
    d = Vector((C[i, 0], C[i, 1], 0)).normalized()
    h = OBI.ray(Vector((0, 0, C[i, 2])) + d * 0.8, -d)
    if h:
        r0 = Vector((h[0].x, h[0].y, 0)).length
        r = math.hypot(C[i, 0], C[i, 1])
        C[i, :2] *= (r0 + (r - r0) * (1 - 0.8 * wc[i])) / r
set_verts(cd, C)
fit(md, 0, MW, (0.5, 1.0, 1.0), (0.0, yo + 0.003, 1.084))
P = verts(md)
ax = np.abs(P[:, 0])
X0 = 0.042 * MW / 0.19
dx = np.maximum(ax - X0, 0)
ang = np.sign(P[:, 0]) * dx / R0
rx, ry = P[:, 0] - np.sign(P[:, 0]) * X0, P[:, 1] - yo
# the bow loops beside the disc are puffy; seen from the side or below they stood off the obi like horns.
# Halve their depth so they lie on the sash.
ry = 0.003 + (ry - 0.003) * (1 - 0.55 * np.clip(dx / 0.012, 0, 1))
P[:, 0] = np.where(dx > 0, np.sign(P[:, 0]) * X0 + rx * np.cos(ang) - ry * np.sin(ang), P[:, 0])
P[:, 1] = np.where(dx > 0, yo + rx * np.sin(ang) + ry * np.cos(ang), P[:, 1])
set_verts(md, P)
lo, hi = box(md)
disc = (np.abs(P[:, 0]) < X0 + 0.005) & (P[:, 2] > lo[2] + 0.42 * (hi[2] - lo[2]))
UNDER_MD = Multi(cloth("SW_Obi", "SW_ObiCord", "SW_VestTrim", "SW_Vest", "SW_TassetL", "SW_TassetR", "SW_Skirt",
                       "SW_Robe"), BODYR)
blame("medallion", md, UNDER_MD)
fwd = rigid_clear(md, UNDER_MD, (0, -1, 0), 0.002, maxd=0.04, mask=disc)
m = np.where(disc, 0.0, 1.0)
log("medallion R0", round(R0, 3), "fwd", round(fwd, 4), "soft",
    soft_push(md, UNDER_MD, 0.003, mask=m, maxd=0.05, smooth=4))
bind(md, KNOT_W, "SW_ObiMedallion")
MED = closed(md)

# ---------- jade pendant: hangs upright from the obi cord on a short cord; its tassel lies over what is below ----
TH_P = math.radians(-27)  # front right, beside the knot tails (as in the reference)
outp = dirv(TH_P)
sidep = Vector((math.cos(TH_P), math.sin(TH_P), 0))
hit = OBI.ray(Vector((0, 0, 0.972)) + outp * 0.6, -outp)
pivot = (hit[0] if hit else PEND_TOP_OLD) + outp * 0.004
(pj,) = load("A_props", [2])
about(pj, Vector(np.mean(box(pj), 0)), Matrix.Rotation(TH_P, 3, "Z"))
fit(pj, 2, 0.21, (0.5, 0.5, 1.0), pivot)
lo, hi = box(pj)
P = verts(pj)
jade = P[:, 2] > lo[2] + 0.48 * (hi[2] - lo[2])  # ring and caps; below is the tassel
UNDER_PJ = Multi(cloth("SW_Robe", "SW_Skirt", "SW_TassetR", "SW_TassetL", "SW_Obi", "SW_ObiCord"), BODYR, MED)
blame("pendant", pj, UNDER_PJ)
fwd = rigid_clear(pj, UNDER_PJ, outp, 0.003, maxd=0.07, mask=jade)
m = np.where(jade, 0.0, np.clip((lo[2] + 0.48 * (hi[2] - lo[2]) - P[:, 2]) / 0.025, 0, 1))
moved, worst = soft_push(pj, UNDER_PJ, 0.003, mask=m, maxd=0.07, smooth=4)
log("pendant fwd", round(fwd, 4), "tassel bent", moved, "worst", round(worst, 4))
# hanging cord: from the obi cord (tied around it) down to the pendant's top loop
C = verts(ob("SW_ObiCord"))
ang = np.arctan2(C[:, 0], -C[:, 1])
near = np.abs(((ang - TH_P + math.pi) % (2 * math.pi)) - math.pi) < math.radians(3)
anchor = Vector(C[near].mean(0)) if near.any() else pivot + Vector((0, 0, 0.045))
P = verts(pj)
top = Vector(P[P[:, 2] > P[:, 2].max() - 0.004].mean(0))
if (top - anchor).length > 0.008:
    pts = [anchor.lerp(top, k) for k in np.linspace(0, 1, 10)]
    pc = strap("SW_JadeCord", pts, sidep, width=0.005, thick=0.0035, tile="cord")
    Pc = verts(pc)
    mc = (np.arange(len(Pc)) // 4 >= 2).astype(float) * (np.arange(len(Pc)) // 4 <= 8)
    log("jade cord len", round((top - anchor).length, 3), "pushed",
        soft_push(pc, Multi(cloth("SW_Obi"), MED), 0.002, mask=mc, maxd=0.03, smooth=2))
    bind(pc, PEND_W, "SW_JadeCord")
bind(pj, PEND_W, "SW_JadePendant")
PJ = closed(pj)


# ---------- sword assembly at the left hip ----------
def profile(o, tip_up):
    """Long axis a (oriented), n2 = face toward the probe camera (-y), n1 = n2 x a, fraction f along a."""
    v = verts(o)
    c = v.mean(0)
    a = np.linalg.eigh(np.cov((v - c).T))[1][:, -1]
    a = a if (a[2] > 0) == tip_up else -a
    y = np.array([0, -1.0, 0])
    n2 = y - a * a.dot(y)
    n2 /= np.linalg.norm(n2)
    n1 = np.cross(n2, a)
    t = (v - c) @ a
    f = (t - t.min()) / (t.max() - t.min())
    return v, c, a, n1, n2, t, f


def centerline(v, a, f, f0, f1):
    pts = []
    for q in np.linspace(f0, f1, 11):
        m = np.abs(f - q) < 0.012
        if m.sum() >= 4:
            pts.append((v[m].min(0) + v[m].max(0)) / 2)
    pts = np.array(pts)
    c = pts.mean(0)
    d = np.linalg.eigh(np.cov((pts - c).T))[1][:, -1]
    return c, (d if d.dot(a) > 0 else -d)


def lateral(v, c, d, n):
    r = (v - c) - np.outer((v - c) @ d, d)
    return r @ n


HIP = Multi(cloth("SW_Robe", "SW_Skirt", "SW_TassetL", "SW_Obi", "SW_ObiCord", "SW_Vest", "SW_VestTrim"), BODYR,
            MED)
TH_M = math.radians(72)
outm = dirv(TH_M)
ZM = 0.948
hit = HIP.ray(Vector((0, 0, ZM)) + outm * 0.8, -outm)
S0 = hit[0] if hit else Vector((0.19, -0.06, ZM))
EL = math.radians(38)
D = (dirv(TH_M + math.radians(90)) * math.cos(EL) + Vector((0, 0, -math.sin(EL))) + outm * 0.12).normalized()
O = (outm - D * D.dot(outm)).normalized()
U = D.cross(O).normalized()
U = U if U.z > 0 else -U

# scabbard (a: mouth -> tip)
(sc,) = load("F_scabbard", [0])
v, c, a, n1, n2, t, f = profile(sc, tip_up=False)
cl_c, cl_d = centerline(v, a, f, 0.25, 0.80)
SC_LEN = 0.60
ks = SC_LEN / (t.max() - t.min())
q = lateral(v, cl_c, cl_d, n1)
core = (f > 0.55) & (f < 0.85)
hw = np.percentile(np.abs(q[core]), 97)
bump = (np.abs(q) > hw * 1.35) & (f > 0.03) & (f < 0.65)
side = 1.0 if q[bump].sum() > 0 else -1.0
rings = np.nonzero(bump & (np.sign(q) == side))[0]
fr = np.sort(f[rings])
gap = np.argmax(np.diff(fr)) if len(fr) > 1 else 0
split = (fr[gap] + fr[gap + 1]) / 2 if len(fr) > 1 else 0.3
ring_groups = [rings[f[rings] < split], rings[f[rings] >= split]]
ring_tips = [g[np.argmax(side * q[g])] for g in ring_groups if len(g)]
log("scabbard rings", [len(g) for g in ring_groups], "f", [round(float(f[i]), 3) for i in ring_tips], "side", side)
half_t = 0.5 * ks * np.ptp((v - cl_c) @ n2)
mouth_local = Vector(cl_c) + Vector(cl_d) * float((v[f.argmin()] - cl_c) @ cl_d)
R = frame_rot(Vector(cl_d), Vector(n2), D, O)
M = S0 + O * (half_t + 0.006)
xform(sc, Matrix.Translation(M) @ Matrix.Scale(ks, 4) @ R.to_4x4() @ Matrix.Translation(-mouth_local))
mir_sc = (R @ Vector(n1 * side)).dot(U) < 0
if mir_sc:
    mirror_plane(sc, M, U)

# sword (a2: pommel -> tip); keep the hilt, the blade is inside the scabbard
(sw,) = load("E_sword", [0])
v2, c2, a2, n1b, n2b, t2, f2 = profile(sw, tip_up=True)
bl_c, bl_d = centerline(v2, a2, f2, 0.50, 0.85)
q2 = lateral(v2, bl_c, bl_d, n1b)
bins = np.arange(0.20, 0.60, 0.005)
width = np.array([np.ptp(q2[np.abs(f2 - b) < 0.004]) if (np.abs(f2 - b) < 0.004).sum() > 3 else 0 for b in bins])
blade_w = np.median([np.ptp(q2[np.abs(f2 - b) < 0.004]) for b in np.arange(0.55, 0.80, 0.02)])
gi = int(np.argmax(width))
ge = gi
while ge < len(bins) - 1 and width[ge] > 1.12 * blade_w:
    ge += 1
f_guard = float(bins[ge])
L2 = t2.max() - t2.min()
KW = (0.95 * SC_LEN) / ((1 - f_guard) * L2)  # blade length = 95% of the scabbard
handle = (f2 < f_guard - 0.06)
hw2 = np.percentile(np.abs(q2[handle]), 60)
tside = 1.0 if q2[handle & (np.abs(q2) > 1.5 * hw2)].sum() > 0 else -1.0
gpt = Vector(bl_c) + Vector(bl_d) * float(((v2[np.abs(f2 - f_guard) < 0.006].mean(0)) - bl_c) @ bl_d)
R2 = frame_rot(Vector(bl_d), Vector(n2b), D, O)
xform(sw, Matrix.Translation(M - D * 0.002) @ Matrix.Scale(KW, 4) @ R2.to_4x4() @ Matrix.Translation(-gpt))
mir_sw = (R2 @ Vector(n1b * tside)).dot(U) > 0  # the tassel hangs on the lower side
if mir_sw:
    mirror_plane(sw, M, U)
delete_verts(sw, f2 > f_guard + 0.004)
log("sword f_guard", round(f_guard, 3), "KW", round(KW, 3), "hilt len", round(f_guard * L2 * KW, 3), "mirror",
    mir_sc, mir_sw)

# both pieces move together, perpendicular to the scabbard, until clear of the hip layers
blame("scabbard", sc, HIP, maxd=0.07)
blame("sword", sw, Multi(HIP, PJ), maxd=0.07)
total = 0.0
for _ in range(5):
    s1 = rigid_clear(sc, HIP, O, 0.004, maxd=0.07)
    xform(sw, Matrix.Translation(O * s1))
    s2 = rigid_clear(sw, Multi(HIP, PJ), O, 0.004, maxd=0.07)
    xform(sc, Matrix.Translation(O * s2))
    total += s1 + s2
    if s1 + s2 < 1e-4:
        break
M = M + O * total
log("sword mouth", np.round(M, 3), "clear shift", round(total, 4))

# two hanger straps: from under the obi's lower edge to the scabbard rings
SCP = verts(sc)
HANG = Multi(cloth("SW_Robe", "SW_Skirt", "SW_TassetL", "SW_Obi", "SW_ObiCord"), BODYR)
SCS = closed(sc)  # the straps come down onto the rings from above and used to clip the scabbard's back
CORD_R = 0.0024
for j, (ti, grp) in enumerate(zip(ring_tips, [g for g in ring_groups if len(g)])):
    # the ring itself: points near the tip, their plane, centre, and tube size
    tip = SCP[ti]
    R = SCP[grp][np.linalg.norm(SCP[grp] - tip, axis=1) < 0.03]
    rc = R.mean(0)
    nrm = np.linalg.eigh(np.cov((R - rc).T))[1][:, 0]
    inpl = (R - rc) - np.outer((R - rc) @ nrm, nrm)
    rad = np.linalg.norm(inpl, axis=1)
    r_out, r_in = float(rad.max()), float(np.percentile(rad, 3))
    r_bar, r_tube = (r_out + r_in) / 2, max((r_out - r_in) / 2, 0.0015)
    rc, nrm = Vector(rc), Vector(nrm)
    dirx = Vector((tip[0], tip[1], 0)).normalized()
    # hang from the obi's lower edge right above the ring, tucked under it
    hit = OBI.ray(Vector((0, 0, 0.985)) + dirx * 0.8, -dirx)
    top = (hit[0] - dirx * 0.003) if hit else Vector((tip[0] * 0.6, tip[1] * 0.6, 0.985))
    top.z = 0.985
    # the cord hooks over the bar of the ring nearest the obi: down to it, through the hole and round once
    w = (top - rc) - nrm * (top - rc).dot(nrm)
    w.normalize()
    B = rc + w * r_bar
    tau = nrm.cross(w).normalized()
    rho = r_tube + CORD_R + 0.0005
    entry = B + w * rho - tau * 0.0035
    pts = [top.lerp(entry, k) for k in np.linspace(0, 1, 12)]
    for phi in np.linspace(0, 2 * math.pi * 1.1, 16)[1:]:
        pts.append(B + (w * math.cos(phi) + nrm * math.sin(phi)) * rho + tau * (-0.0035 + 0.007 * phi / (2 * math.pi)))
    so = strap(f"SW_SwordStrap{j}", pts, tau, width=CORD_R * 2, thick=CORD_R * 2, tile="cord")  # braided cord
    P = verts(so)
    m = ((np.arange(len(P)) // 4 >= 2) & (np.arange(len(P)) // 4 < 9)).astype(float)  # obi end and hook stay put
    log("strap", j, "ring r_out/r_in", round(r_out, 4), round(r_in, 4), "bar", np.round(np.array(B), 3))
    end = B
    moved, worst = soft_push(so, Multi(HANG, SCS), 0.002, mask=m, maxd=0.05, smooth=3)
    bind(so, rigid(HIPS), f"SW_SwordStrap{j}")
    log("strap", j, "len", round((end - top).length, 3), "pushed", moved, "worst", round(worst, 4))
bind(sc, rigid(HIPS), "SW_Scabbard")
bind(sw, rigid(HIPS), "SW_Sword")

# ---------- topknot (Tripo bun, head cap cut off), crown over it, two kanzashi ----------
crown_hit = Vector((0.0, 0.05, 1.598))
(bun,) = load("C_hair", [2])
lo, hi = box(bun)
v = verts(bun)
delete_verts(bun, v[:, 2] < hi[2] - 0.34 * (hi[2] - lo[2]))
fit(bun, 0, 0.074, (0.5, 0.5, 0.0), crown_hit + Vector((0, 0.004, -0.018)))
bl, bh = box(bun)
v = verts(bun)
topv = v[v[:, 2] > bl[2] + 0.55 * (bh[2] - bl[2])]
tc = topv.mean(0)
tw = np.ptp(topv[:, 0])

(cr,) = load("A_props", [3])
lo, hi = box(cr)
v = verts(cr)
cx = (lo[0] + hi[0]) / 2
body_sel = np.abs(v[:, 0] - cx) < 0.25 * (hi[0] - lo[0])
bw = np.ptp(v[body_sel][:, 0])
k_cr = (tw + 0.010) / bw
xform(cr, Matrix.Diagonal((k_cr, k_cr, k_cr * 0.72, 1)))
v = verts(cr)
lo, hi = v.min(0), v.max(0)
bc = v[np.abs(v[:, 0] - (lo[0] + hi[0]) / 2) < 0.25 * (hi[0] - lo[0])].mean(0)
xform(cr, Matrix.Translation(Vector((tc[0], tc[1], bl[2] + 0.45 * (bh[2] - bl[2]))) - Vector((bc[0], bc[1], lo[2]))))
trim_inside(bun, BODYR, 0.0, maxd=0.1)
log("crown k", round(k_cr, 3), "topknot w", round(float(np.ptp(verts(bun)[:, 0])), 3), "trimmed",
    trim_inside(bun, closed(cr), 0.0005, maxd=0.1))
bind(bun, rigid(HEAD), "SW_Topknot")
bind(cr, rigid(HEAD), "SW_Crown")
bl, bh = box(bun)

for idx, s, tag in ((0, 1, "L"), (1, -1, "R")):
    (kz,) = load("C_hair", [idx])
    if s < 0:
        mirror_plane(kz, Vector((0, 0, 0)), Vector((1, 0, 0)))
    lo, hi = box(kz)
    about(kz, Vector((lo + hi) / 2), Matrix.Rotation(math.radians(25 * s), 3, "Z"))
    anchor = (0.70, 0.5, 0.80) if s > 0 else (0.30, 0.5, 0.80)
    side_x = bh[0] if s > 0 else bl[0]
    fit(kz, 0, 0.068, anchor, (side_x + s * 0.006, (bl[1] + bh[1]) / 2 + 0.006, bl[2] + 0.55 * (bh[2] - bl[2])))
    trim_inside(kz, BODYR, 0.0, maxd=0.1)
    bind(kz, rigid(HEAD), f"SW_Kanzashi_{tag}")
    log("kanzashi", tag, "box", np.round(box(kz)[0], 3), np.round(box(kz)[1], 3))

# ---------- hair lies over the clothes and armour ----------
H = verts(hair)
hm = np.clip((1.36 - H[:, 2]) / 0.06, 0, 1)
TORSO = Multi(cloth("SW_InnerTop", "SW_Top", "SW_Collar", "SW_Vest", "SW_Obi", "SW_ObiCord",
                    "SW_KnotBack", "SW_BowBack+1", "SW_BowBack-1", "SW_TailBack0", "SW_TailBack1", "SW_Robe",
                    "SW_Sleeve_L", "SW_Sleeve_R"), PAUL, MED)
moved, worst = soft_push(hair, TORSO, 0.006, mask=hm, maxd=0.06, rounds=10, smooth=4)
log("hair over clothes", moved, "worst", round(worst, 4))
# the gold neckline trim stands ~1 cm off the vest: keep the hair that far off the vest where they meet
TR = verts(ob("SW_VestTrim"))
VS = cloth("SW_Vest")
lift = float(np.percentile([r[0] for r in (VS.sd(Vector(p), 0.03) for p in TR) if r is not None], 90))
H = verts(hair)
hm = np.clip((1.36 - H[:, 2]) / 0.05, 0, 1) * (H[:, 2] > 1.20) * (np.abs(H[:, 0]) < 0.17)
moved, worst = soft_push(hair, VS, lift + 0.005, mask=hm, maxd=0.04, rounds=8, smooth=3)
log("hair over trim: trim height", round(lift, 4), "moved", moved, "worst", round(worst, 4))

# ---------- textures 4K -> 1K on disk ----------
for img in list(bpy.data.images):
    if img.users == 0 or img.size[0] < 2048 or img.name.startswith(("N00_", "Shader_", "sw_", "iris")):
        continue
    fp = os.path.join(TEXO, bpy.path.clean_name(os.path.splitext(img.name)[0]) + ".png")
    img.scale(1024, 1024)
    tmp = bpy.data.images.new("tmp_tex", 1024, 1024, alpha=True)
    tmp.pixels.foreach_set(np.array(img.pixels[:], dtype=np.float32))
    tmp.filepath_raw = fp
    tmp.file_format = "PNG"
    tmp.save()
    bpy.data.images.remove(tmp)
    new = bpy.data.images.load(fp)
    new.colorspace_settings.name = img.colorspace_settings.name
    img.user_remap(new)
    bpy.data.images.remove(img)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "sw_outfit_v4.blend"))
with open(os.path.join(ROOT, "renders", "fit_log.txt"), "w") as fh:
    fh.write("\n".join(LOG))
print("SAVED")
