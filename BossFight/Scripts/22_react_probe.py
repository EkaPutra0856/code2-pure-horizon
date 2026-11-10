# Probe: hit-react / knockdown / get-up clips of the dummy (InsaneAirCombo) and Sevarog.
# Prints length, root-motion flags, root and pelvis travel, and pelvis height over time,
# so reactions can be matched (knockdown end pose vs get-up start pose, sliding roots).
import unreal
AL = unreal.AnimationLibrary
APE = unreal.AnimPoseExtensions
eal = unreal.EditorAssetLibrary
opts = unreal.AnimPoseEvaluationOptions()

SETS = [("/Game/InsaneAirCombo/Animation", ["hit", "knock", "down", "dead", "stun", "fall", "get", "damage", "blow"]),
        ("/Game/ParagonSevarog/Characters/Heroes/Sevarog/Animations", ["hit", "knock", "stun", "death", "react", "get", "flinch", "stagger", "fall", "down"])]


def pose_at(seq, t, bone):
    p = APE.get_anim_pose_at_time(seq, t, opts)
    return APE.get_bone_pose(p, bone, unreal.AnimPoseSpaces.WORLD).translation


for folder, keys in SETS:
    for path in sorted(eal.list_assets(folder, recursive=True, include_folder=False)):
        name = path.split(".")[-1]
        if not any(k in name.lower() for k in keys):
            continue
        seq = unreal.load_asset(path)
        if not isinstance(seq, unreal.AnimSequence):
            continue
        L = seq.get_play_length()
        tracks = [str(n) for n in AL.get_animation_track_names(seq)]
        pelvis = "pelvis" if "pelvis" in tracks else next((t for t in tracks if "pelvis" in t.lower() or "hips" in t.lower()), tracks[1] if len(tracks) > 1 else "root")
        rm = seq.get_editor_property("enable_root_motion")
        lock = seq.get_editor_property("force_root_lock")
        r0, r1 = pose_at(seq, 0.0, "root"), pose_at(seq, L, "root")
        samples = []
        for f in [0.0, 0.15, 0.3, 0.5, 0.7, 0.85, 1.0]:
            p = pose_at(seq, L * f, pelvis)
            samples.append("%.2f:(%.0f,%.0f,%.0f)" % (L * f, p.x, p.y, p.z))
        print("RP %s len=%.2f rm=%d lock=%d root_d=(%.0f,%.0f,%.0f) pelvis[%s] %s" % (
            path.replace("/Game/", ""), L, rm, lock, r1.x - r0.x, r1.y - r0.y, r1.z - r0.z, pelvis, " ".join(samples)))
