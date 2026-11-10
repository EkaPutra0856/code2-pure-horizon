# Procedural hair, elf ears and flowers built to match referensi/rambut_ref.webp.
# Character faces -Y; viewer's right in the front view is +X.
# Safe to re-run: removes its own objects first, never touches Body/Face/Armature.
import os
# Project root (the folder that holds BossFight/, scripts/, char4/, swordswoman/ ...).
# Set the ANIME_GAME_ROOT environment variable; defaults to the current directory.
ANIME_GAME_ROOT = os.environ.get("ANIME_GAME_ROOT", ".")

import bpy, bmesh, math, os, random
import numpy as np
from mathutils import Vector

ROOT = ANIME_GAME_ROOT
CY, CZ = 0.032, 1.50
RX, RY, RZ = 0.125, 0.138, 0.14
random.seed(7)

# ---------- helpers ----------
def ell(theta, phi, s=1.06):
    return Vector((RX * s * math.sin(phi) * math.sin(theta),
                   CY - RY * s * math.sin(phi) * math.cos(theta),
                   CZ + RZ * s * math.cos(phi)))


def catmull(pts, n):
    p = [pts[0]] + list(pts) + [pts[-1]]
    segs = len(pts) - 1
    out = []
    for i in range(n):
        f = i / (n - 1) * segs
        k = min(int(f), segs - 1)
        t = f - k
        a, b, c, d = p[k], p[k + 1], p[k + 2], p[k + 3]
        out.append(0.5 * ((2 * b) + (c - a) * t + (2 * a - 5 * b + 4 * c - d) * t * t
                          + (3 * b - a - 3 * c + d) * t ** 3))
    return out


def grad_v(z):
    return min(1.0, max(0.0, (1.25 - z) / 0.22))


def profile_hair(t):
    rise = min(1.0, 0.55 + t * 3.0)
    fall = 1.0 if t < 0.66 else max(0.0, 1 - ((t - 0.66) / 0.34) ** 1.5)
    return rise * fall


def profile_petal(t):
    return math.sin(min(1.0, t ** 0.72 * 1.01) * math.pi) ** 0.95


class Builder:
    def __init__(self, name):
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.name = name

    def lock(self, pts, width, thick, n=26, K=8, prof=profile_hair, bend=0.3,
             mat=0, flat_ref=None, uvmode="height"):
        path = catmull(pts, n)
        rings = []
        for i, p in enumerate(path):
            t = i / (n - 1)
            tan = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
            out = flat_ref if flat_ref is not None else Vector((p.x, p.y - CY, (p.z - CZ) * 0.3))
            if out.length < 1e-5:
                out = Vector((0, 1, 0))
            side = tan.cross(out).normalized()
            nrm = side.cross(tan).normalized()
            w = max(width * prof(t), 0.0004)
            th = max(thick * prof(t), 0.0003)
            ring = []
            for k in range(K):
                a = 2 * math.pi * k / K
                x, y = math.cos(a), math.sin(a)
                ring.append(self.bm.verts.new(p + side * (x * w) + nrm * (y * th - bend * w * x * x)))
            rings.append(ring)
        for i in range(n - 1):
            for k in range(K):
                k2 = (k + 1) % K
                f = self.bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]))
                f.smooth = True
                f.material_index = mat
                for loop, (uu, ii) in zip(f.loops, ((k, i), (k + 1, i), (k + 1, i + 1), (k, i + 1))):
                    u = abs((uu / K) * 2 - 1)
                    v = grad_v(path[ii].z) if uvmode == "height" else ii / (n - 1)
                    loop[self.uv].uv = (u, v)
        for ring in (rings[0], rings[-1]):
            f = self.bm.faces.new(ring)
            f.smooth = True
            f.material_index = mat
            for loop in f.loops:
                loop[self.uv].uv = (0.5, grad_v(path[0].z if ring is rings[0] else path[-1].z))

    def sphere(self, c, r, mat=0, sz=1.0):
        m = bmesh.ops.create_uvsphere(self.bm, u_segments=12, v_segments=8, radius=r)
        for v in m["verts"]:
            v.co = Vector((v.co.x, v.co.y, v.co.z * sz)) + c
            for f in v.link_faces:
                f.material_index = mat
                f.smooth = True

    def finish(self, mats, coll):
        me = bpy.data.meshes.new(self.name)
        self.bm.normal_update()
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        self.bm.to_mesh(me)
        self.bm.free()
        for m in mats:
            me.materials.append(m)
        ob = bpy.data.objects.new(self.name, me)
        coll.objects.link(ob)
        return ob


