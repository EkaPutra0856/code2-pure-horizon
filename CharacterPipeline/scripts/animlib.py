# Clip editing on baked Mixamo data. A Clip stores local bone rotations plus hips and root tracks,
# so retiming, blending and overlays are plain array work. Rotations are (w, x, y, z) quaternions.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import json, math, os
import numpy as np

ROOT = ANIME_GAME_ROOT
BAKED = os.path.join(ROOT, "mixamo", "baked")
FPS = 30
_r = json.load(open(os.path.join(ROOT, "mixamo", "target_rest.json")))
REST = {k: np.array(v, dtype=np.float64) for k, v in _r["rest"].items()}
PARENT = _r["parent"]
HEADS = {k: np.array(v) for k, v in _r.get("heads", {}).items()}


def qmul(a, b):
    aw, ax, ay, az = np.moveaxis(a, -1, 0)
    bw, bx, by, bz = np.moveaxis(b, -1, 0)
    return np.stack([aw * bw - ax * bx - ay * by - az * bz, aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx, aw * bz + ax * by - ay * bx + az * bw], axis=-1)


def qinv(q):
    return q * np.array([1, -1, -1, -1])


def qrot(q, v):
    p = np.concatenate([np.zeros(v.shape[:-1] + (1,)), v], axis=-1)
    return qmul(qmul(q, p), qinv(q))[..., 1:]


def qaxis(axis, deg):
    """Quaternions for an angle array around one axis."""
    a = np.radians(np.asarray(deg, dtype=np.float64)) / 2
    ax = np.asarray(axis, dtype=np.float64)
    ax = ax / np.linalg.norm(ax)
    return np.concatenate([np.cos(a)[..., None], np.sin(a)[..., None] * ax], axis=-1)


def nlerp(a, b, t):
    """Shortest-path blend between quaternion arrays."""
    d = np.sum(a * b, axis=-1, keepdims=True)
    b = np.where(d < 0, -b, b)
    r = a * (1 - t) + b * t
    return r / np.linalg.norm(r, axis=-1, keepdims=True)


