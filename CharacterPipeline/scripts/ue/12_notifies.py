# Adds VFX and SFX notifies to the character's moves, timed from export_unreal/anim/moves.json.
# Effects use timed notifies, so a looping system stops at the end of its window. Looping sound
# cues are skipped, because a PlaySound notify has no way to stop them. Looping clips get nothing:
# they would retrigger each cycle, so sustained effects belong in the character Blueprint.
# Safe to rerun: the VFX and SFX tracks are removed first.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import json, os
import unreal

ROOT = ANIME_GAME_ROOT
LOG = os.path.join(ROOT, "scripts", "ue", "report_notifies.txt")
lines = []


def say(*a):
    lines.append(" ".join(str(x) for x in a))
    open(LOG, "w", encoding="utf-8").write("\n".join(lines))


L = unreal.AnimationLibrary
lib = unreal.EditorAssetLibrary
reg = unreal.AssetRegistryHelpers.get_asset_registry()
reg.scan_paths_synchronous(["/Game"], True)
moves = json.load(open(os.path.join(ROOT, "export_unreal", "anim", "moves.json")))["moves"]
FPS = 30.0
TIMED = unreal.load_class(None, "/Script/NiagaraAnimNotifies.AnimNotifyState_TimedNiagaraEffect")
TRACKS = ("VFX", "VFX2", "SFX", "SFX2")
R, Lh, CH, HI, RT = "J_Bip_R_Hand", "J_Bip_L_Hand", "J_Bip_C_UpperChest", "J_Bip_C_Hips", "Root"

systems, cues = {}, []
for root in ("MagicKit", "SlashHitVFX", "BalticVFX_MagicCirclesToolkit", "Hack_And_Slash_FX", "Casting___Loops", "Chimes___Pads", "Elements___School", "General", "Special_Attacks"):
    for a in reg.get_assets_by_path("/Game/" + root, recursive=True):
        kind = str(a.asset_class_path.asset_name)
        if kind == "NiagaraSystem":
            systems[str(a.asset_name)] = str(a.package_name)
        elif kind == "SoundCue" and "loop" not in str(a.asset_name).lower():
            cues.append((str(a.asset_name), str(a.package_name)))
cues.sort()
resolved = {}


def cue(prefix):
    if prefix not in resolved:
        hit = [p for n, p in cues if n == prefix or n.startswith(prefix + "_") or n.startswith(prefix + " ")] or [p for n, p in cues if n.startswith(prefix)]
        resolved[prefix] = hit[0] if hit else None
        if not hit:
            say("NO CUE", prefix)
    return resolved[prefix]


def N(frame, name, socket, dur=1.0):
    return ("n", frame, name, socket, dur)


def S(frame, name, volume=1.0):
    return ("s", frame, name, volume)


def dodge():
    return [S(1, "Magic_Whoosh_8"), N(1, "NS_Firecracker_Sparks_01", RT, 0.4)]


