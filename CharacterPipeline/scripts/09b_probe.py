import bpy
import numpy as np
sc = bpy.context.scene
print("engine", sc.render.engine, "res", sc.render.resolution_x, sc.render.resolution_y, "ortho", bpy.data.objects["RefCam"].data.type, bpy.data.objects["RefCam"].data.ortho_scale)
body = bpy.data.objects["Body"]
co = np.array([body.matrix_world @ v.co for v in body.data.vertices])
foot = co[(co[:, 2] < 0.12) & (co[:, 0] > 0)]
for z in (0.005, 0.02, 0.04, 0.06, 0.08, 0.1):
    s = foot[np.abs(foot[:, 2] - z) < 0.01]
    if len(s):
        print("foot z", z, "x", s[:, 0].min().round(3), s[:, 0].max().round(3), "y", s[:, 1].min().round(3), s[:, 1].max().round(3))
for y in np.arange(-0.2, 0.1, 0.03):
    s = foot[np.abs(foot[:, 1] - y) < 0.012]
    if len(s):
        print("foot y", round(float(y), 2), "x", s[:, 0].min().round(3), s[:, 0].max().round(3), "z", s[:, 2].min().round(3), s[:, 2].max().round(3))
hair = bpy.data.objects["Hair_New"]
h = np.array([hair.matrix_world @ v.co for v in hair.data.vertices])
for z in np.arange(0.85, 1.35, 0.05):
    s = h[np.abs(h[:, 2] - z) < 0.02]
    if len(s):
        print("hair z", round(float(z), 2), "x", s[:, 0].min().round(3), s[:, 0].max().round(3), "y", s[:, 1].min().round(3), s[:, 1].max().round(3))
print("hair zmin", h[:, 2].min().round(3))
vg = {g.index: g.name for g in body.vertex_groups}
print("body groups", sorted(n for n in vg.values() if "J_Sec" in n)[:12])
print("slots", [(i, m.name) for i, m in enumerate(body.data.materials)], "faces by mat", np.bincount([p.material_index for p in body.data.polygons]))