def smooth(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def ease(n, frames, keys):
    """Curve over n frames through (frame, value) keys with smooth steps between them."""
    x = np.arange(n, dtype=np.float64)
    out = np.full(n, float(keys[0][1]))
    for (f0, v0), (f1, v1) in zip(keys, keys[1:]):
        m = (x >= f0)
        out[m] = v0 + (v1 - v0) * smooth((x[m] - f0) / max(f1 - f0, 1e-6))
    return out


class Clip:
    def __init__(self, q, hips, bones, root=None, yaw=None):
        self.q = np.asarray(q, dtype=np.float64)
        self.hips = np.asarray(hips, dtype=np.float64)
        self.bones = list(bones)
        n = len(self.q)
        self.root = np.zeros((n, 3)) if root is None else np.asarray(root, dtype=np.float64)
        self.yaw = np.zeros(n) if yaw is None else np.asarray(yaw, dtype=np.float64)
        self.events = {}

    def __len__(self):
        return len(self.q)

    def copy(self):
        c = Clip(self.q.copy(), self.hips.copy(), self.bones, self.root.copy(), self.yaw.copy())
        c.events = dict(self.events)
        return c

    def idx(self, bone):
        return self.bones.index(bone if bone.startswith("J_") else "J_Bip_" + bone)

    def sample(self, t):
        """Resample at fractional source frames t."""
        t = np.clip(np.asarray(t, dtype=np.float64), 0, len(self) - 1)
        i = np.minimum(t.astype(int), len(self) - 2)
        f = (t - i)[:, None]
        q = nlerp(self.q[i], self.q[i + 1], f[..., None])
        lin = lambda a: a[i] * (1 - f) + a[i + 1] * f
        c = Clip(q, lin(self.hips), self.bones, lin(self.root), self.yaw[i] * (1 - f[:, 0]) + self.yaw[i + 1] * f[:, 0])
        return c

    def seg(self, a, b):
        return self.sample(np.arange(a, b + 1))

    def warp(self, keys):
        """Retime through (source_frame, output_frame) pairs, smoothing nothing else."""
        src = [k[0] for k in keys]
        dst = [k[1] for k in keys]
        return self.sample(np.interp(np.arange(dst[0], dst[-1] + 1), dst, src))

    def speed(self, k):
        return self.sample(np.arange(0, len(self) - 1 + 1e-9, k))

    def pose_at(self, f):
        return self.q[int(f)], self.hips[int(f)]

    def fade_from(self, pose, n):
        """Blend the first n frames out of a fixed pose."""
        q, h = pose
        n = min(n, len(self))
        w = smooth(np.arange(n) / max(n - 1, 1))
        self.q[:n] = nlerp(np.broadcast_to(q, self.q[:n].shape), self.q[:n], w[:, None, None])
        self.hips[:n] = h * (1 - w[:, None]) + self.hips[:n] * w[:, None]
        return self

    def fade_to(self, pose, n):
        """Blend the last n frames into a fixed pose."""
        q, h = pose
        n = min(n, len(self))
        w = smooth(np.arange(1, n + 1) / n)
        self.q[-n:] = nlerp(self.q[-n:], np.broadcast_to(q, self.q[-n:].shape), w[:, None, None])
        self.hips[-n:] = self.hips[-n:] * (1 - w[:, None]) + h * w[:, None]
        return self

    def add(self, bone, axis, deg):
        """Extra rotation on one bone, axis in T-pose character space, deg per frame or constant."""
        j = self.idx(bone)
        name = self.bones[j]
        deg = np.broadcast_to(np.asarray(deg, dtype=np.float64), (len(self),))
        w = qaxis(axis, deg)
        r = REST[name]
        e = qmul(qmul(qinv(r), w), r)
        self.q[:, j] = qmul(e, self.q[:, j])
        return self

    def layer(self, other, bones, w=1.0):
        """Take listed bones from another clip of the same length, by weight."""
        for b in bones:
            j = self.idx(b)
            k = other.idx(b)
            ww = np.broadcast_to(np.asarray(w, dtype=np.float64), (len(self),))[:, None]
            self.q[:, j] = nlerp(self.q[:, j], other.q[:, k], ww)
        return self

    def in_place(self):
        """Remove steady travel from hips so the clip stays on the spot."""
        n = len(self)
        x = np.arange(n) / max(n - 1, 1)
        for a in (0, 1):
            self.hips[:, a] -= self.hips[0, a] + (self.hips[-1, a] - self.hips[0, a]) * x
        return self

    def to_root(self, ground_axes=(0, 1)):
        """Move travel from hips to the Root bone, which gives Unreal real root motion."""
        k = np.ones(9) / 9
        for a in ground_axes:
            p = np.pad(self.hips[:, a], 4, mode="edge")
            s = np.convolve(p, k, mode="valid")
            self.root[:, a] += s - s[0]
            self.hips[:, a] -= s - s[0]
        return self

    def loop(self, n=6):
        """Make the last frames flow back into the first frame."""
        self.fade_to((self.q[0].copy(), self.hips[0].copy()), n)
        return self


def load(name):
    d = np.load(os.path.join(BAKED, name + ".npz"))
    return Clip(d["q"], d["hips"], [str(b) for b in d["bones"]])


def join(clips, n=6):
    """Chain clips with a crossfade of n frames at each seam."""
    out = clips[0].copy()
    for c in clips[1:]:
        c = c.copy()
        c.root += out.root[-1] - c.root[0]
        c.yaw += out.yaw[-1] - c.yaw[0]
        m = min(n, len(out), len(c))
        w = smooth((np.arange(m) + 1) / (m + 1))
        q = nlerp(out.q[-m:], c.q[:m], w[:, None, None])
        h = out.hips[-m:] * (1 - w[:, None]) + c.hips[:m] * w[:, None]
        r = out.root[-m:] * (1 - w[:, None]) + c.root[:m] * w[:, None]
        y = out.yaw[-m:] * (1 - w) + c.yaw[:m] * w
        out = Clip(np.concatenate([out.q[:-m], q, c.q[m:]]), np.concatenate([out.hips[:-m], h, c.hips[m:]]), out.bones,
                   np.concatenate([out.root[:-m], r, c.root[m:]]), np.concatenate([out.yaw[:-m], y, c.yaw[m:]]))
    return out


def hand_paths(c):
    """World positions of both hands per frame, by forward kinematics on the clip."""
    W, P = {}, {}
    order = []
    pending = list(c.bones)
    while pending:
        for b in list(pending):
            if PARENT[b] is None or PARENT[b] in order:
                order.append(b)
                pending.remove(b)
    for b in order:
        j = c.bones.index(b)
        r = np.broadcast_to(REST[b], c.q[:, j].shape)
        d = qmul(qmul(r, c.q[:, j]), qinv(r))
        p = PARENT[b]
        if p is None:
            W[b], P[b] = d, HEADS[b] + c.hips
        else:
            off = np.broadcast_to(HEADS[b] - HEADS[p], c.hips.shape)
            P[b] = P[p] + qrot(W[p], off)
            W[b] = qmul(W[p], d)
    return P["J_Bip_L_Hand"], P["J_Bip_R_Hand"], P["J_Bip_C_Hips"]


def world_rot(c):
    """Character-space rotation change of every bone, in parent-first order."""
    D = {}
    pending = list(c.bones)
    while pending:
        for b in list(pending):
            p = PARENT[b]
            if p is None or p in D:
                j = c.bones.index(b)
                r = np.broadcast_to(REST[b], c.q[:, j].shape)
                d = qmul(qmul(r, c.q[:, j]), qinv(r))
                D[b] = d if p is None else qmul(D[p], d)
                pending.remove(b)
    return D


def mirror(c):
    """Swap left and right so a right-hand move becomes a left-hand one."""
    D = world_rot(c)
    swap = lambda n: n.replace("_L_", "_#_").replace("_R_", "_L_").replace("_#_", "_R_")
    M = {swap(b): d * np.array([1, 1, -1, -1]) for b, d in D.items()}
    out = c.copy()
    for j, b in enumerate(c.bones):
        r = np.broadcast_to(REST[b], c.q[:, j].shape)
        p = PARENT[b]
        rel = M[b] if p is None else qmul(qinv(M[p]), M[b])
        out.q[:, j] = qmul(qmul(qinv(r), rel), r)
    out.hips = c.hips * np.array([-1, 1, 1])
    out.root = c.root * np.array([-1, 1, 1])
    out.yaw = -c.yaw
    return out


def hips_yaw(c):
    """Yaw of the hips per frame in degrees, 0 when facing the character's forward."""
    d = world_rot(c)["J_Bip_C_Hips"]
    v = qrot(d, np.broadcast_to(np.array([1.0, 0, 0]), d.shape[:-1] + (3,)))
    return np.degrees(np.unwrap(np.arctan2(v[:, 1], v[:, 0])))


def straighten(c):
    """Turn the Mixamo side-on stance to face forward. Clips that hold one heading get a constant
    correction. Clips that swing keep the part of the swing past forward, so an attack starts and
    ends straight and still turns into the hit. Returns the correction curve."""
    y = hips_yaw(c)
    if np.ptp(y) < 25:
        corr = np.full(len(c), -float(np.median(y)))
    else:
        raw = np.maximum(-y, 0)
        corr = np.convolve(np.pad(raw, 2, mode="edge"), np.ones(5) / 5, mode="valid")
        corr[:2], corr[-2:] = raw[:2], raw[-2:]  # ends must land exactly, so clips chain cleanly
    c.add("J_Bip_C_Hips", (0, 0, 1), corr)
    # In the stance the head already looks forward, so it must not turn with the body.
    c.add("C_Neck", (0, 0, 1), -corr / 2).add("C_Head", (0, 0, 1), -corr / 2)
    return corr


def foot_z(c):
    """Lowest ankle height per frame."""
    D = world_rot(c)
    res = []
    for side in ("L", "R"):
        p = HEADS["J_Bip_C_Hips"] + c.hips
        prev = "J_Bip_C_Hips"
        for b in (f"J_Bip_{side}_UpperLeg", f"J_Bip_{side}_LowerLeg", f"J_Bip_{side}_Foot"):
            p = p + qrot(D[prev], np.broadcast_to(HEADS[b] - HEADS[prev], c.hips.shape))
            prev = b
        res.append(p[:, 2])
    return np.minimum(res[0], res[1])


def ground(c, ankle=0.086):
    """Shift the whole clip up or down so the planted foot sits on the floor."""
    c.hips[:, 2] += ankle - float(np.median(foot_z(c)))
    return c
