# Materials for the twilight flooded-temple boss arena (ArtSource/Landscape/boss_ref_C2.jpg):
#   M_TwilightSky        - sky dome: purple-orange gradient, stars, big moon with halo (unlit, Is Sky)
#   M_RuneCircle         - additive glowing teal hexagram rune circle, drawn on a plane's UVs (param Reveal)
#   M_LanternGlow        - warm unlit glow for lantern boxes
#   M_Mud                - dark wet ground (world aligned) between the floor tiles and around the arena
#   MI_TreeLeaves_Sakura - Dreamscape tree leaves recoloured pink (cherry blossom)
# Re-running rebuilds all of them.
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
DIR = "/Game/BossFight/Env"
LUSH = "/Game/LUSH_StylizedEnvironmentSet"
DS = "/Game/DreamscapeSeries"


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def delete_if_exists(path):
    if eal.does_asset_exist(path):
        unreal.load_asset(path)
        eal.delete_asset(path)


def new_material(name):
    delete_if_exists("%s/%s" % (DIR, name))
    return tools.create_asset(name, DIR, unreal.Material, unreal.MaterialFactoryNew())


def custom(m, code, inputs, x, y, desc, out_type=unreal.CustomMaterialOutputType.CMOT_FLOAT3):
    c = mel.create_material_expression(m, unreal.MaterialExpressionCustom, x, y)
    c.set_editor_property("description", desc)
    c.set_editor_property("code", code)
    c.set_editor_property("output_type", out_type)
    ins = []
    for name in inputs:
        ci = unreal.CustomInput()
        ci.set_editor_property("input_name", name)
        ins.append(ci)
    c.set_editor_property("inputs", ins)
    return c


def const(m, v, x, y):
    c = mel.create_material_expression(m, unreal.MaterialExpressionConstant, x, y)
    c.set_editor_property("r", v)
    return c


def finish(m, name, ok):
    mel.recompile_material(m)
    eal.save_loaded_asset(m)
    log(name, ok)


# ---- Sky dome
SKY = """
float3 d = normalize(Dir);
float e = d.z;
float3 horizon = float3(0.95, 0.45, 0.28);
float3 mid = float3(0.40, 0.19, 0.52);
float3 top = float3(0.045, 0.035, 0.15);
float3 c = lerp(horizon, mid, saturate(e / 0.16));
c = lerp(c, top, saturate((e - 0.14) / 0.5));
float3 md = normalize(float3(0.883, 0.412, 0.225));
float m = dot(d, md);
c += float3(1.0, 0.62, 0.45) * pow(saturate(m), 18.0) * 0.35 * saturate(1.0 - e * 2.0);
// wispy cloud bands near the horizon
float az = atan2(d.y, d.x);
float band = sin(az * 9.0 + e * 40.0 + sin(az * 23.0) * 0.6) * 0.5 + 0.5;
band *= smoothstep(0.02, 0.10, e) * (1.0 - smoothstep(0.18, 0.32, e));
c = lerp(c, c * float3(0.75, 0.55, 0.85), band * 0.45);
c = lerp(c, float3(0.10, 0.07, 0.14), saturate(-e * 5.0));
// stars
float2 sp = float2(az * 110.0, e * 210.0);
float2 ci = floor(sp);
float2 cf = frac(sp);
float h = frac(sin(dot(ci, float2(12.9898, 78.233))) * 43758.5453);
float h2 = frac(sin(dot(ci, float2(39.3468, 11.135))) * 24634.6345);
float2 sc = float2(h, h2) * 0.6 + 0.2;
float star = step(0.94, h) * (1.0 - smoothstep(0.0, 0.09, length(cf - sc))) * saturate((e - 0.12) * 3.0);
c += star * float3(1.0, 0.95, 0.85) * (0.5 + h2) * 1.5;
// moon: big soft disc with craters and a halo
float disc = smoothstep(0.99430, 0.99470, m);
float2 mp = float2(dot(d, normalize(cross(md, float3(0, 0, 1)))), d.z - md.z);
float crat = sin(mp.x * 160.0 + 1.3) * sin(mp.y * 140.0) * 0.5 + sin(mp.x * 55.0 - mp.y * 75.0) * 0.5;
float3 moon = float3(1.0, 0.92, 0.75) * (0.85 + 0.12 * crat);
c = lerp(c, moon * 4.0, disc);
c += float3(1.0, 0.85, 0.70) * (pow(saturate(m), 500.0) * 0.9 + pow(saturate(m), 60.0) * 0.3) * (1.0 - disc);
return c * Brightness;
"""
m = new_material("M_TwilightSky")
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property("two_sided", True)
m.set_editor_property("is_sky", True)
wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -1100, 0)
cam = mel.create_material_expression(m, unreal.MaterialExpressionCameraPositionWS, -1100, 150)
sub = mel.create_material_expression(m, unreal.MaterialExpressionSubtract, -850, 50)
mel.connect_material_expressions(wp, "", sub, "A")
mel.connect_material_expressions(cam, "", sub, "B")
bright = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -850, 250)
bright.set_editor_property("parameter_name", "Brightness")
bright.set_editor_property("default_value", 0.42)
sky = custom(m, SKY, ["Dir", "Brightness"], -500, 50, "TwilightSky")
mel.connect_material_expressions(sub, "", sky, "Dir")
mel.connect_material_expressions(bright, "", sky, "Brightness")
finish(m, "M_TwilightSky", [mel.connect_material_property(sky, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)])

