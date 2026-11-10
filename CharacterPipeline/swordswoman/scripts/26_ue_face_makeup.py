# Unreal side of the face pass (run with UnrealEditor-Cmd -ExecutePythonScript). Safe to rerun.
#  1. All VRoid materials (M_N00_*) get "Used with Morph Targets" (and skeletal mesh). Without it the
#     game falls back to the default material path and the face blend shapes (blinks, smiles) never show.
#  2. The face skin uses textures/face_makeup.png (script 25: blush, eyeshadow, lip tint, side shade).
#  3. Face and body skin: warm tint, matte (roughness 0.8, specular 0.25) and a small emissive lift
#     so the skin reads peach instead of grey-white under the night light.
import os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "renders", "_log_ue_face_makeup.txt")
MAKEUP_PNG = os.path.join(ROOT, "textures", "face_makeup.png")
DIR = "/Game/Swordswoman"
SKIN_TINT = unreal.LinearColor(1.0, 0.86, 0.78, 1.0)
EMISSIVE_LIFT = 0.07
mel = unreal.MaterialEditingLibrary
lib = unreal.EditorAssetLibrary
MP = unreal.MaterialProperty
out = []


def say(*a):
    out.append(" ".join(str(x) for x in a))


# Makeup texture
task = unreal.AssetImportTask()
task.set_editor_property("filename", MAKEUP_PNG)
task.set_editor_property("destination_path", DIR)
task.set_editor_property("destination_name", "T_SW_FaceMakeup")
task.set_editor_property("replace_existing", True)
task.set_editor_property("automated", True)
task.set_editor_property("save", True)
unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
makeup = unreal.load_asset(DIR + "/T_SW_FaceMakeup")
say("makeup texture", makeup)


def tex_node(m):
    """(tint node or None, base colour texture sample): a rerun finds the texture under the tint."""
    node = mel.get_material_property_input_node(m, MP.MP_BASE_COLOR)
    if isinstance(node, unreal.MaterialExpressionMultiply) and node.get_editor_property("desc") == "SW_SkinTint":
        return node, mel.get_inputs_for_material_expression(m, node)[0]
    return None, node


mesh = unreal.load_asset(DIR + "/sw_ue")
for slot in mesh.get_editor_property("materials"):
    m = slot.get_editor_property("material_interface")
    name = m.get_name()
    if not name.startswith("M_N00_"):
        continue
    m.set_editor_property("used_with_morph_targets", True)
    m.set_editor_property("used_with_skeletal_mesh", True)
    skin = name.endswith("_SKIN")
    if skin:
        tint, tex = tex_node(m)
        if not isinstance(tex, unreal.MaterialExpressionTextureSample):
            say(name, "no texture sample under base colour:", type(tex).__name__)
        else:
            if "Face_00_SKIN" in name:
                tex.set_editor_property("texture", makeup)
            if tint is None:
                pos = tex.get_editor_property("material_expression_editor_y")
                tint = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -250, pos + 220)
                tint.set_editor_property("desc", "SW_SkinTint")
                col = mel.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, pos + 300)
                col.set_editor_property("desc", "SW_SkinTintColor")
                mel.connect_material_expressions(tex, "RGB", tint, "A")
                mel.connect_material_expressions(col, "", tint, "B")
                mel.connect_material_property(tint, "", MP.MP_BASE_COLOR)
                lift = mel.create_material_expression(m, unreal.MaterialExpressionMultiply, -250, pos + 420)
                lift.set_editor_property("desc", "SW_SkinLift")
                mel.connect_material_expressions(tint, "", lift, "A")
                lift.set_editor_property("const_b", EMISSIVE_LIFT)
                mel.connect_material_property(lift, "", MP.MP_EMISSIVE_COLOR)
                rough = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -250, pos + 520)
                rough.set_editor_property("r", 0.8)
                mel.connect_material_property(rough, "", MP.MP_ROUGHNESS)
                spec = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -250, pos + 600)
                spec.set_editor_property("r", 0.25)
                mel.connect_material_property(spec, "", MP.MP_SPECULAR)
            col = mel.get_inputs_for_material_expression(m, tint)[1]
            col.set_editor_property("constant", SKIN_TINT)
            say(name, "tint", SKIN_TINT, "texture", tex.get_editor_property("texture").get_name())
    mel.recompile_material(m)
    lib.save_loaded_asset(m, False)
    say(name, "morph", m.get_editor_property("used_with_morph_targets"), "skin" if skin else "")
say("DONE")
open(LOG, "w", encoding="utf-8").write("\n".join(out))
