# Builds the full moveset from the baked Mixamo clips and writes one Blender action per move.
# Each attack is retimed into startup, hit and recovery, starts and ends on the ready pose, and
# records its gameplay frames in export_unreal/anim/moves.json.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, json, math, os, sys, importlib
import numpy as np

ROOT = ANIME_GAME_ROOT
sys.path.insert(0, ROOT + r"\scripts")
import animlib as A
importlib.reload(A)
from animlib import ease, load, join, mirror, ground

FWD = -1.0  # the character faces -Y
UP, SIDE, FRONT = (0, 0, 1), (1, 0, 0), (0, 1, 0)
MOVES, INFO = {}, {}

IDLE = ground(load("standing_idle")).in_place()
IDLE.loop(10)
READY = (IDLE.q[0].copy(), IDLE.hips[0].copy())


def keep(name, clip, kind, **info):
    MOVES[name] = clip
    INFO[name] = dict(kind=kind, frames=len(clip), seconds=round(len(clip) / A.FPS, 2), **info)


def step(c, dist, a, b):
    """Glide forward by dist metres between frames a and b, as root motion."""
    c.root[:, 1] += FWD * dist * ease(len(c), None, [(a, 0), (b, 1)])
    return c


def attack(name, src, a, hit, end, startup, recover, mir=False, dist=0.0, cancel=None, nxt=None, hand="R", fade_in=4, fade_out=9):
    c = ground(load(src))
    if mir:
        c = mirror(c)
        hand = "L" if hand == "R" else "R"
    c = c.warp([(a, 0), (hit, startup), (end, startup + recover)])
    c.fade_from(READY, fade_in).fade_to(READY, fade_out)
    if dist:
        step(c, dist, 0, startup + 2)
    keep(name, c, "attack", hit=startup, active=[startup, startup + 3], cancel_from=cancel or startup + 6,
         recovery_from=startup + 4, next=nxt, hand=hand, root_motion=bool(dist))
    return c


# ---------- basic attack chain ----------
n1 = attack("Attack_N1", "standing_1h_magic_attack_01", 9, 20, 42, 7, 18, dist=0.12, nxt="Attack_N2")
n1.add("C_Spine", UP, ease(len(n1), None, [(0, 0), (6, -14), (9, 16), (20, 0)]))
n2 = attack("Attack_N2", "standing_1h_magic_attack_02", 6, 18, 42, 7, 19, mir=True, dist=0.14, nxt="Attack_N3")
n2.add("C_Spine", UP, ease(len(n2), None, [(0, 0), (6, 16), (10, -18), (22, 0)]))
n3 = attack("Attack_N3", "standing_1h_magic_attack_03", 8, 23, 50, 11, 21, dist=0.2, nxt="Attack_N4")
n3.yaw += ease(len(n3), None, [(0, 0), (11, 360)])  # pirouette into the upward flick
n3.add("C_Chest", SIDE, ease(len(n3), None, [(0, 0), (9, 8), (13, -10), (24, 0)]))
n4 = attack("Attack_N4", "standing_2h_magic_attack_01", 10, 33, 62, 15, 27, dist=0.28, cancel=26)
n4.hips[:, 2] += ease(len(n4), None, [(0, 0), (9, 0.13), (15, 0), (20, -0.05), (32, 0)])
n4.add("C_Spine", SIDE, ease(len(n4), None, [(0, 0), (11, -12), (15, 18), (28, 0)]))

# ---------- charged attack: start, hold loop, release ----------
c = ground(load("standing_2h_magic_attack_04"))
cs = c.warp([(3, 0), (27, 12)]).fade_from(READY, 4)
keep("Charge_Start", cs, "charge", next="Charge_Loop")
cl = c.seg(35, 75).loop(10)
keep("Charge_Loop", cl, "loop", next="Charge_Release")
cr = ground(load("standing_2h_magic_attack_01")).warp([(26, 0), (33, 5), (64, 28)])
cr.fade_from((cl.q[0].copy(), cl.hips[0].copy()), 5).fade_to(READY, 10)
cr.add("C_Spine", SIDE, ease(len(cr), None, [(0, -6), (5, 16), (20, 0)]))
keep("Charge_Release", cr, "attack", hit=5, active=[5, 9], cancel_from=16, recovery_from=10, hand="both", root_motion=False)

