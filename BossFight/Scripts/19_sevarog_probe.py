# Phase 7 probe: Sevarog bones, anim lengths, root motion, weapon-speed swing windows, loco blendspace.
import unreal
AL = unreal.AnimationLibrary
APE = unreal.AnimPoseExtensions
BASE = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/"

idle = unreal.load_asset(BASE + "Animations/Idle")
tracks = [str(n) for n in AL.get_animation_track_names(idle)]
pass #print("SVP bones(%d): %s" % (len(tracks), ", ".join(tracks)))

mesh = unreal.load_asset(BASE + "Meshes/Sevarog")
if mesh:
    b = mesh.get_bounds()
    print("SVP mesh bounds origin=%s extent=%s" % (b.origin, b.box_extent))
    for s in mesh.get_editor_property("skeleton").get_editor_property("sockets") if hasattr(mesh.get_editor_property("skeleton"), "sockets") else []:
        print("SVP socket", s.get_editor_property("socket_name"), s.get_editor_property("bone_name"))

bs = unreal.load_asset(BASE + "Animations/Blendspaces/Sevarog_Locomotion_1D")
if bs:
    for p in ["blend_parameters"]:
        try:
            print("SVP bs", p, bs.get_editor_property(p))
        except Exception as e:
            print("SVP bs err", e)

cands = [t for t in tracks if any(k in t.lower() for k in ["weapon", "hammer", "hand_r", "hand_l", "prop"])]
print("SVP weapon candidates:", cands)
WEAPON = "root_weapon_end_r"
r0w = APE.get_bone_pose(APE.get_anim_pose_at_time(idle, 0.0, unreal.AnimPoseEvaluationOptions()), "weapon_r", unreal.AnimPoseSpaces.WORLD).translation
r1w = APE.get_bone_pose(APE.get_anim_pose_at_time(idle, 0.0, unreal.AnimPoseEvaluationOptions()), "root_weapon_end_r", unreal.AnimPoseSpaces.WORLD).translation
print("SVP idle weapon_r=%s end=%s" % (r0w, r1w))

opts = unreal.AnimPoseEvaluationOptions()
NAMES = ["Swing1_Medium", "Swing2_Medium", "Swing3_Medium", "Swing1_Slow", "Swing2_Slow", "Swing3_Slow",
         "Swing1_FAST_v2", "Swing2_FAST_v2", "Swing3_FAST_v2", "Ultimate_Swing_120fps", "Subjugation", "Soul_Siphon", "Cast"]
for n in NAMES:
    seq = unreal.load_asset(BASE + "Animations/" + n)
    if not seq:
        print("SVP missing", n); continue
    L = seq.get_play_length()
    dt = 1.0 / 30.0
    def wpos(t):
        pose = APE.get_anim_pose_at_time(seq, t, opts)
        return APE.get_bone_pose(pose, WEAPON, unreal.AnimPoseSpaces.WORLD).translation
    speeds = []
    prev = wpos(0.0)
    t = dt
    while t <= L + 1e-4:
        cur = wpos(t)
        speeds.append((t, (cur - prev).length() / dt))
        prev = cur
        t += dt
    wins, on = [], None
    for (tt, s) in speeds:
        if s > 700 and on is None: on = tt
        if s <= 700 and on is not None: wins.append((on, tt)); on = None
    if on is not None: wins.append((on, L))
    peak = max(speeds, key=lambda x: x[1]) if speeds else (0, 0)
    r0 = APE.get_bone_pose(APE.get_anim_pose_at_time(seq, 0.0, opts), "root", unreal.AnimPoseSpaces.WORLD).translation
    r1 = APE.get_bone_pose(APE.get_anim_pose_at_time(seq, L, opts), "root", unreal.AnimPoseSpaces.WORLD).translation
    print("SVP %s len=%.2f rm=%s root_d=(%.0f,%.0f,%.0f) peak=%.0f@%.2f wins=%s" % (n, L, seq.get_editor_property("enable_root_motion"),
          r1.x - r0.x, r1.y - r0.y, r1.z - r0.z, peak[1], peak[0], ["%.2f-%.2f" % w for w in wins]))
