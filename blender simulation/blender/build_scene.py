"""Procedural dialysis-bay scene for the HemoTwin landing simulation.

Run (Windows):
  blender.exe -b -P build_scene.py -- [--preview] [--no-render]

Outputs:
  public/models/dialysis_bay.glb
  public/models/poster.jpg
  blender/dialysis_bay.blend

Everything is built at real scale in metres, +Z up. Runtime-controlled
objects/materials are prefixed SM_/M_; the JS side finds them by name.
"""

import bpy
import math
import os
import sys
import random
from math import radians, cos, sin, pi
from mathutils import Vector, Matrix

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "public", "models")
TEX = os.path.join(MODELS, "textures")
BLEND_OUT = os.path.join(ROOT, "blender", "dialysis_bay.blend")

args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
PREVIEW = "--preview" in args
NO_RENDER = "--no-render" in args

os.makedirs(MODELS, exist_ok=True)
os.makedirs(TEX, exist_ok=True)

rng = random.Random(12)

# ----------------------------------------------------------------------------
# scene reset
# ----------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.render.engine = "CYCLES"
scene.cycles.samples = 48 if PREVIEW else 128
scene.cycles.use_denoising = True
scene.render.resolution_x = 1280 if PREVIEW else 1920
scene.render.resolution_y = 720 if PREVIEW else 1080
scene.render.resolution_percentage = 100
scene.render.film_transparent = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -0.42


