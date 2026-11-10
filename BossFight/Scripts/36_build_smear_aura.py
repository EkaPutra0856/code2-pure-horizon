# Builds the smear / aura materials, makes the Lucy slide clips playable on the player, and rebuilds
# ABP_Player (its blend space gains the Shift-sprint sample).
#   M_Smear     additive ribbon for UBFSmearTrail (sword slash arc, speed streaks)
#   M_BossAura  additive inflated shell on Sevarog (fresnel rim + rising noise), faded by "Fade"
# Run: UnrealEditor-Cmd BossFight.uproject -ExecutePythonScript=Scripts/36_build_smear_aura.py -unattended -nullrhi
import unreal

eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
tools = unreal.AssetToolsHelpers.get_asset_tools()
NOISE = "/Game/Hack_And_Slash_FX/Textures/Noise/T_VFX_Noise_3.T_VFX_Noise_3"


def log(*a):
    unreal.log("BUILD: " + " ".join(str(x) for x in a))


def new_material(path):
    folder, name = path.rsplit("/", 1)
    if eal.does_asset_exist(path):
        eal.load_asset(path)
        eal.delete_asset(path)
    return tools.create_asset(name, folder, unreal.Material, unreal.MaterialFactoryNew())


def mk(mat, cls, x, y, **props):
    n = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


def link(a, b, pin, out=""):
    mel.connect_material_expressions(a, out, b, pin)


def mul(mat, x, y, a, b=None, const_b=None, out_a=""):
    n = mk(mat, unreal.MaterialExpressionMultiply, x, y)
    link(a, n, "A", out_a)
    if b is not None:
        link(b, n, "B")
    elif const_b is not None:
        n.set_editor_property("const_b", const_b)
    return n


noise_tex = unreal.load_asset(NOISE)
log("noise", noise_tex.get_path_name() if noise_tex else "MISSING")

# ---------------------------------------------------------------- M_Smear
# UV: U = age (0 new .. 1 old), V = 0 inner edge .. 1 outer edge.
# Emissive = Color * Intensity * (1-U)^2 * Profile(V) * Noise
# Profile = lerp(centre streak 1-|2V-1|, outer crescent V^1.5 * sat((1-V)*10), Outer)
P = "/Game/BossFight/FX/M_Smear"
m = new_material(P)
m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property("two_sided", True)

uv = mk(m, unreal.MaterialExpressionTextureCoordinate, -1600, 0)
u = mk(m, unreal.MaterialExpressionComponentMask, -1400, -100, r=True, g=False, b=False, a=False)
v = mk(m, unreal.MaterialExpressionComponentMask, -1400, 150, r=False, g=True, b=False, a=False)
link(uv, u, "")
link(uv, v, "")
# age fade
inv_u = mk(m, unreal.MaterialExpressionOneMinus, -1200, -100)
link(u, inv_u, "")
age = mul(m, -1000, -100, inv_u, inv_u)
# outer crescent
vp = mk(m, unreal.MaterialExpressionPower, -1200, 150)
link(v, vp, "Base")
vp.set_editor_property("const_exponent", 1.5)
inv_v = mk(m, unreal.MaterialExpressionOneMinus, -1200, 300)
link(v, inv_v, "")
rim = mul(m, -1000, 300, inv_v, const_b=10.0)
rim_s = mk(m, unreal.MaterialExpressionSaturate, -850, 300)
link(rim, rim_s, "")
outer = mul(m, -700, 200, vp, rim_s)
# centre streak: 1 - |2V - 1|
v2 = mul(m, -1200, 450, v, const_b=2.0)
v2m = mk(m, unreal.MaterialExpressionSubtract, -1050, 450)
link(v2, v2m, "A")
v2m.set_editor_property("const_b", 1.0)
vabs = mk(m, unreal.MaterialExpressionAbs, -900, 450)
link(v2m, vabs, "")
centre = mk(m, unreal.MaterialExpressionOneMinus, -750, 450)
link(vabs, centre, "")
outer_p = mk(m, unreal.MaterialExpressionScalarParameter, -700, 600, parameter_name="Outer", default_value=1.0)
prof = mk(m, unreal.MaterialExpressionLinearInterpolate, -500, 300)
link(centre, prof, "A")
link(outer, prof, "B")
link(outer_p, prof, "Alpha")
# noise streaks along the ribbon: sample (U * 0.6 + time, V * 0.15)
nuv = mul(m, -1200, 700, uv, None, None)
nuv_scale = mk(m, unreal.MaterialExpressionConstant2Vector, -1400, 800, r=0.6, g=0.15)
link(nuv_scale, nuv, "B")
pan = mk(m, unreal.MaterialExpressionPanner, -1000, 700, speed_x=1.5, speed_y=0.0)
link(nuv, pan, "Coordinate")
tex = mk(m, unreal.MaterialExpressionTextureSample, -800, 700)
tex.set_editor_property("texture", noise_tex)
link(pan, tex, "UVs")
nz = mk(m, unreal.MaterialExpressionLinearInterpolate, -550, 700)
nz.set_editor_property("const_a", 0.45)
nz.set_editor_property("const_b", 1.25)
link(tex, nz, "Alpha", "R")
color = mk(m, unreal.MaterialExpressionVectorParameter, -500, -300, parameter_name="Color", default_value=unreal.LinearColor(0.35, 0.8, 1.0, 1.0))
inten = mk(m, unreal.MaterialExpressionScalarParameter, -500, -150, parameter_name="Intensity", default_value=4.0)
e1 = mul(m, -300, -200, color, inten)
e2 = mul(m, -300, 0, age, prof)
e3 = mul(m, -150, 100, e2, nz)
emis = mul(m, 0, 0, e1, e3)
mel.connect_material_property(emis, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(m)
eal.save_asset(P, only_if_is_dirty=False)
log("saved", P)

# ---------------------------------------------------------------- M_BossAura
# Inflated shell (WPO along the normal), emissive = Color * Intensity * Fade * (fresnel^2 * (0.35 + noise))
P = "/Game/BossFight/FX/M_BossAura"
m = new_material(P)
m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_ADDITIVE)
m.set_editor_property("shading_model", unreal.MaterialShadingModel.MSM_UNLIT)
m.set_editor_property("used_with_skeletal_mesh", True)

