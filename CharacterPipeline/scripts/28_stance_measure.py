# Prints, for each baked source clip, the yaw of hips and upper chest, foot spread direction and
# travel direction, in degrees from the character's forward. Run with Blender's python.
import math, os, sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import animlib as A


def yaw(q):
    v = A.qrot(q, np.broadcast_to(np.array([1.0, 0, 0]), q.shape[:-1] + (3,)))
    return np.degrees(np.arctan2(v[..., 1], v[..., 0]))


names = sys.argv[1:] or sorted(os.path.splitext(f)[0] for f in os.listdir(A.BAKED) if f.endswith(".npz"))
print("clip | hips start mid end | chest start mid end | travel m, deg from forward")
for n in names:
    c = A.load(n)
    D = A.world_rot(c)
    F = len(c)
    pick = [0, F // 2, F - 1]
    h, ch = yaw(D["J_Bip_C_Hips"]), yaw(D["J_Bip_C_UpperChest"])
    t = c.hips[-1, :2] - c.hips[0, :2]
    dist = float(np.linalg.norm(t))
    head = math.degrees(math.atan2(t[0], -t[1])) if dist > 0.2 else float("nan")
    print(f"{n} | {[round(float(h[i])) for i in pick]} | {[round(float(ch[i])) for i in pick]} | {dist:.2f} {head:.0f}")
