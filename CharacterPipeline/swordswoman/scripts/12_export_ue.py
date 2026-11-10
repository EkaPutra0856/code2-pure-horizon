# Unreal export for the swordswoman. Run in a background Blender on sw_outfit_v4.blend:
#   blender -b sw_outfit_v4.blend --python-exit-code 1 --python scripts/12_export_ue.py
# Writes export_unreal/sw_ue.fbx (skeleton truly in centimetres), textures/*.png and
# ue_physics_setup.json. Never saves the .blend.
# Same rules as the main character's scripts 12 + 27: MToon materials carry no FBX texture,
# so each MToon slot is swapped to a plain Principled material with its lit image. A metre-scale
# FBX puts x100 on the Root bone in Unreal and breaks retargeting, so scale is applied first and
# every evaluated mesh is checked to have grown exactly 100 times.
import bpy, json, os, re, shutil, sys
from mathutils import Vector

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "export_unreal")
TEX = os.path.join(OUT, "textures")
os.makedirs(TEX, exist_ok=True)
sc = bpy.context.scene
arm = bpy.data.objects["Armature"]
ad = arm.animation_data
if ad:
    ad.action = None
    for t in list(ad.nla_tracks):
        ad.nla_tracks.remove(t)
for pb in arm.pose.bones:
    pb.matrix_basis.identity()
meshes = [o for o in sc.objects if o.type == "MESH" and not o.hide_render]
SCALED = {"SOLIDIFY": ["thickness"], "DISPLACE": ["strength"], "SHRINKWRAP": ["offset"], "BEVEL": ["width"],
          "WELD": ["merge_threshold"], "MIRROR": ["merge_threshold"], "WIREFRAME": ["thickness"]}


def clean_name(n):
    return re.sub(r"[^A-Za-z0-9_]+", "_", n.replace(" (Instance)", "")).strip("_")


saved = {}


def export_image(im):
    if im.name in saved:
        return saved[im.name]
    path = os.path.join(TEX, clean_name(os.path.splitext(im.name)[0]) + ".png")
    src = bpy.path.abspath(im.filepath)
    if im.packed_file and src.lower().endswith(".png"):
        with open(path, "wb") as fh:
            fh.write(im.packed_file.data)
    elif os.path.isfile(src) and src.lower().endswith(".png"):
        shutil.copyfile(src, path)
    else:
        im2 = im.copy()
        im2.filepath_raw = path
        im2.file_format = "PNG"
        im2.save()
        bpy.data.images.remove(im2)
    saved[im.name] = bpy.data.images.load(path, check_existing=True)
    return saved[im.name]


def lit_image(m):
    n = m.node_tree.nodes.get("Image Texture")
    if n and n.type == "TEX_IMAGE" and n.image:
        return n.image
    for n in m.node_tree.nodes:
        if n.type == "TEX_IMAGE" and n.image:
            return n.image
    return None


# material swap: MToon (group-node) materials -> Principled with the lit texture.
# Tripo materials are already Principled; their images are re-pointed at exported PNGs.
made, table = {}, {}
for o in meshes:
    for i, slot in enumerate(o.material_slots):
        m = slot.material
        if m is None or not m.use_nodes:
            continue
        principled = any(n.type == "BSDF_PRINCIPLED" for n in m.node_tree.nodes)
        if principled:
            if m.name not in made:
                for n in m.node_tree.nodes:
                    if n.type == "TEX_IMAGE" and n.image:
                        n.image = export_image(n.image)
                m.name = "M_" + clean_name(m.name)
                made[m.name] = m
                table[m.name] = [os.path.basename(n.image.filepath) for n in m.node_tree.nodes if n.type == "TEX_IMAGE" and n.image]
            continue
        if m.name not in made:
            im = lit_image(m)
            p = bpy.data.materials.new("M_" + clean_name(m.name))
            p.use_nodes = True
            b = p.node_tree.nodes["Principled BSDF"]
            b.inputs["Roughness"].default_value = 0.8
            if im:
                t = p.node_tree.nodes.new("ShaderNodeTexImage")
                t.image = export_image(im)
                p.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
                if m.blend_method in ("BLEND", "CLIP", "HASHED"):
                    p.node_tree.links.new(t.outputs["Alpha"], b.inputs["Alpha"])
                    p.blend_method = "CLIP"
                table[p.name] = [os.path.basename(t.image.filepath)]
            made[m.name] = p
        o.material_slots[i].material = made[m.name]
print("RESULT materials", len(table))

# VRoid's eye white bulges up to ~1.7 mm in front of the iris and relies on MToon render order to
# stay behind it; Unreal sorts by depth. Move every EyeWhite vertex back (+y, the character faces -y)
# until it sits behind the iris, in the basis and every shape key alike, so blinks keep their shape.
# Safety margin only: the blank eyes seen in Unreal came from the main character's FaceEye anim
# tracks, which 14_ue_anims.py now strips.
import numpy as np
from mathutils.kdtree import KDTree
face = bpy.data.objects["Face"]
fm = face.data
slot_of = {i: s.material.name if s.material else "" for i, s in enumerate(face.material_slots)}
def verts_of(key):
    return sorted({v for p in fm.polygons if key in slot_of[p.material_index] for v in p.vertices})
