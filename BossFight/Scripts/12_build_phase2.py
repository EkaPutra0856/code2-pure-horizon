# Phase 2 builder: root motion on combat anims, afterimage material.
import unreal
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary

ANIMS = ["combo01_1", "combo01_2", "combo01_3", "combo02_1", "combo02_2", "combo02_3", "Rolling",
         "hit_knockdown01", "hit_down_up", "Attack_Shockwave", "Attack_Jump_to_Air"]
for n in ANIMS:
    path = "/Game/InsaneAirCombo/Animation/" + n
    seq = unreal.load_asset(path)
    if not seq:
        unreal.log_warning("BUILD: missing " + path); continue
    if not seq.get_editor_property("enable_root_motion"):
        seq.set_editor_property("enable_root_motion", True)
        eal.save_asset(path, only_if_is_dirty=False)
    unreal.log("BUILD: root motion on " + n)

# Fresnel ghost: Color * (fresnel + 0.25) * 4 emissive, Opacity * (fresnel + 0.35) opacity.
MAT = "/Game/BossFight/FX/M_AfterImage"
if eal.does_asset_exist(MAT):
    eal.delete_asset(MAT)
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_AfterImage", "/Game/BossFight/FX", unreal.Material, unreal.MaterialFactoryNew())
mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
mat.set_editor_property("two_sided", False)
mat.set_editor_property("used_with_skeletal_mesh", True)
E = unreal.MaterialExpression
color = mel.create_material_expression(mat, unreal.MaterialExpressionVectorParameter, -800, 0)
color.set_editor_property("parameter_name", "Color")
color.set_editor_property("default_value", unreal.LinearColor(0.25, 0.75, 1.0, 1.0))
opac = mel.create_material_expression(mat, unreal.MaterialExpressionScalarParameter, -800, 300)
opac.set_editor_property("parameter_name", "Opacity")
opac.set_editor_property("default_value", 0.6)
fres = mel.create_material_expression(mat, unreal.MaterialExpressionFresnel, -800, 150)
fres.set_editor_property("exponent", 2.0)
add_e = mel.create_material_expression(mat, unreal.MaterialExpressionAdd, -600, 100)
add_e.set_editor_property("const_b", 0.25)
mel.connect_material_expressions(fres, "", add_e, "A")
mul_c = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -400, 0)
mel.connect_material_expressions(color, "", mul_c, "A")
mel.connect_material_expressions(add_e, "", mul_c, "B")
mul_e = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -200, 0)
mul_e.set_editor_property("const_b", 4.0)
mel.connect_material_expressions(mul_c, "", mul_e, "A")
mel.connect_material_property(mul_e, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
add_o = mel.create_material_expression(mat, unreal.MaterialExpressionAdd, -600, 250)
add_o.set_editor_property("const_b", 0.35)
mel.connect_material_expressions(fres, "", add_o, "A")
mul_o = mel.create_material_expression(mat, unreal.MaterialExpressionMultiply, -400, 300)
mel.connect_material_expressions(opac, "", mul_o, "A")
mel.connect_material_expressions(add_o, "", mul_o, "B")
mel.connect_material_property(mul_o, "", unreal.MaterialProperty.MP_OPACITY)
mel.recompile_material(mat)
eal.save_asset(MAT, only_if_is_dirty=False)
unreal.log("BUILD: material " + MAT)
