# Anime-style makeup baked into the face skin texture (blender -b --python 25_face_makeup.py).
# Reads export_unreal/sw_ue.fbx and export_unreal/sw_ue.fbm/04.png (the VRoid face skin), writes
# textures/face_makeup.png (+ renders/_face_makeup_preview.png). Script 26 (in Unreal) swaps it in.
#
# Placement comes from the face itself: the eye and mouth centres are the vertices the
# Fcl_EYE_Close_L/R and Fcl_MTH_A blend shapes move, so it follows this face's proportions.
# Every texel of the skin gets its 3D position and normal (rasterised in UV space), and the
# makeup is a function of where that texel sits on the face:
#   - blush under each eye, eyeshadow over the lid, lip tint, a touch on the nose tip
#   - soft warm shade where the face turns away (sides, under the jaw) so it reads less flat
# Layers multiply the base colour, so the painted detail of the VRoid texture stays.
import math
import os

import bpy
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FBX = os.path.join(ROOT, "export_unreal", "sw_ue.fbx")
SRC = os.path.join(ROOT, "export_unreal", "sw_ue.fbm", "04.png")
OUT = os.path.join(ROOT, "textures", "face_makeup.png")
PREVIEW = os.path.join(ROOT, "renders", "_face_makeup_preview.png")

# (multiply colour, strength) per layer
BLUSH = ((1.0, 0.58, 0.60), 0.55)
SHADOW = ((0.86, 0.50, 0.46), 0.42)
LIPS = ((0.95, 0.50, 0.52), 0.55)
NOSE = ((1.0, 0.70, 0.70), 0.30)
TURN = ((0.90, 0.76, 0.74), 0.4)


def say(*a):
    print("RESULT", *a)


bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.fbx(filepath=FBX)
face = next(o for o in bpy.data.objects if o.type == "MESH" and o.data.shape_keys and "Fcl_MTH_A" in o.data.shape_keys.key_blocks)
me = face.data
kb = me.shape_keys.key_blocks
base = np.array([v.co for v in kb[0].data], dtype=np.float64)


def moved(name):
    d = np.linalg.norm(np.array([v.co for v in kb[name].data]) - base, axis=1)
    sel = d > d.max() * 0.35
    return base[sel].mean(axis=0)


eye_l, eye_r, mouth = moved("Fcl_EYE_Close_L"), moved("Fcl_EYE_Close_R"), moved("Fcl_MTH_A")
mid = (eye_l + eye_r) / 2
side = eye_r - eye_l
d_eye = np.linalg.norm(side)
side /= d_eye
up = mid - mouth
h = np.linalg.norm(up)
up = up - side * np.dot(up, side)
up /= np.linalg.norm(up)
fwd = np.cross(side, up)
# The face points away from the head centre: flip fwd if the vertices sit mostly in front of it.
if np.dot(base.mean(axis=0) - mid, fwd) > 0:
    fwd = -fwd
say("eyes", d_eye.round(2), "eye-mouth", h.round(2))

# Skin texture
img = bpy.data.images.load(SRC)
W, H = img.size
px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
pos = np.zeros((H, W, 3))
nrm = np.zeros((H, W, 3))
cover = np.zeros((H, W), dtype=np.int32)
# Several parts of the head share texels (11% overlap): keep the frontmost surface, the one the camera sees.
zbuf = np.full((H, W), -1e9)

skin_slots = {i for i, m in enumerate(me.materials) if m and "Face_00_SKIN" in m.name}
uv = me.uv_layers.active.data
me.calc_loop_triangles()
vnorm = np.array([v.normal for v in me.vertices])
for tri in me.loop_triangles:
    if tri.material_index not in skin_slots:
        continue
    t_uv = np.array([uv[l].uv for l in tri.loops]) * (W, H)
    t_p = base[list(tri.vertices)]
    t_n = vnorm[list(tri.vertices)]
    x0, y0 = np.floor(t_uv.min(axis=0)).astype(int)
    x1, y1 = np.ceil(t_uv.max(axis=0)).astype(int)
    x0, y0, x1, y1 = max(x0, 0), max(y0, 0), min(x1, W - 1), min(y1, H - 1)
    if x1 < x0 or y1 < y0:
        continue
    gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
    (ax, ay), (bx, by), (cx, cy) = t_uv
    den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
    if abs(den) < 1e-9:
        continue
    w0 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
    w1 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
    w2 = 1 - w0 - w1
    m = (w0 >= -0.02) & (w1 >= -0.02) & (w2 >= -0.02)
    if not m.any():
        continue
    ws = np.stack([w0, w1, w2], axis=-1)[m]
    yy, xx = np.nonzero(m)
    yy, xx = yy + y0, xx + x0
    p = ws @ t_p
    z = (p - mid) @ fwd
    win = z > zbuf[yy, xx]
    yy, xx, p, z = yy[win], xx[win], p[win], z[win]
    pos[yy, xx] = p
    nrm[yy, xx] = (ws @ t_n)[win]
    zbuf[yy, xx] = z
    cover[yy, xx] += 1