def flat_mat(name, rgb, rough=0.6):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*rgb, 1)
    b.inputs["Roughness"].default_value = rough
    return m


def srgb(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


# ---------- hair texture: silver to green by height, dark strand edges ----------
def hair_texture():
    path = os.path.join(ROOT, "textures", "hair_gradient.png")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    W, H = 64, 256
    silver = np.array(srgb("DDE0DE"))
    pale = np.array(srgb("CFE2CE"))
    green = np.array(srgb("74B983"))
    deep = np.array(srgb("4C9C63"))
    px = np.zeros((H, W, 4), dtype=np.float32)
    for y in range(H):
        v = y / (H - 1)
        if v < 0.35:
            c = silver + (pale - silver) * (v / 0.35)
        elif v < 0.75:
            c = pale + (green - pale) * ((v - 0.35) / 0.4)
        else:
            c = green + (deep - green) * ((v - 0.75) / 0.25)
        for x in range(W):
            u = x / (W - 1)
            edge = abs(u - 0.5) * 2
            shade = 1.0 - 0.42 * max(0.0, (edge - 0.82) / 0.18) ** 1.5
            shade *= 1.0 - 0.20 * math.exp(-((edge - 0.5) / 0.05) ** 2) - 0.12 * math.exp(-((edge - 0.25) / 0.04) ** 2)
            px[y, x, :3] = np.power(np.clip(c * shade, 0, 1), 1 / 2.2)
            px[y, x, 3] = 1
    img = bpy.data.images.get("hair_gradient")
    if img:
        bpy.data.images.remove(img)
    img = bpy.data.images.new("hair_gradient", W, H, alpha=False)
    img.colorspace_settings.name = "Linear Rec.709" if False else img.colorspace_settings.name
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    return img


def hair_material(img):
    m = bpy.data.materials.get("Hair_New") or bpy.data.materials.new("Hair_New")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    b = nt.nodes.new("ShaderNodeBsdfPrincipled")
    t = nt.nodes.new("ShaderNodeTexImage")
    t.image = img
    t.extension = "EXTEND"
    b.inputs["Roughness"].default_value = 0.55
    nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(b.outputs["BSDF"], o.inputs["Surface"])
    return m


# ---------- hair ----------
def build_hair(h):
    # scalp shell, follows the skull from the centre part
    for s in (1, -1):
        for i in range(16):
            th = s * (0.10 + i / 15 * (math.pi - 0.10))
            end = 1.05 if abs(th) < 1.1 else 1.75
            pts = [ell(th, ph, 1.05) for ph in np.linspace(0.05, end, 7)]
            pts[0] = pts[0] + Vector((s * 0.003, 0, 0))
            h.lock(pts, 0.040, 0.007, n=18, bend=0.18)

    # long wavy back hair, two layers
    # neighbours share a wave phase so strands clump into S-shaped waves
    for layer, (count, z_end, wv, ww) in enumerate(((16, 1.07, 0.030, 0.036),
                                                    (14, 1.035, 0.034, 0.040),
                                                    (10, 1.10, 0.026, 0.052))):
        for s in (1, -1):
            for i in range(count):
                f = i / (count - 1)
                th = s * (0.98 + f * (math.pi - 0.98))
                pts = [ell(th, ph, 1.07 + layer * 0.022) for ph in np.linspace(0.08, 1.72, 6)]
                base = pts[-1].copy()
                z0 = base.z
                ze = z_end + random.uniform(-0.022, 0.022) + 0.03 * (1 - f)
                phase = int(f * 4.99) * 1.25 + layer * 0.25 + (0 if s > 0 else 1.9)
                # target width at the bottom: hair fans out a little, stays behind the arms
                x_end = s * (0.035 + 0.20 * math.sin(min(1.0, (math.pi - abs(th)) / 1.9) * math.pi / 2))
                y_end = 0.100 + 0.012 * layer + 0.03 * f
                steps = 14
                for j in range(1, steps + 1):
                    t = j / steps
                    e = t * t * (3 - 2 * t)
                    z = z0 + (ze - z0) * t
                    amp = wv * t ** 1.15
                    x = base.x + (x_end - base.x) * e + amp * math.sin(t * 7.6 + phase)
                    y = base.y + (y_end - base.y) * min(1.0, e * 1.6) + amp * 0.3 * math.cos(t * 7.6 + phase)
                    pts.append(Vector((x, y, z)))
                pts[-1] = pts[-1] + Vector((s * random.uniform(0.0, 0.018), 0.006, 0))
                h.lock(pts, ww, 0.0085, n=70, bend=0.2)

    # bangs, mirrored with small variation
    bangs = [
        [(.006, -.02, 1.652), (.022, -.095, 1.625), (.032, -.128, 1.565), (.024, -.133, 1.51), (.010, -.128, 1.470)],
        [(.008, -.01, 1.652), (.045, -.09, 1.625), (.062, -.122, 1.565), (.072, -.125, 1.50), (.070, -.120, 1.45), (.082, -.108, 1.405)],
        [(.010, .00, 1.650), (.06, -.07, 1.625), (.095, -.108, 1.56), (.113, -.105, 1.48), (.122, -.095, 1.40), (.135, -.082, 1.335), (.165, -.055, 1.29)],
        [(.012, .01, 1.648), (.085, -.04, 1.615), (.125, -.075, 1.55), (.143, -.075, 1.46), (.146, -.070, 1.38), (.152, -.060, 1.30), (.180, -.035, 1.245)],
    ]
    for s in (1, -1):
        for b in bangs:
            pts = [Vector((c[0] * s, c[1], c[2])) for c in b]
            if s < 0:
                pts = [p + Vector((0, 0, random.uniform(-.004, .004))) for p in pts]
            h.lock(pts, 0.030, 0.0085, n=30, bend=0.35)
        # thin accents between the main bangs
        for off in (0.022, 0.05, 0.09):
            pts = [Vector((.008 * s, -.01, 1.65)), Vector(((.03 + off * .6) * s, -.09, 1.625)),
                   Vector(((.04 + off) * s, -.124, 1.56)), Vector(((.035 + off) * s, -.127, 1.49)),
                   Vector(((.028 + off) * s, -.12, 1.43 + off * .25))]
            h.lock(pts, 0.015, 0.006, n=24)

    # long loose lock on the viewer's right (+X)
    for dx, dz, w in ((0, 0, .026), (.014, .05, .018), (-.012, .03, .016)):
        pts = [Vector(p) for p in ((.112 + dx, -.03, 1.60), (.146 + dx, -.055, 1.50), (.150 + dx, -.075, 1.40),
                                   (.138 + dx, -.095, 1.30), (.172 + dx, -.105, 1.21),
                                   (.146 + dx, -.105, 1.13 + dz), (.186 + dx, -.095, 1.05 + dz))]
        h.lock(pts, w, 0.0075, n=36)


def build_braid(h, band):
    # braid on the viewer's left (-X), from behind the ear down to the chest
    spine = catmull([Vector(p) for p in ((-.122, -.02, 1.56), (-.150, -.045, 1.44), (-.158, -.075, 1.33),
                                         (-.160, -.105, 1.22), (-.160, -.115, 1.12))], 60)
    turns = 4.5
    for k in range(3):
        pts = []
        for i, p in enumerate(spine):
            t = i / 59
            ang = t * turns * 2 * math.pi + k * 2 * math.pi / 3
            a = 0.0165 * min(1.0, t * 6) * (1 - 0.30 * t)
            pts.append(p + Vector((math.sin(ang) * a * 1.25, -abs(1) * math.sin(2 * ang) * a * 0.75, 0)))
        h.lock(pts[::2], 0.0150, 0.0080, n=110, prof=lambda t: min(1.0, 0.6 + t * 4), bend=0.05, K=8)
    end = spine[-1]
    # hair tie and tassel
    for i in range(3):
        ang = i * 2.1
        tip = end + Vector((math.cos(ang) * .022 - .004, math.sin(ang) * .012, -.09 - i * .012))
        h.lock([end + Vector((0, 0, .004)), end + Vector((math.cos(ang) * .012, 0, -.04)), tip], 0.012, 0.006, n=16)
    band.sphere(end + Vector((0, 0, .002)), 0.0115, sz=0.42)


def build_ears(e):
    for s in (1, -1):
        pts = [Vector((s * .120, .035, 1.440)), Vector((s * .142, .046, 1.452)),
               Vector((s * .175, .048, 1.470)), Vector((s * .212, .056, 1.500))]
        e.lock(pts, 0.030, 0.0055, n=18, prof=lambda t: (1 - t) ** 0.75 * min(1, .8 + t * 2), bend=0.2,
               flat_ref=Vector((s * .2, -1, .15)), uvmode="len")


def petal_ring(f, c, axis, count, length, width, lift, mat, phase=0.0, curl=0.3):
    axis = axis.normalized()
    ref = Vector((0, 0, 1)) if abs(axis.z) < 0.9 else Vector((1, 0, 0))
    a1 = axis.cross(ref).normalized()
    a2 = axis.cross(a1).normalized()
    for i in range(count):
        ang = phase + i * 2 * math.pi / count
        d = a1 * math.cos(ang) + a2 * math.sin(ang)
        pts = [c, c + d * length * .4 + axis * lift * length * .45,
               c + d * length * .8 + axis * lift * length * .5,
               c + d * length + axis * (lift - curl) * length * .4]
        f.lock(pts, width, 0.0016, n=14, K=8, prof=profile_petal, bend=0.25, mat=mat, flat_ref=axis, uvmode="len")


def rosebud(f, c, axis, r):
    f.sphere(c, r * .8, mat=2)
    petal_ring(f, c, axis, 5, r * 1.6, r * .85, 1.05, 2, curl=-0.2)
    petal_ring(f, c - axis.normalized() * r * .2, axis, 5, r * 1.9, r * 1.0, .55, 2, phase=.6, curl=.1)
    petal_ring(f, c - axis.normalized() * r * .5, axis, 4, r * 1.3, r * .5, -.2, 3, phase=.2)


def leaf(f, c, d, L, W):
    d = d.normalized()
    pts = [c, c + d * L * .4 + Vector((0, 0, .004)), c + d * L]
    f.lock(pts, W, 0.0012, n=12, prof=profile_petal, bend=0.3, mat=3, flat_ref=Vector((0.2, -1, .4)), uvmode="len")


def build_flowers(f):
    # large pink flower, upper right of the head from the front
    c = Vector((.098, -.098, 1.602))
    ax = Vector((.34, -.84, .42))
    petal_ring(f, c, ax, 7, .078, .027, .45, 0, curl=.30)
    petal_ring(f, c + ax.normalized() * .004, ax, 6, .056, .021, .80, 1, phase=.45, curl=.15)
    f.sphere(c + ax.normalized() * .012, .0115, mat=2)
    for i in range(14):
        a = i * 2.4
        rr = .010 + .004 * (i % 3)
        ref = ax.normalized().cross(Vector((0, 0, 1))).normalized()
        up = ax.normalized().cross(ref)
        f.sphere(c + ax.normalized() * .017 + ref * math.cos(a) * rr + up * math.sin(a) * rr, .0022, mat=4)
    leaf(f, c + Vector((-.03, 0, .0)), Vector((-.9, -.2, .05)), .05, .012)
    leaf(f, c + Vector((.03, -.004, -.03)), Vector((.3, -.3, -1)), .05, .011)
    # buds along the top and behind the flower
    rosebud(f, ell(0.42, 0.42, 1.14), Vector((.2, -.7, .8)), .013)
    rosebud(f, ell(0.85, 0.50, 1.14), Vector((.5, -.5, .8)), .014)
    rosebud(f, Vector((.150, -.025, 1.530)), Vector((1, -.4, .1)), .012)
    rosebud(f, Vector((.142, -.005, 1.500)), Vector((1, -.1, -.2)), .010)
    # vine trailing from the flower
    vine = [c + Vector((.02, 0, -.04)), Vector((.152, -.04, 1.46)), Vector((.150, -.05, 1.41)), Vector((.145, -.052, 1.37))]
    f.lock(vine, .0016, .0016, n=14, mat=3, uvmode="len", bend=0)
    leaf(f, Vector((.152, -.04, 1.45)), Vector((.5, -.6, -.3)), .022, .006)
    leaf(f, Vector((.150, -.05, 1.40)), Vector((-.3, -.7, -.3)), .020, .005)
    # yellow cluster on the viewer's left
    rosebud(f, Vector((-.140, -.018, 1.545)), Vector((-1, -.4, .3)), .014)
    rosebud(f, Vector((-.148, .014, 1.525)), Vector((-1, .0, .2)), .012)
    rosebud(f, Vector((-.132, -.040, 1.515)), Vector((-.9, -.7, -.1)), .011)
    leaf(f, Vector((-.135, -.01, 1.56)), Vector((-.4, -.4, .9)), .035, .009)
    leaf(f, Vector((-.14, -.02, 1.50)), Vector((-.7, -.4, -.7)), .035, .008)


# ---------- scene ----------
def clean():
    for n in ("Hair_New", "Ears_Elf", "Flowers", "Hair_Band"):
        o = bpy.data.objects.get(n)
        if o:
            me = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            bpy.data.meshes.remove(me)


def setup_views():
    sc = bpy.context.scene
    sc.render.engine = "BLENDER_EEVEE"
    sc.render.resolution_x = sc.render.resolution_y = 620
    sc.render.film_transparent = False
    w = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    sc.world = w
    w.use_nodes = True
    w.node_tree.nodes["Background"].inputs[0].default_value = (0.13, 0.13, 0.13, 1)
    w.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    sun = bpy.data.objects.get("KeySun")
    if not sun:
        sd = bpy.data.lights.new("KeySun", "SUN")
        sd.energy = 2.2
        sun = bpy.data.objects.new("KeySun", sd)
        sc.collection.objects.link(sun)
    cam = bpy.data.objects.get("RefCam")
    if not cam:
        cd = bpy.data.cameras.new("RefCam")
        cd.type = "ORTHO"
        cam = bpy.data.objects.new("RefCam", cd)
        sc.collection.objects.link(cam)
    cam.data.ortho_scale = 0.92
    sc.camera = cam
    return cam, sun


def render_views(cam, sun):
    sc = bpy.context.scene
    target = Vector((0, 0.02, 1.33))
    views = (("front", Vector((0, -2, 0))), ("left", Vector((-2, 0, 0))),
             ("right", Vector((2, 0, 0))), ("back", Vector((0, 2, 0))))
    out = os.path.join(ROOT, "renders")
    os.makedirs(out, exist_ok=True)
    tiles = []
    for name, off in views:
        cam.location = target + off
        cam.rotation_euler = (-off).to_track_quat("-Z", "Y").to_euler()
        sun.rotation_euler = (-(off + Vector((0.8, 0, 1.2)))).to_track_quat("-Z", "Y").to_euler()
        fp = os.path.join(out, name + ".png")
        sc.render.filepath = fp
        bpy.ops.render.render(write_still=True)
        im = bpy.data.images.load(fp, check_existing=False)
        a = np.array(im.pixels[:], dtype=np.float32).reshape(im.size[1], im.size[0], 4)
        tiles.append(a)
        bpy.data.images.remove(im)
    top = np.concatenate([tiles[3 - 3], tiles[1]], axis=1)
    bot = np.concatenate([tiles[2], tiles[3]], axis=1)
    sheet = np.concatenate([bot, top], axis=0)
    H, W = sheet.shape[:2]
    im = bpy.data.images.new("sheet", W, H, alpha=True)
    im.pixels.foreach_set(sheet.ravel())
    im.filepath_raw = os.path.join(out, "sheet.png")
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


clean()
coll = bpy.context.scene.collection
hair_img = hair_texture()
m_hair = hair_material(hair_img)
h = Builder("Hair_New")
build_hair(h)
band = Builder("Hair_Band")
build_braid(h, band)
ob_h = h.finish([m_hair], coll)
ob_b = band.finish([flat_mat("Hair_Tie", srgb("C9A24A"))], coll)
e = Builder("Ears_Elf")
build_ears(e)
ob_e = e.finish([flat_mat("Ear_Skin", srgb("FAEBDE"))], coll)
f = Builder("Flowers")
build_flowers(f)
mats = [flat_mat("Petal_Pink", srgb("F2B6C0")), flat_mat("Petal_White", srgb("F9DDE0")),
        flat_mat("Bud_Yellow", srgb("E9C44E")), flat_mat("Leaf_Green", srgb("5E9A4E")),
        flat_mat("Stamen", srgb("C98A2B"))]
ob_f = f.finish(mats, coll)

old = bpy.data.objects.get("Hair")
if old:
    old.hide_render = True
    old.hide_viewport = True

cam, sun = setup_views()
render_views(cam, sun)
print("verts hair", len(ob_h.data.vertices), "flowers", len(ob_f.data.vertices))
bpy.ops.wm.save_mainfile()
