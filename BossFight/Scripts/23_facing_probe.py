# Which mesh axis is "forward" for each skeleton: toe minus ankle in the idle pose.
import unreal
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
for path in ["/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/Idle", "/Game/InsaneAirCombo/Animation/Idle"]:
    seq = unreal.load_asset(path)
    names = [str(n) for n in unreal.AnimationLibrary.get_animation_track_names(seq)]
    pose = APE.get_anim_pose_at_time(seq, 0.0, opts)
    def w(b): return APE.get_bone_pose(pose, b, unreal.AnimPoseSpaces.WORLD).translation
    feet = [n for n in names if any(k in n.lower() for k in ["foot", "ball", "toe"])]
    print("FP", path, feet)
    for side in ["l", "r"]:
        f = next((n for n in names if n.lower() == "foot_" + side), None)
        b = next((n for n in names if n.lower() in ("ball_" + side, "toe_" + side, "toes_" + side)), None)
        if f and b:
            print("FP %s %s->%s %s" % (side, f, b, w(b) - w(f)))
    for n in ["head", "pelvis", "hand_r", "hand_l"]:
        if n in names:
            print("FP", n, w(n))
