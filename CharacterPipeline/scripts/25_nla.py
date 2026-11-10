# Lays every move out on the Armature's NLA, one track per group, strips running one after
# another so the timeline plays the whole moveset. Safe to rerun: it replaces only MOVE_ tracks.
import bpy

GAP = 15
GROUPS = [
    ("MOVE_Combo", ["Attack_N1", "Attack_N2", "Attack_N3", "Attack_N4", "Charge_Start", "Charge_Loop", "Charge_Release"]),
    ("MOVE_Skill", ["Skill_BloomField", "Skill_Heal", "Skill_Buff", "Skill_Hold_Start", "Skill_Hold_Loop", "Skill_Hold_Release"]),
    ("MOVE_Dodge", ["Dodge_Back", "Dodge_Forward", "Dodge_Left", "Dodge_Right", "Dodge_Counter"]),
    ("MOVE_Swap", ["Swap_In", "Swap_Out"]),
    ("MOVE_Air", ["Jump_Start", "Jump_Loop", "Jump_Land", "Plunge_Start", "Plunge_Loop", "Plunge_Land"]),
    ("MOVE_Locomotion", ["Idle_Combat", "Idle_Relaxed", "Idle_Break_Magic", "Walk_F", "Walk_B", "Walk_L", "Walk_R",
                         "Run_F", "Run_B", "Run_L", "Run_R", "Sprint_F"]),
    ("MOVE_Reaction", ["Hit_Light_Front", "Hit_Light_Back", "Hit_Light_Left", "Hit_Light_Right", "Hit_Heavy_Front",
                       "Hit_Heavy_Back", "Death_Back", "Death_Front"]),
    ("MOVE_Ultimate", ["Ultimate_EternalBloom"]),
]
arm = bpy.data.objects["Armature"]
sc = bpy.context.scene
ad = arm.animation_data or arm.animation_data_create()
ad.action = None
for t in [t for t in ad.nla_tracks if t.name.startswith("MOVE_")]:
    ad.nla_tracks.remove(t)
names = {n for _, g in GROUPS for n in g}
for m in [m for m in sc.timeline_markers if m.name in names]:
    sc.timeline_markers.remove(m)

listed = sorted(names)
missing = sorted(a.name[2:] for a in bpy.data.actions if a.name.startswith("A_") and a.name[2:] not in names)
print("not placed", missing)
frame = 1
count = 0
for track_name, moves in GROUPS:
    tr = ad.nla_tracks.new()
    tr.name = track_name
    for n in moves:
        act = bpy.data.actions["A_" + n]
        st = tr.strips.new(n, frame, act)
        st.name = n
        st.extrapolation = "NOTHING"
        st.blend_type = "REPLACE"
        sc.timeline_markers.new(n, frame=frame)
        frame = int(st.frame_end) + GAP
        count += 1
sc.frame_start, sc.frame_end = 1, frame - GAP
sc.render.fps = 30

# make it visible: the NLA editor lists only the selected object by default
for o in bpy.context.view_layer.objects:
    o.select_set(False)
arm.select_set(True)
bpy.context.view_layer.objects.active = arm
win = bpy.context.window_manager.windows[0]
areas = [a.type for a in win.screen.areas]
print("areas", areas)
target = next((a for a in win.screen.areas if a.type == "NLA_EDITOR"), None)
if target is None:
    target = next((a for a in win.screen.areas if a.type in ("DOPESHEET_EDITOR", "TIMELINE")), None)
    if target:
        target.type = "NLA_EDITOR"
if target:
    region = next((r for r in target.regions if r.type == "WINDOW"), None)
    print("nla regions", [r.type for r in target.regions])
    if region:
        with bpy.context.temp_override(window=win, area=target, region=region):
            bpy.ops.nla.view_all()
    target.tag_redraw()

n3 = next(s for t in ad.nla_tracks for s in t.strips if s.name == "Attack_N3")
sc.frame_set(int(n3.frame_start) + 20)
print("root at N3 frame 20", tuple(round(x, 3) for x in arm.pose.bones["Root"].matrix.translation))
sc.frame_set(1)
print("tracks", [(t.name, len(t.strips)) for t in ad.nla_tracks], "strips", count, "end frame", sc.frame_end, "seconds", round(sc.frame_end / 30, 1))
bpy.ops.wm.save_mainfile()
