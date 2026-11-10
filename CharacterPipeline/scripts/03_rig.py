# Replaces the VRoid hair with Hair_New: removes the old hair mesh and bones,
# builds new bone chains, and skins hair, ears and flowers to the armature.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, math, json
from mathutils import Vector

arm = bpy.data.objects["Armature"]
HEAD = "J_Bip_C_Head"

old = bpy.data.objects.get("Hair")
if old:
    me = old.data
    bpy.data.objects.remove(old, do_unlink=True)
    bpy.data.meshes.remove(me)

chains = {}
for s, tag in ((1, "L"), (-1, "R")):
    for c in range(5):
        f = c / 4
        x0 = s * (0.03 + 0.10 * (1 - f))
        x1 = s * (0.04 + 0.20 * (1 - f))
        top = Vector((x0, 0.135 - 0.03 * (1 - f), 1.40))
        end = Vector((x1, 0.115, 1.06))
        chains[f"Back{tag}{c}"] = [top.lerp(end, i / 5) for i in range(6)]
chains["LockL"] = [Vector(p) for p in ((.150, -.075, 1.40), (.142, -.095, 1.30), (.172, -.105, 1.21),
                                       (.150, -.105, 1.14), (.186, -.095, 1.06))]
chains["BraidR"] = [Vector(p) for p in ((-.152, -.05, 1.42), (-.158, -.075, 1.33), (-.160, -.105, 1.22),
                                        (-.160, -.115, 1.12), (-.158, -.115, 1.03))]

bpy.context.view_layer.objects.active = arm
arm.hide_set(False)
arm.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
eb = arm.data.edit_bones
removed = 0
for b in [b for b in eb if "Hair" in b.name]:
    eb.remove(b)
    removed += 1
inv = arm.matrix_world.inverted()
names = {}
for cname, pts in chains.items():
    parent = eb[HEAD]
    names[cname] = []
    for i in range(len(pts) - 1):
        b = eb.new(f"J_Sec_HairNew_{cname}_{i + 1:02d}")
        b.head = inv @ pts[i]
        b.tail = inv @ pts[i + 1]
        b.parent = parent
        b.use_connect = i > 0
        parent = b
        names[cname].append(b.name)
bpy.ops.object.mode_set(mode="OBJECT")

segs = []
for cname, pts in chains.items():
    for i, bn in enumerate(names[cname]):
        segs.append((bn, pts[i], pts[i + 1]))


def seg_dist(p, a, b):
    ab = b - a
    t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
    return (p - (a + ab * t)).length


def skin(ob, rigid=False):
    ob.parent = arm
    ob.matrix_parent_inverse = arm.matrix_world.inverted()
    ob.vertex_groups.clear()
    groups = {}

    def grp(n):
        if n not in groups:
            groups[n] = ob.vertex_groups.new(name=n)
        return groups[n]

    for v in ob.data.vertices:
        p = ob.matrix_world @ v.co
        if rigid or p.z > 1.42:
            grp(HEAD).add([v.index], 1.0, "REPLACE")
            continue
        near = sorted(((seg_dist(p, a, b), n) for n, a, b in segs), key=lambda x: x[0])[:2]
        w = [1 / (d + 0.004) ** 2 for d, _ in near]
        tot = sum(w)
        hw = max(0.0, min(1.0, (p.z - 1.36) / 0.06))  # blend into the head near the top
        for (d, n), wi in zip(near, w):
            grp(n).add([v.index], wi / tot * (1 - hw), "REPLACE")
        if hw > 0:
            grp(HEAD).add([v.index], hw, "REPLACE")
    if not any(m.type == "ARMATURE" for m in ob.modifiers):
        m = ob.modifiers.new("Armature", "ARMATURE")
        m.object = arm


skin(bpy.data.objects["Hair_New"])
skin(bpy.data.objects["Hair_Band"])
skin(bpy.data.objects["Ears_Elf"], rigid=True)
skin(bpy.data.objects["Flowers"], rigid=True)

ext = arm.data.vrm_addon_extension
sa = ext.vrm0.secondary_animation
print("bones removed", removed, "chains", len(chains), "bones now", len(arm.data.bones))
print("spring groups", len(sa.bone_groups), "collider groups", len(sa.collider_groups))
if len(sa.bone_groups):
    g = sa.bone_groups[0]
    print("group fields", [p.identifier for p in g.bl_rna.properties if p.identifier != "rna_type"])
    print("bones in g0", [b.bone_name for b in g.bones][:4])
    print("collider field", [p.identifier for p in g.collider_groups[0].bl_rna.properties] if len(g.collider_groups) else None)
print("export op", "vrm" in dir(bpy.ops.export_scene))
with open(os.path.join(ANIME_GAME_ROOT, r"scripts\_bridge\chains.json"), "w") as fh:
    json.dump(names, fh)
bpy.ops.wm.save_mainfile()
