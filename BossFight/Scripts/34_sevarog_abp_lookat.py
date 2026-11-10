# Rebuild ABP_Sevarog only (gains the Idle_AO look-at aim offset under the montage slot).
# Run with -ExecutePythonScript; lines start with "BFABP".
import unreal
for line in unreal.BFEditorTools.build_sevarog_anim_blueprint().splitlines():
    print("BFABP", line)
