# Sevarog body facing per clip: yaw of the shoulder line (upperarm_l -> upperarm_r) and of the
# pelvis line (thigh_l -> thigh_r) in component space, plus the root bone yaw, over time.
import math
import unreal
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
B = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/"


def yaw(v):
    return math.degrees(math.atan2(v.y, v.x))


for n in ["Idle", "Walk_Fwd", "Jog_Fwd", "Swing1_Slow", "Swing2_Slow", "Swing3_Slow", "Ultimate_Swing_120fps", "Swing1_Return2Idle_120fps",
          "Swing3_Return2Idle_120fps", "Hitreact_Front", "Stun_Start", "Stun_Loop", "Stun_End", "Turn_Rt_90"]:
    s = unreal.load_asset(B + n)
    L = s.get_play_length()
    row = []
    for f in [0, 0.05, 0.25, 0.5, 0.75, 1.0]:
        p = APE.get_anim_pose_at_time(s, L * f, opts)
        g = lambda b: APE.get_bone_pose(p, b, unreal.AnimPoseSpaces.WORLD)
        sh = g("upperarm_r").translation - g("upperarm_l").translation
        hp = g("thigh_r").translation - g("thigh_l").translation
        ry = g("root").rotation.rotator().yaw
        row.append("%.0f/%.0f/%.0f" % (yaw(sh), yaw(hp), ry))
    print("FACE %s (shoulder/hips/root yaw at 0,5,25,50,75,100%%): %s" % (n, " ".join(row)))