# ---- Rune circle
RUNE = """
float2 p = (UV - 0.5) * 2.0;
float r = length(p);
float g = 0.0;
g += 1.0 - smoothstep(0.0, 0.010, abs(r - 0.965));
g += 1.0 - smoothstep(0.0, 0.008, abs(r - 0.815));
g += (1.0 - smoothstep(0.0, 0.007, abs(r - 0.64))) * 0.9;
g += (1.0 - smoothstep(0.0, 0.006, abs(r - 0.25))) * 0.6;
for (int t = 0; t < 2; t++)
{
    for (int k = 0; k < 3; k++)
    {
        float a0 = 1.5707963 + t * 3.14159265 + k * 2.0943951;
        float a1 = a0 + 2.0943951;
        float2 A = float2(cos(a0), sin(a0)) * 0.64;
        float2 B = float2(cos(a1), sin(a1)) * 0.64;
        float2 pa = p - A;
        float2 ba = B - A;
        float hh = saturate(dot(pa, ba) / dot(ba, ba));
        g = max(g, 1.0 - smoothstep(0.0, 0.0075, length(pa - ba * hh)));
    }
}
float band = step(0.83, r) * step(r, 0.95);
float a = atan2(p.y, p.x) / 6.2831853 + 0.5;
float seg = floor(a * 44.0);
float u = frac(a * 44.0);
float v = (r - 0.83) / 0.12;
float h = frac(sin(seg * 91.7) * 43758.5453);
float h2 = frac(sin(seg * 37.3 + 4.1) * 12543.13);
float gl = 0.0;
gl += (1.0 - smoothstep(0.04, 0.08, abs(u - lerp(0.35, 0.65, h2)))) * step(0.18, v) * step(v, 0.82);
gl += (1.0 - smoothstep(0.035, 0.07, abs(v - lerp(0.3, 0.7, h)))) * step(0.25, u) * step(u, 0.75) * step(0.3, h2);
float dg = (u - 0.5) - (v - 0.5) * (h > 0.5 ? 0.7 : -0.7);
gl += (1.0 - smoothstep(0.035, 0.07, abs(dg))) * step(0.18, v) * step(v, 0.82) * step(h2, 0.6);
gl += (1.0 - smoothstep(0.035, 0.07, abs(length(float2((u - 0.5) * 0.8, v - 0.5)) - 0.22))) * step(0.72, h);
g += saturate(gl) * band * step(0.12, u) * step(u, 0.88);
float glow = exp(-abs(r - 0.965) * 40.0) * 0.25 + exp(-abs(r - 0.815) * 40.0) * 0.2 + exp(-r * 3.0) * 0.06;
float pulse = 0.85 + 0.15 * sin(Time * 1.6 + a * 18.0);
return float3(0.25, 1.0, 0.82) * (saturate(g) * 3.5 + glow * 1.2) * pulse * step(r, 1.0) * Reveal;
"""
m = new_material("M_RuneCircle")
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
uv = mel.create_material_expression(m, unreal.MaterialExpressionTextureCoordinate, -900, 0)
time = mel.create_material_expression(m, unreal.MaterialExpressionTime, -900, 150)
reveal = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -900, 300)
reveal.set_editor_property("parameter_name", "Reveal")  # 0..1, driven by the boss: on at his entrance and while he casts
reveal.set_editor_property("default_value", 1.0)
rc = custom(m, RUNE, ["UV", "Time", "Reveal"], -500, 0, "RuneCircle")
mel.connect_material_expressions(uv, "", rc, "UV")
mel.connect_material_expressions(time, "", rc, "Time")
mel.connect_material_expressions(reveal, "", rc, "Reveal")
finish(m, "M_RuneCircle", [mel.connect_material_property(rc, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)])

# ---- Lantern glow
m = new_material("M_LanternGlow")
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
col = mel.create_material_expression(m, unreal.MaterialExpressionConstant3Vector, -500, 0)
col.set_editor_property("constant", unreal.LinearColor(18.0, 8.5, 2.6, 1.0))
finish(m, "M_LanternGlow", [mel.connect_material_property(col, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)])