# ---------- skills ----------
sk = attack("Skill_BloomField", "standing_2h_magic_area_attack_01", 6, 27, 62, 12, 26, hand="both", cancel=24)
sk.hips[:, 2] += ease(len(sk), None, [(0, 0), (9, 0.05), (12, -0.04), (24, 0)])
attack("Skill_Heal", "magic_heal", 6, 22, 70, 10, 30, hand="R", cancel=30)
INFO["Skill_Heal"]["kind"] = "support"
attack("Skill_Buff", "standing_1h_cast_spell_01", 3, 17, 45, 9, 22, cancel=22)
INFO["Skill_Buff"]["kind"] = "support"
c = ground(load("two_hand_spell_casting"))
hs = c.warp([(5, 0), (27, 12)]).fade_from(READY, 4)
keep("Skill_Hold_Start", hs, "charge", next="Skill_Hold_Loop")
hl = c.seg(30, 72).loop(10)
keep("Skill_Hold_Loop", hl, "loop", next="Skill_Hold_Release")
hr = ground(load("wide_arm_spell_casting")).warp([(16, 0), (26, 7), (78, 32)])
hr.fade_from((hl.q[0].copy(), hl.hips[0].copy()), 6).fade_to(READY, 10)
keep("Skill_Hold_Release", hr, "support", hit=7, active=[7, 11], cancel_from=20, recovery_from=12, hand="both", root_motion=False)

# ---------- dodges ----------
ARMS = [f"{s}_{b}" for s in "LR" for b in ("Shoulder", "UpperArm", "LowerArm", "Hand")]
run = ground(load("standing_run_forward")).in_place()


