# Phase 4 builder: M_PP_Ink, a post-process ink outline used by the parry clash camera.
# Edges come from depth and world-normal discontinuities; edge pixels are darkened toward black ink.
import unreal
eal = unreal.EditorAssetLibrary
mel = unreal.MaterialEditingLibrary
MAT = "/Game/BossFight/FX/M_PP_Ink"
if eal.does_asset_exist(MAT):
    eal.delete_asset(MAT)
mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset("M_PP_Ink", "/Game/BossFight/FX", unreal.Material, unreal.MaterialFactoryNew())
mat.set_editor_property("material_domain", unreal.MaterialDomain.MD_POST_PROCESS)
mat.set_editor_property("blendable_location", unreal.BlendableLocation.BL_SCENE_COLOR_AFTER_TONEMAPPING)


def node(cls, x, y, **props):
    n = mel.create_material_expression(mat, cls, x, y)
    for k, v in props.items():
        n.set_editor_property(k, v)
    return n


# Scene texture node so SceneTextureLookup is available to the custom node.
st = node(unreal.MaterialExpressionSceneTexture, -900, 200)
st.set_editor_property("scene_texture_id", unreal.SceneTextureId.PPI_POST_PROCESS_INPUT0)
thick = node(unreal.MaterialExpressionScalarParameter, -900, 0, parameter_name="Thickness", default_value=1.6)
strength = node(unreal.MaterialExpressionScalarParameter, -900, 100, parameter_name="Strength", default_value=0.9)

code = r"""
float2 uv = GetDefaultSceneTextureUV(Parameters, 14);
float2 t = View.BufferSizeAndInvSize.zw * Thickness;
float3 c = SceneTextureLookup(uv, 14, false).rgb;
float dC = SceneTextureLookup(uv, 1, false).r;
float3 nC = SceneTextureLookup(uv, 8, false).rgb;
float e = 0;
float2 o[4] = { float2(t.x, 0), float2(-t.x, 0), float2(0, t.y), float2(0, -t.y) };
for (int i = 0; i < 4; i++)
{
    float d = SceneTextureLookup(uv + o[i], 1, false).r;
    float3 n = SceneTextureLookup(uv + o[i], 8, false).rgb;
    e = max(e, saturate((abs(d - dC) / max(dC, 1.0) - 0.04) * 12.0));
    e = max(e, saturate((1.0 - dot(n, nC)) * 2.5 - 0.35));
}
e *= saturate(1.0 - dC / 6000.0);
float3 ink = c * 0.06;
// Slight punchier shading inside shapes.
float3 graded = saturate((c - 0.5) * 1.12 + 0.5);
return lerp(graded, ink, saturate(e * Strength)) + Dummy.r * 0;
"""
custom = node(unreal.MaterialExpressionCustom, -500, 100)
custom.set_editor_property("code", code)
custom.set_editor_property("output_type", unreal.CustomMaterialOutputType.CMOT_FLOAT3)
custom.set_editor_property("description", "InkOutline")
ins = []
for name in ["Thickness", "Strength", "Dummy"]:
    ci = unreal.CustomInput()
    ci.set_editor_property("input_name", name)
    ins.append(ci)
custom.set_editor_property("inputs", ins)
mel.connect_material_expressions(thick, "", custom, "Thickness")
mel.connect_material_expressions(strength, "", custom, "Strength")
mel.connect_material_expressions(st, "Color", custom, "Dummy")
mel.connect_material_property(custom, "", unreal.MaterialProperty.MP_EMISSIVE_COLOR)
mel.recompile_material(mat)
eal.save_asset(MAT, only_if_is_dirty=False)
unreal.log("BUILD: material " + MAT)