PLAN = {
    "Attack_N1": [S(4, "Magic_Whoosh_1"), N(7, "NS_Stellar_Attack_LVL_01", R), S(7, "Nature_Spell_1")],
    "Attack_N2": [S(4, "Magic_Whoosh_2"), N(7, "NS_Stellar_Attack_LVL_01", Lh), S(7, "Nature_Spell_2")],
    "Attack_N3": [S(7, "Magic_Whoosh_3"), N(11, "NS_Stellar_Attack_LVL_01", R), S(11, "Nature_Spell_3")],
    # LVL_03 fills the screen and hides the character, so it stays reserved for the ultimate.
    "Attack_N4": [S(10, "Magic_Whoosh_4"), N(15, "NS_Stellar_Attack_LVL_02", R), N(15, "NS_Sakura_Slash_Impact", R, 0.8), S(15, "Nature_Spell_9")],
    "Charge_Start": [S(1, "Field_1_Start"), N(1, "NS_CircleExample1", RT, 0.4)],
    "Charge_Release": [S(0, "Field_1_Stop"), N(5, "NS_Stellar_Special_01_End", CH), S(5, "Magic_Explosion_2")],
    "Skill_BloomField": [N(12, "NS_Stellar_Special_01_Start_Ground", RT), N(12, "NS_CircleExample2", RT), S(12, "Nature_Spell_13")],
    "Skill_Heal": [N(10, "NS_Stellar_Shield_01", HI), S(10, "Healing_1")],
    "Skill_Buff": [N(9, "NS_CircleExample3", RT, 0.75), S(9, "Buff_Attack_1")],
    "Skill_Hold_Start": [S(1, "Field_2_Start")],
    "Skill_Hold_Release": [S(0, "Field_2_Stop"), N(7, "NS_Stellar_Special_01_End", CH), S(7, "Buff_Defense_1")],
    "Dodge_Back": dodge(), "Dodge_Forward": dodge(), "Dodge_Left": dodge(), "Dodge_Right": dodge(),
    "Dodge_Counter": [N(4, "NS_Stellar_Hit_01", Lh, 0.6), S(4, "Sfx_Hit_MagicStaff")],
    "Swap_In": [N(10, "NS_Stellar_Hit_02", RT, 0.6), S(10, "Positive_Effect_1")],
    "Swap_Out": [S(8, "Magic_Whoosh_9")],
    "Plunge_Land": [N(2, "NS_Sakura_Slash_Impact", RT, 0.8), N(2, "NS_Stellar_Special_01_End", RT), S(2, "Magic_Explosion_3")],
}
ev = moves["Ultimate_EternalBloom"]["events"]
PLAN["Ultimate_EternalBloom"] = [
    N(ev["gather_start"], "NS_CircleExample1", RT, (ev["petals_converge"] - ev["gather_start"]) / FPS), S(ev["gather_start"], "Field_3_Start"),
    N(ev["petals_converge"], "NS_Stellar_Special_01_Start", HI), S(ev["petals_converge"], "Magic_Element_1"),
    N(ev["liftoff"], "NS_Stellar_Special_01_Start_Ground", RT), S(ev["liftoff"], "Magic_Whoosh_10"),
    N(ev["pull_in"], "NS_Stellar_Attack_LVL_02", CH), S(ev["pull_in"], "Wind_Spell_14"),
    N(ev["blast_out"], "NS_Stellar_Special_01_End", CH), N(ev["blast_out"], "NS_Sakura_Slash_Impact", CH, 0.8), S(ev["blast_out"], "Magic_Explosion_4"),
    N(ev["channel_start"], "NS_CircleExample2", RT, (ev["clap_hit"] - ev["channel_start"]) / FPS), S(ev["channel_start"], "Pad_1"),
    N(ev["channel_peak"], "NS_Stellar_Attack_LVL_03", CH), S(ev["channel_peak"], "Special_Attack_1"),
    N(ev["clap_hit"], "NS_Holy_Slash_Impact", CH, 0.8), S(ev["clap_hit"], "Special_Attack_2"), S(ev["clap_hit"], "Magic_Explosion_5"),
    N(ev["field_open"], "NS_CircleExample3", RT, 2.0), N(ev["field_open"], "NS_Nature_Slash_Impact", RT, 0.8), S(ev["field_open"], "Nature_Spell_17"),
    N(ev["final_flick"], "NS_Sakura_Slash_Impact", R, 0.8), S(ev["final_flick"], "Magic_Whoosh_11"),
    N(ev["landing"], "NS_Stellar_Hit_02", RT, 0.6), S(ev["landing"], "Field_3_Stop"),
]


def world(a, bone, frame):
    t = unreal.Transform()
    for b in reversed([str(x) for x in L.find_bone_path_to_root(a, bone)]):
        t = L.get_bone_pose_for_frame(a, b, frame, False).multiply(t)
    return t.translation


def fastest(a, bone):
    n = L.get_num_frames(a)
    pts = [world(a, bone, f) for f in range(n)]
    return max(range(1, n), key=lambda f: (pts[f] - pts[f - 1]).length())


def thrust(a, bone):
    # Frame where the hand moves forward fastest. Character faces +Y.
    n = L.get_num_frames(a)
    ys = [world(a, bone, f).y - world(a, "Root", f).y for f in range(n)]
    return max(range(1, n), key=lambda f: ys[f] - ys[f - 1])


def lowest(a, bone):
    n = L.get_num_frames(a)
    return min(range(n), key=lambda f: world(a, bone, f).z)


