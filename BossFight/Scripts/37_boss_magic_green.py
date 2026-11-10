# Recolors Sevarog's magic (MagicKit NightFlame systems: fire line, circle, cast aura) from purple to
# his aura green. The systems have no color user parameter: the purple comes from MI vector params and
# from particle colors baked in the emitters. So each MagicKit base material those systems use gets a
# hue rotation (Custom HLSL, rotation about the grey axis) between its emissive graph and the output.
# MagicKit is used only by the boss in this project; the other MagicKit systems shift hue as well.
# Param "BFHueShift" (fraction of a turn, 0.648 = purple -> aura green). Re-running is a no-op.
# Backups of the untouched materials: scratchpad magickit_bak (session only).
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
ROOT = "/Game/MagicKit/Material/"
BASES = ["Fire/M_Fire_01", "Flare/M_Flare_03", "M_SoftDot", "Wind/M_Wind_Shape_02", "Divine/M_Divine_GroundImpact_01",
         "Divine/M_Divine_Impact_Mesh_01", "Shockwave/M_Shockwave_01", "Wind/M_Wind_Shape_03", "Flare/M_Flare_01",
         "Wind/M_WindShield_02", "Wind/M_WindSphere_02"]
TAG = "BFHueShift"
CODE = """float l = (In.r + In.g + In.b) / 3.0;
float x = In.r - 0.5 * (In.g + In.b);
float y = 0.8660254 * (In.g - In.b);
float a = Angle * 6.2831853;
float xr = x * cos(a) - y * sin(a);
float yr = x * sin(a) + y * cos(a);
float r = l + xr / 1.5;
float gb = 3.0 * l - r;
float d = yr / 0.8660254;
return max(float3(r, (gb + d) * 0.5, (gb - d) * 0.5), 0.0);"""


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


for rel in BASES:
    path = ROOT + rel
    m = unreal.load_asset(path)
    if not m:
        log("missing", path)
        continue
    src = mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    if not src:
        log("no emissive", path)
        continue
    if isinstance(src, unreal.MaterialExpressionCustom) and src.get_editor_property("description") == TAG:
        log("already", path)
        continue
    out = mel.get_material_property_input_node_output_name(m, unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    pos_x = src.get_editor_property("material_expression_editor_x") + 300
    pos_y = src.get_editor_property("material_expression_editor_y")
    custom = mel.create_material_expression(m, unreal.MaterialExpressionCustom, pos_x, pos_y)
    custom.set_editor_property("description", TAG)
    custom.set_editor_property("code", CODE)
    custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
    ins = []
    for name in ("In", "Angle"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        ins.append(ci)
    custom.set_editor_property("inputs", ins)
    shift = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, pos_x - 200, pos_y + 150)
    shift.set_editor_property("parameter_name", TAG)
    shift.set_editor_property("default_value", 0.648)
    ok1 = mel.connect_material_expressions(src, out, custom, "In")
    ok2 = mel.connect_material_expressions(shift, "", custom, "Angle")
    ok3 = mel.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
    mel.recompile_material(m)
    eal.save_asset(path, only_if_is_dirty=False)
    log("recolored", path, "from", src.get_class().get_name(), "out='%s'" % out, ok1, ok2, ok3)
