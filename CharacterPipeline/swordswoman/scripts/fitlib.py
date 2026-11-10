# Fitting helpers for the swordswoman outfit: signed distance to unions of meshes, rigid clearance, soft
# (smoothed) push-out of vertices, and trimming of hidden geometry. All objects are expected to sit at identity
# under the armature (rest pose), so mesh coordinates are world coordinates.
import bpy, bmesh, math
import numpy as np
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree


def dg():
    return bpy.context.evaluated_depsgraph_get()


def tri_arrays(objs, raw=False):
    """World-space vertices and triangles of the evaluated meshes (so modifiers such as masks apply).
    raw=True uses the plain mesh data (e.g. the whole body, ignoring Outfit_Mask)."""
    V, F = [], []
    d = dg()
    for o in objs:
        ev = o if raw else o.evaluated_get(d)
        me = o.data.copy() if raw else ev.to_mesh()
        mw = o.matrix_world
        base = len(V)
        V.extend(mw @ v.co for v in me.vertices)
        me.calc_loop_triangles()
        F.extend([base + t.vertices[0], base + t.vertices[1], base + t.vertices[2]] for t in me.loop_triangles)
        if raw:
            bpy.data.meshes.remove(me)
        else:
            ev.to_mesh_clear()
    return V, F


def components(T, A):
    """Connected parts of a triangle list: per-triangle label, and per label whether the part is closed
    (every edge shared by exactly two triangles). Vertices at the same spot (UV seams) are welded first."""
    if len(T) == 0:
        return np.zeros(0, dtype=np.int64), np.zeros(0, dtype=bool)
    _, weld = np.unique(np.round(A / 1e-6).astype(np.int64), axis=0, return_inverse=True)
    T = weld.ravel()[T]
    parent = np.arange(T.max() + 1)

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for t in T:
        r0 = find(t[0])
        for v in t[1:]:
            r = find(v)
            if r != r0:
                parent[r] = r0
    roots = np.array([find(t[0]) for t in T], dtype=np.int64)
    _, comp = np.unique(roots, return_inverse=True)
    ok = (T[:, 0] != T[:, 1]) & (T[:, 1] != T[:, 2]) & (T[:, 0] != T[:, 2])  # pole rows collapse to points
    Tn, cn = T[ok], comp[ok]
    E = np.sort(np.concatenate([Tn[:, [0, 1]], Tn[:, [1, 2]], Tn[:, [2, 0]]]), axis=1)
    ecomp = np.concatenate([cn, cn, cn])
    _, inv, cnt = np.unique(E, axis=0, return_inverse=True, return_counts=True)
    bad = cnt[inv.ravel()] != 2
    is_closed = np.ones(comp.max() + 1, dtype=bool)
    is_closed[np.unique(ecomp[bad])] = False
    return comp, is_closed


