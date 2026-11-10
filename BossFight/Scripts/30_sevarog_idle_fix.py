# Sevarog's Idle clip has a stray first frame (legs straight down, 60 cm from frame 1, where the
# looping idle has its legs folded under the robe). Each loop wrap flashed that pose for a frame.
# Make /Game/BossFight/Anim/Sevarog_IdleLoop = Idle without frame 0 (its last frame then matches its
# first), used by ABP_Sevarog's locomotion. The Paragon asset stays untouched.
import unreal
APE = unreal.AnimPoseExtensions
opts = unreal.AnimPoseEvaluationOptions()
SRC = "/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations/Idle"
DST = "/Game/BossFight/Anim/Sevarog_IdleLoop"
BONES = ["pelvis", "head", "hand_l", "hand_r", "foot_l", "foot_r", "spine_03", "root_weapon_end_r"]


def pose(seq, t):
    p = APE.get_anim_pose_at_time(seq, t, opts)
    return {b: APE.get_bone_pose(p, b, unreal.AnimPoseSpaces.WORLD).translation for b in BONES}


def dist(a, b):
    return sum((a[k] - b[k]).length() for k in BONES) / len(BONES)


eal = unreal.EditorAssetLibrary
if eal.does_asset_exist(DST):
    eal.delete_asset(DST)
seq = eal.duplicate_asset(SRC, DST)
ctrl = seq.get_editor_property("controller")
print("IDLEFIX before len=%.3f" % seq.get_play_length())
AL = unreal.AnimationLibrary
src = unreal.load_asset(SRC)
nf = AL.get_num_frames(src)
tracks = AL.get_animation_track_names(src)
print("IDLEFIX frames=%d tracks=%d" % (nf, len(tracks)))
# Re-key every bone track from source frames 1..nf (drops frame 0), then shorten by one frame.
ctrl.open_bracket(unreal.Text("trim idle"), False)
ctrl.set_number_of_frames(unreal.FrameNumber(nf - 1), False)
for bone in tracks:
    pos, rot, scl = [], [], []
    for f in range(1, nf + 1):
        t = AL.get_bone_pose_for_frame(src, bone, f, False)
        pos.append(t.translation)
        rot.append(t.rotation)
        scl.append(t.scale3d)
    ctrl.set_bone_track_keys(bone, pos, rot, scl, False)
ctrl.close_bracket(False)
ok = True
print("IDLEFIX remove ok=%s len=%.3f" % (ok, seq.get_play_length()))
L = seq.get_play_length()
print("IDLEFIX start_vs_end=%.1f start_vs_next=%.1f" % (dist(pose(seq, 0.0), pose(seq, L)), dist(pose(seq, 0.0), pose(seq, 1.0 / 30))))
for t in [0.0, 1.0 / 30, 2.0, L]:
    p = pose(seq, t)
    print("IDLEFIX t=%.3f feet=%.0f/%.0f" % (t, p["foot_l"].z, p["foot_r"].z))
eal.save_asset(DST, only_if_is_dirty=False)
