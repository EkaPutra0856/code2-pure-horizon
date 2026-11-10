# Unreal export. MToon materials carry no FBX texture, so each slot is swapped to a plain
# Principled material for the export and restored afterwards. Also writes the physics setup data.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, os, re, shutil

ROOT = ANIME_GAME_ROOT
OUT = os.path.join(ROOT, "export_unreal")
TEX = os.path.join(OUT, "textures")
os.makedirs(TEX, exist_ok=True)
arm = bpy.data.objects["Armature"]
meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]


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


saved = {}


def export_image(im):
    if im.name in saved:
        return saved[im.name]
    path = os.path.join(TEX, clean_name(os.path.splitext(im.name)[0]) + ".png")
    src = bpy.path.abspath(im.filepath)
    if im.packed_file:
        with open(path, "wb") as fh:
            fh.write(im.packed_file.data)
    elif os.path.isfile(src):
        shutil.copyfile(src, path)
    else:
        raise RuntimeError(f"no source for image {im.name}: {src}")
    saved[im.name] = bpy.data.images.load(path, check_existing=True)
    return saved[im.name]


# undo any swap left behind by an interrupted run
by_clean = {"M_" + clean_name(m.name): m for m in bpy.data.materials if not m.name.startswith("M_")}
for o in meshes:
    for slot in o.material_slots:
        if slot.material and slot.material.name.split(".")[0] in by_clean:
            slot.material = by_clean[slot.material.name.split(".")[0]]
for m in [m for m in bpy.data.materials if m.name.split(".")[0] in by_clean and m.users == 0]:
    bpy.data.materials.remove(m)

swap, made, table = [], {}, {}
for o in meshes:
    for i, slot in enumerate(o.material_slots):
        m = slot.material
        if m is None or m.name.startswith("M_Outfit"):
            if m:
                table[m.name] = "outfit_atlas.png"
            continue
        if m.name not in made:
            im = lit_image(m)
            p = bpy.data.materials.new("M_" + clean_name(m.name))
            p.use_nodes = True
            b = p.node_tree.nodes["Principled BSDF"]
            if im:
                t = p.node_tree.nodes.new("ShaderNodeTexImage")
                t.image = export_image(im)
                p.node_tree.links.new(t.outputs["Color"], b.inputs["Base Color"])
                table[p.name] = os.path.basename(t.image.filepath)
            made[m.name] = p
        swap.append((o, i, m))
        o.material_slots[i].material = made[m.name]
export_image(bpy.data.images["outfit_atlas"])

# Metre-scale check file only. The file Unreal imports comes from scripts/27_export_mesh_cm.py.
fbx = os.path.join(OUT, "karakter_ue_metres.fbx")
try:
    r = bpy.ops.export_scene.fbx(
        filepath=fbx, object_types={"ARMATURE", "MESH"}, use_mesh_modifiers=True,
        mesh_smooth_type="FACE", use_tspace=True, add_leaf_bones=False, bake_anim=False,
        primary_bone_axis="Y", secondary_bone_axis="X", axis_forward="-Y", axis_up="Z",
        apply_scale_options="FBX_SCALE_ALL", apply_unit_scale=True, global_scale=1.0,
        path_mode="COPY", embed_textures=True)
finally:
    for o, i, m in swap:
        o.material_slots[i].material = m
    for p in made.values():
        bpy.data.materials.remove(p)
print("fbx", r)

br = os.path.join(ROOT, "scripts", "_bridge")
hair = json.load(open(os.path.join(br, "chains.json")))
cloth = json.load(open(os.path.join(br, "cloth_chains.json")))


def group(chains, source, parent, damping, stiffness, gravity, radius):
    return dict(root_bones=[source[c]["bones"][0] if isinstance(source[c], dict) else source[c][0] for c in chains],
                parent=parent, damping=damping, stiffness=stiffness, gravity_scale=gravity, collision_radius_cm=radius)


H, C = "J_Bip_C_Head", "J_Bip_C_Hips"
setup = dict(
    units="cm", note="Starting values for KawaiiPhysics, not yet tested in Unreal. Tune them in the Animation Blueprint.",
    groups=dict(
        hair_back=group([c for c in hair if c.startswith("Back")], hair, H, 0.25, 0.08, 0.6, 2.2),
        hair_bangs=group([c for c in hair if c.startswith("Bang")], hair, H, 0.45, 0.30, 0.1, 1.0),
        hair_side=group([c for c in hair if c.startswith("Lock")], hair, H, 0.3, 0.12, 0.6, 1.2),
        hair_braid=group(["Braid"], hair, H, 0.35, 0.10, 0.9, 1.8),
        skirt=group([c for c in cloth if c.startswith("Skirt")], cloth, C, 0.35, 0.20, 0.7, 2.0),
        petals=group([c for c in cloth if c.startswith("Petal")], cloth, C, 0.3, 0.14, 0.7, 2.0),
        leaves=group([c for c in cloth if c.startswith("Leaf")], cloth, C, 0.3, 0.15, 0.6, 1.0),
        pouch=group(["Pouch"], cloth, C, 0.5, 0.25, 1.0, 3.0),
        cape=group([c for c in cloth if c.startswith("Cape")], cloth, "J_Bip_C_UpperChest", 0.25, 0.06, 0.8, 2.5)),
    colliders=[dict(bone=b, type="capsule", radius_cm=r) for b, r in (
        ("J_Bip_C_Head", 14), ("J_Bip_C_UpperChest", 12), ("J_Bip_C_Chest", 11), ("J_Bip_C_Spine", 10), ("J_Bip_C_Hips", 14),
        ("J_Bip_L_UpperLeg", 8), ("J_Bip_R_UpperLeg", 8), ("J_Bip_L_LowerLeg", 6), ("J_Bip_R_LowerLeg", 6),
        ("J_Bip_L_UpperArm", 5), ("J_Bip_R_UpperArm", 5), ("J_Bip_L_LowerArm", 4), ("J_Bip_R_LowerArm", 4))],
    materials=table)
with open(os.path.join(OUT, "ue_physics_setup.json"), "w") as fh:
    json.dump(setup, fh, indent=1)
print("materials", len(table), "textures", len(os.listdir(TEX)))
bpy.ops.wm.save_mainfile()
