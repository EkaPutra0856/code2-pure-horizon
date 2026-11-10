# Root displacement / native speed of locomotion anims, plus root-lock flags.
import unreal
AL = unreal.AnimationLibrary
NAMES = ["Idle", "run", "run_fast", "strafe_walk_F", "strafe_walk_B", "strafe_walk_L", "strafe_walk_R",
         "strafe_run_F", "strafe_run_B", "strafe_run_L", "strafe_run_R", "strafe_run_L45", "jump_start", "jump_loop", "jump_landing", "Rolling"]
for n in NAMES:
    seq = unreal.load_asset("/Game/InsaneAirCombo/Animation/" + n)
    if not seq:
        print("BFL missing", n); continue
    L = seq.get_play_length()
    r = [AL.get_bone_pose_for_time(seq, "root", t, False).translation for t in (0.0, L * 0.5, L)]
    p = [AL.get_bone_pose_for_time(seq, "pelvis", t, False).translation for t in (0.0, L * 0.5, L)]
    d = r[2] - r[0]
    dist = (d.x ** 2 + d.y ** 2) ** 0.5
    print("BFL %-16s len=%.2f rm=%s lock=%s root_d=(%.0f,%.0f,%.0f) speed=%.0f pelvis_mid=(%.0f,%.0f,%.0f)" % (
        n, L, seq.get_editor_property("enable_root_motion"), seq.get_editor_property("force_root_lock"),
        d.x, d.y, d.z, dist / L if L > 0 else 0, p[1].x - p[0].x, p[1].y - p[0].y, p[1].z - p[0].z))