# ---- Wet mud
MUD = """
float n = frac(sin(dot(floor(WP.xy / 70.0), float2(41.3, 289.1))) * 9871.13) * 0.5
        + frac(sin(dot(floor(WP.xy / 23.0), float2(17.1, 93.7))) * 4371.7) * 0.5;
float l = dot(Dirt, float3(0.33, 0.33, 0.34));
return float3(0.30, 0.25, 0.22) * (0.45 + 0.9 * l) * lerp(0.8, 1.1, n);
"""
m = new_material("M_Mud")
wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -1400, 0)
mask = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, -1200, -100)
mask.set_editor_property("r", True)
mask.set_editor_property("g", True)
mask.set_editor_property("b", False)
mel.connect_material_expressions(wp, "", mask, "")
div = mel.create_material_expression(m, unreal.MaterialExpressionDivide, -1050, -100)
div.set_editor_property("const_b", 260.0)
mel.connect_material_expressions(mask, "", div, "A")
t = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -850, -100)
t.set_editor_property("texture", unreal.load_asset(LUSH + "/Landscape/Textures/T_GenericGravel_D"))
mel.connect_material_expressions(div, "", t, "UVs")
mc = custom(m, MUD, ["WP", "Dirt"], -450, 0, "Mud")
mel.connect_material_expressions(wp, "", mc, "WP")
mel.connect_material_expressions(t, "RGB", mc, "Dirt")
finish(m, "M_Mud", [mel.connect_material_property(mc, "", unreal.MaterialProperty.MP_BASE_COLOR),
                    mel.connect_material_property(const(m, 0.32, -300, 250), "", unreal.MaterialProperty.MP_ROUGHNESS)])

# ---- Cherry blossom leaves
path = DIR + "/MI_TreeLeaves_Sakura"
delete_if_exists(path)
mi = tools.create_asset("MI_TreeLeaves_Sakura", DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
mi.set_editor_property("parent", unreal.load_asset(DS + "/DreamscapeTower/Materials/Trees/MI_TreeLeaves_01"))
mel.set_material_instance_vector_parameter_value(mi, "Gradient Color Top", unreal.LinearColor(1.0, 0.62, 0.80, 1.0))
mel.set_material_instance_vector_parameter_value(mi, "Gradient Color Bottom", unreal.LinearColor(0.78, 0.30, 0.52, 1.0))
mel.set_material_instance_vector_parameter_value(mi, "Emissive Color", unreal.LinearColor(1.0, 0.75, 0.88, 1.0))
mel.update_material_instance(mi)
eal.save_loaded_asset(mi)
log("MI_TreeLeaves_Sakura")

# ---- Shallow water placeholder (until Fluid Flux): opaque, glossy, drifting ripple normals so the sky, moon and
# lanterns reflect in it.
m = new_material("M_ShallowWater")
wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -1500, 0)
time = mel.create_material_expression(m, unreal.MaterialExpressionTime, -1500, 200)
uv_code = "return WP.xy / %f + Time * float2(%f, %f);"
nrm = unreal.load_asset("/Game/DreamscapeSeries/SharedResources/Textures/Water/T_WaterNormal_01")
samples = []
for i, (size, fx, fy) in enumerate(((420.0, -0.045, -0.018), (260.0, -0.03, 0.02))):
    uvc = custom(m, uv_code % (size, fx, fy), ["WP", "Time"], -1150, i * 250, "WaterUV%d" % i,
                 unreal.CustomMaterialOutputType.CMOT_FLOAT2)
    mel.connect_material_expressions(wp, "", uvc, "WP")
    mel.connect_material_expressions(time, "", uvc, "Time")
    t = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, -850, i * 250)
    t.set_editor_property("texture", nrm)
    t.set_editor_property("sampler_type", unreal.MaterialSamplerType.SAMPLERTYPE_NORMAL)
    mel.connect_material_expressions(uvc, "", t, "UVs")
    samples.append(t)
nc = custom(m, "float3 n = normalize(float3(A.xy + B.xy, A.z * B.z)); return normalize(lerp(float3(0, 0, 1), n, 0.45));",
            ["A", "B"], -500, 100, "WaterNormal")
mel.connect_material_expressions(samples[0], "RGB", nc, "A")
mel.connect_material_expressions(samples[1], "RGB", nc, "B")
bc = custom(m, "float w = A.x * 0.5 + 0.5; return lerp(float3(0.015, 0.035, 0.06), float3(0.03, 0.09, 0.12), w);",
            ["A"], -500, -150, "WaterColor")
mel.connect_material_expressions(samples[0], "RGB", bc, "A")
finish(m, "M_ShallowWater", [mel.connect_material_property(bc, "", unreal.MaterialProperty.MP_BASE_COLOR),
                             mel.connect_material_property(nc, "", unreal.MaterialProperty.MP_NORMAL),
                             mel.connect_material_property(const(m, 0.03, -300, 300), "", unreal.MaterialProperty.MP_ROUGHNESS),
                             mel.connect_material_property(const(m, 0.9, -300, 400), "", unreal.MaterialProperty.MP_SPECULAR)])

# ---- Wet floor slabs: the Dreamscape floor instances with low roughness.
for src in ("MI_Floor_01", "MI_Floor_03"):
    name = src.replace("MI_Floor", "MI_FloorWet")
    delete_if_exists(DIR + "/" + name)
    mi = tools.create_asset(name, DIR, unreal.MaterialInstanceConstant, unreal.MaterialInstanceConstantFactoryNew())
    mi.set_editor_property("parent", unreal.load_asset(DS + "/DreamscapeTower/Materials/Structures/" + src))
    mel.set_material_instance_scalar_parameter_value(mi, "Roughness Intensity", 0.28)
    mel.update_material_instance(mi)
    eal.save_loaded_asset(mi)
    log(name)