class Surf:
    """Union of meshes with per-triangle normals. away_from: a Surf whose nearest point defines 'inside' for
    open cloth shells (normals are flipped to point away from it). Otherwise the mesh's own winding is used,
    corrected globally if most normals point at the centroid."""

    def __init__(self, objs, away_from=None, raw=False):
        self.objs = [o.name for o in objs]
        V, F = tri_arrays(objs, raw)
        self.bvh = BVHTree.FromPolygons(V, F, all_triangles=True)
        A = np.array([tuple(v) for v in V]) if V else np.zeros((0, 3))
        T = np.array(F, dtype=np.int64) if F else np.zeros((0, 3), dtype=np.int64)
        a, b, c = A[T[:, 0]], A[T[:, 1]], A[T[:, 2]]
        n = np.cross(b - a, c - a)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        cen = (a + b + c) / 3
        comp, is_closed = components(T, A)
        vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
        for k in np.unique(comp):
            sel = comp == k
            if is_closed[k]:
                # closed part (tube, cord, rim, solid prop): its own winding, made outward by the signed volume
                if vol6[sel].sum() < 0:
                    n[sel] = -n[sel]
            elif away_from is not None:
                # open part with a consistent winding: one sign for the whole part.
                # 1) ray parity: a ray along an outward normal leaves the part, one along the inward normal
                #    meets the far wall (tubes, trims, sleeves, robe, a shell around the torso)
                idx = np.nonzero(sel)[0]
                part = BVHTree.FromPolygons([Vector(x) for x in A], T[idx].tolist(), all_triangles=True)
                votes = []
                for i in idx[::max(1, len(idx) // 200)]:
                    p, nn = Vector(cen[i]), Vector(n[i])
                    fwd = part.ray_cast(p + nn * 1e-4, nn, 0.4)[0] is not None
                    back = part.ray_cast(p - nn * 1e-4, -nn, 0.4)[0] is not None
                    if fwd != back:
                        votes.append(fwd)  # True: the normal points into the part
                frac = np.mean(votes) if len(votes) >= 8 else 0.5
                if 0.3 < frac < 0.7:
                    # 2) undecided (a sheet that does not wrap around anything): the side facing away from the body
                    votes = []
                    for i in idx[::max(1, len(idx) // 3000)]:
                        loc = away_from.bvh.find_nearest(Vector(cen[i]))[0]
                        if loc is not None:
                            votes.append(np.dot(cen[i] - np.array(loc), n[i]) < 0)
                    frac = np.mean(votes) if votes else 0.0
                if frac > 0.5:
                    n[sel] = -n[sel]
            # open part without a reference (imported props, the body): trust the file's winding
        self.N = n
        self.V, self.T = A, T
        self.open = away_from is not None

    def sd(self, p, maxd):
        loc, _, idx, dist = self.bvh.find_nearest(p, maxd)
        if loc is None:
            return None
        n = Vector(self.N[idx])
        d = (p - loc).dot(n)
        # open sheet: a point that is nearest to the sheet's border (offset not along the normal) is beside the
        # sheet, neither in front of nor behind it, so the sheet sets no constraint there
        if self.open and dist > 2e-4 and abs(d) < 0.6 * dist:
            return None
        return d, loc, n

    def ray(self, origin, direction, dist=10.0):
        loc, _, idx, d = self.bvh.ray_cast(Vector(origin), Vector(direction).normalized(), dist)
        return (loc, Vector(self.N[idx]), d) if loc is not None else None


class Multi:
    """Several Surfs treated as one: sd() reports the most violating (deepest) surface."""

    def __init__(self, *surfs):
        self.surfs = [s for s in surfs if s is not None]

    def sd(self, p, maxd):
        best = None
        for s in self.surfs:
            r = s.sd(p, maxd)
            if r is not None and (best is None or r[0] < best[0]):
                best = r
        return best

    def ray(self, origin, direction, dist=10.0):
        best = None
        for s in self.surfs:
            r = s.ray(origin, direction, dist)
            if r is not None and (best is None or r[2] < best[2]):
                best = r
        return best


def verts(o):
    a = np.empty(len(o.data.vertices) * 3)
    o.data.vertices.foreach_get("co", a)
    return a.reshape(-1, 3)


def set_verts(o, P):
    o.data.vertices.foreach_set("co", np.asarray(P, dtype=np.float64).ravel())
    o.data.update()


def xform(o, M):
    o.data.transform(M)
    o.data.update()


def edges(o):
    e = np.empty(len(o.data.edges) * 2, dtype=np.int64)
    o.data.edges.foreach_get("vertices", e)
    return e.reshape(-1, 2)


def smooth_field(D, E, n, iters, lam=0.5, keep=None):
    deg = np.zeros(n)
    np.add.at(deg, E[:, 0], 1)
    np.add.at(deg, E[:, 1], 1)
    has = deg > 0
    for _ in range(iters):
        S = np.zeros_like(D)
        np.add.at(S, E[:, 0], D[E[:, 1]])
        np.add.at(S, E[:, 1], D[E[:, 0]])
        avg = np.where(has[:, None], S / np.maximum(deg, 1)[:, None], D)
        new = D * (1 - lam) + avg * lam
        if keep is not None:
            new[keep] = D[keep]
        D = new
    return D


def penetration(P, surf, margin, side=1, maxd=0.05, idx=None, guide=None):
    """Per-vertex correction vectors that bring each point to side*d >= margin, plus the worst depth.
    guide: a Surf whose nearest normal gives the push direction (e.g. hair moves straight out from the body
    instead of sideways around a thin trim)."""
    out = np.zeros_like(P)
    worst = 0.0
    for i in (range(len(P)) if idx is None else idx):
        p = P[i]
        r = surf.sd(Vector(p), maxd)
        if r is None:
            continue
        d, loc, n = r
        want = margin - side * d
        if want > 0:
            if guide is not None:
                g = guide.sd(Vector(p), 0.5)
                if g is not None:
                    gd = np.array(g[2]) * side
                    out[i] = gd * (want / max(float(gd.dot(np.array(n) * side)), 0.35))
                    worst = max(worst, want)
                    continue
            out[i] = np.array(n) * (want * side)
            worst = max(worst, want)
    return out, worst


def rigid_clear(o, surf, direction, margin, maxd=0.05, iters=12, mask=None):
    """Translates o along direction until its vertices are outside surf by margin. Returns the total shift."""
    d = Vector(direction).normalized()
    total = 0.0
    for _ in range(iters):
        P = verts(o)
        if mask is not None:
            P = P[mask]
        need = 0.0
        for p in P:
            r = surf.sd(Vector(p), maxd)
            if r is None:
                continue
            dd, loc, n = r
            if dd < margin:
                along = n.dot(d)
                if along > 0.15:
                    # capped: a surface almost parallel to the move would otherwise ask for a huge jump
                    need = max(need, (margin - dd) / max(along, 0.5))
        if need < 1e-4:
            break
        step = need + 0.0005
        xform(o, Matrix.Translation(d * step))
        total += step
    return total


def drop(o, surf, direction, margin, travel=0.25, step=0.003, maxd=0.03, every=3):
    """Moves o along direction from where it is (outside) until it first touches surf (margin), like setting a
    piece down onto the body. Returns the distance travelled."""
    d = Vector(direction).normalized()
    P0 = verts(o)[::every]
    moved = 0.0
    while moved < travel:
        hit = False
        for p in P0:
            r = surf.sd(Vector(p) + d * (moved + step), maxd)
            if r is not None and r[0] < margin:
                hit = True
                break
        if hit:
            break
        moved += step
    xform(o, Matrix.Translation(d * moved))
    return moved


def soft_push(o, surf, margin, side=1, mask=None, maxd=0.05, rounds=14, smooth=3, lam=0.5, guide=None):
    """Moves vertices of o to side*d >= margin w.r.t. surf, spreading the motion over the mesh so it bends
    smoothly instead of spiking. mask: per-vertex 0..1 freedom. Returns (moved verts, worst remaining)."""
    P0 = verts(o)
    E = edges(o)
    n = len(P0)
    D = np.zeros_like(P0)
    m = np.ones(n) if mask is None else np.asarray(mask, dtype=np.float64)
    worst = 0.0
    idx = np.nonzero(m > 0)[0]
    for _ in range(rounds):
        corr, worst = penetration(P0 + D, surf, margin, side, maxd, idx, guide)
        if worst < 2e-4:
            break
        D += corr * 1.1 * m[:, None]
        if smooth:
            D = smooth_field(D, E, n, smooth, lam)
            D *= m[:, None]
    corr, worst = penetration(P0 + D, surf, margin, side, maxd, idx, guide)
    D += corr * (m[:, None] > 0)  # final exact pass, no smoothing
    set_verts(o, P0 + D)
    worst = penetration(P0 + D, surf, margin * 0.5, side, maxd, idx, guide)[1]  # what is left after the last pass
    return int((np.linalg.norm(D, axis=1) > 1e-5).sum()), worst


def snap(o, surf, offset, mask, maxd=0.06, smooth=4):
    """Pulls masked vertices onto surf + offset (both directions), smoothed: makes straps hug a limb."""
    P0 = verts(o)
    E = edges(o)
    D = np.zeros_like(P0)
    m = np.asarray(mask, dtype=np.float64)
    for i, p in enumerate(P0):
        if m[i] <= 0:
            continue
        r = surf.sd(Vector(p), maxd)
        if r is None:
            continue
        d, loc, n = r
        D[i] = np.array(n) * (offset - d) * m[i]
    D = smooth_field(D, E, len(P0), smooth, 0.5)
    set_verts(o, P0 + D)


def trim_inside(o, surf, margin=0.0, maxd=0.2):
    """Deletes vertices of o that lie inside surf (hidden geometry that would otherwise poke out elsewhere)."""
    P = verts(o)
    kill = []
    for i, p in enumerate(P):
        r = surf.sd(Vector(p), maxd)
        if r is not None and r[0] < -margin:
            kill.append(i)
    if kill:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bm.verts.ensure_lookup_table()
        bmesh.ops.delete(bm, geom=[bm.verts[i] for i in kill], context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
    return len(kill)


def frame(a, b):
    """Orthonormal frame (columns): a, b made perpendicular to a, a x b."""
    a = Vector(a).normalized()
    b = (Vector(b) - a * a.dot(Vector(b))).normalized()
    return Matrix((a, b, a.cross(b))).transposed()


def frame_rot(a_src, b_src, a_dst, b_dst):
    return frame(a_dst, b_dst) @ frame(a_src, b_src).transposed()


def mirror_plane(o, point, normal):
    n = Vector(normal).normalized()
    M = Matrix.Translation(point) @ (Matrix.Identity(4) - 2 * Matrix((
        (n.x * n.x, n.x * n.y, n.x * n.z, 0), (n.y * n.x, n.y * n.y, n.y * n.z, 0),
        (n.z * n.x, n.z * n.y, n.z * n.z, 0), (0, 0, 0, 0)))) @ Matrix.Translation(-Vector(point))
    xform(o, M)
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(o.data)
    bm.free()
    o.data.update()


def overlaps(a, b):
    """Number of intersecting triangle pairs between two objects (evaluated, world)."""
    ta = BVHTree.FromPolygons(*tri_arrays([a]), all_triangles=True)
    tb = BVHTree.FromPolygons(*tri_arrays([b]), all_triangles=True)
    return len(ta.overlap(tb))
