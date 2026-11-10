import bpy, json
from mathutils import Vector
out = {}
for name in ("Body", "Face"):
    o = bpy.data.objects[name]
    vs = [o.matrix_world @ v.co for v in o.data.vertices if (o.matrix_world @ v.co).z > 1.30]
    out[name] = {"n": len(vs), "min": [round(min(v[i] for v in vs), 4) for i in range(3)],
                 "max": [round(max(v[i] for v in vs), 4) for i in range(3)]}
# skull profile: widest x and y extents per height slice
vs = []
for name in ("Body", "Face"):
    o = bpy.data.objects[name]
    vs += [o.matrix_world @ v.co for v in o.data.vertices]
prof = []
for z in [1.62, 1.60, 1.56, 1.52, 1.48, 1.44, 1.40, 1.36, 1.32]:
    s = [v for v in vs if abs(v.z - z) < 0.01]
    if s:
        prof.append({"z": z, "x": round(max(abs(v.x) for v in s), 4),
                     "ymin": round(min(v.y for v in s), 4), "ymax": round(max(v.y for v in s), 4)})
out["profile"] = prof
# shoulders / chest clearance for hair fall
s = [v for v in vs if 1.05 < v.z < 1.30]
out["torso_ymax"] = round(max(v.y for v in s), 4)
out["torso_ymin"] = round(min(v.y for v in s), 4)
# ear position: outermost x on the face mesh
f = bpy.data.objects["Face"]
ear = max((f.matrix_world @ v.co for v in f.data.vertices), key=lambda p: p.x)
out["ear_tip"] = [round(c, 4) for c in ear]
print(json.dumps(out))
