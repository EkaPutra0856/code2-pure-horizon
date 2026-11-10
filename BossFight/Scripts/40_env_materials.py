# Environment materials for the two maps (world-aligned, so they work on scaled basic shapes):
#   /Game/BossFight/Env/M_ArenaFloor  - cracked flagstones (procedural Voronoi cells over LUSH rock texture),
#                                       moss in the joints, and a glowing aura-green rune circle (emissive).
#   /Game/BossFight/Env/M_TrainGround - grass with a worn dirt clearing in the middle (LUSH grass/gravel textures).
# Re-running rebuilds both from scratch.
import unreal

mel = unreal.MaterialEditingLibrary
eal = unreal.EditorAssetLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
DIR = "/Game/BossFight/Env"
LUSH = "/Game/LUSH_StylizedEnvironmentSet"


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def new_material(name):
    path = "%s/%s" % (DIR, name)
    if eal.does_asset_exist(path):
        eal.delete_asset(path)
    return tools.create_asset(name, DIR, unreal.Material, unreal.MaterialFactoryNew())


def tex(m, path, uv_node, x, y):
    t = mel.create_material_expression(m, unreal.MaterialExpressionTextureSample, x, y)
    t.set_editor_property("texture", unreal.load_asset(path))
    mel.connect_material_expressions(uv_node, "", t, "UVs")
    return t


def world_uv(m, wp, size, x, y):
    # WorldPosition.xy / size
    mask = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, x, y)
    mask.set_editor_property("r", True)
    mask.set_editor_property("g", True)
    mask.set_editor_property("b", False)
    mel.connect_material_expressions(wp, "", mask, "")
    div = mel.create_material_expression(m, unreal.MaterialExpressionDivide, x + 150, y)
    div.set_editor_property("const_b", size)
    mel.connect_material_expressions(mask, "", div, "A")
    return div


def custom(m, code, out_type, inputs, x, y, desc):
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


VORONOI = """
float2 p = WP.xy / 150.0;
float2 ip = floor(p);
float2 fp = frac(p);
float d1 = 8.0;
float d2 = 8.0;
float2 id = float2(0, 0);
for (int j = -1; j <= 1; j++)
{
    for (int i = -1; i <= 1; i++)
    {
        float2 g = float2(i, j);
        float2 h = frac(sin(float2(dot(ip + g, float2(127.1, 311.7)), dot(ip + g, float2(269.5, 183.3)))) * 43758.5453);
        float2 r = g + 0.15 + 0.7 * h - fp;
        float d = dot(r, r);
        if (d < d1) { d2 = d1; d1 = d; id = ip + g; }
        else if (d < d2) { d2 = d; }
    }
}
float edge = sqrt(d2) - sqrt(d1);
float groove = smoothstep(0.03, 0.11, edge);
float tint = frac(sin(dot(id, float2(12.9898, 78.233))) * 43758.5453);
float crack = smoothstep(0.0, 0.012, abs(frac(dot(fp, float2(0.7, 0.3)) * 1.7 + tint * 3.1) - 0.5) - 0.01 + step(0.35, tint));
"""

FLOOR_COLOR = VORONOI + """
float rl = dot(Rock, float3(0.33, 0.33, 0.34));
float3 rock = lerp(rl.xxx, Rock, 0.35) * float3(0.95, 0.98, 1.05) * lerp(0.75, 1.2, tint) * 1.7;
float n = frac(sin(dot(floor(WP.xy / 260.0), float2(41.3, 289.1))) * 9871.13);
float mossMask = saturate((1.0 - groove) * 0.85 + step(0.78, n) * 0.35 * (1.0 - groove * 0.5));
float3 c = lerp(rock * lerp(0.25, 1.0, groove) * lerp(0.6, 1.0, crack), Moss * float3(0.45, 0.6, 0.4), mossMask * 0.55);
return c;
"""

RUNES = """
float r = length(WP.xy);
float ring = 0.0;
ring += 1.0 - smoothstep(0.0, 7.0, abs(r - 1120.0));
ring += 1.0 - smoothstep(0.0, 7.0, abs(r - 1380.0));
ring += (1.0 - smoothstep(0.0, 5.0, abs(r - 620.0))) * 0.6;
float band = step(1165.0, r) * step(r, 1335.0);
float a = atan2(WP.y, WP.x) / 6.2831853 + 0.5;
float seg = floor(a * 60.0);
float u = frac(a * 60.0);
float v = (r - 1165.0) / 170.0;
float h = frac(sin(seg * 91.7) * 43758.5453);
float h2 = frac(sin(seg * 37.3 + 4.1) * 12543.13);
float g = 0.0;
g += (1.0 - smoothstep(0.035, 0.07, abs(u - lerp(0.35, 0.65, h2)))) * step(0.15, v) * step(v, 0.85);
g += (1.0 - smoothstep(0.03, 0.06, abs(v - lerp(0.25, 0.75, h)))) * step(0.22, u) * step(u, 0.78) * step(0.25, h2);
float dg = (u - 0.5) - (v - 0.5) * (h > 0.5 ? 0.6 : -0.6);
g += (1.0 - smoothstep(0.03, 0.06, abs(dg))) * step(0.15, v) * step(v, 0.85) * step(h2, 0.65);
g += (1.0 - smoothstep(0.03, 0.06, abs(length(float2((u - 0.5) * 0.7, v - 0.5)) - 0.22))) * step(0.7, h);
g *= band * step(0.1, u) * step(u, 0.9);
float pulse = 0.85 + 0.15 * sin(Time * 1.7 + a * 25.0);
return float3(0.25, 1.0, 0.6) * saturate(ring + g) * 7.0 * pulse;
"""

