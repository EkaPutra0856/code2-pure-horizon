# Read-only survey of the body before modelling the outfit: objects, key bones, body cross-sections.
import bpy
import numpy as np

arm = bpy.data.objects["Armature"]
print("OBJECTS")
for o in bpy.data.objects:
    if o.type == "MESH":
        print(" ", o.name, "verts", len(o.data.vertices), "mats", [m.name for m in o.data.materials if m],
              "vgroups", len(o.vertex_groups), "shapekeys", len(o.data.shape_keys.key_blocks) if o.data.shape_keys else 0)
    else:
        print(" ", o.name, o.type)
print("arm matrix", [round(x, 3) for x in arm.matrix_world.translation], "scale", arm.scale[:], "bones", len(arm.data.bones))

print("BONES")
for b in arm.data.bones:
    if "J_Bip" in b.name or b.parent is None:
        h, t = arm.matrix_world @ b.head_local, arm.matrix_world @ b.tail_local
        if "Hand" in b.name and any(k in b.name for k in ("Index", "Middle", "Ring", "Little", "Thumb")):
            continue
        print(" ", b.name, "<-", b.parent.name if b.parent else None,
              [round(x, 3) for x in h], [round(x, 3) for x in t])
print("OTHER SEC", sorted({b.name.rsplit("_", 1)[0] for b in arm.data.bones if "J_Sec" in b.name and "HairNew" not in b.name}))

body = next(o for o in bpy.data.objects if o.type == "MESH" and "Body" in o.name)
print("BODY OBJECT", body.name)
co = np.array([body.matrix_world @ v.co for v in body.data.vertices])
print("bounds", co.min(axis=0).round(3), co.max(axis=0).round(3))
print("Z-SLICES (center torso/legs, |x| limits per z)")
for z in np.arange(0.05, 1.46, 0.05):
    s = co[np.abs(co[:, 2] - z) < 0.012]
    if len(s) == 0:
        continue
    r = s[s[:, 0] > 0.002]
    if len(r) == 0:
        continue
    print(" z", round(float(z), 2), "x", r[:, 0].min().round(3), r[:, 0].max().round(3),
          "y", s[:, 1].min().round(3), s[:, 1].max().round(3), "n", len(s))
print("ARM SLICES (x, y and z limits)")
for x in np.arange(0.15, 0.75, 0.06):
    s = co[np.abs(co[:, 0] - x) < 0.01]
    s = s[s[:, 2] > 1.1]
    if len(s):
        print(" x", round(float(x), 2), "y", s[:, 1].min().round(3), s[:, 1].max().round(3),
              "z", s[:, 2].min().round(3), s[:, 2].max().round(3))
