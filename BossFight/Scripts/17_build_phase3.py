# Phase 3 builder: M_Ring (additive camera-facing ring for parry flash / telegraph glint).
import unreal
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
MAT = "/Game/BossFight/FX/M_Ring"
if eal.does_asset_exist(MAT):
    eal.delete_asset(MAT)
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_Ring", "/Game/BossFight/FX", unreal.Material, unreal.MaterialFactoryNew())
mat.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
mat.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
mat.set_editor_property("two_sided", True)

def node(cls, x, y, **props):
    n = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n

# ring = saturate(1 - |length(uv - 0.5) - 0.40| / 0.05), plus a faint inner glow.
uv = node(unreal.MaterialExpressionTextureCoordinate, -1400, 0)
centered = node(unreal.MaterialExpressionSubtract, -1250, 0, const_b=0.5)
mel.connect_material_expressions(uv, "", centered, "A")
dist = node(unreal.MaterialExpressionLength, -1100, 0)
mel.connect_material_expressions(centered, "", dist, "")
off = node(unreal.MaterialExpressionSubtract, -950, 0, const_b=0.40)
mel.connect_material_expressions(dist, "", off, "A")
ab = node(unreal.MaterialExpressionAbs, -800, 0)
mel.connect_material_expressions(off, "", ab, "")
scale = node(unreal.MaterialExpressionMultiply, -650, 0, const_b=20.0)
mel.connect_material_expressions(ab, "", scale, "A")
inv = node(unreal.MaterialExpressionOneMinus, -500, 0)
mel.connect_material_expressions(scale, "", inv, "")
ring = node(unreal.MaterialExpressionSaturate, -350, 0)
mel.connect_material_expressions(inv, "", ring, "")
# inner glow: saturate(1 - dist / 0.4) * 0.25
gscale = node(unreal.MaterialExpressionMultiply, -950, 200, const_b=2.5)
mel.connect_material_expressions(dist, "", gscale, "A")
ginv = node(unreal.MaterialExpressionOneMinus, -800, 200)
mel.connect_material_expressions(gscale, "", ginv, "")
gsat = node(unreal.MaterialExpressionSaturate, -650, 200)
mel.connect_material_expressions(ginv, "", gsat, "")
gmul = node(unreal.MaterialExpressionMultiply, -500, 200, const_b=0.25)
mel.connect_material_expressions(gsat, "", gmul, "A")
shape = node(unreal.MaterialExpressionAdd, -200, 100)
mel.connect_material_expressions(ring, "", shape, "A")
mel.connect_material_expressions(gmul, "", shape, "B")

color = node(unreal.MaterialExpressionVectorParameter, -350, -250, parameter_name="Color", default_value=unreal.LinearColor(1.0, 0.42, 0.04, 1.0))
opac = node(unreal.MaterialExpressionScalarParameter, -350, 350, parameter_name="Opacity", default_value=1.0)
m1 = node(unreal.MaterialExpressionMultiply, -50, 0)
mel.connect_material_expressions(color, "", m1, "A")
mel.connect_material_expressions(shape, "", m1, "B")
m2 = node(unreal.MaterialExpressionMultiply, 100, 0)
mel.connect_material_expressions(m1, "", m2, "A")
mel.connect_material_expressions(opac, "", m2, "B")
gain = node(unreal.MaterialExpressionMultiply, 250, 0, const_b=8.0)
mel.connect_material_expressions(m2, "", gain, "A")
mel.connect_material_property(gain, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(mat)
eal.save_asset(MAT, only_if_is_dirty=False)
unreal.log("BUILD: material " + MAT)

for p in ["/Game/SlashHitVFX/NS/NS_Hit_Sword", "/Game/SlashHitVFX/NS/NS_Hit_Block"]:
    for line in unreal.BFEditorTools.dump_niagara_user_params(p).splitlines():
        unreal.log("BUILD: %s | %s" % (p.split("/")[-1], line))