nrm = mk(m, unreal.MaterialExpressionVertexNormalWS, -900, 900)
infl = mk(m, unreal.MaterialExpressionScalarParameter, -900, 1050, parameter_name="Inflate", default_value=2.5)
fade = mk(m, unreal.MaterialExpressionScalarParameter, -900, 500, parameter_name="Fade", default_value=1.0)
infl_f = mul(m, -700, 1050, infl, fade)
wpo = mul(m, -500, 950, nrm, infl_f)
mel.connect_material_property(wpo, "", unreal.MaterialProperty.MP_WORLD_POSITION_OFFSET)

fres = mk(m, unreal.MaterialExpressionFresnel, -1100, 0)
fres.set_editor_property("exponent", 2.2)
fres.set_editor_property("base_reflect_fraction", 0.0)
# world-space noise rising up the body: UV = ((x + y) * k, z * k), panned upward
wp = mk(m, unreal.MaterialExpressionWorldPosition, -1700, 300)
wx = mk(m, unreal.MaterialExpressionComponentMask, -1500, 250, r=True, g=False, b=False, a=False)
wy = mk(m, unreal.MaterialExpressionComponentMask, -1500, 350, r=False, g=True, b=False, a=False)
wz = mk(m, unreal.MaterialExpressionComponentMask, -1500, 450, r=False, g=False, b=True, a=False)
for c in (wx, wy, wz):
    link(wp, c, "")
wxy = mk(m, unreal.MaterialExpressionAdd, -1350, 300)
link(wx, wxy, "A")
link(wy, wxy, "B")
app = mk(m, unreal.MaterialExpressionAppendVector, -1200, 350)
link(wxy, app, "A")
link(wz, app, "B")
wuv = mul(m, -1050, 350, app, const_b=0.006)
pan = mk(m, unreal.MaterialExpressionPanner, -900, 350, speed_x=0.03, speed_y=-0.35)
link(wuv, pan, "Coordinate")
tex = mk(m, unreal.MaterialExpressionTextureSample, -700, 350)
tex.set_editor_property("texture", noise_tex)
link(pan, tex, "UVs")
nz = mk(m, unreal.MaterialExpressionAdd, -500, 350)
link(tex, nz, "A", "R")
nz.set_editor_property("const_b", 0.35)
glow = mul(m, -350, 200, fres, nz)
color = mk(m, unreal.MaterialExpressionVectorParameter, -500, -250, parameter_name="Color", default_value=unreal.LinearColor(0.2, 0.9, 0.5, 1.0))
inten = mk(m, unreal.MaterialExpressionScalarParameter, -500, -100, parameter_name="Intensity", default_value=3.0)
ci = mul(m, -300, -200, color, inten)
cif = mul(m, -150, -100, ci, fade)
emis = mul(m, 0, 0, cif, glow)
mel.connect_material_property(emis, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(m)
eal.save_asset(P, only_if_is_dirty=False)
log("saved", P)

# ---------------------------------------------------------------- Lucy slides on the player skeleton
PLAYER_SK = "/Game/InsaneAirCombo/Animation/Skeleton/UE4_Mannequin_Skeleton.UE4_Mannequin_Skeleton"
LUCY_SK = "/Game/Lucy/DEMO/Mannequin/Character/Mesh/UE4_Mannequin_Skeleton.UE4_Mannequin_Skeleton"
psk = unreal.load_asset(PLAYER_SK)
lsk = unreal.load_asset(LUCY_SK)
for a, b in ((psk, lsk), (lsk, psk)):
    comp = list(a.get_editor_property("compatible_skeletons"))
    paths = [str(c.get_path_name()) if hasattr(c, "get_path_name") else str(c) for c in comp]
    if b.get_path_name() not in paths:
        comp.append(b)
        a.set_editor_property("compatible_skeletons", comp)
        eal.save_loaded_asset(a, only_if_is_dirty=False)
    log("compatible", a.get_path_name(), [str(c) for c in a.get_editor_property("compatible_skeletons")])

# ---------------------------------------------------------------- player Anim Blueprint (sprint sample)
for line in unreal.BFEditorTools.build_player_anim_blueprint().splitlines():
    log(line)
