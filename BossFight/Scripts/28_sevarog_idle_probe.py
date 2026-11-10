# Sevarog idle audit: the Idle clip's frame 0 differs a lot from frame 1. Sample it over time and
# compare candidate idle clips with the pose the hit reacts / Return2Idle clips end in.
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


ref = pose(load("Hitreact_Front"), load("Hitreact_Front").get_play_length())
idle = load("Idle")
print("IDLE frames=%d additive=%s" % (idle.get_editor_property("number_of_sampled_frames") if hasattr(idle, "number_of_sampled_frames") else -1, idle.get_editor_property("additive_anim_type")))
for t in [0.0, 1 / 60, 1 / 30, 0.1, 0.5, 1, 2, 3, 4, 5, 6, 7, 8, 8.8, 8.9]:
    p = pose(idle, t)
    print("IDLE t=%.3f vs_hitend=%.1f feet=%.0f/%.0f pelvis=%.0f tip=%.0f" % (t, dist(p, ref), p["foot_l"].z, p["foot_r"].z, p["pelvis"].z, p["root_weapon_end_r"].z))
for n in ["Idle_additive", "Travel_Mode_Idle", "FrontEndPose", "Swing1_Return2Idle_120fps", "Swing2_Return2Idle_120fps", "Swing3_Return2Idle_120fps", "Walk_Fwd", "Hitreact_Front", "Ultimate_Swing_120fps", "Stun_End"]:
    s = load(n)
    if not s:
        print("CAND missing " + n)
        continue
    L = s.get_play_length()
    p0, p1 = pose(s, 0), pose(s, L)
    print("CAND %s len=%.2f start_vs_hitend=%.1f end_vs_hitend=%.1f end_feet=%.0f/%.0f" % (n, L, dist(p0, ref), dist(p1, ref), p1["foot_l"].z, p1["foot_r"].z))
# Stun loop: where does its pose come closest to Stun_End's first frame?
loop, end = load("Stun_Loop"), load("Stun_End")
e0 = pose(end, 0)
L = loop.get_play_length()
print("STUN " + " ".join("%.2f:%.0f" % (L * i / 20, dist(pose(loop, L * i / 20), e0)) for i in range(21)))
st = load("Stun_Start")
L = st.get_play_length()
print("STUNSTART " + " ".join("%.2f:%.0f" % (L * i / 20, dist(pose(st, L * i / 20), e0)) for i in range(21)))
