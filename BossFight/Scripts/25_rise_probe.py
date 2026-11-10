# Get-up matching: compare the end pose of each knockdown clip with the start pose of each rise clip
# (bone positions relative to the pelvis), and print the rise clips' length, root motion and pelvis
# height over time, so the get-up that continues a knockdown without a pop can be picked.
import unreal
AL = unreal.AnimationLibrary
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
B = "/Game/InsaneAirCombo/Animation/"
BONES = ["head", "hand_l", "hand_r", "foot_l", "foot_r", "spine_03", "lowerarm_l", "lowerarm_r", "calf_l", "calf_r"]


def rel(seq, t):
    pose = APE.get_anim_pose_at_time(seq, t, opts)
    p = APE.get_bone_pose(pose, "pelvis", unreal.AnimPoseSpaces.WORLD).translation
    return {b: APE.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation - p for b in BONES}, p


def dist(a, b):
    return sum((a[k] - b[k]).length() for k in BONES) / len(BONES)


ends = {}
for n in ["hit_knockdown01", "hit_knockdown02", "hit_knockdown03", "hit_knockdown_down", "hit_down_idle_up", "hit_down_idle_down", "hit_bound_down"]:
    s = unreal.load_asset(B + n)
    ends[n], p = rel(s, s.get_play_length())
    print("RISE end %s pelvis=(%.0f,%.0f,%.0f) head_rel=%s" % (n, p.x, p.y, p.z, ends[n]["head"]))
for n in ["rise_1", "rise_2", "rise_left_roll", "rise_right_roll", "hit_down_up"]:
    s = unreal.load_asset(B + n)
    L = s.get_play_length()
    start, p0 = rel(s, 0.0)
    _, p1 = rel(s, L)
    r0 = APE.get_bone_pose(APE.get_anim_pose_at_time(s, 0.0, opts), "root", unreal.AnimPoseSpaces.WORLD).translation
    r1 = APE.get_bone_pose(APE.get_anim_pose_at_time(s, L, opts), "root", unreal.AnimPoseSpaces.WORLD).translation
    zs = []
    for f in [0, 0.2, 0.4, 0.6, 0.8, 1.0]:
        _, pp = rel(s, L * f)
        zs.append("%.0f" % pp.z)
    print("RISE clip %s len=%.2f rm=%d root_d=(%.0f,%.0f) pelvis0=(%.0f,%.0f,%.0f) pelvis1=(%.0f,%.0f,%.0f) z=%s" % (
        n, L, s.get_editor_property("enable_root_motion"), r1.x - r0.x, r1.y - r0.y, p0.x, p0.y, p0.z, p1.x, p1.y, p1.z, ",".join(zs)))
    for e, ep in ends.items():
        print("RISE match %s -> %s : %.1f" % (e, n, dist(ep, start)))
