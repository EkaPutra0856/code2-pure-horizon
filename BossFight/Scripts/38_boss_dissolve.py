# Boss death dissolve. Sevarog's base materials (opaque, Material Attributes) become Masked with a noise dissolve:
# scalar param "BFDissolve" 0 = whole, 1 = gone, driven by ABFEnemyBase via SetScalarParameterValueOnMaterials.
# The burning edge glows aura green (emissive). Also builds /Game/BossFight/FX/M_Mote: unlit emissive for the
# motes ABFDissolveFX spawns (vector param "Color").
# Re-running is a no-op for materials that already have the dissolve (tagged Custom node "BFDissolve").
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
ROOT = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Materials/"
BASES = ["M_Sevarog_Torso", "M_Sevarog_ArmourRuins", "M_Sevarog_Back_01", "M_Sevarog_Chainmail", "M_Sevarog_Hammer_01"]
TAG = "BFDissolve"

NOISE = """float3 p = WP * 0.035;
float n = 0.0;
float amp = 0.65;
for (int o = 0; o < 2; o++)
{
    float3 i = floor(p);
    float3 f = frac(p);
    f = f * f * (3.0 - 2.0 * f);
    float v[8];
    for (int k = 0; k < 8; k++)
    {
        float3 c = i + float3(k & 1, (k >> 1) & 1, (k >> 2) & 1);
        v[k] = frac(sin(dot(c, float3(127.1, 311.7, 74.7))) * 43758.5453);
    }
    float x0 = lerp(lerp(v[0], v[1], f.x), lerp(v[2], v[3], f.x), f.y);
    float x1 = lerp(lerp(v[4], v[5], f.x), lerp(v[6], v[7], f.x), f.y);
    n += amp * lerp(x0, x1, f.z);
    amp = 0.35;
    p = p * 2.7 + 17.3;
}
float thr = A * 1.25 - 0.1;
"""
MASK = NOISE + "return 0.3333 + (n - thr);"
EDGE = NOISE + "float e = saturate(1.0 - (n - thr) / 0.07) * step(thr, n) * step(0.001, A);\nreturn float3(0.3, 1.0, 0.5) * e * 25.0;"


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def custom(m, code, out_type, x, y, desc):
    c = mel.create_material_expression(m, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("description", desc)
    c.set_editor_property("code", code)
    c.set_editor_property("output_type", out_type)
    ins = []
    for name in ("WP", "A"):
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    return c


PINS = ["BaseColor", "Metallic", "Specular", "Roughness", "Anisotropy", "Opacity", "Normal", "Tangent",
        "WorldPositionOffset", "SubsurfaceColor", "ClearCoat", "ClearCoatRoughness", "AmbientOcclusion", "Refraction",
        "PixelDepthOffset", "ShadingModel", "Displacement"] + ["CustomizedUV%d" % i for i in range(8)]

for name in BASES:
    path = ROOT + name
    m = unreal.load_asset(path)
    if not m:
        log("missing", path)
        continue
    # These materials use Material Attributes: the plain OpacityMask/Emissive pins are ignored. So the attributes
    # get broken out and re-made with the dissolve mask and the edge glow added.
    src = mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    if not src:
        log("no attributes", path)
        continue
    if isinstance(src, unreal.MaterialExpressionMakeMaterialAttributes) and src.get_editor_property("desc") == TAG:
        log("already", path)
        continue
    out = mel.get_material_property_input_node_output_name(m, unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)
    x = src.get_editor_property("material_expression_editor_x") + 350
    y = src.get_editor_property("material_expression_editor_y")
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("opacity_mask_clip_value", 0.3333)
    brk = mel.create_material_expression(m, unreal.MaterialExpressionBreakMaterialAttributes, x, y)
    mk = mel.create_material_expression(m, unreal.MaterialExpressionMakeMaterialAttributes, x + 400, y)
    mk.set_editor_property("desc", TAG)
    ok_in = mel.connect_material_expressions(src, out, brk, "MaterialAttributes") or mel.connect_material_expressions(src, out, brk, "Attr")
    failed = [p for p in PINS if not mel.connect_material_expressions(brk, p, mk, p)]
    wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, x, y + 700)
    a = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, x, y + 850)
    a.set_editor_property("parameter_name", TAG)
    a.set_editor_property("default_value", 0.0)
    mask = custom(m, MASK, unreal.CustomMaterialOutputType.CMOT_FLOAT1, x + 200, y + 700, TAG)
    edge = custom(m, EDGE, unreal.CustomMaterialOutputType.CMOT_FLOAT3, x + 200, y + 900, TAG + "Edge")
    add = mel.create_material_expression(m, unreal.MaterialExpressionAdd, x + 300, y + 600)
    ok = [ok_in, mel.connect_material_expressions(wp, "", mask, "WP"), mel.connect_material_expressions(a, "", mask, "A"),
          mel.connect_material_expressions(wp, "", edge, "WP"), mel.connect_material_expressions(a, "", edge, "A"),
          mel.connect_material_expressions(brk, "EmissiveColor", add, "A"), mel.connect_material_expressions(edge, "", add, "B"),
          mel.connect_material_expressions(add, "", mk, "EmissiveColor"), mel.connect_material_expressions(mask, "", mk, "OpacityMask"),
          mel.connect_material_property(mk, "", unreal.MaterialProperty.MP_MATERIAL_ATTRIBUTES)]
    mel.recompile_material(m)
    eal.save_asset(path, only_if_is_dirty=False)
    log("dissolve", path, ok, "unlinked pins:", failed)

# Mote material
MOTE = "/Game/BossFight/FX/M_Mote"
if not eal.does_asset_exist(MOTE):
    mote = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_Mote", "/Game/BossFight/FX", unreal.Material, unreal.MaterialFactoryNew())
    mote.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
    mote.set_editor_property("used_with_instanced_static_meshes", True)
    col = mel.create_material_expression(mote, unreal.MaterialExpressionVectorParameter, -500, 0)
    col.set_editor_property("parameter_name", "Color")
    col.set_editor_property("default_value", unreal.LinearColor(0.3, 1.0, 0.5, 1.0))
    k = mel.create_material_expression(mote, unreal.MaterialExpressionScalarParameter, -500, 200)
    k.set_editor_property("parameter_name", "Intensity")
    k.set_editor_property("default_value", 30.0)
    mul = mel.create_material_expression(mote, unreal.MaterialExpressionMultiply, -250, 100)
    ok = [mel.connect_material_expressions(col, "", mul, "A"), mel.connect_material_expressions(k, "", mul, "B"),
          mel.connect_material_property(mul, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)]
    mel.recompile_material(mote)
    eal.save_asset(MOTE, only_if_is_dirty=False)
    log("mote", MOTE, ok)
else:
    log("mote exists")
