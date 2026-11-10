# Sevarog animation audit: for every clip the boss uses (and candidates), print length, root motion,
# root travel, pelvis / foot heights, how far its first and last poses are from Idle (blend joins),
# and per-frame pose jumps (pops). Bone positions are taken relative to the root bone.
import unreal
AL = unreal.AnimationLibrary
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
B = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/"
BONES = ["pelvis", "head", "hand_l", "hand_r", "foot_l", "foot_r", "spine_03", "root_weapon_end_r"]
CLIPS = ["Idle", "Walk_Fwd", "Jog_Fwd", "Swing1_Slow", "Swing2_Slow", "Swing3_Slow", "Ultimate_Swing_120fps",
         "Swing1_Return2Idle", "Swing2_Return2Idle", "Swing3_Return2Idle", "Swing1_Medium", "Swing1Start_120fps",
         "Hitreact_Front", "Hitreact_Back", "Hitreact_Left", "Hitreact_Right", "Stun_Start", "Stun_Loop", "Stun_End",
         "Death_front", "Knock_back", "Turn_Lt_90", "Turn_Rt_90"]


def pose(seq, t):
    p = APE.get_anim_pose_at_time(seq, t, opts)
    r = APE.get_bone_pose(p, "root", unreal.AnimPoseSpaces.WORLD).translation
    return {b: APE.get_bone_pose(p, b, unreal.AnimPoseSpaces.WORLD).translation - r for b in BONES}, r


def dist(a, b, bones=BONES):
    return sum((a[k] - b[k]).length() for k in bones) / len(bones)


idle0, _ = pose(unreal.load_asset(B + "Idle"), 0.0)
for n in CLIPS:
    s = unreal.load_asset(B + n)
    if not s:
        print("SEV missing %s" % n)
        continue
    L = s.get_play_length()
    rate = s.get_editor_property("rate_scale")
    rm = s.get_editor_property("enable_root_motion")
    p0, r0 = pose(s, 0.0)
    p1, r1 = pose(s, L)
    steps = max(10, int(L * 30))
    prev = p0
    pz = []
    fz = []
    jumps = []
    for i in range(1, steps + 1):
        t = L * i / steps
        p, r = pose(s, t)
        pz.append(p["pelvis"].z + r.z)
        fz.append(min(p["foot_l"].z, p["foot_r"].z) + r.z)
        d = dist(p, prev, ["pelvis", "head", "hand_r", "foot_l", "foot_r"])
        jumps.append((d, t))
        prev = p
    med = sorted(j[0] for j in jumps)[len(jumps) // 2]
    big = [("%.2f:%.0f" % (t, d)) for d, t in jumps if d > max(6.0, med * 4)]
    print("SEV %s len=%.2f rate=%.2f rm=%d root=(%.0f,%.0f,%.0f) pelvisZ=%.0f..%.0f footZmin=%.0f..max %.0f start_vs_idle=%.1f end_vs_idle=%.1f medstep=%.1f pops=%s" % (
        n, L, rate, rm, r1.x - r0.x, r1.y - r0.y, r1.z - r0.z, min(pz), max(pz), min(fz), max(fz),
        dist(p0, idle0), dist(p1, idle0), med, ",".join(big[:8])))