TRAIN_COLOR = """
float r = length(WP.xy - Center);
float n = frac(sin(dot(floor(WP.xy / 90.0), float2(41.3, 289.1))) * 9871.13) * 0.5
        + frac(sin(dot(floor(WP.xy / 37.0), float2(17.1, 93.7))) * 4371.7) * 0.5;
float dirt = 1.0 - smoothstep(Radius - 160.0 + n * 120.0, Radius + 90.0 + n * 120.0, r);
float3 grass = Grass * lerp(0.85, 1.1, n);
float dl = dot(Dirt, float3(0.33, 0.33, 0.34));
float3 soil = float3(0.60, 0.49, 0.33) * (0.55 + 0.9 * dl) * lerp(0.9, 1.08, n);
return lerp(grass, soil, dirt);
"""


# ---- Arena floor
m = new_material("M_ArenaFloor")
wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -1400, 0)
uv_rock = world_uv(m, wp, 420.0, -1200, -300)
uv_moss = world_uv(m, wp, 300.0, -1200, -100)
rock = tex(m, LUSH + "/Meshes/Rocks/Textures/T_RockSurface_D_01", uv_rock, -850, -350)
moss = tex(m, LUSH + "/Meshes/Rocks/Textures/T_StylizedMoss_D", uv_moss, -850, -100)
col = custom(m, FLOOR_COLOR, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Rock", "Moss"], -450, -200, "ArenaFloorColor")
mel.connect_material_expressions(wp, "", col, "WP")
mel.connect_material_expressions(rock, "RGB", col, "Rock")
mel.connect_material_expressions(moss, "RGB", col, "Moss")
time = mel.create_material_expression(m, unreal.MaterialExpressionTime, -700, 300)
runes = custom(m, RUNES, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Time"], -450, 200, "ArenaRunes")
mel.connect_material_expressions(wp, "", runes, "WP")
mel.connect_material_expressions(time, "", runes, "Time")
rough = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 450)
rough.set_editor_property("r", 0.88)
ok = [mel.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR),
      mel.connect_material_property(runes, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR),
      mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)]
mel.recompile_material(m)
eal.save_loaded_asset(m)
log("M_ArenaFloor", ok)

# ---- Training ground
m = new_material("M_TrainGround")
wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -1400, 0)
uv_g = world_uv(m, wp, 380.0, -1200, -300)
uv_d = world_uv(m, wp, 300.0, -1200, -100)
grass = tex(m, LUSH + "/Landscape/Textures/T_LushGrass_D", uv_g, -850, -350)
dirt = tex(m, LUSH + "/Landscape/Textures/T_GenericGravel_D", uv_d, -850, -100)
center = mel.create_material_expression(m, unreal.MaterialExpressionVectorParameter, -850, 150)
center.set_editor_property("parameter_name", "Center")
center.set_editor_property("default_value", unreal.LinearColor(-400.0, 0.0, 0.0, 0.0))
cmask = mel.create_material_expression(m, unreal.MaterialExpressionComponentMask, -650, 150)
cmask.set_editor_property("r", True)
cmask.set_editor_property("g", True)
cmask.set_editor_property("b", False)
mel.connect_material_expressions(center, "", cmask, "")
radius = mel.create_material_expression(m, unreal.MaterialExpressionScalarParameter, -850, 300)
radius.set_editor_property("parameter_name", "Radius")
radius.set_editor_property("default_value", 1100.0)
col = custom(m, TRAIN_COLOR, unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Grass", "Dirt", "Center", "Radius"], -450, -100, "TrainGroundColor")
for a, b in ((wp, "WP"), (cmask, "Center"), (radius, "Radius")):
    mel.connect_material_expressions(a, "", col, b)
mel.connect_material_expressions(grass, "RGB", col, "Grass")
mel.connect_material_expressions(dirt, "RGB", col, "Dirt")
rough = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 300)
rough.set_editor_property("r", 0.92)
ok = [mel.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR),
      mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS)]
mel.recompile_material(m)
eal.save_loaded_asset(m)
log("M_TrainGround", ok)

# ---- Stream water: the LUSH water needs real depth below it, our stream sits on flat ground, so use a simple
# glossy blue surface (sky reflections + fresnel sheen) with slowly drifting ripples in the colour.
m = new_material("M_RiverWater")
wp = mel.create_material_expression(m, unreal.MaterialExpressionWorldPosition, -900, 0)
time = mel.create_material_expression(m, unreal.MaterialExpressionTime, -900, 200)
col = custom(m, """
float2 p = WP.xy / 90.0 + float2(Time * 0.35, Time * 0.12);
float w = sin(p.x * 1.7 + sin(p.y * 1.3)) * 0.5 + sin(p.y * 2.3 - p.x * 0.7) * 0.5;
return lerp(float3(0.03, 0.13, 0.20), float3(0.10, 0.30, 0.38), saturate(w * 0.5 + 0.5) * 0.6);
""", unreal.CustomMaterialOutputType.CMOT_FLOAT3, ["WP", "Time"], -500, 0, "RiverColor")
mel.connect_material_expressions(wp, "", col, "WP")
mel.connect_material_expressions(time, "", col, "Time")
rough = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 250)
rough.set_editor_property("r", 0.06)
spec = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -300, 350)
spec.set_editor_property("r", 0.9)
ok = [mel.connect_material_property(col, "", unreal.MaterialProperty.MP_BASE_COLOR),
      mel.connect_material_property(rough, "", unreal.MaterialProperty.MP_ROUGHNESS),
      mel.connect_material_property(spec, "", unreal.MaterialProperty.MP_SPECULAR)]
mel.recompile_material(m)
eal.save_loaded_asset(m)
log("M_RiverWater", ok)
