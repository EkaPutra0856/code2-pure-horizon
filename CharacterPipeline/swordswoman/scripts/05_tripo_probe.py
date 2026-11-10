# Probes the Tripo GLBs: decimates each, splits loose parts, clusters overlapping parts into items,
# and saves tripo/<name>_lo.blend plus a front render with the cluster numbers so items can be identified.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import sys, os, json
import bpy, bmesh
from mathutils import Vector

ROOT = os.path.join(ANIME_GAME_ROOT, r"swordswoman")
TRI = 60000  # target triangles per sheet before splitting


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


def bbox(o):
    ws = [o.matrix_world @ Vector(c) for c in o.bound_box]
    return Vector([min(v[i] for v in ws) for i in range(3)]), Vector([max(v[i] for v in ws) for i in range(3)])


def probe(name):
    clear()
    bpy.ops.import_scene.gltf(filepath=os.path.join(ROOT, "tripo", name + ".glb"))
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    info = {"name": name, "objects": [(o.name, len(o.data.polygons)) for o in meshes],
            "images": [(i.name, list(i.size)) for i in bpy.data.images]}
    # Apply transforms, join, decimate.
    bpy.ops.object.select_all(action="DESELECT")
    for o in meshes:
        o.select_set(True)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    for o in [o for o in bpy.data.objects if o.type != "MESH"]:
        bpy.data.objects.remove(o, do_unlink=True)
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    m = ob.modifiers.new("dec", "DECIMATE")
    m.ratio = min(1.0, TRI / max(tris, 1))
    bpy.ops.object.modifier_apply(modifier="dec")
    info["tris_in"] = tris
    # Split loose parts.
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.separate(type="LOOSE")
    bpy.ops.object.mode_set(mode="OBJECT")
    parts = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    bbs = []
    for o in parts:
        a, b = bbox(o)
        bbs.append((a, b))
        lo = Vector([min(lo[i], a[i]) for i in range(3)])
        hi = Vector([max(hi[i], b[i]) for i in range(3)])
    pad = (hi - lo).length * 0.004
    # Union-find of overlapping (padded) bounding boxes.
    par = list(range(len(parts)))

    def f(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            a1, b1 = bbs[i]
            a2, b2 = bbs[j]
            if all(a1[k] - pad <= b2[k] and a2[k] - pad <= b1[k] for k in range(3)):
                par[f(i)] = f(j)
    groups = {}
    for i in range(len(parts)):
        groups.setdefault(f(i), []).append(i)
    items = []
    for gi, (root, idx) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1]))):
        objs = [parts[i] for i in idx]
        bpy.ops.object.select_all(action="DESELECT")
        for o in objs:
            o.select_set(True)
        bpy.context.view_layer.objects.active = objs[0]
        if len(objs) > 1:
            bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active
        o.name = "%s_%02d" % (name, gi)
        a, b = bbox(o)
        items.append({"obj": o.name, "tris": len(o.data.polygons), "min": [round(x, 3) for x in a],
                      "max": [round(x, 3) for x in b]})
    info["items"] = sorted(items, key=lambda d: -d["tris"])
    info["extent"] = [[round(x, 3) for x in lo], [round(x, 3) for x in hi]]
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(ROOT, "tripo", name + "_lo.blend"))
    render(name, items, lo, hi)
    return info


def render(name, items, lo, hi):
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 800
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.3, 0.3, 0.3, 1)
    cd = bpy.data.cameras.new("C")
    cd.type = "ORTHO"
    c = (lo + hi) / 2
    cd.ortho_scale = max(hi.x - lo.x, hi.z - lo.z) * 1.15
    cam = bpy.data.objects.new("C", cd)
    sc.collection.objects.link(cam)
    cam.location = c + Vector((0, -(hi.y - lo.y) - 5, 0))
    cam.rotation_euler = (1.5708, 0, 0)
    sc.camera = cam
    for it in items:
        o = bpy.data.objects[it["obj"]]
        a, b = bbox(o)
        cu = bpy.data.curves.new(it["obj"], "FONT")
        cu.body = it["obj"].split("_")[-1]
        cu.size = cd.ortho_scale * 0.05
        t = bpy.data.objects.new("T" + it["obj"], cu)
        sc.collection.objects.link(t)
        t.location = Vector(((a.x + b.x) / 2, lo.y - 0.5, b.z))
        t.rotation_euler = (1.5708, 0, 0)
        mt = bpy.data.materials.new("red")
        mt.use_nodes = True
        e = mt.node_tree.nodes.new("ShaderNodeEmission")
        e.inputs[0].default_value = (1, 0.1, 0.1, 1)
        mt.node_tree.links.new(e.outputs[0], mt.node_tree.nodes["Material Output"].inputs[0])
        cu.materials.append(mt)
    sd = bpy.data.lights.new("S", "SUN")
    sd.energy = 3
    s = bpy.data.objects.new("S", sd)
    sc.collection.objects.link(s)
    s.rotation_euler = (0.9, 0.2, 0.3)
    sc.render.filepath = os.path.join(ROOT, "tripo", "_probe_" + name + ".png")
    bpy.ops.render.render(write_still=True)


names = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else ["A_props", "B_armor", "C_hair", "D_bracers", "E_sword", "F_scabbard"]
res = [probe(n) for n in names]
with open(os.path.join(ROOT, "tripo", "_probe.json"), "w") as fh:
    json.dump(res, fh, indent=1)
print("PROBE", json.dumps(res))
