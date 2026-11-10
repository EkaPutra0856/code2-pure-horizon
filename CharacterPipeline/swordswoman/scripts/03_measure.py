# Prints bone positions and torso/limb cross-sections of the swordswoman body, for fitting the outfit.
import bpy, json, math
import numpy as np
arm = bpy.data.objects["Armature"]
body = bpy.data.objects["Body"]
mw = arm.matrix_world
out = {}
for b in arm.data.bones:
    if b.name.startswith("J_Bip") and not any(k in b.name for k in ("Thumb", "Index", "Middle", "Ring", "Little")):
        out[b.name] = [round(x, 3) for x in (mw @ b.head_local)] + [round(x, 3) for x in (mw @ b.tail_local)]
print("BONES", json.dumps(out))
print("SEC", [b.name for b in arm.data.bones if not b.name.startswith("J_Bip")][:60])
P = np.array([body.matrix_world @ v.co for v in body.data.vertices])
mi = np.array([p.material_index for p in body.data.polygons])
print("matslots", [m.name for m in body.data.materials], "polys per slot", np.bincount(mi).tolist())
# body-only verts (slot 0)
used = set()
for p in body.data.polygons:
    if p.material_index == 0:
        used.update(p.vertices)
B = P[sorted(used)]
torso = B[np.abs(B[:, 0]) < 0.2]
for z in np.arange(0.05, 1.45, 0.05):
    s = torso[np.abs(torso[:, 2] - z) < 0.012]
    if len(s):
        print("Z %.2f x[%.3f,%.3f] y[%.3f,%.3f]" % (z, s[:, 0].min(), s[:, 0].max(), s[:, 1].min(), s[:, 1].max()))
# other slot: HairBack on body? where
o = P[sorted({v for p in body.data.polygons if p.material_index == 1 for v in p.vertices})]
if len(o):
    print("slot1 bbox", o.min(0).round(3).tolist(), o.max(0).round(3).tolist(), len(o))
