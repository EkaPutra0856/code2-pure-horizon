# Unreal export for char4 (archer/healer). Adapted from swordswoman/scripts/12_export_ue.py. Run:
#   blender -b char4/rig/rig_v3.blend --python-exit-code 1 --python char4/rig/scripts/06_export_ue.py
# Writes char4/export_unreal/char4_ue.fbx (skeleton truly in centimetres), textures/*.png and
# ue_physics_setup.json. Never saves the .blend.
# Same rules as the main character's scripts 12 + 27: MToon materials carry no FBX texture,
# so each MToon slot is swapped to a plain Principled material with its lit image. A metre-scale
# FBX puts x100 on the Root bone in Unreal and breaks retargeting, so scale is applied first and
# every evaluated mesh is checked to have grown exactly 100 times.
import bpy, json, os, re, shutil, sys
from mathutils import Vector

RIG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.path.dirname(RIG)
OUT = os.path.join(ROOT, "export_unreal")
TEX = os.path.join(OUT, "textures")
os.makedirs(TEX, exist_ok=True)
sc = bpy.context.scene
arm = bpy.data.objects["Char4_Armature"]
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
            em = next((n for n in m.node_tree.nodes if n.type == "EMISSION" and not n.inputs["Color"].links), None)
            if em and not im:  # flat emission (hair outline): carry its colour over
                b.inputs["Base Color"].default_value = em.inputs["Color"].default_value
            if m.use_backface_culling:
                p.use_backface_culling = True
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
# Blender's FBX exporter drops an armature object named exactly "Armature"; any other name becomes an extra
# root bone above Root (Char4_Armature), and Unreal then refuses the shared J_Bip clips ("Mesh contains
# Char4_Armature bone as root but animation doesn't contain the root track"). The blend is never saved here.
for o in bpy.data.objects:
    if o.name == "Armature" and o != arm:
        o.name = "Armature_other"
arm.name = "Armature"
print("RESULT armature object renamed", arm.name)
fbx = os.path.join(OUT, "char4_ue.fbx")
r = bpy.ops.export_scene.fbx(
    filepath=fbx, use_selection=True, object_types={"ARMATURE", "MESH"}, use_mesh_modifiers=True,
    mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False, bake_anim=False,
    primary_bone_axis="Y", secondary_bone_axis="X", axis_forward="-Y", axis_up="Z",
    apply_scale_options="FBX_SCALE_NONE", apply_unit_scale=True, global_scale=1.0,
    path_mode="COPY", embed_textures=True)
print("RESULT exported", r, os.path.getsize(fbx))

# physics data from 04_cloth_hair.py (cloth_chains.json: list of chains)
chains = json.load(open(os.path.join(RIG, "cloth_chains.json")))


def group(prefix, parent, damping, stiffness, gravity, radius):
    cs = [c for c in chains if c["chain"].startswith(prefix)]
    return dict(root_bones=[c["bones"][0] for c in cs], chains={c["chain"]: c["bones"] for c in cs}, parent=parent,
                damping=damping, stiffness=stiffness, gravity_scale=gravity, collision_radius_cm=radius)


H, C, U = "J_Bip_C_Head", "J_Bip_C_Hips", "J_Bip_C_UpperChest"
setup = dict(
    units="cm", note="Starting values for AnimDynamics, not yet tested in Unreal. Bones: J_Bip = VRoid humanoid (same names as the main character).",
    groups=dict(
        hair_tails=group("Hair_Tail", H, 0.3, 0.12, 0.6, 1.5),
        hair_short=group("Hair_Side", H, 0.35, 0.2, 0.5, 1.0) | dict(extra=group("Hair_Back", H, 0.35, 0.2, 0.5, 1.0)),
        hair_bangs=group("Hair_Bang", H, 0.45, 0.35, 0.3, 0.8),
        ahoge=group("Hair_Ahoge", H, 0.5, 0.4, 0.2, 0.5),
        skirt=group("J_Sec_Skirt", C, 0.35, 0.20, 0.7, 2.0),
        capelet=group("J_Sec_Cape", U, 0.35, 0.22, 0.7, 2.0),
        hood=group("J_Sec_Hood", U, 0.4, 0.3, 0.6, 2.0),
        pendant=group("J_Sec_Pendant", U, 0.5, 0.2, 1.0, 1.0)),
    colliders=json.load(open(os.path.join(RIG, "colliders.json"))),
    collider_note="Spheres for AnimDynamics spherical limits (LimitType Outer) on every chain: offset along the bone from its head, radius from the outer shell incl. cloth.",
    materials=table)
with open(os.path.join(OUT, "ue_physics_setup.json"), "w") as fh:
    json.dump(setup, fh, indent=1)
print("RESULT chains", len(chains), "textures", len(os.listdir(TEX)))
