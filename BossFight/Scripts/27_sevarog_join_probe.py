# Sevarog clip joins: pose distance (cm, mean over key bones, root-relative) between the end of one
# clip and points of the next, to pick chains that continue without a pop. Also lists where the
# best match inside the next clip is (so a chain can start the follow-up mid-clip).
import unreal
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
B = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/"
BONES = ["pelvis", "head", "hand_l", "hand_r", "foot_l", "foot_r", "spine_03", "root_weapon_end_r"]


def pose(seq, t):
    p = APE.get_anim_pose_at_time(seq, t, opts)
    r = APE.get_bone_pose(p, "root", unreal.AnimPoseSpaces.WORLD).translation
    return {b: APE.get_bone_pose(p, b, unreal.AnimPoseSpaces.WORLD).translation - r for b in BONES}


def dist(a, b):
    return sum((a[k] - b[k]).length() for k in BONES) / len(BONES)


def load(n):
    return unreal.load_asset(B + n)


PAIRS = [("Swing1Start_120fps", "Swing1_Slow"), ("Swing1Start_120fps", "Swing2_Slow"), ("Swing1Start_120fps", "Swing3_Slow"),
         ("Swing1_Slow", "Swing1_Return2Idle"), ("Swing2_Slow", "Swing2_Return2Idle"), ("Swing3_Slow", "Swing3_Return2Idle"),
         ("Swing1_Slow", "Swing2_Slow"), ("Swing2_Slow", "Swing3_Slow"), ("Swing2_Slow", "Swing1_Slow"), ("Swing3_Slow", "Swing1_Slow"),
         ("Swing1_120fps", "Swing1_Return2Idle_120fps"), ("Swing1_Slow", "Swing1_Return2Idle_120fps"),
         ("Stun_Start", "Stun_Loop"), ("Stun_Loop", "Stun_End"), ("Idle", "Swing1_Slow"), ("Idle", "Ultimate_Swing_120fps"),
         ("Ultimate_Swing_120fps", "Idle"), ("Stun_End", "Idle"), ("Idle", "Swing1Start_120fps")]
for a, b in PAIRS:
    A, Bq = load(a), load(b)
    if not A or not Bq:
        print("JOIN missing %s/%s" % (a, b))
        continue
    end = pose(A, A.get_play_length())
    L = Bq.get_play_length()
    best = min(((dist(end, pose(Bq, L * i / 40)), L * i / 40) for i in range(41)))
    print("JOIN %s(end) -> %s: start=%.1f best=%.1f@%.2f/%.2f" % (a, b, dist(end, pose(Bq, 0.0)), best[0], best[1], L))
# Where in each swing the wind-up pose sits (Swing1Start pose) and the slow swing timeline of the weapon tip.
for n in ["Swing1_Slow", "Swing2_Slow", "Swing3_Slow", "Swing1_Return2Idle", "Swing2_Return2Idle", "Swing3_Return2Idle", "Death_front", "Ultimate_Swing_120fps"]:
    s = load(n)
    L = s.get_play_length()
    row = []
    for i in range(11):
        p = pose(s, L * i / 10)
        row.append("%.0f/%.0f/%.0f" % (p["pelvis"].z, p["root_weapon_end_r"].z, min(p["foot_l"].z, p["foot_r"].z)))
    print("TL %s (pelvisZ/tipZ/footZ per 10%%): %s" % (n, " ".join(row)))
