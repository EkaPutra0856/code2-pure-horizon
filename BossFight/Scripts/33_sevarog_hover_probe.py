# Sevarog hover/cast candidates: length plus root and pelvis motion over time (read-only).
# Run with -ExecutePythonScript; lines start with "BFHOV".
import unreal
AL = unreal.AnimationLibrary
A = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/"
NAMES = ["Cast", "Travel_Mode_Start_InPlace", "Travel_Mode_Idle", "Travel_Mode_Idle_Hover_Left",
         "Travel_Mode_Idle_Hover_Rt", "Soul_Siphon", "Soul_Siphon_Targeting", "Soul_Siphon_Targeting_Loop",
         "Ultimate_Targeting", "Ultimate_Targeting_Loop", "Ultimate_Swing_120fps", "Subjugation",
         "Stage_1", "Stage_2", "Stage_3", "Stage_4", "Speedburst", "Jump_Fall_Loop", "Jump_Land", "LevelStart"]
for n in NAMES:
    seq = unreal.load_asset(A + n)
    if not seq:
        print("BFHOV missing", n)
        continue
    L = seq.get_play_length()
    rows = []
    t = 0.0
    while t <= L + 1e-4:
        r = AL.get_bone_pose_for_time(seq, "root", t, False).translation
        p = AL.get_bone_pose_for_time(seq, "pelvis", t, False).translation
        rows.append("%.2f:r(%.0f,%.0f,%.0f)p(%.0f,%.0f,%.0f)" % (t, r.x, r.y, r.z, p.x, p.y, p.z))
        t += max(L / 8.0, 0.05)
    print("BFHOV %s len=%.2f loop=%s %s" % (n, L, seq.get_editor_property("loop") if hasattr(seq, "loop") else "?", " ".join(rows)))
