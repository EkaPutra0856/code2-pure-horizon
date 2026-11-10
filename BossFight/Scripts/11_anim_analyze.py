# Prints per-animation root motion flag, root displacement, and hand_r speed peaks (swing timing).
import unreal
AL = unreal.AnimationLibrary
CHAIN = ["root", "pelvis", "spine_01", "spine_02", "spine_03", "clavicle_r", "upperarm_r", "lowerarm_r", "hand_r"]
NAMES = ["combo01_1", "combo01_2", "combo01_3", "combo02_1", "combo02_2", "combo02_3", "Rolling", "Attack_Shockwave",
         "Attack_Jump_to_Air", "Air_Down_Attack_Z0", "Air_Combo01_Z0_1", "Air_Combo01_Z0_2", "Air_Combo01_Z0_3", "depence",
         "hit_light_F_head", "hit_light_L_body", "hit_light_R_body", "hit_knockdown01", "Air_Dash_Z0", "Upper_Swing"]
def comp_pos(seq, t):
    x = unreal.Transform()
    for b in CHAIN:
        local = AL.get_bone_pose_for_time(seq, b, t, False)
        x = local.multiply(x)
    return x.translation
for n in NAMES:
    seq = unreal.load_asset("/Game/InsaneAirCombo/Animation/" + n)
    if not seq:
        print("BFA missing", n); continue
    L = seq.get_play_length()
    r0 = AL.get_bone_pose_for_time(seq, "root", 0.0, False).translation
    r1 = AL.get_bone_pose_for_time(seq, "root", L, False).translation
    p1 = AL.get_bone_pose_for_time(seq, "pelvis", L, False).translation
    p0 = AL.get_bone_pose_for_time(seq, "pelvis", 0.0, False).translation
    dt = 1.0 / 30.0
    speeds = []
    prev = comp_pos(seq, 0.0)
    t = dt
    while t <= L + 1e-4:
        cur = comp_pos(seq, t)
        speeds.append((t, (cur - prev).length() / dt))
        prev = cur
        t += dt
    # windows where hand speed > 600 cm/s
    wins = []
    on = None
    for (tt, s) in speeds:
        if s > 600 and on is None: on = tt
        if s <= 600 and on is not None:
            wins.append((on, tt)); on = None
    if on is not None: wins.append((on, L))
    peak = max(speeds, key=lambda x: x[1]) if speeds else (0, 0)
    print("BFA %s len=%.2f rm=%s root_d=%s pelvis_d=(%.0f,%.0f,%.0f) peak=%.0f@%.2f wins=%s" % (
        n, L, seq.get_editor_property("enable_root_motion"), (r1 - r0).to_tuple() if hasattr(r1,'to_tuple') else (round(r1.x-r0.x),round(r1.y-r0.y),round(r1.z-r0.z)),
        p1.x - p0.x, p1.y - p0.y, p1.z - p0.z, peak[1], peak[0], ["%.2f-%.2f" % w for w in wins]))
