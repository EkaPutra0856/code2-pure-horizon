# Session-only command bridge for Blender 4.5.
# Runs scripts/_bridge/cmd.py when it appears, writes the outcome to result.txt.
# Nothing here is saved to Blender preferences; it stops when Blender closes.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, os, io, traceback, contextlib

BRIDGE_DIR = os.path.join(ANIME_GAME_ROOT, r"scripts\_bridge")
CMD = os.path.join(BRIDGE_DIR, "cmd.py")
RESULT = os.path.join(BRIDGE_DIR, "result.txt")
os.makedirs(BRIDGE_DIR, exist_ok=True)


def _tick():
    if not os.path.exists(CMD):
        return 0.5
    with open(CMD, "r", encoding="utf-8") as f:
        code = f.read()
    os.remove(CMD)
    out = io.StringIO()
    try:
        with contextlib.redirect_stdout(out):
            window = bpy.context.window_manager.windows[0]
            with bpy.context.temp_override(window=window, screen=window.screen):
                exec(compile(code, "cmd.py", "exec"), {"__name__": "__bridge__", "bpy": bpy})
        status = "OK"
    except Exception:
        status = "ERROR\n" + traceback.format_exc()
    with open(RESULT + ".tmp", "w", encoding="utf-8") as f:
        f.write(status + "\n" + out.getvalue())
    os.replace(RESULT + ".tmp", RESULT)
    return 0.5


if not bpy.app.timers.is_registered(_tick):
    bpy.app.timers.register(_tick, persistent=True)
print("bridge running")
