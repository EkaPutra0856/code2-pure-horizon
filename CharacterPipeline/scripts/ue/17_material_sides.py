# Blender draws thin cloth, petals and hair from both sides, Unreal does not by default, so much
# of the skirt vanished. Turns on two-sided for those materials and makes the cape see-through.
# Safe to rerun.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_sides.txt")
mel = unreal.MaterialEditingLibrary
lib = unreal.EditorAssetLibrary
out = []
SKIN_ONLY = ("EyeIris", "EyeWhite", "EyeHighlight", "FaceMouth", "Face_00", "FaceBrow", "FaceEyeline", "Body_00")
mesh = unreal.load_asset("/Game/Character/karakter_ue")
for slot in mesh.get_editor_property("materials"):
    m = slot.get_editor_property("material_interface")
    name = m.get_name()
    if any(k in name for k in SKIN_ONLY):
        continue
    m.set_editor_property("two_sided", True)
    if name == "M_Outfit_Cape":
        m.set_editor_property("blend_mode", unreal.BlendMode.BLEND_TRANSLUCENT)
        if mel.get_material_property_input_node(m, unreal.MaterialProperty.MP_OPACITY) is None:
            c = mel.create_material_expression(m, unreal.MaterialExpressionConstant, -400, 300)
            c.set_editor_property("r", 0.35)
            mel.connect_material_property(c, "", unreal.MaterialProperty.MP_OPACITY)
    mel.recompile_material(m)
    lib.save_loaded_asset(m, False)
    out.append(f"{name} two_sided {m.get_editor_property('two_sided')} blend {m.get_editor_property('blend_mode')}")
out.append("DONE")
open(LOG, "w", encoding="utf-8").write("\n".join(out))
