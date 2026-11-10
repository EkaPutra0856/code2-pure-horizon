# The VRoid face, eye, body and hair materials use alpha cutout in Blender (CLIP/HASHED), but the FBX
# importer makes them opaque, so the eye highlight covers the iris and the eyes render white.
# Sets those materials to Masked with the base texture's alpha as opacity mask. Safe to rerun.
import os
import unreal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "renders", "_log_ue_face_mats.txt")
mel = unreal.MaterialEditingLibrary
lib = unreal.EditorAssetLibrary
out = []
mesh = unreal.load_asset("/Game/Swordswoman/sw_ue")
for slot in mesh.get_editor_property("materials"):
    m = slot.get_editor_property("material_interface")
    name = m.get_name()
    if not name.startswith("M_N00_"):
        continue
    node = mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_BASE_COLOR)
    if not isinstance(node, unreal.MaterialExpressionTextureSample):
        out.append(f"{name} base node {type(node).__name__}, skipped")
        continue
    m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_MASKED)
    m.set_editor_property("opacity_mask_clip_value", 0.5)
    ok = mel.connect_material_property(node, "A", unreal.MaterialProperty.MP_OPACITY_MASK)
    mel.recompile_material(m)
    lib.save_loaded_asset(m, False)
    out.append(f"{name} masked {m.get_editor_property('blend_mode')} alpha linked {ok} two_sided {m.get_editor_property('two_sided')}")
out.append("DONE")
open(LOG, "w", encoding="utf-8").write("\n".join(out))
