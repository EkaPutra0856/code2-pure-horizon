# Checks each character material's Base Color graph and links the exported texture where the
# FBX import left it empty. Table comes from export_unreal/ue_physics_setup.json. Safe to rerun.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import json, os
import unreal

ROOT = ANIME_GAME_ROOT
EXP = os.path.join(ROOT, "export_unreal")
LOG = os.path.join(ROOT, "scripts", "ue", "report_materials.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


lib = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
table = json.load(open(os.path.join(EXP, "ue_physics_setup.json")))["materials"]
say("table", len(table), sorted(set(table.values())))
reg = unreal.AssetRegistryHelpers.get_asset_registry()
textures = {str(a.asset_name): str(a.package_name) for a in reg.get_assets_by_path("/Game/Character", recursive=True) if str(a.asset_class_path.asset_name) == "Texture2D"}
say("textures in project", len(textures), sorted(textures))


def texture(file_name):
    name = os.path.splitext(file_name)[0]
    if name in textures:
        return unreal.load_asset(textures[name])
    src = os.path.join(EXP, "textures", file_name)
    if not os.path.isfile(src):
        say("no file", src)
        return None
    t = unreal.AssetImportTask()
    t.set_editor_property("filename", src)
    t.set_editor_property("destination_path", "/Game/Character/Textures")
    t.set_editor_property("automated", True)
    t.set_editor_property("save", True)
    t.set_editor_property("replace_existing", True)
    tools.import_asset_tasks([t])
    asset = unreal.load_asset("/Game/Character/Textures/" + name)
    if asset:
        textures[name] = asset.get_path_name().split(".")[0]
    return asset


mesh = unreal.load_asset("/Game/Character/karakter_ue")
linked = kept = missing = 0
for slot in mesh.get_editor_property("materials"):
    m = slot.get_editor_property("material_interface")
    if not isinstance(m, unreal.Material):
        say("not a base material", m)
        continue
    node = mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_BASE_COLOR)
    current = node.get_editor_property("texture") if isinstance(node, unreal.MaterialExpressionTextureBase) else None
    if current:
        kept += 1
        say(m.get_name(), "has", current.get_name())
        continue
    file_name = table.get(m.get_name()) or table.get(m.get_name()[2:]) or ("outfit_atlas.png" if m.get_name().startswith("M_Outfit") else None)
    tex = texture(file_name) if file_name else None
    if not tex:
        missing += 1
        say(m.get_name(), "node", type(node).__name__, "no texture known")
        continue
    s = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -400, 0)
    s.set_editor_property("texture", tex)
    mel.connect_material_property(s, "RGB", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.recompile_material(m)
    lib.save_loaded_asset(m, False)
    linked += 1
    say(m.get_name(), "linked", tex.get_name())
lib.save_directory("/Game/Character")
say("kept", kept, "linked", linked, "missing", missing)
say("DONE")
