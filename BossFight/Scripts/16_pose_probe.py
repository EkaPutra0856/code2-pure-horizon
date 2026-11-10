# Pelvis height change at end of candidate reaction clips: ~-80 lying, ~-30..-55 kneel/crouch.
import unreal
AL = unreal.AnimationLibrary
names = ["hit_knockdown01", "hit_knockdown02", "hit_knockdown03", "hit_knockdown_down", "hit_down_idle_down", "hit_down_idle_up",
         "hit_wall_down_down", "hit_wall_down_up", "hit_bound_down", "hit_bound_up", "rise_1", "rise_2", "depence", "equip"] + ["Dead_Dead%d" % i for i in range(1, 10)]
for n in names:
    s = unreal.load_asset("/Game/InsaneAirCombo/Animation/" + n)
    if not s: continue
    L = s.get_play_length()
    zs = []
    for f in (0.0, 0.25, 0.5, 0.75, 1.0):
        zs.append(AL.get_bone_pose_for_time(s, "pelvis", L * f, False).translation.z + AL.get_bone_pose_for_time(s, "root", L * f, False).translation.z)
    print("BFP %-20s len=%.2f pelvisZ=%s" % (n, L, " ".join("%.0f" % (z - zs[0]) for z in zs)))
