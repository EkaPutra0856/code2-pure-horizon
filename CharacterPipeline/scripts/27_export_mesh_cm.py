# Run in a background Blender. Writes karakter_ue.fbx with the skeleton truly in centimetres.
# An FBX exported at metre scale puts a x100 scale on the Root bone in Unreal, which leaves bone
# offsets in the reference pose 100 times too small and breaks retargeting.
# Applies the scale to the armature and meshes, checks each evaluated mesh grew exactly 100 times,
# and never saves back to the .blend. Run scripts/12_export_ue.py first for textures and physics data.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, os, re, sys
from mathutils import Vector

ROOT = ANIME_GAME_ROOT
OUT = os.path.join(ROOT, "export_unreal")
TEX = os.path.join(OUT, "textures")
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT, "karakter_rambut.blend"))
sc = bpy.context.scene
arm = bpy.data.objects["Armature"]
ad = arm.animation_data
if ad:
    ad.action = None
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
for pb in arm.pose.bones:
    pb.matrix_basis.identity()
meshes = [o for o in sc.objects if o.type == "MESH"]
SCALED = {"SOLIDIFY": ["thickness"], "DISPLACE": ["strength"], "SHRINKWRAP": ["offset"], "BEVEL": ["width"], "WELD": ["merge_threshold"],
          "MIRROR": ["merge_threshold"], "WIREFRAME": ["thickness"], "SCREW": ["screw_offset"]}


def size(o):
    dg = bpy.context.evaluated_depsgraph_get()
    e = o.evaluated_get(dg)
    pts = [e.matrix_world @ Vector(c) for c in e.bound_box]
    return Vector((max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)))


bpy.context.view_layer.update()
before = {o.name: size(o) for o in meshes}
kinds = {}
for o in meshes:
    for m in o.modifiers:
        kinds[m.type] = kinds.get(m.type, 0) + 1
print("RESULT modifiers", kinds)
print("RESULT parents", {o.parent.name if o.parent else None for o in meshes}, "scales", {tuple(round(s, 4) for s in o.scale) for o in meshes}, "arm", tuple(arm.scale))

for o in meshes:
    if o.data.users > 1:
        o.data = o.data.copy()
    for m in o.modifiers:
        for prop in SCALED.get(m.type, []):
            setattr(m, prop, getattr(m, prop) * 100)

sc.unit_settings.system = "METRIC"
sc.unit_settings.scale_length = 0.01
bpy.ops.object.select_all(action="DESELECT")
for o in [arm] + meshes:
    o.hide_set(False)
    o.select_set(True)
bpy.context.view_layer.objects.active = arm
arm.scale = tuple(s * 100 for s in arm.scale)
for o in meshes:
    if o.parent is None:
        o.scale = tuple(s * 100 for s in o.scale)
        o.location = tuple(c * 100 for c in o.location)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
bpy.context.view_layer.update()

bad = []
for o in meshes:
    a, b = before[o.name], size(o)
    for i in range(3):
        if a[i] > 1e-4 and abs(b[i] / a[i] - 100) > 0.5:
            bad.append((o.name, i, round(a[i], 4), round(b[i], 3)))
            break
print("RESULT bad", len(bad), bad[:12])
print("RESULT arm scale", tuple(arm.scale), "foot head z", round((arm.matrix_world @ arm.data.bones["J_Bip_L_Foot"].head_local).z, 2))
print("RESULT tallest", round(max(size(o).z for o in meshes), 2))
if bad:
    print("RESULT stopped, nothing exported")
    sys.exit(1)


def lit_image(m):
    if not m or not m.use_nodes:
        return None
    n = m.node_tree.nodes.get("Image Texture")
    if n and n.image:
        return n.image
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            return n.image
    return None


def clean_name(n):
    return re.sub(r"[^A-Za-z0-9_]+", "_", n.replace(" (Instance)", "")).strip("_")


made = {}
for o in meshes:
    for i, slot in enumerate(o.material_slots):
        m = slot.material
        if m is None or m.name.startswith("M_Outfit"):
            continue
        if m.name not in made:
            im = lit_image(m)
            p = bpy.data.materials.new("M_" + clean_name(m.name))
            p.use_nodes = True
            b = p.node_tree.nodes["Principled BSDF"]
            if im:
                path = os.path.join(TEX, clean_name(os.path.splitext(im.name)[0]) + ".png")
                t = p.node_tree.nodes.new("ShaderNodeTexImage")
                t.image = bpy.data.images.load(path, check_existing=True)
                p.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
            made[m.name] = p
        o.material_slots[i].material = made[m.name]

r = bpy.ops.export_scene.fbx(
    filepath=os.path.join(OUT, "karakter_ue.fbx"), object_types={"ARMATURE", "MESH"}, use_mesh_modifiers=True,
    mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False, bake_anim=False,
    primary_bone_axis="Y", secondary_bone_axis="X", axis_forward="-Y", axis_up="Z",
    apply_scale_options="FBX_SCALE_NONE", apply_unit_scale=True, global_scale=1.0,
    path_mode="COPY", embed_textures=True)
print("RESULT exported", r, "materials", len(made))