white, iris = verts_of("EyeWhite"), verts_of("EyeIris") + verts_of("EyeHighlight")
co = np.array([v.co for v in fm.vertices])
kd = KDTree(len(white))
for i in white:
    kd.insert((co[i, 0], 0.0, co[i, 2]), i)
kd.balance()
# how far the white's nearest surface sits in front of each iris/highlight vertex (y grows backwards)
front = max(co[i, 1] - min(co[j, 1] for _, j, _ in kd.find_n((co[i, 0], 0.0, co[i, 2]), 3)) for i in iris)
shift = max(front, 0.0) + 0.0012
keys = fm.shape_keys.key_blocks if fm.shape_keys else []
for i in white:
    fm.vertices[i].co.y += shift
    for k in keys:
        k.data[i].co.y += shift
fm.update()
print("RESULT eye white moved back", round(shift * 1000, 2), "mm on", len(white), "verts and", len(keys), "shape keys")

# centimetre scale
def size(o):
    e = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    pts = [e.matrix_world @ Vector(c) for c in e.bound_box]
    return Vector((max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)))


bpy.context.view_layer.update()
before = {o.name: size(o) for o in meshes}
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
print("RESULT arm scale", tuple(arm.scale), "foot z", round((arm.matrix_world @ arm.data.bones["J_Bip_L_Foot"].head_local).z, 2),
      "tallest", round(max(size(o).z for o in meshes), 2))
if bad:
    print("RESULT stopped, nothing exported")
    sys.exit(1)

bpy.ops.object.select_all(action="DESELECT")
for o in [arm] + meshes:
    o.select_set(True)
fbx = os.path.join(OUT, "sw_ue.fbx")
r = bpy.ops.export_scene.fbx(
    filepath=fbx, use_selection=True, object_types={"ARMATURE", "MESH"}, use_mesh_modifiers=True,
    mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False, bake_anim=False,
    primary_bone_axis="Y", secondary_bone_axis="X", axis_forward="-Y", axis_up="Z",
    apply_scale_options="FBX_SCALE_NONE", apply_unit_scale=True, global_scale=1.0,
    path_mode="COPY", embed_textures=True)
print("RESULT exported", r, os.path.getsize(fbx))

# physics data: hair chains from the VRoid secondary bones, cloth chains from 04_outfit.py
bones = arm.data.bones
hair_roots = [b.name for b in bones if "Hair" in b.name and not (b.parent and "Hair" in b.parent.name)]
cloth = json.load(open(os.path.join(ROOT, "cloth_chains.json")))


def group(roots, parent, damping, stiffness, gravity, radius):
    return dict(root_bones=roots, parent=parent, damping=damping, stiffness=stiffness,
                gravity_scale=gravity, collision_radius_cm=radius)


def roots(prefix):
    return [cloth[c]["bones"][0] for c in cloth if c.startswith(prefix)]


H, C = "J_Bip_C_Head", "J_Bip_C_Hips"
setup = dict(
    units="cm", note="Starting values for AnimDynamics/KawaiiPhysics, not yet tested in Unreal.",
    groups=dict(
        hair=group(hair_roots, H, 0.3, 0.12, 0.6, 1.5),
        skirt=group(roots("Skirt"), C, 0.35, 0.20, 0.7, 2.0),
        robe=group(roots("Robe"), C, 0.3, 0.15, 0.8, 2.5),
        obi_tails=group(roots("Tail"), C, 0.3, 0.10, 0.9, 1.0),
        sleeves=group(roots("Sleeve"), None, 0.4, 0.25, 0.6, 2.0),
        pendant=group(roots("Pendant"), C, 0.5, 0.2, 1.0, 1.0)),
    colliders=[dict(bone=b, type="capsule", radius_cm=r) for b, r in (
        ("J_Bip_C_Head", 14), ("J_Bip_C_UpperChest", 12), ("J_Bip_C_Chest", 11), ("J_Bip_C_Spine", 10), ("J_Bip_C_Hips", 14),
        ("J_Bip_L_UpperLeg", 8), ("J_Bip_R_UpperLeg", 8), ("J_Bip_L_LowerLeg", 6), ("J_Bip_R_LowerLeg", 6),
        ("J_Bip_L_UpperArm", 5), ("J_Bip_R_UpperArm", 5), ("J_Bip_L_LowerArm", 4), ("J_Bip_R_LowerArm", 4))],
    materials=table)
for k in ("SleeveL", "SleeveR"):
    if k in cloth:
        setup["groups"]["sleeves"].setdefault("parents", {})[cloth[k]["bones"][0]] = cloth[k]["parent"]
with open(os.path.join(OUT, "ue_physics_setup.json"), "w") as fh:
    json.dump(setup, fh, indent=1)
print("RESULT hair roots", len(hair_roots), "textures", len(os.listdir(TEX)))
