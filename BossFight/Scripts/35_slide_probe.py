# Read-only probe: Lucy slide clips vs the player's Rolling dash (length, skeleton, root motion travel).
# Run with -ExecutePythonScript; lines start with "BFSLIDE".
import unreal

PLAYER_SK = "/Game/InsaneAirCombo/Animation/Skeleton/UE4_Mannequin_Skeleton.UE4_Mannequin_Skeleton"
CLIPS = [
    "/Game/InsaneAirCombo/Animation/Rolling.Rolling",
    "/Game/Lucy/Animations/Dodge/Root/Lucy_Slide_F_Root.Lucy_Slide_F_Root",
    "/Game/Lucy/Animations/Dodge/Root/Lucy_Slide_B_Root.Lucy_Slide_B_Root",
    "/Game/Lucy/Animations/Dodge/Root/Lucy_Slide_L_Root.Lucy_Slide_L_Root",
    "/Game/Lucy/Animations/Dodge/Root/Lucy_Slide_R_Root.Lucy_Slide_R_Root",
    "/Game/Lucy/Animations/Dodge/Root/Lucy_Dodge_F_Root.Lucy_Dodge_F_Root",
]

def log(*a):
    print("BFSLIDE", *a)

psk = unreal.load_asset(PLAYER_SK)
log("player skeleton", psk.get_path_name() if psk else None)
try:
    log("player compatible", [s.get_path_name() for s in psk.get_editor_property("compatible_skeletons")])
except Exception as e:
    log("compatible_skeletons n/a", e)

for path in CLIPS:
    a = unreal.load_asset(path)
    if not a:
        log("missing", path)
        continue
    sk = a.get_editor_property("skeleton")
    length = unreal.AnimationLibrary.get_sequence_length(a)
    frames = unreal.AnimationLibrary.get_num_frames(a)
    rm = a.get_editor_property("enable_root_motion")
    line = []
    for t in [0.0, length * 0.25, length * 0.5, length * 0.75, length]:
        try:
            tr = unreal.AnimationLibrary.get_bone_pose_for_time(a, "root", t, False)
            line.append("%.2f:(%.0f,%.0f,%.0f)" % (t, tr.translation.x, tr.translation.y, tr.translation.z))
        except Exception as e:
            line.append("err %s" % e)
            break
    try:
        p = unreal.AnimationLibrary.get_bone_pose_for_time(a, "pelvis", length * 0.5, False)
        pel = "pelvisZ@mid=%.0f" % p.translation.z
    except Exception:
        pel = ""
    log(path.split(".")[-1], "len=%.2f frames=%d rootmotion=%s skel=%s" % (length, frames, rm, sk.get_path_name() if sk else None), " ".join(line), pel)
