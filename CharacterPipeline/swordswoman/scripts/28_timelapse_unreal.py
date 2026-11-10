# Making-of timelapse, Unreal part: tours the swordswoman's setup in the BossFight editor UI so it can be
# screen recorded (the real setup ran headless through scripts 12-26). Content browser on /Game/Swordswoman
# -> skeletal mesh editor (sw_ue) -> IK retargeter (mannequin -> swordswoman) -> hair/cloth physics Anim BP
# -> Play In Editor on L_Arena (launch the editor with -BFAutoTest=showcase so the bot fights).
# Run: UnrealEditor.exe BossFight.uproject -ExecCmds="py <this file>" -BFAutoTest=showcase -BFShowLen=90
# Handshake for the recorder (BossFight/Saved): writes _tl_ready.flag once the editor ticks, waits for
# _tl_go.flag, writes _tl_done.flag at the end and quits the editor. Nothing is saved.
import os, time
import unreal

SAVED = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())
FLAG = lambda n: os.path.join(SAVED, f"_tl_{n}.flag")
for n in ("ready", "go", "done"):
    if os.path.exists(FLAG(n)):
        os.remove(FLAG(n))

AES = unreal.get_editor_subsystem(unreal.AssetEditorSubsystem)
LES = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
EAL = unreal.EditorAssetLibrary
MESH = "/Game/Swordswoman/sw_ue"
STEPS = [  # (start s, action, asset)
    (0.0, "browse", MESH),
    (3.5, "open", MESH),
    (11.5, "open", "/Game/Swordswoman/Retarget/RTG_IAC_To_Swordswoman"),
    (19.5, "open", "/Game/Swordswoman/Physics/ABP_Swordswoman_Physics"),
    (26.0, "level", "/Game/BossFight/Maps/L_Arena"),
    (27.0, "play", None),
    (55.0, "stop", None),
    (56.5, "quit", None),
]
# The recorder captures this window in the background (ffmpeg gfxcapture), so: no CPU throttling when the
# editor is not in front, and asset editors dock into the main window (else they open as separate windows
# that the capture misses). Set on the class defaults in memory only; the config is not saved.
for path, prop, val in (("/Script/UnrealEd.Default__EditorPerformanceSettings", "bThrottleCPUWhenNotForeground", "False"),
                        ("/Script/UnrealEd.Default__EditorStyleSettings", "AssetEditorOpenLocation", "MainWindow")):
    cdo = unreal.find_object(None, path)
    ok = unreal.BFEditorTools.set_property_text(cdo, prop, val) if cdo else False
    unreal.log(f"BFTL setting {prop}={val} ok={ok}")
state = {"t0": None, "i": 0, "ready_at": time.time() + 8.0, "ready": False, "opened": []}


def close_editors():
    for a in state["opened"]:
        AES.close_all_editors_for_asset(a)
    state["opened"] = []


def run(action, path):
    unreal.log(f"BFTL step {action} {path or ''}")
    if action == "browse":
        EAL.sync_browser_to_objects([path])
    elif action == "open":
        close_editors()
        a = unreal.load_asset(path)
        AES.open_editor_for_assets([a])
        state["opened"].append(a)
    elif action == "level":
        # bring the level editor tab back in front of the Content Browser tab, or PIE plays out of sight
        close_editors()
        AES.open_editor_for_assets([unreal.load_asset(path)])
    elif action == "play":
        LES.editor_request_begin_play()
    elif action == "stop":
        LES.editor_request_end_play()
    elif action == "quit":
        open(FLAG("done"), "w").write("1")
        unreal.unregister_slate_post_tick_callback(handle)
        unreal.SystemLibrary.quit_editor()


def tick(dt):
    now = time.time()
    if not state["ready"]:
        if now >= state["ready_at"]:  # let the editor finish loading the map and shaders first
            open(FLAG("ready"), "w").write("1")
            state["ready"] = True
        return
    if state["t0"] is None:
        if not os.path.exists(FLAG("go")):
            return
        state["t0"] = now
    t = now - state["t0"]
    while state["i"] < len(STEPS) and t >= STEPS[state["i"]][0]:
        _, action, path = STEPS[state["i"]]
        state["i"] += 1
        run(action, path)


handle = unreal.register_slate_post_tick_callback(tick)
