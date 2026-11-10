# Hit impact builder: M_HitFlash (additive overlay used by UBFHitFlashComponent), then rebuild the
# player / Sevarog Anim Blueprints (they gain the procedural spine flinch node).
import unreal
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
MAT = "/Game/BossFight/FX/M_HitFlash"
if eal.does_asset_exist(MAT):
    eal.delete_asset(MAT)
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_HitFlash", "/Game/BossFight/FX", unreal.Material, unreal.MaterialFactoryNew())
# Translucent (not additive) so a red tint also shows on the near-white mannequin.
mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
mat.set_editor_property("used_with_skeletal_mesh", True)


def node(cls, x, y, **props):
    n = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


# Emissive = Color * 2 * (1 + 2 * fresnel): bright tint with a hot rim.
# Opacity  = Opacity * (0.55 + 0.45 * fresnel): body covered, edges fully.
color = node(unreal.MaterialExpressionVectorParameter, -900, 0, parameter_name="Color", default_value=unreal.LinearColor(1, 1, 1, 1))
opacity = node(unreal.MaterialExpressionScalarParameter, -900, 400, parameter_name="Opacity", default_value=1.0)
fres = node(unreal.MaterialExpressionFresnel, -900, 200)
fres.set_editor_property("exponent", 2.5)
rim = node(unreal.MaterialExpressionMultiply, -650, 200)
rim.set_editor_property("const_b", 2.0)
glow = node(unreal.MaterialExpressionAdd, -450, 200)
glow.set_editor_property("const_b", 1.0)
c2 = node(unreal.MaterialExpressionMultiply, -650, 0)
c2.set_editor_property("const_b", 2.0)
emis = node(unreal.MaterialExpressionMultiply, -250, 100)
mel.connect_material_expressions(fres, "", rim, "A")
mel.connect_material_expressions(rim, "", glow, "A")
mel.connect_material_expressions(color, "", c2, "A")
mel.connect_material_expressions(c2, "", emis, "A")
mel.connect_material_expressions(glow, "", emis, "B")
mel.connect_material_property(emis, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
fo = node(unreal.MaterialExpressionMultiply, -650, 350)
fo.set_editor_property("const_b", 0.45)
fo2 = node(unreal.MaterialExpressionAdd, -450, 350)
fo2.set_editor_property("const_b", 0.55)
op = node(unreal.MaterialExpressionMultiply, -250, 380)
mel.connect_material_expressions(fres, "", fo, "A")
mel.connect_material_expressions(fo, "", fo2, "A")
mel.connect_material_expressions(fo2, "", op, "A")
mel.connect_material_expressions(opacity, "", op, "B")
mel.connect_material_property(op, "", unreal.MaterialProperty.MP_OPACITY)
mel.recompile_material(mat)
eal.save_asset(MAT, only_if_is_dirty=False)
unreal.log("BUILD: saved " + MAT)

for line in unreal.BFEditorTools.build_player_anim_blueprint().splitlines():
    unreal.log("BUILD: " + line)
for line in unreal.BFEditorTools.build_sevarog_anim_blueprint().splitlines():
    unreal.log("BUILD: " + line)
