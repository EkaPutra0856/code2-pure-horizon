# Imports export_unreal/sw_ue.fbx (truly cm) into AnimeGame as /Game/Swordswoman with its own
# skeleton, so the main character under /Game/Character is never touched. Then links any empty
# Base Color from the exported textures and turns on two-sided for cloth/hair (Unreal draws thin
# shells one-sided). Run with UnrealEditor-Cmd -run=pythonscript. Safe to rerun.
import json, os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXP = os.path.join(ROOT, "export_unreal")
LOG = os.path.join(ROOT, "renders", "_log_ue_import.txt")
DEST = "/Game/Swordswoman"
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
tools = unreal.AssetToolsHelpers.get_asset_tools()
lib = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary


def run(path, dest, opts=None):
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", path)
    t.set_editor_property("destination_path", dest)
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    if opts:
        t.set_editor_property("options", opts)
    tools.import_asset_tasks([t])
    return list(t.get_editor_property("imported_object_paths"))


o = unreal.FbxImportUI()
o.set_editor_property("import_as_skeletal", True)
o.set_editor_property("import_mesh", True)
o.set_editor_property("import_animations", False)
o.set_editor_property("import_materials", True)
o.set_editor_property("import_textures", True)
o.set_editor_property("create_physics_asset", True)
o.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
sm = o.get_editor_property("skeletal_mesh_import_data")
sm.set_editor_property("import_morph_targets", True)
sm.set_editor_property("convert_scene", True)
sm.set_editor_property("convert_scene_unit", False)
got = run(os.path.join(EXP, "sw_ue.fbx"), DEST, o)
say("imported", len(got))
mesh = unreal.load_asset(DEST + "/sw_ue")
if not mesh:
    say("FAILED no mesh")
    raise SystemExit(1)
skeleton = mesh.get_editor_property("skeleton")
b = mesh.get_bounds()
say("extent", b.box_extent, "origin", b.origin, "morphs", len(mesh.get_editor_property("morph_targets")),
    "materials", len(mesh.get_editor_property("materials")), "skeleton", skeleton.get_path_name())
pose = unreal.AnimPoseExtensions.get_reference_pose(skeleton)
for bone in ("Root", "J_Bip_C_Hips", "J_Bip_L_Foot", "J_Bip_C_Head"):
    loc = unreal.AnimPoseExtensions.get_ref_bone_pose(pose, bone, unreal.AnimPoseSpaces.LOCAL)
    wor = unreal.AnimPoseExtensions.get_ref_bone_pose(pose, bone, unreal.AnimPoseSpaces.WORLD)
    say(bone, "scale", loc.scale3d, "world", wor.translation)

# materials
table = json.load(open(os.path.join(EXP, "ue_physics_setup.json")))["materials"]
reg = unreal.AssetRegistryHelpers.get_asset_registry()
textures = {str(a.asset_name): str(a.package_name) for a in reg.get_assets_by_path(DEST, recursive=True)
            if str(a.asset_class_path.asset_name) == "Texture2D"}


def texture(file_name):
    name = os.path.splitext(file_name)[0]
    if name in textures:
        return unreal.load_asset(textures[name])
    src = os.path.join(EXP, "textures", file_name)
    if not os.path.isfile(src):
        return None
    run(src, DEST + "/Textures")
    asset = unreal.load_asset(DEST + "/Textures/" + name)
    if asset:
        textures[name] = asset.get_path_name().split(".")[0]
    return asset


SKIN_ONLY = ("EyeIris", "EyeWhite", "EyeHighlight", "FaceMouth", "Face_00", "FaceBrow", "FaceEyeline", "Body_00")
TWO_SIDED = ("Outfit", "HAIR", "Hair")
kept = linked = missing = 0
for slot in mesh.get_editor_property("materials"):
    m = slot.get_editor_property("material_interface")
    if not isinstance(m, unreal.Material):
        say("not a base material", m)
        continue
    name = m.get_name()
    changed = False
    node = mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_BASE_COLOR)
    current = node.get_editor_property("texture") if isinstance(node, unreal.MaterialExpressionTextureBase) else None
    if current:
        kept += 1
    else:
        files = table.get(name) or table.get("M_" + name) or []
        base = [f for f in files if "normal" not in f and "_rm" not in f]
        tex = texture(base[0]) if base else None
        if tex:
            s = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -400, 0)
            s.set_editor_property("texture", tex)
            mel.connect_material_property(s, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
            changed = True
            linked += 1
            current = tex
        else:
            missing += 1
    if any(k in name for k in TWO_SIDED) and not any(k in name for k in SKIN_ONLY):
        m.set_editor_property("two_sided", True)
        changed = True
    if changed:
        mel.recompile_material(m)
        lib.save_loaded_asset(m, False)
    say(name, "base", current.get_name() if current else None, "two_sided", m.get_editor_property("two_sided"))
lib.save_directory(DEST)
assets = [str(p).split(".")[-1] for p in lib.list_assets(DEST, recursive=True, include_folder=False)]
say("kept", kept, "linked", linked, "missing", missing, "assets", len(assets),
    [a for a in assets if "Physics" in a or "Skeleton" in a])
say("DONE")
