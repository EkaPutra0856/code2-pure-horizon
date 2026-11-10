# Air combo / knock-up clips: print root and pelvis motion over time, then turn on root motion where
# the root travels (the player's montages use RootMotionFromMontagesOnly; without it the body slides
# off the capsule and snaps back). Run with -ExecutePythonScript; lines start with "BFAIR".
import unreal
AL = unreal.AnimationLibrary
eal = unreal.EditorAssetLibrary
NAMES = ["Air_Combo01_Z0_1", "Air_Combo01_Z0_2", "Air_Combo01_Z0_3", "Air_Down_Attack_Z0",
         "hit_bound_up_high", "hit_air01", "hit_down_idle_up", "rise_1", "hit_knockdown01"]
ENABLE = {"Air_Combo01_Z0_1", "Air_Combo01_Z0_2", "Air_Combo01_Z0_3", "hit_bound_up_high"}
for n in NAMES:
    path = "/Game/InsaneAirCombo/Animation/" + n
    seq = unreal.load_asset(path)
    if not seq:
        print("BFAIR missing", n); continue
    L = seq.get_play_length()
    rows = []
    t = 0.0
    while t <= L + 1e-4:
        r = AL.get_bone_pose_for_time(seq, "root", t, False).translation
        p = AL.get_bone_pose_for_time(seq, "pelvis", t, False).translation
        rows.append("%.2f:r(%.0f,%.0f,%.0f)p(%.0f,%.0f,%.0f)" % (t, r.x, r.y, r.z, p.x, p.y, p.z))
        t += max(L / 8.0, 0.05)
    print("BFAIR %s len=%.2f rm=%s %s" % (n, L, seq.get_editor_property("enable_root_motion"), " ".join(rows)))
    if n in ENABLE and not seq.get_editor_property("enable_root_motion"):
        seq.set_editor_property("enable_root_motion", True)
        eal.save_asset(path, only_if_is_dirty=False)
        print("BFAIR root motion on", n)
