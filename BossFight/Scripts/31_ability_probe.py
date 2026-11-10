# Feature batch probe: Sevarog ability clips (grab / sweep / thrust / phase-2 candidates) and the
# player's strafe + air clips. Sevarog: per clip, hammer head (root_weapon_end_r) and hand_r path in
# component space (mesh yaw -90: actor forward = mesh +Y), weapon-speed windows, root and pelvis motion.
import unreal
AL = unreal.AnimationLibrary
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
SB = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/"
PB = "/Game/InsaneAirCombo/Animation/"


def bone(seq, b, t):
    return APE.get_bone_pose(APE.get_anim_pose_at_time(seq, t, opts), b, unreal.AnimPoseSpaces.WORLD).translation


SEV = ["Soul_Siphon", "Subjugation", "Swing_In_Air", "Swing_In_Air_120fps", "Cast", "Speedburst", "LevelStart",
       "Stage_1", "Stage_2", "Stage_3", "Stage_4", "Emote_Pointing_MC_T3", "Emote_Pull_MC_T1", "Victory_Emote", "Recall",
       "Travel_Mode_Start", "Travel_Mode_Start_InPlace", "Travel_Mode_Idle", "Travel_Mode_Bwd_Start", "Ultimate_Targeting",
       "Swing1_Slow", "Swing2_Slow", "Swing3_Slow", "Knock_back_bwd", "Jump_Start", "Jump_Land", "Soul_Siphon_Targeting"]
for n in SEV:
    seq = unreal.load_asset(SB + n)
    if not seq:
        print("ABP missing", n)
        continue
    L = seq.get_play_length()
    N = 12
    rows = []
    for i in range(N + 1):
        t = L * i / N
        w = bone(seq, "root_weapon_end_r", t)
        h = bone(seq, "hand_r", t)
        p = bone(seq, "pelvis", t)
        # forward = mesh +Y, right = mesh -X (mesh yaw -90)
        rows.append("%.2f:W(f%.0f r%.0f z%.0f) H(f%.0f z%.0f) P(f%.0f z%.0f)" % (t, w.y, -w.x, w.z, h.y, h.z, p.y, p.z))
    dt = 1.0 / 30.0
    prev = bone(seq, "root_weapon_end_r", 0.0)
    t = dt
    wins, on, peak = [], None, (0.0, 0.0)
    while t <= L + 1e-4:
        cur = bone(seq, "root_weapon_end_r", t)
        s = (cur - prev).length() / dt
        if s > peak[1]:
            peak = (t, s)
        if s > 700 and on is None:
            on = t
        if s <= 700 and on is not None:
            wins.append("%.2f-%.2f" % (on, t))
            on = None
        prev = cur
        t += dt
    if on is not None:
        wins.append("%.2f-%.2f" % (on, L))
    r0 = bone(seq, "root", 0.0)
    r1 = bone(seq, "root", L)
    print("ABP %s len=%.2f rm=%s root_d=(f%.0f r%.0f z%.0f) peak=%.0f@%.2f wins=%s" % (n, L, seq.get_editor_property("enable_root_motion"),
          r1.y - r0.y, -(r1.x - r0.x), r1.z - r0.z, peak[1], peak[0], ",".join(wins)))
    print("ABP   " + " | ".join(rows))

PL = ["run", "strafe_run_F", "strafe_run_B", "strafe_run_L", "strafe_run_R", "strafe_run_L45", "strafe_run_R45", "strafe_run_L135",
      "strafe_run_R135", "strafe_walk_F", "strafe_walk_B", "strafe_walk_L", "strafe_walk_R", "strafe_walk_L45", "strafe_walk_R45",
      "strafe_walk_L135", "strafe_walk_R135", "Air_Down_Attack_Z0", "Air_Attack01_Z0", "Air_Attack05_Z0", "Air_Dash_Attack_Z0",
      "Attack_Jump_to_Air", "Pierce_Air", "Upper_Swing", "Air_Spin_Attack_Z0", "jump_start", "jump_landing", "hit_air01", "Rolling"]
for n in PL:
    seq = unreal.load_asset(PB + n)
    if not seq:
        print("ABP missing", n)
        continue
    L = seq.get_play_length()
    r0 = AL.get_bone_pose_for_time(seq, "root", 0.0, False).translation
    r1 = AL.get_bone_pose_for_time(seq, "root", L, False).translation
    p = [bone(seq, "pelvis", L * i / 6) for i in range(7)]
    hr = [bone(seq, "hand_r", L * i / 6) for i in range(7)]
    d = r1 - r0
    # mannequin: forward = mesh +Y, right = mesh +X
    print("ABP P %s len=%.2f rm=%s root_d=(f%.0f r%.0f z%.0f) speed=%.0f pelvis=%s hand_r_z=%s" % (
        n, L, seq.get_editor_property("enable_root_motion"), d.y, d.x, d.z, (d.x ** 2 + d.y ** 2) ** 0.5 / L,
        " ".join("(%.0f,%.0f,%.0f)" % (q.x, q.y, q.z) for q in p), " ".join("%.0f" % q.z for q in hr)))