def dodge(name, src, a, b, frames):
    c = ground(load(src)).warp([(a, 0), (b, frames)])
    arm_pose = run.sample(np.linspace(0, 8, len(c)))
    c.layer(arm_pose, ARMS, 0.85)
    c.to_root()
    c.fade_from(READY, 3).fade_to(READY, 5)
    keep(name, c, "dodge", iframes=[1, frames // 2 + 2], cancel_from=frames - 4, root_motion=True)
    return c


dodge("Dodge_Back", "dodge_back", 2, 30, 18)
dodge("Dodge_Forward", "dodge_forward", 2, 28, 18)
dodge("Dodge_Left", "dodge_left", 1, 27, 18)
dodge("Dodge_Right", "dodge_right", 1, 27, 18)
dc = attack("Dodge_Counter", "standing_1h_magic_attack_03", 15, 23, 48, 4, 16, mir=True, dist=0.3, cancel=10, fade_in=2)
dc.yaw += ease(len(dc), None, [(0, -180), (4, 0)])
INFO["Dodge_Counter"]["kind"] = "counter"

# ---------- team swap ----------
sw = ground(load("standing_1h_cast_spell_01")).warp([(3, 0), (17, 10), (45, 30)])
sw.hips[:, 2] += ease(len(sw), None, [(0, 0.5), (8, 0), (11, -0.06), (20, 0)])
sw.fade_to(READY, 8)
keep("Swap_In", sw, "swap", hit=10, active=[10, 13], cancel_from=18, root_motion=False)
so = ground(load("wide_arm_spell_casting")).warp([(10, 0), (26, 8), (46, 20)]).fade_from(READY, 4)
step(so, -0.5, 8, 20)
keep("Swap_Out", so, "swap", hit=8, active=[8, 11], root_motion=True)

# ---------- air ----------
j = ground(load("standing_jump"))
top = j.hips[:, 2].copy()
peak = int(np.argmax(top))
j.hips[:, 2] = np.minimum(j.hips[:, 2], READY[1][2] + 0.03)  # height comes from gameplay, not the clip
js = j.seg(6, peak).speed(1.4).fade_from(READY, 4)
keep("Jump_Start", js, "move", next="Jump_Loop")
jl = j.seg(peak - 2, peak + 2).sample(np.linspace(0, 4, 40))
jl.add("L_UpperArm", FRONT, 5 * np.sin(np.arange(40) / 40 * 2 * math.pi))
jl.add("R_UpperArm", FRONT, -5 * np.sin(np.arange(40) / 40 * 2 * math.pi))
keep("Jump_Loop", jl.loop(6), "loop")
land = j.seg(peak + 8, min(peak + 34, len(j) - 1)).fade_to(READY, 8)
keep("Jump_Land", land, "move")
area = ground(load("standing_2h_magic_area_attack_01"))
ps = area.warp([(6, 0), (20, 8)])
ps.fade_from((jl.q[0].copy(), jl.hips[0].copy()), 3)
keep("Plunge_Start", ps, "charge", next="Plunge_Loop")
hold = area.seg(19, 21).sample(np.linspace(0, 2, 20)).loop(4)
keep("Plunge_Loop", hold, "loop", next="Plunge_Land")
pl = area.warp([(21, 0), (27, 2), (62, 26)]).fade_to(READY, 9)
keep("Plunge_Land", pl, "attack", hit=2, active=[2, 5], cancel_from=14, recovery_from=6, hand="both", root_motion=False)

# ---------- locomotion ----------
keep("Idle_Combat", IDLE, "loop")
rel = ground(load("standing_idle_02")).in_place().loop(16)
keep("Idle_Relaxed", rel, "loop")
keep("Idle_Break_Magic", ground(load("standing_idle_03")).in_place().fade_from(READY, 10).fade_to(READY, 14), "idle_break")
for n, src in (("Walk_F", "standing_walk_forward"), ("Walk_B", "standing_walk_back"), ("Walk_L", "standing_walk_left"),
               ("Walk_R", "standing_walk_right"), ("Run_F", "standing_run_forward"), ("Run_B", "standing_run_back"),
               ("Run_L", "standing_run_left"), ("Run_R", "standing_run_right"), ("Sprint_F", "standing_sprint_forward")):
    keep(n, ground(load(src)).in_place().loop(4), "loop", speed_cm_s=None)
    raw = load(src)
    INFO[n]["speed_cm_s"] = round(float(np.linalg.norm(raw.hips[-1, :2] - raw.hips[0, :2])) / (len(raw) / A.FPS) * 100)

# ---------- reactions ----------
for n, src in (("Hit_Light_Front", "standing_react_small_from_front"), ("Hit_Light_Back", "standing_react_small_from_back"),
               ("Hit_Light_Left", "standing_react_small_from_left"), ("Hit_Light_Right", "standing_react_small_from_right")):
    keep(n, ground(load(src)).in_place().fade_to(READY, 8), "hit")
for n, src in (("Hit_Heavy_Front", "standing_react_large_from_front"), ("Hit_Heavy_Back", "standing_react_large_from_back")):
    keep(n, ground(load(src)).to_root().fade_to(READY, 8), "hit", root_motion=True)
for n, src in (("Death_Back", "standing_react_death_backward"), ("Death_Front", "standing_react_death_forward")):
    keep(n, load(src).to_root(), "death", root_motion=True)

# ---------- ultimate ----------
# Sixteen seconds in seven phases: gather petals, rise, spin, pull the field in, channel,
# clap it shut, then open the arms and float down. Events cue VFX and camera in Unreal.
sm = ground(load("spell_casting_summon"))
two = ground(load("two_hand_spell_casting"))
ar2 = ground(load("standing_2h_magic_area_attack_02"))
ch = ground(load("standing_2h_magic_attack_03"))
clap = ground(load("standing_2h_magic_attack_05"))
wide = ground(load("wide_arm_spell_casting"))
upc = ground(load("standing_1h_cast_spell_01"))
parts = [sm.warp([(8, 0), (113, 90)]), two.warp([(10, 0), (78, 70)]), ar2.warp([(4, 0), (54, 62), (85, 84)]),
         ch.warp([(10, 0), (30, 22), (105, 118)]), clap.warp([(12, 0), (62, 60), (90, 78)]),
         wide.warp([(10, 0), (77, 72)]), upc.warp([(3, 0), (17, 20), (60, 60)])]
ult = join(parts, 10).fade_from(READY, 8).fade_to(READY, 16)
n = len(ult)
starts = np.cumsum([0] + [len(p) - 10 for p in parts])
p1, p2, p3, p4, p5, p6, p7 = (int(x) for x in starts[:7])
lift = ease(n, None, [(0, 0), (p2, 0), (p2 + 45, 1.5), (p6 + 30, 1.7), (p7 + 8, 0.9), (p7 + 26, 0), (n, 0)])
bob = 0.035 * np.sin(np.arange(n) / 24) * ease(n, None, [(p2 + 30, 0), (p2 + 45, 1), (p7, 1), (p7 + 20, 0)])
ult.root[:, 2] += lift + bob
ult.yaw += ease(n, None, [(0, 0), (p2 + 10, 0), (p2 + 60, 720), (p7 + 6, 720), (p7 + 30, 1080), (n, 1080)])
fl = ease(n, None, [(p2 + 8, 0), (p2 + 34, 1), (p7 + 4, 1), (p7 + 26, 0)])  # legs trail while airborne
rest = load("standing_idle").seg(0, 1).sample(np.zeros(n))
rest.q[:] = (1, 0, 0, 0)  # straight T-pose legs, so the stance does not carry into the air
LEGS =[f"{s}_{b}" for s in "LR" for b in ("UpperLeg", "LowerLeg", "Foot", "ToeBase")]
ult.layer(rest, LEGS, fl)
sway = 7 * np.sin(np.arange(n) / 19)
ult.add("L_UpperLeg", SIDE, (-16 + sway) * fl).add("R_UpperLeg", SIDE, (-6 - sway) * fl)
ult.add("L_LowerLeg", SIDE, (34 + sway) * fl).add("R_LowerLeg", SIDE, (14 - sway) * fl)
ult.add("L_Foot", SIDE, 32 * fl).add("R_Foot", SIDE, 26 * fl)
ult.hips[:, 2] += (0.0 - ult.hips[:, 2]) * fl
ult.add("C_Spine", SIDE, ease(n, None, [(p5 + 30, 0), (p5 + 44, -16), (p5 + 56, 22), (p6, 0)]))
ult.add("C_Chest", SIDE, ease(n, None, [(p6, 0), (p6 + 30, -14), (p7, 0)]))
keep("Ultimate_EternalBloom", ult, "ultimate", root_motion=True, invulnerable=[0, n - 20], events=dict(
    gather_start=p1 + 6, petals_converge=p1 + 70, liftoff=p2 + 8, spin_end=p2 + 60, pull_in=p3 + 16, blast_out=p3 + 54,
    channel_start=p4 + 22, channel_peak=p4 + 95, clap_windup=p5 + 16, clap_hit=p5 + 56, field_open=p6 + 26,
    final_flick=p7 + 20, landing=p7 + 28, control_return=n - 12))

# ---------- face forward ----------
# The Mixamo magic pack stands side-on, about 58 degrees off the direction of travel.
for name, c in MOVES.items():
    corr = A.straighten(c)
    print("straighten", name, round(float(corr.min())), round(float(corr.max())), "hips after", [round(float(A.hips_yaw(c)[i])) for i in (0, len(c) // 2, -1)])

# ---------- write actions ----------
arm = bpy.data.objects["Armature"]
rest_json = json.load(open(ROOT + r"\mixamo\target_rest.json"))
root_rest = np.array(rest_json["root_rest"])
bones = IDLE.bones
for b in bones + ["Root"]:
    arm.pose.bones[b].rotation_mode = "QUATERNION"
if not arm.animation_data:
    arm.animation_data_create()


def track(act, path, values, group):
    F = values.shape[0]
    for i in range(values.shape[1]):
        fc = act.fcurves.new(path, index=i, action_group=group)
        fc.keyframe_points.add(F)
        co = np.empty(F * 2)
        co[0::2], co[1::2] = np.arange(F), values[:, i]
        fc.keyframe_points.foreach_set("co", co)
        fc.keyframe_points.foreach_set("interpolation", [1] * F)
        fc.update()


def fix_signs(q):
    q = q.copy()
    for i in range(1, len(q)):
        if np.dot(q[i], q[i - 1]) < 0:
            q[i] = -q[i]
    return q


for name, c in MOVES.items():
    old = bpy.data.actions.get("A_" + name)
    if old:
        bpy.data.actions.remove(old)
    act = bpy.data.actions.new("A_" + name)
    act.use_fake_user = True
    hips_j = bones.index("J_Bip_C_Hips")
    for j, b in enumerate(bones):
        track(act, f'pose.bones["{b}"].rotation_quaternion', fix_signs(c.q[:, j]), b)
    hr = np.broadcast_to(A.REST["J_Bip_C_Hips"], (len(c), 4))
    track(act, 'pose.bones["J_Bip_C_Hips"].location', A.qrot(A.qinv(hr), c.hips), "J_Bip_C_Hips")
    rr = np.broadcast_to(root_rest, (len(c), 4))
    track(act, 'pose.bones["Root"].location', A.qrot(A.qinv(rr), c.root), "Root")
    yq = A.qaxis(UP, c.yaw)
    track(act, 'pose.bones["Root"].rotation_quaternion', fix_signs(A.qmul(A.qmul(A.qinv(rr), yq), rr)), "Root")

out = ROOT + r"\export_unreal\anim"
os.makedirs(out, exist_ok=True)
json.dump(dict(fps=A.FPS, moves=INFO), open(out + r"\moves.json", "w"), indent=1)
print("moves", len(MOVES), "ultimate seconds", INFO["Ultimate_EternalBloom"]["seconds"])
print({k: v["frames"] for k, v in INFO.items() if v["kind"] in ("attack", "support", "dodge", "ultimate", "counter")})
bpy.ops.wm.save_mainfile()