# ----------------------------------------------------------------------------
# helpers
# ----------------------------------------------------------------------------
def make_mat(name, color, rough=0.5, metal=0.0, alpha=1.0,
             emit=None, emit_str=0.0, transmission=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    bsdf.inputs["Alpha"].default_value = alpha
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_str
    if alpha < 1.0:
        try:
            m.blend_method = "BLEND"
        except Exception:
            pass
        m.use_backface_culling = False
        try:
            m.show_transparent_back = False
        except Exception:
            pass
    return m


def smooth(ob, angle=35.0):
    for p in ob.data.polygons:
        p.use_smooth = True
    if angle is not None:
        mod = ob.modifiers.new("EdgeSplit", "EDGE_SPLIT")
        mod.split_angle = radians(angle)
        mod.use_edge_angle = True
        mod.use_edge_sharp = False
    return ob


def bevel(ob, width=0.01, segments=3, angle=44.0):
    if width <= 0:
        return ob
    mod = ob.modifiers.new("Bevel", "BEVEL")
    mod.width = width
    mod.segments = segments
    mod.limit_method = "ANGLE"
    mod.angle_limit = radians(angle)
    mod.use_clamp_overlap = True
    return ob


def box(name, size, loc=(0, 0, 0), rot=(0, 0, 0), mat=None,
        bev=0.01, seg=3, smooth_angle=35.0, parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        ob.data.materials.append(mat)
    if bev > 0:
        bevel(ob, bev, seg)
    smooth(ob, smooth_angle)
    if parent:
        ob.parent = parent
    return ob


def cyl(name, radius, depth, loc=(0, 0, 0), rot=(0, 0, 0), mat=None,
        verts=48, bev=0.004, parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=verts, radius=radius,
                                        depth=depth, location=loc, rotation=rot)
    ob = bpy.context.object
    ob.name = name
    if mat:
        ob.data.materials.append(mat)
    if bev > 0:
        bevel(ob, bev, 2, 44.0)
    smooth(ob, 34.0)
    if parent:
        ob.parent = parent
    return ob


def sphere(name, radius, loc=(0, 0, 0), scale=(1, 1, 1), mat=None,
           segs=40, rings=24, parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=segs, ring_count=rings,
                                         radius=radius, location=loc)
    ob = bpy.context.object
    ob.name = name
    ob.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if mat:
        ob.data.materials.append(mat)
    smooth(ob, None)
    if parent:
        ob.parent = parent
    return ob


def tube(name, pts, radius, mat, res_u=24, bevel_res=3, parent=None):
    curve = bpy.data.curves.new(name, "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = res_u
    curve.bevel_depth = radius
    curve.bevel_resolution = bevel_res
    curve.use_fill_caps = True
    try:
        curve.use_uv_as_generated = True
    except Exception:
        pass
    sp = curve.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for i, p in enumerate(pts):
        bp = sp.bezier_points[i]
        bp.co = Vector(p)
        bp.handle_left_type = "AUTO"
        bp.handle_right_type = "AUTO"
    ob = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.convert(target="MESH")
    ob = bpy.context.object
    smooth(ob, None)
    if parent:
        ob.parent = parent
    return ob


def loft(name, rings, mat, parent=None, cap_start=True, cap_end=True):
    verts = []
    faces = []
    n = len(rings[0])
    for ring in rings:
        verts.extend(tuple(p) for p in ring)
    for j in range(len(rings) - 1):
        for i in range(n):
            a0 = j * n + i
            a1 = j * n + (i + 1) % n
            b0 = (j + 1) * n + i
            b1 = (j + 1) * n + (i + 1) % n
            faces.append((a0, b0, b1, a1))
    if cap_start:
        c = len(verts)
        verts.append(tuple(sum((Vector(p) for p in rings[0]), Vector()) / n))
        for i in range(n):
            faces.append((c, (i + 1) % n, i))
    if cap_end:
        c = len(verts)
        base = (len(rings) - 1) * n
        verts.append(tuple(sum((Vector(p) for p in rings[-1]), Vector()) / n))
        for i in range(n):
            faces.append((c, base + i, base + (i + 1) % n))
    mesh = bpy.data.meshes.new(name + "Mesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    ob = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    smooth(ob, None)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.mesh.normals_make_consistent(inside=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    if parent:
        ob.parent = parent
    return ob


def empty(name, loc=(0, 0, 0), rot=(0, 0, 0)):
    ob = bpy.data.objects.new(name, None)
    ob.empty_display_size = 0.15
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = rot
    return ob


# ----------------------------------------------------------------------------
# palette
# ----------------------------------------------------------------------------
M = {
    "floor":     make_mat("M_Floor",       (0.028, 0.033, 0.037), 0.30, 0.08),
    "wall":      make_mat("M_Wall",        (0.072, 0.080, 0.088), 0.80),
    "wall_dark": make_mat("M_WallDark",    (0.030, 0.035, 0.042), 0.72),
    "metal":     make_mat("M_Metal",       (0.52, 0.55, 0.57),    0.30, 0.9),
    "metal_dark":make_mat("M_MetalDark",   (0.09, 0.10, 0.11),    0.34, 0.75),
    "frame":     make_mat("M_BedFrame",    (0.115, 0.125, 0.135), 0.34, 0.5),
    "headboard": make_mat("M_Headboard",   (0.052, 0.058, 0.066), 0.6, 0.08),
    "headpad":   make_mat("M_HeadboardPad",(0.075, 0.086, 0.094), 0.85, 0.05),
    "plastic_w": make_mat("M_PlasticWhite",(0.52, 0.525, 0.50),   0.56, 0.0),
    "plastic_g": make_mat("M_PlasticGrey", (0.21, 0.225, 0.235),  0.52, 0.05),
    "dark_inset":make_mat("M_PlasticDark", (0.035, 0.04, 0.045),  0.45, 0.1),
    "mattress":  make_mat("M_Mattress",    (0.16, 0.155, 0.145),  0.9),
    "sheet":     make_mat("M_Sheet",       (0.205, 0.198, 0.180), 0.93),
    "pillow":    make_mat("M_Pillow",      (0.215, 0.228, 0.232), 0.95),
    "blanket":   make_mat("M_Blanket",     (0.105, 0.135, 0.145), 0.96),
    "towel":     make_mat("M_Towel",       (0.18, 0.21, 0.22),    0.96),
    "skin":      make_mat("M_Skin",      (0.435, 0.30, 0.232),  0.55),
    "skin_dark": make_mat("M_SkinShadow",  (0.42, 0.275, 0.205),  0.62),
    "hair":      make_mat("M_Hair",        (0.075, 0.068, 0.062), 0.72),
    "brow":      make_mat("M_Brow",        (0.09, 0.07, 0.06),    0.7),
    "lip":       make_mat("M_Lip",         (0.32, 0.175, 0.15),   0.55),
    "tape":      make_mat("M_Tape",        (0.63, 0.60, 0.51),    0.85),
    "blood":     make_mat("M_BloodLine",   (0.16, 0.025, 0.03),   0.32),
    "blood_core":make_mat("M_DialyzerBlood",(0.22, 0.03, 0.035),  0.4),
    "dialysate": make_mat("M_DialysateLine",(0.14, 0.30, 0.33),   0.4),
    "bag":       make_mat("M_Bag",         (0.55, 0.72, 0.74),    0.34, 0.0, 0.30),
    "saline":    make_mat("M_Saline",      (0.62, 0.76, 0.78),    0.32, 0.0, 0.32),
    "screen":    make_mat("M_MachineScreen",(0.012, 0.016, 0.02), 0.34, 0.0,
                          emit=(0.07, 0.24, 0.24), emit_str=1.1),
    "monitor":   make_mat("M_WallMonitor", (0.012, 0.016, 0.02), 0.30, 0.0,
                          emit=(0.06, 0.22, 0.23), emit_str=1.0),
    "alarm":     make_mat("M_AlarmLens",   (0.02, 0.04, 0.04),   0.25, 0.0,
                          emit=(0.08, 0.45, 0.40), emit_str=0.8),
    "window":    make_mat("M_WindowGlass", (0.035, 0.06, 0.075), 0.2, 0.0,
                          emit=(0.06, 0.13, 0.19), emit_str=1.4),
    "blind":     make_mat("M_Blind",       (0.10, 0.115, 0.12),  0.72),
    "cove":      make_mat("M_CoveLight",   (1.0, 0.72, 0.45),    0.5, 0.0,
                          emit=(1.0, 0.63, 0.34), emit_str=3.0),
    "sconce":    make_mat("M_SconceShade", (0.85, 0.60, 0.38),   0.6, 0.0,
                          emit=(1.0, 0.58, 0.30), emit_str=1.6),
    "accent":    make_mat("M_AccentTeal",  (0.10, 0.42, 0.40),   0.4, 0.0,
                          emit=(0.05, 0.35, 0.32), emit_str=1.2),
    "rubber":    make_mat("M_Rubber",      (0.03, 0.03, 0.032),  0.65),
    "paper":     make_mat("M_Paper",       (0.62, 0.60, 0.55),   0.85),
    "droplet":   make_mat("M_Droplet",     (0.62, 0.78, 0.82),   0.1, 0.0, 0.55),
    "gown":      make_mat("M_Gown",        (0.21, 0.262, 0.272),   0.96),
    "gown_seam": make_mat("M_GownSeam",    (0.13, 0.17, 0.18),   0.9),
    "sharps":    make_mat("M_Sharps",      (0.30, 0.055, 0.045),  0.35),
    "colored_0": make_mat("M_ConnectorRed",(0.30, 0.045, 0.04),   0.4),
    "colored_1": make_mat("M_ConnectorBlue",(0.05, 0.13, 0.28),   0.4),
}

# ----------------------------------------------------------------------------
# room shell
# ----------------------------------------------------------------------------
floor = box("SM_Floor", (7.2, 6.0, 0.08), (0, 0.4, -0.04), mat=M["floor"],
            bev=0.0, smooth_angle=None)
box("SM_WallBack", (7.2, 0.12, 3.0), (0, -2.28, 1.5), mat=M["wall"],
    bev=0.005, smooth_angle=None)
box("SM_WallLeft", (0.12, 6.0, 3.0), (-3.55, 0.4, 1.5), mat=M["wall"],
    bev=0.005, smooth_angle=None)
box("SM_WallRight", (0.12, 6.0, 3.0), (3.55, 0.4, 1.5), mat=M["wall"],
    bev=0.005, smooth_angle=None)
box("SM_Ceiling", (7.2, 6.0, 0.1), (0, 0.4, 2.85), mat=M["wall_dark"],
    bev=0.0, smooth_angle=None)

# chair rail
box("SM_ChairRail", (7.2, 0.035, 0.03), (0, -2.205, 1.06), mat=M["wall_dark"], bev=0.006)

# skirting + wall seams
box("SM_Skirting", (7.2, 0.035, 0.09), (0, -2.205, 0.05), mat=M["wall_dark"],
    bev=0.006)
for i, x in enumerate((-2.7, -1.8, -0.9, 0.9, 1.8, 2.7)):
    box(f"SM_WallSeam_{i}", (0.012, 0.01, 2.6), (x, -2.214, 1.4),
        mat=M["wall_dark"], bev=0.0, smooth_angle=None)

# cove light + recess
box("SM_CoveRecess", (6.9, 0.10, 0.06), (0, -2.20, 2.43), mat=M["wall_dark"], bev=0.004)
box("SM_CoveStrip", (6.7, 0.02, 0.018), (0, -2.165, 2.415), mat=M["cove"], bev=0.003)

# window with blinds (back wall, left of bed)
win_x, win_z = -2.05, 1.62
box("SM_WindowFrame", (1.34, 0.05, 1.18), (win_x, -2.225, win_z), mat=M["metal_dark"], bev=0.02)
box("SM_WindowGlass", (1.24, 0.02, 1.08), (win_x, -2.20, win_z), mat=M["window"], bev=0.0)
for i in range(7):
    z = win_z - 0.46 + i * 0.153
    box(f"SM_Blind_{i}", (1.26, 0.055, 0.018), (win_x, -2.17, z),
        rot=(radians(28), 0, 0), mat=M["blind"], bev=0.002)
box("SM_WindowSill", (1.44, 0.13, 0.05), (win_x, -2.15, win_z - 0.63), mat=M["metal_dark"], bev=0.008)

# wall monitor cable
tube("SM_MonitorCable",
     [(-0.25, -2.20, 1.52), (-0.30, -2.21, 1.10), (-0.42, -2.20, 0.62),
      (-0.45, -2.19, 0.10)],
     0.008, M["rubber"], res_u=12, bevel_res=2)

# ----------------------------------------------------------------------------
# bed
# ----------------------------------------------------------------------------
GRP_BED = empty("GRP_Bed", (0, 0, 0))
box("SM_BedRailLower", (0.98, 2.05, 0.10), (0, 0.02, 0.44), mat=M["frame"], bev=0.02, parent=GRP_BED)
box("SM_BedDeck", (0.94, 1.98, 0.05), (0, 0.02, 0.545), mat=M["metal_dark"], bev=0.012, parent=GRP_BED)

for sx in (-1, 1):
    for sy in (-1, 1):
        px, py = sx * 0.40, sy * 0.90
        cyl(f"SM_BedLeg_{sx}_{sy}", 0.030, 0.32, (px, py, 0.26), mat=M["metal"],
            verts=20, bev=0.004, parent=GRP_BED)
        cyl(f"SM_BedWheel_{sx}_{sy}", 0.055, 0.042, (px, py, 0.075),
            rot=(0, radians(90), 0), mat=M["rubber"], verts=28, bev=0.006, parent=GRP_BED)

# headboard / footboard
box("SM_Headboard", (0.98, 0.06, 0.62), (0, -1.03, 0.88), mat=M["headboard"], bev=0.03, parent=GRP_BED)
box("SM_HeadboardInset", (0.78, 0.02, 0.42), (0, -0.995, 0.88), mat=M["headpad"], bev=0.02, parent=GRP_BED)
pass  # no footboard: the blanket drapes into the foreground

# (no side rails - cleaner silhouette, nothing intersects the cloth)

# mattresses
box("SM_MattressFlat", (0.90, 1.22, 0.16), (0, 0.44, 0.655), mat=M["mattress"], bev=0.05, seg=4, parent=GRP_BED)
a = radians(28)


def mattress_z(y):
    if y >= -0.15:
        return 0.735
    return 0.735 + (-0.15 - y) * math.tan(a)


back_len = 0.62
back_center = Vector((0, -0.15 - (back_len / 2) * cos(a), 0.615 + (back_len / 2) * sin(a)))
bpy.ops.mesh.primitive_cube_add(size=1, location=back_center)
back_mat = bpy.context.object
back_mat.name = "SM_MattressBack"
back_mat.scale = (0.72, back_len, 0.10)
back_mat.rotation_euler = (a, 0, 0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
back_mat.data.materials.append(M["sheet"])
bevel(back_mat, 0.05, 4)
smooth(back_mat, 34.0)
back_mat.parent = GRP_BED

# backrest support (so the raised section reads mechanical, not floating)
box("SM_BackrestStrut", (0.72, 0.06, 0.05), (0, -0.48, 0.62),
    rot=(radians(-14), 0, 0), mat=M["metal_dark"], bev=0.012, parent=GRP_BED)
box("SM_BackrestHinge", (0.78, 0.10, 0.08), (0, -0.16, 0.62),
    mat=M["metal_dark"], bev=0.012, parent=GRP_BED)


# pillow on the incline
bpy.ops.mesh.primitive_cube_add(size=1, location=(0, -0.805, 1.085))
pillow = bpy.context.object
pillow.name = "SM_Pillow"
pillow.scale = (0.42, 0.20, 0.058)
pillow.rotation_euler = (a, 0, 0)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
pillow.data.materials.append(M["pillow"])
bevel(pillow, 0.034, 4)
smooth(pillow, 40.0)
pillow.parent = GRP_BED

# ----------------------------------------------------------------------------
# patient: head, neck, forearm, hand (rest under the blanket)
# ----------------------------------------------------------------------------
GRP_PATIENT = empty("GRP_Patient", (0, 0, 0))
head_loc = Vector((0.0, -0.735, 1.288))
head_rot = (radians(42), 0, radians(-20))

bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0, location=head_loc)
head = bpy.context.object
head.name = "SM_Head"
me = head.data
for v in me.vertices:
    z = v.co.z
    if z < 0.05:
        taper = 0.76 + 0.24 * max(0.0, (z + 1.0) / 1.05)
        v.co.x *= taper
        v.co.y *= 0.94 + 0.06 * max(0.0, (z + 1.0) / 1.05)
head.scale = (0.092, 0.106, 0.133)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
head.rotation_euler = head_rot
head.data.materials.append(M["skin"])
smooth(head, None)
head.parent = GRP_PATIENT

GRP_HEAD = empty("GRP_HeadFeatures", head_loc, head_rot)
GRP_HEAD.parent = GRP_PATIENT

# features are authored on +Y (upright face), rotated with the head
def face_pt(x, y, z):
    return (x, y, z)

# nose
n = sphere("SM_Nose", 1.0, (0, 0.096, -0.010), scale=(0.020, 0.027, 0.036), mat=M["skin"], parent=GRP_HEAD)
# brow ridge / brows
for sx in (-1, 1):
    # closed eye / lid
    sphere(f"SM_EyeLid_{sx}", 1.0, (sx * 0.038, 0.0915, 0.012),
           scale=(0.027, 0.0095, 0.0075), mat=M["skin_dark"], parent=GRP_HEAD)
    # ear
    sphere(f"SM_Ear_{sx}", 1.0, (sx * 0.095, 0.004, -0.012),
           scale=(0.013, 0.020, 0.030), mat=M["skin"], parent=GRP_HEAD)
# lips
tube("SM_Mouth", [(-0.026, 0.088, -0.058), (0.0, 0.094, -0.062), (0.026, 0.088, -0.058)],
     0.0038, M["lip"], res_u=12, bevel_res=2, parent=GRP_HEAD)
sphere("SM_LowerLip", 1.0, (0, 0.090, -0.072), scale=(0.022, 0.008, 0.0055),
       mat=M["lip"], parent=GRP_HEAD)
for sx in (-1, 1):
    tube(f"SM_Nasolabial_{sx}", [(sx * 0.030, 0.092, -0.030), (sx * 0.041, 0.083, -0.048),
                                 (sx * 0.044, 0.078, -0.060)],
         0.0024, M["skin_dark"], res_u=8, bevel_res=2, parent=GRP_HEAD)
# cheek/jaw blend
sphere("SM_Chin", 1.0, (0, 0.052, -0.098), scale=(0.040, 0.043, 0.033),
       mat=M["skin"], parent=GRP_HEAD)
for sx in (-1, 1):
    tube(f"SM_Sideburn_{sx}", [(sx * 0.086, 0.026, 0.006), (sx * 0.088, 0.032, -0.036),
                               (sx * 0.083, 0.045, -0.066)],
         0.010, M["hair"], res_u=8, bevel_res=2, parent=GRP_HEAD)

# hair cap: hollow shell over top/back, leaving the face open
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0, location=head_loc)
hair = bpy.context.object
hair.name = "SM_Hair"
hm = hair.data
import bmesh
bm = bmesh.new()
bm.from_mesh(hm)
for f in list(bm.faces):
    c = f.calc_center_median()
    c = Vector((c.x / 0.097, c.y / 0.111, c.z / 0.128))
    keep = not (c.y > 0.26 and c.z < 0.665)         # carve the face opening
    if c.z < -0.55:
        keep = False                                 # neck opening
    if not keep:
        bm.faces.remove(f)
bm.to_mesh(hm)
bm.free()
hair.scale = (0.101, 0.115, 0.132)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
hair.rotation_euler = head_rot
hair.location = head_loc + Vector((0, 0.002, 0.003))
hair.data.materials.append(M["hair"])
sol = hair.modifiers.new("Solidify", "SOLIDIFY")
sol.thickness = 0.006
sol.offset = 1.0
smooth(hair, None)
hair.parent = GRP_PATIENT

# neck: thick at the base, elliptical, angled back into the skull
NECK_AXIS = Vector((0.0, -0.515, 0.857)).normalized()
NECK_SIDE = Vector((0.0, NECK_AXIS.z, -NECK_AXIS.y))


def neck_ring(center, rx, rs, steps=36):
    c = Vector(center)
    return [c + Vector((rx * cos(2 * pi * i / steps), 0, 0))
            + NECK_SIDE * (rs * sin(2 * pi * i / steps)) for i in range(steps)]


NECK_RINGS = [
    neck_ring((0, -0.596, 1.090), 0.060, 0.054),
    neck_ring((0, -0.620, 1.135), 0.056, 0.052),
    neck_ring((0, -0.650, 1.185), 0.050, 0.048),
    neck_ring((0, -0.678, 1.232), 0.044, 0.043),
    neck_ring((0, -0.700, 1.270), 0.038, 0.040),
]
loft("SM_Neck", NECK_RINGS, M["skin"], parent=GRP_PATIENT)

# upper chest / shoulders in the gown, rising from under the blanket to the neck
def body_ring(y, top, wx, ratio, p=2.5, steps=56):
    n = Vector((0, sin(a), cos(a)))
    hn = top * ratio
    hc = top - hn
    c = Vector((0, y, mattress_z(y))) + n * hc
    pts = []
    for i in range(steps):
        th = 2 * pi * i / steps
        cx = math.copysign(abs(cos(th)) ** (2.0 / p), cos(th))
        sz = math.copysign(abs(sin(th)) ** (2.0 / p), sin(th))
        pts.append(c + Vector((wx * cx, 0, 0)) + n * (hn * sz))
    return pts


BIB = [
    (-0.400, 0.062, 0.200, 0.50),
    (-0.470, 0.100, 0.215, 0.49),
    (-0.520, 0.126, 0.228, 0.47),
    (-0.560, 0.150, 0.240, 0.45),
    (-0.600, 0.160, 0.238, 0.43),
    (-0.635, 0.157, 0.215, 0.41),
    (-0.665, 0.142, 0.172, 0.40),
    (-0.690, 0.124, 0.132, 0.40),
    (-0.712, 0.104, 0.094, 0.40),
    (-0.732, 0.086, 0.074, 0.40),
]
loft("SM_GownChest", [body_ring(*st) for st in BIB], M["gown"], parent=GRP_PATIENT)

# deltoids round off the shoulder line
for sx in (-1, 1):
    sphere(f"SM_Shoulder_{'L' if sx > 0 else 'R'}", 1.0,
           (sx * 0.155, -0.575, 1.062), scale=(0.058, 0.080, 0.048),
           mat=M["gown"], segs=36, rings=22, parent=GRP_PATIENT)

# gown neckline collar
bpy.ops.mesh.primitive_torus_add(
    major_radius=0.060, minor_radius=0.008, major_segments=44, minor_segments=12,
    location=(0, -0.641, 1.143), rotation=(radians(31), 0, 0))
collar = bpy.context.object
collar.name = "SM_GownCollar"
collar.data.materials.append(M["gown_seam"])
smooth(collar, None)
collar.parent = GRP_PATIENT

# left forearm resting on the blanket, hand toward the foot of the bed
towel = box("SM_ArmTowel", (0.16, 0.40, 0.030), (0.345, -0.02, 0.812),
            rot=(radians(2), radians(1), radians(5)), mat=M["towel"], bev=0.012, parent=GRP_PATIENT)
# gown sleeve on the near arm; the right arm stays under the blanket
L_ARM = [(0.205, -0.618, 1.050), (0.235, -0.560, 1.032), (0.258, -0.490, 1.020),
         (0.275, -0.420, 1.008), (0.288, -0.350, 0.972), (0.296, -0.290, 0.928),
         (0.300, -0.252, 0.888)]
tube("SM_GownSleeve", L_ARM, 0.047, M["gown"], res_u=24, bevel_res=4, parent=GRP_PATIENT)
tube("SM_GownSleeveSeam", [(0.282, -0.440, 1.030), (0.308, -0.300, 0.938)],
     0.0045, M["gown_seam"], res_u=12, bevel_res=2, parent=GRP_PATIENT)
tube("SM_Forearm", [(0.300, -0.250, 0.885), (0.342, -0.095, 0.842), (0.380, 0.060, 0.812)],
     0.043, M["skin"], res_u=18, bevel_res=4, parent=GRP_PATIENT)
# taper the wrist visually with a second smaller skin tube
tube("SM_Wrist", [(0.380, 0.045, 0.812), (0.390, 0.100, 0.805), (0.398, 0.145, 0.800)],
     0.030, M["skin"], res_u=14, bevel_res=3, parent=GRP_PATIENT)

# hand: palm + fingers, relaxed
palm = sphere("SM_HandPalm", 1.0, (0.404, 0.196, 0.796),
              scale=(0.031, 0.046, 0.013), mat=M["skin"], parent=GRP_PATIENT)
for i in range(4):
    fx = 0.381 + i * 0.014
    tube(f"SM_Finger_{i}",
         [(fx, 0.228, 0.796), (fx + 0.002, 0.260 - abs(i - 1.5) * 0.003, 0.790),
          (fx + 0.004, 0.280 - abs(i - 1.5) * 0.005, 0.780)],
         0.0088, M["skin"], res_u=8, bevel_res=2, parent=GRP_PATIENT)
    sphere(f"SM_Knuckle_{i}", 1.0, (fx, 0.230, 0.804),
           scale=(0.009, 0.012, 0.007), mat=M["skin"], parent=GRP_PATIENT)
tube("SM_Thumb", [(0.376, 0.190, 0.798), (0.362, 0.214, 0.794), (0.366, 0.234, 0.787)],
     0.011, M["skin"], res_u=8, bevel_res=2, parent=GRP_PATIENT)

# AVF access (subtle bump + tape, no needle)
sphere("SM_AVFBump", 1.0, (0.376, 0.092, 0.822), scale=(0.018, 0.030, 0.012),
       mat=M["skin_dark"], parent=GRP_PATIENT)
for i, ty in enumerate((0.100, 0.120)):
    cyl(f"SM_AccessTape_{i}", 0.030, 0.014, (0.384, ty, 0.804),
        rot=(0, radians(4), 0), mat=M["tape"], verts=24, bev=0.003, parent=GRP_PATIENT)
cyl("SM_Wristband", 0.0305, 0.013, (0.400, 0.172, 0.797),
    rot=(radians(90), 0, 0), mat=M["accent"], verts=24, bev=0.002, parent=GRP_PATIENT)

# ----------------------------------------------------------------------------
# blanket (procedural drape)
# ----------------------------------------------------------------------------
# near arm centreline (y, x, z, radius); the cloth is pressed under it
ARM_REST = [
    (-0.618, 0.205, 1.050, 0.047),
    (-0.490, 0.258, 1.020, 0.047),
    (-0.350, 0.288, 0.972, 0.047),
    (-0.252, 0.300, 0.888, 0.047),
    (-0.095, 0.342, 0.842, 0.043),
    (0.060, 0.380, 0.812, 0.043),
    (0.196, 0.404, 0.796, 0.036),
]


def build_blanket():
    nx, ny = 90, 140
    y1 = 1.14
    verts = []
    uv = []

    def smoothstep(x):
        x = min(1.0, max(0.0, x))
        return x * x * (3 - 2 * x)

    for j in range(ny + 1):
        fy = j / ny
        for i in range(nx + 1):
            fx = i / nx
            x = -0.60 + 1.20 * fx
            ax = abs(x)
            # blanket edge sits at mid-chest, leaving the upper body visible
            y0 = -0.425 - 0.030 * smoothstep((ax - 0.05) / 0.25)
            y = y0 + (y1 - y0) * fy
            # mattress reference (head section only for y < -0.15)
            z = mattress_z(y) + 0.02
            # body under the cloth
            torso = 0.108 * math.exp(-((y + 0.28) / 0.30) ** 2) * max(0.0, 1 - (ax / 0.45) ** 4)
            legs = 0.082 * math.exp(-((y - 0.60) / 0.38) ** 2) * max(0.0, 1 - (ax / 0.38) ** 4)
            knee = 0.022 * math.exp(-((y - 0.34) / 0.10) ** 2) * max(0.0, 1 - (ax / 0.34) ** 4)
            z += torso + legs + knee
            # chest mound under the cloth
            chest = 0.052 * math.exp(-((y + 0.60) / 0.16) ** 2) * max(0.0, 1 - (ax / 0.34) ** 4)
            z += chest
            # cloth lifted over the right upper arm tucked under the covers
            arm = (0.040 * math.exp(-((x + 0.265) / 0.10) ** 2)
                   * math.exp(-((y + 0.34) / 0.26) ** 2))
            z += arm
            # drape down over the mattress edges
            if ax > 0.40:
                z -= ((ax - 0.40) / 0.19) ** 2 * 0.34
            # foot-end overhang
            if y > 1.02:
                z -= (y - 1.02) * 0.9
            # cloth wrinkles (deterministic)
            edge_f = min(1.0, max(0.0, (ax - 0.18) / 0.28))
            wr = (0.0085 * sin(7.0 * y + 1.6 * sin(2.4 * x) + 0.4)
                  + 0.0055 * sin(13.0 * y + 2.4 * x + 1.7)
                  + 0.0035 * sin(29.0 * y + 5.0 * x + 0.3)
                  + 0.009 * edge_f * sin(19.0 * y + 4.0 * x))
            fold = (-0.016 * math.exp(-((ax - 0.235) / 0.05) ** 2) * (0.5 + 0.5 * sin(6.0 * y + 0.8))
                    -0.012 * math.exp(-((y - 0.42) / 0.09) ** 2) * (0.5 + 0.5 * sin(5.0 * x + 2.0)))
            z += wr + fold
            # the near arm and its towel rest on top of the cloth: press the
            # sheet beneath them so it never rises through the arm
            pad = ((1.0 - smoothstep((abs(x - 0.345) - 0.100) / 0.030))
                   * (1.0 - smoothstep((abs(y + 0.02) - 0.210) / 0.030)))
            pad_cap = max(0.788, mattress_z(y) + 0.0205)
            if z > pad_cap:
                z = z + (pad_cap - z) * pad
            for k in range(len(ARM_REST) - 1):
                ya, xa, za, ra = ARM_REST[k]
                yb, xb, zb, rb = ARM_REST[k + 1]
                if ya <= y <= yb:
                    f = (y - ya) / (yb - ya)
                    ax_arm = xa + (xb - xa) * f
                    slope = math.sqrt(1.0 + ((zb - za) / (yb - ya)) ** 2)
                    cap = max(za + (zb - za) * f - (ra + (rb - ra) * f) * slope - 0.012,
                              mattress_z(y) + 0.0205)
                    press = 1.0 - smoothstep((abs(x - ax_arm) - 0.05) / 0.055)
                    if z > cap and press > 0:
                        z = z + (cap - z) * 0.98 * press
                    break
            verts.append((x, y, z))
            uv.append((fx, fy))

    faces = []
    for j in range(ny):
        for i in range(nx):
            p = j * (nx + 1) + i
            q = p + nx + 1
            faces.append((p, p + 1, q + 1, q))

    mesh = bpy.data.meshes.new("SM_BlanketMesh")
    mesh.from_pydata(verts, [], faces)
    mesh.update()
    uvl = mesh.uv_layers.new(name="UVMap")
    for li, loop in enumerate(mesh.loops):
        uvl.data[li].uv = uv[loop.vertex_index]
    ob = bpy.data.objects.new("SM_Blanket", mesh)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(M["blanket"])
    sol = ob.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness = 0.018
    sol.offset = -1.0
    smooth(ob, None)
    # keep cloth from intersecting the pillow/head zone
    ob.parent = GRP_PATIENT
    return ob

blanket = build_blanket()

# folded top edge of the blanket at the chest
# nothing floating above the cloth; the chest roll is part of the drape itself

# ----------------------------------------------------------------------------
# dialysis machine (local coords, then placed with a pivot empty)
# ----------------------------------------------------------------------------
PIVOT = Vector((1.06, -0.30, 0.0))
MACH_ROT = radians(-28)
GRP_MACHINE = empty("GRP_Machine", PIVOT, (0, 0, MACH_ROT))
R = Matrix.Rotation(MACH_ROT, 3, "Z")


def mach_world(local):
    v = R @ Vector(local)
    return (v.x + PIVOT.x, v.y + PIVOT.y, v.z)


def mbox(name, size, loc, mat, bev=0.02, seg=3, rot=(0, 0, 0), smooth_angle=35):
    # local machine coordinates; the pivot empty supplies placement + rotation
    return box(name, size, loc, rot=rot,
               mat=mat, bev=bev, seg=seg, smooth_angle=smooth_angle, parent=GRP_MACHINE)


# casters
for i, (lx, ly) in enumerate(((-0.17, -0.20), (0.17, -0.20), (-0.17, 0.20), (0.17, 0.20))):
    cyl(f"SM_MachWheel_{i}", 0.045, 0.035, (lx, ly, 0.055),
        rot=(0, radians(90), 0), mat=M["rubber"], verts=24, bev=0.005, parent=GRP_MACHINE)
    cyl(f"SM_MachFork_{i}", 0.014, 0.09, (lx, ly, 0.105),
        mat=M["metal"], verts=14, bev=0.003, parent=GRP_MACHINE)

mbox("SM_MachBase", (0.50, 0.54, 0.10), (0, 0, 0.155), M["dark_inset"], 0.02)
mbox("SM_MachBody", (0.50, 0.52, 0.94), (0, 0, 0.70), M["plastic_w"], 0.045, 4)
mbox("SM_MachBodyInset", (0.02, 0.40, 0.52), (0.255, 0.0, 0.72), M["plastic_g"], 0.01)
mbox("SM_MachAccentStrip", (0.505, 0.02, 0.018), (0, -0.262, 0.54), M["accent"], 0.004)
mbox("SM_MachTopRail", (0.50, 0.50, 0.045), (0, 0.01, 1.19), M["plastic_g"], 0.012)
mbox("SM_MachControlStrip", (0.02, 0.34, 0.075), (-0.258, -0.02, 1.135), M["dark_inset"], 0.006)
for i in range(3):
    mbox(f"SM_MachBtn_{i}", (0.026, 0.036, 0.026), (-0.268, -0.115 + i * 0.075, 1.14), M["metal"], 0.004)
mbox("SM_ConnectorBlock", (0.075, 0.13, 0.09), (-0.245, -0.12, 0.72), M["plastic_g"], 0.012)
for i, (cy, cc) in enumerate(((0.03, (0.30, 0.055, 0.05)), (-0.03, (0.06, 0.16, 0.30)))):
    cyl(f"SM_ConnectorPort_{i}", 0.016, 0.035, (-0.29, -0.12 + cy, 0.72),
        rot=(0, radians(90), 0), mat=M["colored_" + str(i)], verts=16, bev=0.003, parent=GRP_MACHINE)
mbox("SM_BrandPlate", (0.002, 0.24, 0.035), (-0.253, 0.07, 1.075), M["metal"], 0.002)
mbox("SM_MachVent", (0.30, 0.012, 0.10), (0, -0.264, 0.37), M["dark_inset"], 0.006)
for i in range(6):
    mbox(f"SM_MachVentSlat_{i}", (0.27, 0.004, 0.006), (0, -0.271, 0.335 + i * 0.014), M["metal_dark"], 0.001)

# control head + tilted screen
mbox("SM_MachHead", (0.50, 0.44, 0.13), (0, -0.02, 1.235), M["plastic_w"], 0.035, 4, rot=(radians(8), 0, 0))
mbox("SM_ScreenBezel", (0.026, 0.40, 0.285), (-0.252, 0.0, 1.30), M["dark_inset"], 0.010, 3, rot=(0, radians(8), 0))
# tilted screen panel (unique material swapped for a live canvas at runtime)
mbox("SM_MachineScreen", (0.014, 0.356, 0.238), (-0.268, 0.0, 1.30), M["screen"], 0.004, 2, rot=(0, radians(8), 0), smooth_angle=None)
mbox("SM_ScreenGloss", (0.006, 0.366, 0.248), (-0.277, 0.0, 1.30), M["screen"], 0.003, 2, rot=(0, radians(8), 0), smooth_angle=None)

# pump housing + rotor
mbox("SM_PumpHousing", (0.055, 0.21, 0.21), (-0.27, 0.12, 0.93), M["plastic_g"], 0.02, 3)
cyl("SM_PumpRotor", 0.066, 0.036, (-0.30, 0.12, 0.93),
    rot=(0, radians(90), 0), mat=M["plastic_w"], verts=32, bev=0.006, parent=GRP_MACHINE)
cyl("SM_PumpHub", 0.030, 0.048, (-0.315, 0.12, 0.93),
    rot=(0, radians(90), 0), mat=M["dark_inset"], verts=24, bev=0.004, parent=GRP_MACHINE)
cyl("SM_PumpCover", 0.080, 0.008, (-0.330, 0.12, 0.93),
    rot=(0, radians(90), 0), mat=M["bag"], verts=36, bev=0.002, parent=GRP_MACHINE)
mbox("SM_PumpArm", (0.03, 0.05, 0.045), (-0.30, 0.035, 1.015), M["metal"], 0.006)

# dialyzer (vertical, translucent shell with red core)
cyl("SM_DialyzerShell", 0.047, 0.24, (-0.10, -0.20, 1.01),
    mat=M["bag"], verts=32, bev=0.006, parent=GRP_MACHINE)
cyl("SM_DialyzerCore", 0.036, 0.20, (-0.10, -0.20, 1.01),
    mat=M["blood_core"], verts=28, bev=0.004, parent=GRP_MACHINE)
for i, dz in enumerate((0.128, -0.128)):
    cyl(f"SM_DialyzerCap_{i}", 0.042, 0.024, (-0.10, -0.20, 1.01 + dz),
        mat=M["plastic_w"], verts=28, bev=0.004, parent=GRP_MACHINE)
mbox("SM_DialyzerClamp", (0.05, 0.06, 0.07), (-0.17, -0.20, 0.85), M["metal_dark"], 0.008)

# side infusion rails + bags
mbox("SM_BagBar", (0.035, 0.46, 0.03), (-0.02, 0.30, 1.55), M["metal"], 0.006)
for i, (by, bz) in enumerate(((0.20, 1.32), (0.36, 1.20))):
    mbox(f"SM_DialysateBag_{i}", (0.045, 0.19, 0.30), (-0.02, by, bz), M["bag"], 0.03, 4, smooth_angle=None)
    mbox(f"SM_BagLabel_{i}", (0.002, 0.12, 0.10), (-0.046, by, bz + 0.02), M["paper"], 0.002)
    cyl(f"SM_BagHanger_{i}", 0.006, 0.10, (-0.02, by, 1.52),
        rot=(0, 0, 0), mat=M["metal"], verts=10, bev=0.0, parent=GRP_MACHINE)

# alarm lens
cyl("SM_AlarmLens", 0.022, 0.018, (0.15, -0.02, 1.385),
    mat=M["alarm"], verts=24, bev=0.004, parent=GRP_MACHINE)
cyl("SM_AlarmBezel", 0.030, 0.020, (0.15, -0.02, 1.372),
    mat=M["dark_inset"], verts=24, bev=0.004, parent=GRP_MACHINE)
mbox("SM_ControlKnob", (0.045, 0.045, 0.035), (-0.20, 0.02, 1.185), M["plastic_g"], 0.008)
mbox("SM_SideTray", (0.14, 0.28, 0.02), (0.30, 0.02, 0.90), M["plastic_g"], 0.008)
box("SM_Notebook", (0.14, 0.20, 0.012), (0.30, 0.04, 0.92),
    rot=(0, 0, radians(8)), mat=M["paper"], bev=0.004, parent=GRP_MACHINE)
box("SM_SharpsBin", (0.13, 0.13, 0.135), (0.30, -0.13, 0.935),
    rot=(0, 0, radians(-6)), mat=M["sharps"], bev=0.012, parent=GRP_MACHINE)
box("SM_SharpsLid", (0.135, 0.135, 0.022), (0.30, -0.13, 1.01),
    rot=(0, 0, radians(-6)), mat=M["plastic_w"], bev=0.008, parent=GRP_MACHINE)

# machine power cable
tube("SM_MachineCable",
     [mach_world((0.20, 0.26, 0.08)), mach_world((0.30, 0.50, 0.03)),
      (1.7, 0.9, 0.02), (2.2, 1.4, 0.02), (2.45, 1.85, 0.02)],
     0.009, M["rubber"], res_u=14, bevel_res=2)

# ----------------------------------------------------------------------------
# bloodlines (from access to machine, sagging arcs)
# ----------------------------------------------------------------------------
wrist = (0.398, 0.148, 0.803)
p1 = mach_world((-0.315, 0.155, 0.95))
p2 = mach_world((-0.155, -0.155, 1.14))

tube("SM_BloodLineArterial",
     [wrist, (0.47, 0.22, 0.90), (0.60, 0.20, 1.02), (0.76, 0.08, 1.05),
      (p1[0] - 0.02, p1[1] + 0.02, 1.00), p1],
     0.0062, M["blood"], res_u=22, bevel_res=3)
tube("SM_BloodLineVenous",
     [p2, (p2[0] - 0.03, p2[1] + 0.06, 1.10), (0.70, -0.10, 1.04), (0.56, 0.0, 0.94),
      (0.45, 0.09, 0.86), wrist],
     0.0062, M["blood"], res_u=22, bevel_res=3)

# connectors
for i, pt in enumerate((wrist, p1, p2)):
    cyl(f"SM_LineConnector_{i}", 0.011, 0.030,
        (pt[0], pt[1], pt[2]), mat=M["plastic_w"], verts=16, bev=0.003)
cyl("SM_AccessGuard", 0.036, 0.026, (0.396, 0.128, 0.804), rot=(radians(6), 0, 0),
    mat=M["plastic_g"], verts=24, bev=0.004)

# dialysate lines from bags into machine
tube("SM_DialysateLineA",
     [mach_world((-0.02, 0.22, 1.22)), mach_world((0.02, 0.26, 0.92)),
      mach_world((0.20, 0.2, 0.78)), mach_world((0.26, 0.15, 0.82))],
     0.0055, M["dialysate"], res_u=16, bevel_res=2)
tube("SM_DialysateLineB",
     [mach_world((-0.02, 0.38, 1.10)), mach_world((0.02, 0.42, 0.84)),
      mach_world((0.2, 0.40, 0.74)), mach_world((0.26, 0.30, 0.80))],
     0.0055, M["dialysate"], res_u=16, bevel_res=2)

# ----------------------------------------------------------------------------
# IV pole + saline
# ----------------------------------------------------------------------------
IVP = Vector((1.72, -0.86, 0))
for i in range(5):
    ang = radians(i * 72 + 18)
    box(f"SM_IVLeg_{i}", (0.34, 0.035, 0.030),
        (IVP.x + cos(ang) * 0.17, IVP.y + sin(ang) * 0.17, 0.055),
        rot=(0, 0, ang), mat=M["metal"], bev=0.006)
    cyl(f"SM_IVWheel_{i}", 0.032, 0.024,
        (IVP.x + cos(ang) * 0.31, IVP.y + sin(ang) * 0.31, 0.032),
        rot=(0, radians(90), ang), mat=M["rubber"], verts=18, bev=0.004)
cyl("SM_IVPole", 0.016, 1.92, (IVP.x, IVP.y, 1.01), mat=M["metal"], verts=20, bev=0.003)
cyl("SM_IVPoleInner", 0.010, 0.55, (IVP.x, IVP.y, 1.86), mat=M["metal"], verts=16, bev=0.002)
for i, ang in enumerate((0, radians(120), radians(240))):
    tube(f"SM_IVHook_{i}",
         [(IVP.x, IVP.y, 1.98), (IVP.x + cos(ang) * 0.06, IVP.y + sin(ang) * 0.06, 2.0),
          (IVP.x + cos(ang) * 0.12, IVP.y + sin(ang) * 0.12, 1.985)],
         0.005, M["metal"], res_u=8, bevel_res=2)

box("SM_SalineBag", (0.055, 0.20, 0.28), (IVP.x + 0.10, IVP.y + 0.02, 1.83),
    rot=(0, radians(3), 0), mat=M["saline"], bev=0.028, seg=4, smooth_angle=None)
box("SM_SalineLabel", (0.02, 0.13, 0.10), (IVP.x + 0.075, IVP.y + 0.02, 1.80),
    rot=(0, radians(3), 0), mat=M["paper"], bev=0.002)
cyl("SM_DripChamber", 0.020, 0.075, (IVP.x + 0.105, IVP.y + 0.02, 1.63),
    mat=M["saline"], verts=20, bev=0.004)
sphere("CTRL_Droplet", 0.0065, (IVP.x + 0.105, IVP.y + 0.02, 1.655), mat=M["droplet"], segs=12, rings=8)
tube("SM_SalineLine",
     [(IVP.x + 0.105, IVP.y + 0.02, 1.59), (IVP.x + 0.10, IVP.y + 0.04, 1.35),
      (IVP.x + 0.04, IVP.y + 0.10, 1.02), (1.55, -0.10, 0.92), (1.30, 0.02, 0.86)],
     0.005, M["dialysate"], res_u=18, bevel_res=2)
cyl("SM_IVClip", 0.018, 0.045, (IVP.x, IVP.y + 0.005, 1.30), mat=M["plastic_g"],
    verts=16, bev=0.003)

# ----------------------------------------------------------------------------
# wall monitor
# ----------------------------------------------------------------------------
mon = Vector((-0.22, -2.16, 1.74))
box("SM_MonitorBezel", (0.70, 0.045, 0.45), mon, rot=(radians(6), 0, 0),
    mat=M["dark_inset"], bev=0.02)
box("SM_MonitorScreen", (0.645, 0.006, 0.39), (mon.x, mon.y + 0.027, mon.z + 0.005),
    rot=(radians(6), 0, 0), mat=M["monitor"], bev=0.002, seg=2, smooth_angle=None)
box("SM_MonitorBracket", (0.10, 0.08, 0.10), (mon.x, mon.y - 0.05, mon.z),
    mat=M["metal_dark"], bev=0.01)

# warm wall sconce above the bedhead
cyl("SM_SconcePlate", 0.055, 0.02, (0.62, -2.24, 2.02), rot=(radians(90), 0, 0),
    mat=M["metal_dark"], verts=28, bev=0.004)
cyl("SM_SconceShade", 0.085, 0.15, (0.62, -2.12, 1.955), mat=M["sconce"], verts=28, bev=0.012)
cyl("SM_SconceArm", 0.012, 0.16, (0.62, -2.18, 2.02), rot=(radians(90), 0, 0),
    mat=M["metal"], verts=14, bev=0.003)

# medical gas / vacuum outlet plates behind the bedhead
for i, (gx, gc) in enumerate(((-0.55, (0.20, 0.38, 0.20)), (-0.30, (0.22, 0.30, 0.42)))):
    box(f"SM_GasPlate_{i}", (0.12, 0.025, 0.09), (gx, -2.20, 1.62), mat=M["plastic_w"], bev=0.006)
    cyl(f"SM_GasPort_{i}", 0.022, 0.02, (gx, -2.185, 1.62), rot=(radians(90), 0, 0),
        mat=M["metal_dark"], verts=18, bev=0.003)
    box(f"SM_GasLatch_{i}", (0.05, 0.015, 0.02), (gx, -2.186, 1.585), mat=M["plastic_w"], bev=0.003)

# glove dispenser on the right wall
box("SM_GloveBox", (0.10, 0.24, 0.34), (3.44, -0.70, 1.55), mat=M["plastic_w"], bev=0.012)
box("SM_GloveSlot", (0.02, 0.16, 0.03), (3.38, -0.70, 1.40), mat=M["dark_inset"], bev=0.004)

# wall socket + cable to bed area
box("SM_Socket", (0.12, 0.02, 0.08), (1.95, -2.205, 0.35), mat=M["plastic_w"], bev=0.006)
tube("SM_WallCable", [(1.95, -2.19, 0.30), (1.9, -2.16, 0.12), (1.75, -1.8, 0.02)],
     0.007, M["rubber"], res_u=10, bevel_res=2)

# ----------------------------------------------------------------------------
# texture: subtle tileable wrinkle normal map for the blanket
# ----------------------------------------------------------------------------
def build_fabric_normal():
    try:
        import numpy as np
        n = 512
        x = np.linspace(0, 2 * pi, n, endpoint=False)
        xx, yy = np.meshgrid(x, x, indexing="xy")
        h = (0.55 * np.sin(3 * xx + 1.2 * np.sin(2 * yy))
             + 0.35 * np.sin(5 * yy + 0.8 * np.cos(3 * xx))
             + 0.18 * np.sin(11 * xx + 9 * yy)
             + 0.10 * np.sin(23 * xx - 17 * yy))
        gy, gx = np.gradient(h)
        strength = 0.55
        nz = np.ones_like(h)
        nx_ = -gx * strength
        ny_ = -gy * strength
        ln = np.sqrt(nx_ ** 2 + ny_ ** 2 + nz ** 2)
        nx_ /= ln
        ny_ /= ln
        nz /= ln
        rgb = np.stack([nx_ * 0.5 + 0.5, ny_ * 0.5 + 0.5, nz * 0.5 + 0.5,
                        np.ones_like(h)], axis=-1).astype(np.float32)
        img = bpy.data.images.new("fabric_normal", n, n, alpha=False)
        img.pixels.foreach_set(rgb.ravel())
        path = os.path.join(TEX, "fabric_normal.png")
        img.filepath_raw = path
        img.file_format = "PNG"
        img.save()
        img.colorspace_settings.name = "Non-Color"

        tex_node = M["blanket"].node_tree.nodes.new("ShaderNodeTexImage")
        tex_node.image = img
        tex_node.label = "fabric_normal"
        nm = M["blanket"].node_tree.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.75
        M["blanket"].node_tree.links.new(tex_node.outputs["Color"], nm.inputs["Color"])
        bsdf = M["blanket"].node_tree.nodes.get("Principled BSDF")
        M["blanket"].node_tree.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
        print("[scene] fabric normal map written", path)
    except Exception as e:
        print("[scene] fabric normal skipped:", e)


build_fabric_normal()

# ----------------------------------------------------------------------------
# render camera + lights (poster only; not exported)
# ----------------------------------------------------------------------------
cam_data = bpy.data.cameras.new("PosterCam")
cam = bpy.data.objects.new("PosterCam", cam_data)
bpy.context.collection.objects.link(cam)
cam_loc = Vector((-2.15, 1.85, 1.62))
cam_tgt = Vector((0.18, -0.55, 1.08))
cam.location = cam_loc
cam.rotation_euler = (cam_tgt - cam_loc).to_track_quat("-Z", "Y").to_euler()
cam_data.lens = 55
cam_data.sensor_width = 36
scene.camera = cam
try:
    cam_data.dof.use_dof = True
    cam_data.dof.focus_distance = (cam_tgt - cam_loc).length * 0.92
    cam_data.dof.aperture_fstop = 3.4
except Exception:
    pass


def area(name, loc, tgt, size, power, color, shape="DISK"):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = power
    d.shape = shape
    d.size = size
    d.color = color
    ob = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    return ob


area("Key", (-1.8, 1.5, 2.35), (0.0, -0.2, 0.95), 1.5, 300, (1.0, 0.72, 0.48))
area("Fill", (2.6, 0.9, 1.8), (0.3, -0.1, 0.9), 2.6, 42, (0.55, 0.72, 1.0))
area("Rim", (0.7, -1.9, 2.4), (0.1, 0.0, 1.05), 1.4, 220, (0.58, 0.74, 1.0))
area("PracticalScreen", (0.78, 0.02, 1.42), (0.92, -0.1, 1.28), 0.4, 4, (0.35, 0.85, 0.8))
area("HairLight", (0.55, -1.6, 2.1), (0.0, -0.7, 1.3), 0.5, 20, (1.0, 0.78, 0.6))
# cool spill from the machine display
tp = bpy.data.lights.new("ScreenSpill", "POINT")
tp.energy = 3.2
tp.color = (0.30, 0.85, 0.80)
tp.shadow_soft_size = 0.28
tob = bpy.data.objects.new("ScreenSpill", tp)
bpy.context.collection.objects.link(tob)
tob.location = (0.82, 0.05, 1.32)
p = bpy.data.lights.new("WallWash", "POINT")
p.energy = 7
p.color = (1.0, 0.62, 0.36)
p.shadow_soft_size = 0.35
pob = bpy.data.objects.new("WallWash", p)
bpy.context.collection.objects.link(pob)
pob.location = (0.62, -1.95, 1.95)
# window daylight spill
area("Window", (win_x, -1.9, win_z), (0.0, 0.5, 0.9), 1.4, 30, (0.42, 0.58, 0.85))

world = bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.012, 0.016, 0.022, 1)
bg.inputs["Strength"].default_value = 0.35

# ----------------------------------------------------------------------------
# export
# ----------------------------------------------------------------------------
scene.render.image_settings.file_format = "JPEG"
scene.render.image_settings.quality = 92
scene.render.filepath = os.path.join(MODELS, "poster.jpg")

bpy.ops.object.select_all(action="DESELECT")
mesh_objs = [o for o in scene.objects if o.type == "MESH"]
for o in mesh_objs:
    o.select_set(True)
bpy.context.view_layer.objects.active = mesh_objs[0]

glb_path = os.path.join(MODELS, "dialysis_bay.glb")
bpy.ops.export_scene.gltf(
    filepath=glb_path,
    export_format="GLB",
    use_selection=True,
    export_apply=True,
    export_extras=True,
    export_animations=False,
    export_yup=True,
    export_image_format="AUTO",
    export_cameras=False,
    export_lights=False,
)
print(f"[scene] GLB written: {glb_path} ({os.path.getsize(glb_path)/1e6:.2f} MB)")
print(f"[scene] mesh objects: {len(mesh_objs)}, tris ~ {sum(len(o.data.polygons) for o in mesh_objs)} faces")

bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
print("[scene] blend saved:", BLEND_OUT)

if not NO_RENDER:
    print("[scene] rendering poster ...")
    bpy.ops.render.render(write_still=True)
    print("[scene] poster at", scene.render.filepath)
