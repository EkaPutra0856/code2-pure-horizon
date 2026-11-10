# /Game/BossFight/FX/M_BossOrb: the core of Sevarog's green energy orb (EBFMagic::Orb). Unlit additive sphere:
# a white-green hot centre fading to a soul-green rim, with a fast flicker so it reads as live energy.
# The flames around it are MagicKit NightFlame particles (already hue-shifted green, Scripts/37).
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
DIR = "/Game/BossFight/FX"
NAME = "M_BossOrb"

if eal.does_asset_exist("%s/%s" % (DIR, NAME)):
    unreal.load_asset("%s/%s" % (DIR, NAME))
    eal.delete_asset("%s/%s" % (DIR, NAME))
m = tools.create_asset(NAME, DIR, unreal.Material, unreal.MaterialFactoryNew())
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)

fres = mel.create_material_expression(m, unreal.MaterialExpressionFresnel, -900, 0)
fres.set_editor_property("exponent", 1.6)
time = mel.create_material_expression(m, unreal.MaterialExpressionTime, -900, 150)
uv = mel.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -900, 300)
glow = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -900, 450)
glow.set_editor_property("parameter_name", "Glow")
glow.set_editor_property("default_value", 1.0)

CODE = """
float f = saturate(F);
float core = pow(1.0 - f, 2.0);
float rim = pow(f, 1.2);
float swirl = 0.5 + 0.5 * sin(UV.x * 40.0 + UV.y * 25.0 - Time * 9.0);
float flick = 0.8 + 0.2 * sin(Time * 11.0 + UV.x * 31.0) * sin(Time * 6.7 - UV.y * 23.0);
// Kept mostly green so bloom does not wash it out to white; only a small pale heart.
float3 green = float3(0.12, 1.0, 0.35);
float3 hot = float3(0.55, 1.0, 0.65);
// The dusk scene runs a high auto-exposure: anything much above 1 here tonemaps to flat white.
float3 c = green * (core * (0.35 + swirl * 0.35) + rim * 1.3) + hot * pow(core, 8.0) * 0.45;
return c * flick * Glow;
"""
c = mel.create_material_expression(m, unreal.MaterialExpressionCustom, -500, 0)
c.set_editor_property("description", "BossOrb")
c.set_editor_property("code", CODE)
c.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
ins = []
for n in ("F", "Time", "UV", "Glow"):
    ci = unreal.CustomInput()
    ci.set_editor_property("input_name", n)
    ins.append(ci)
c.set_editor_property("inputs", ins)
mel.connect_material_expressions(fres, "", c, "F")
mel.connect_material_expressions(time, "", c, "Time")
mel.connect_material_expressions(uv, "", c, "UV")
mel.connect_material_expressions(glow, "", c, "Glow")
ok = mel.connect_material_property(c, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(m)
eal.save_loaded_asset(m)
unreal.log("BUILD: M_BossOrb %s" % ok)