say("skin texels", int((cover > 0).sum()), "overlapping", int((cover > 1).sum()))

# Face-frame coordinates of every texel, in units of the eye spacing (x) and eye-mouth height (y).
rel = pos - mid
X = (rel @ side) / d_eye
Y = (rel @ up) / h
Z = (rel @ fwd) / d_eye
N = nrm / np.maximum(np.linalg.norm(nrm, axis=-1, keepdims=True), 1e-6)
mask = cover > 0
front = np.clip(N @ fwd, 0, 1)


def blob(cx, cy, rx, ry):
    return np.exp(-(((X - cx) / rx) ** 2 + ((Y - cy) / ry) ** 2)) * mask


def smooth(e0, e1, v):
    t = np.clip((v - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


layers = []
# Blush: under each eye, toward the outside of the cheek. Faint diagonal strokes inside it (anime blush).
blush = blob(-0.55, -0.42, 0.30, 0.17) + blob(0.55, -0.42, 0.30, 0.17)
strokes = 0.85 + 0.15 * np.cos((X * 1.0 + Y * 0.6) * 2 * math.pi * 9.0)
layers.append((BLUSH, np.clip(blush * strokes, 0, 1) * (Z > -0.2)))
# Eyeshadow: on the lid above each eye, deepest at the outer corner, fading up to the brow.
lid = (blob(-0.55, 0.05, 0.30, 0.17) + blob(0.55, 0.05, 0.30, 0.17)) * smooth(-0.14, 0.05, Y)
outer = 0.65 + 0.35 * smooth(0.35, 0.75, np.abs(X))
layers.append((SHADOW, np.clip(lid * outer, 0, 1)))
# Lips: a soft tint on the mouth (the drawn mouth line stays: this multiplies it).
layers.append((LIPS, blob(0.0, -1.0, 0.20, 0.07)))
# Nose tip
layers.append((NOSE, blob(0.0, -0.62, 0.07, 0.06)))
# Turn shade: toward the sides of the face and under the jaw, a warm darker tone (cel-style form).
# Measured by position, not normals: the VRoid face has split normals along the eye line.
turn = smooth(0.6, 1.2, np.abs(X)) * mask
jaw = smooth(-0.95, -1.35, Y) * mask
layers.append((TURN, np.clip(np.maximum(turn, jaw), 0, 1)))

col = px[..., :3].astype(np.float64)
for (tint, strength), w in layers:
    k = (w * strength)[..., None]
    col = col * (1 - k) + col * np.array(tint) * k
say("layer peaks", [round(float(w.max()), 2) for _, w in layers])

px[..., :3] = col.astype(np.float32)
os.makedirs(os.path.dirname(OUT), exist_ok=True)
out = bpy.data.images.new("face_makeup", W, H, alpha=True)
out.pixels[:] = px.ravel()
out.filepath_raw = OUT
out.file_format = "PNG"
out.save()
say("wrote", OUT)

# Preview: layer weights as colour (R blush, G eyeshadow, B turn shade), for a quick look.
wimg = np.stack([layers[0][1], layers[1][1], layers[4][1], np.ones((H, W))], axis=-1)
pv = bpy.data.images.new("face_makeup_preview", W, H, alpha=True)
pv.pixels[:] = wimg.astype(np.float32).ravel()
pv.filepath_raw = PREVIEW
pv.file_format = "PNG"
pv.save()
say("preview", PREVIEW, "Y range at skin", float(Y[mask].min()), float(Y[mask].max()), "X range", float(X[mask].min()), float(X[mask].max()))