def apply(a, plan, fps):
    length = a.get_editor_property("sequence_length") if hasattr(a, "sequence_length") else L.get_sequence_length(a)
    for track in TRACKS:
        if track in [str(x) for x in L.get_animation_notify_track_names(a)]:
            L.remove_animation_notify_track(a, track)
        L.add_animation_notify_track(a, track, unreal.LinearColor(0.9, 0.4, 0.7, 1) if track.startswith("VFX") else unreal.LinearColor(0.3, 0.7, 1, 1))
    done = 0
    used = set()

    def lane(base, t):
        # Two notifies at the same time on one track collapse into one, so the second takes track 2.
        track = base if (base, t) not in used else base + "2"
        used.add((track, t))
        return track

    for e in plan:
        t = min(e[1] / fps, max(length - 0.05, 0.0))
        if e[0] == "n":
            path = systems.get(e[2])
            if not path:
                say("NO SYSTEM", e[2])
                continue
            state = L.add_animation_notify_state_event(a, lane("VFX", t), t, max(min(e[4], length - t), 0.05), TIMED)
            state.set_editor_property("template", unreal.load_asset(path))
            state.set_editor_property("socket_name", e[3])
            # Magic circles linger for seconds after deactivation, so they are cut at the window's end.
            state.set_editor_property("destroy_at_end", e[2].startswith("NS_Circle"))
        else:
            path = cue(e[2])
            if not path:
                continue
            nt = L.add_animation_notify_event(a, lane("SFX", t), t, unreal.AnimNotify_PlaySound)
            nt.set_editor_property("sound", unreal.load_asset(path))
            nt.set_editor_property("volume_multiplier", e[3])
        done += 1
    lib.save_loaded_asset(a, False)
    return done


say("timed class", TIMED)
total = 0
for name, plan in PLAN.items():
    a = unreal.load_asset("/Game/Character/Anim/A_" + name)
    if a is None:
        say("NO CLIP", name)
        continue
    c = apply(a, plan, FPS)
    total += c
    say(name, c, "of", len(plan))

mage = unreal.load_asset("/Game/Character/Mage/Mage_Fireball_R")
mfps = L.get_num_frames(mage) / L.get_sequence_length(mage)
for name, bone, finder, plan in (
        ("Mage_Fireball_R", R, thrust, lambda f: [N(f, "NS_Stellar_Attack_LVL_02", R), S(f, "Nature_Spell_3")]),
        ("Mage_Fireball_L", Lh, thrust, lambda f: [N(f, "NS_Stellar_Attack_LVL_02", Lh), S(f, "Nature_Spell_2")]),
        ("Mage_GroundSlam", R, lowest, lambda f: [N(f, "NS_Sakura_Slash_Impact", RT, 0.8), N(f, "NS_Stellar_Special_01_End", RT), S(f, "Magic_Explosion_3")]),
        ("Mage_Shout", "J_Bip_C_Head", fastest, lambda f: [N(f, "NS_Stellar_Hit_02", CH, 0.6), S(f, "Buff_Attack_7")])):
    a = unreal.load_asset("/Game/Character/Mage/" + name)
    f = finder(a, bone)
    c = apply(a, plan(f), mfps)
    total += c
    say(name, "frame", f, "of", L.get_num_frames(a), "added", c)
say("resolved", {k: (v.split("/")[-1] if v else None) for k, v in resolved.items()})
say("total", total)

# Read back from a fresh load of the saved clips.
idle = unreal.load_asset("/Game/Character/Mage/Mage_Idle")
say("Mage_Idle tracks from pack", [str(t) for t in L.get_animation_notify_track_names(idle)], "events", len(L.get_animation_notify_events(idle)))
found = 0
empty = 0
clips = ["/Game/Character/Anim/A_" + n for n in PLAN] + ["/Game/Character/Mage/" + n for n in ("Mage_Fireball_R", "Mage_Fireball_L", "Mage_GroundSlam", "Mage_Shout")]
for clip in clips:
    a = unreal.load_asset(clip)
    for track in TRACKS:
        for e in L.get_animation_notify_events_for_track(a, track):
            found += 1
            obj = e.notify_state_class or e.notify
            asset = obj.get_editor_property("template" if e.notify_state_class else "sound")
            if asset is None:
                empty += 1
say("read back", found, "of", total, "without asset", empty)
say("DONE")
