# Locks root translation on in-place locomotion clips (they carry root motion that
# made the mesh run ahead of the capsule and snap back each cycle), then rebuilds
# BS_PlayerLoco + ABP_Player.
import unreal
eal = unreal.EditorAssetLibrary
for n in ["run", "run_fast", "jump_start", "jump_landing", "jump", "jump_long"]:
    path = "/Game/InsaneAirCombo/Animation/" + n
    seq = unreal.load_asset(path)
    if not seq:
        unreal.log_warning("BUILD: missing " + path); continue
    seq.set_editor_property("force_root_lock", True)
    seq.set_editor_property("enable_root_motion", False)
    eal.save_asset(path, only_if_is_dirty=False)
    unreal.log("BUILD: root lock " + n)
for line in unreal.BFEditorTools.build_player_anim_blueprint().splitlines():
    unreal.log("BUILD: " + line)
