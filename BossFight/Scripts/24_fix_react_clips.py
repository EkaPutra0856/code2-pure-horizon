# Reaction clip fixes (from Scripts/22_react_probe.py):
#  - hit_knockdown02 (big blow-back, root travels 2.15 m) gets root motion so the capsule follows the body.
#  - Dead_Dead1 / Dead_Dead3 drift their root (0.4 / 0.7 m) without root motion: the body slid away
#    from the capsule and snapped back on recovery. Lock the root so they fall in place.
import unreal
eal = unreal.EditorAssetLibrary
BASE = "/Game/InsaneAirCombo/Animation/"
for name, rm, lock in [("hit_knockdown02", True, False), ("Dead_Dead1", False, True), ("Dead_Dead3", False, True)]:
    seq = unreal.load_asset(BASE + name)
    if not seq:
        unreal.log_warning("BUILD: missing " + name)
        continue
    seq.set_editor_property("enable_root_motion", rm)
    seq.set_editor_property("force_root_lock", lock)
    eal.save_asset(BASE + name, only_if_is_dirty=False)
    unreal.log("BUILD: %s root_motion=%d root_lock=%d" % (name, rm, lock))
