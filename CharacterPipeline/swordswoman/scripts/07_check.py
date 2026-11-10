# Self-check for the outfit: lists every pair of visible meshes whose surfaces intersect (triangle overlap via
# BVHTree.overlap on the evaluated meshes, so the body's Outfit_Mask is respected), with where they cross.
# Usage: blender -b <file.blend> --python scripts/07_check.py [-- name_prefix ...]
import bpy, bmesh, sys, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
dg = bpy.context.evaluated_depsgraph_get()
objs = [o for o in bpy.data.objects if o.type == "MESH" and o.visible_get() and not o.hide_render
        and (o.name.startswith("SW_") or o.name in ("Body", "Face", "Hair"))]
trees, polys = {}, {}
for o in objs:
    ev = o.evaluated_get(dg)
    me = ev.to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.transform(o.matrix_world)
    bmesh.ops.triangulate(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    trees[o.name] = BVHTree.FromBMesh(bm)
    polys[o.name] = [f.calc_center_median().copy() for f in bm.faces]
    bm.free()
    ev.to_mesh_clear()

names = sorted(trees)
rows = []
for i, a in enumerate(names):
    for b in names[i + 1:]:
        if args and not any(a.startswith(p) or b.startswith(p) for p in args):
            continue
        ov = trees[a].overlap(trees[b])
        if not ov:
            continue
        pts = [polys[a][x] for x, _ in ov]
        c = sum(pts, Vector()) / len(pts)
        lo = [round(min(p[k] for p in pts), 3) for k in range(3)]
        hi = [round(max(p[k] for p in pts), 3) for k in range(3)]
        rows.append((len(ov), a, b, [round(x, 3) for x in c], lo, hi))
rows.sort(key=lambda r: -r[0])
for r in rows:
    print("HIT %6d  %-22s %-22s c=%s  lo=%s hi=%s" % r)
print("CHECK pairs", len(rows), "tris", sum(r[0] for r in rows))
