import bpy, addon_utils, traceback

def handler(ex):
    print("ENABLE ERROR:", "".join(traceback.format_exception(ex))[-1800:])

r = addon_utils.enable("bl_ext.user_default.vrm", default_set=False, persistent=False, handle_error=handler)
print("result:", r)
print("ops:", [n for n in dir(bpy.ops.import_scene)])
