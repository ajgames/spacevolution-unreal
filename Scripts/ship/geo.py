"""Geometry Script helpers: bevelled boxes, YZ-profile extrusions, revolves and baking to static meshes.

Coordinates are in cm. Module space: X runs along the corridor, Y across it, Z up, deck top at Z = 0.
"""
import math

import unreal

from .util import EAL, V, V2, log

GSP = unreal.GeometryScript_Primitives
GSB = unreal.GeometryScript_MeshBooleans
GSN = unreal.GeometryScript_Normals
GSM = unreal.GeometryScript_MeshModeling
GSE = unreal.GeometryScript_MeshEdits
GSA = unreal.GeometryScript_NewAssetUtils
GSUV = unreal.GeometryScript_UVs

IDENTITY = unreal.Transform()
CENTER = unreal.GeometryScriptPrimitiveOriginMode.CENTER
BASE = unreal.GeometryScriptPrimitiveOriginMode.BASE

# Axis frames (forward, right, up) used to orient primitives.
X_AXIS, Y_AXIS, Z_AXIS = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)


# --------------------------------------------------------------------------
# Small vector math on tuples (faster than round-tripping through unreal.Vector)
# --------------------------------------------------------------------------
def add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def mul(a, s):
    return tuple(x * s for x in a)


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def norm(a):
    length = math.sqrt(sum(x * x for x in a))
    return tuple(x / length for x in a)


def frame(origin, x_axis, y_axis, z_axis=None):
    """Transform whose local X/Y/Z map onto the given world axes. Z defaults to X cross Y (always a proper rotation)."""
    x_axis, y_axis = norm(x_axis), norm(y_axis)
    z_axis = norm(z_axis) if z_axis else cross(x_axis, y_axis)
    rot = unreal.MathLibrary.make_rotation_from_axes(V(*x_axis), V(*y_axis), V(*z_axis))
    return unreal.Transform(location=V(*origin), rotation=rot, scale=V(1, 1, 1))


def compose(local, parent):
    """local relative to parent -> world."""
    return unreal.MathLibrary.compose_transforms(local, parent)


# --------------------------------------------------------------------------
# Parts: one DynamicMesh plus the material slots its triangles use
# --------------------------------------------------------------------------
class Part:
    def __init__(self, name):
        self.name = name
        self.mesh = unreal.DynamicMesh()
        self.slots = []

    def slot(self, slot_name):
        if slot_name not in self.slots:
            self.slots.append(slot_name)
        return self.slots.index(slot_name)

    def append(self, mesh, xf=IDENTITY):
        GSE.append_mesh(self.mesh, mesh, xf)


def _opts(material_id, per_face=False):
    o = unreal.GeometryScriptPrimitiveOptions()
    o.material_id = material_id
    o.polygroup_mode = (unreal.GeometryScriptPrimitivePolygroupMode.PER_FACE if per_face
                        else unreal.GeometryScriptPrimitivePolygroupMode.SINGLE_GROUP)
    return o


def _bevel(mesh, distance, material_id, subdivisions=1):
    if distance <= 0:
        return
    o = unreal.GeometryScriptMeshBevelOptions()
    o.bevel_distance = distance
    o.subdivisions = subdivisions
    o.round_weight = 1.0
    o.infer_material_id = True
    o.set_material_id = material_id
    GSM.apply_mesh_polygroup_bevel(mesh, o)


# --------------------------------------------------------------------------
# Primitives
# --------------------------------------------------------------------------
def box_xf(part, slot, xf, dx, dy, dz, bevel=0.0):
    """Box centred on xf's origin, sized along xf's local axes, with rounded bevelled edges."""
    mid = part.slot(slot)
    m = unreal.DynamicMesh()
    GSP.append_box(m, _opts(mid, bevel > 0), IDENTITY, dx, dy, dz, 0, 0, 0, CENTER)
    _bevel(m, min(bevel, 0.45 * min(dx, dy, dz)), mid)
    part.append(m, xf)


def box_mesh(material_id, x0, x1, y0, y1, z0, z1, bevel=0.0):
    """Standalone axis-aligned box mesh, for boolean work before appending to a part."""
    m = unreal.DynamicMesh()
    xf = unreal.Transform(location=V((x0 + x1) * .5, (y0 + y1) * .5, (z0 + z1) * .5))
    dx, dy, dz = abs(x1 - x0), abs(y1 - y0), abs(z1 - z0)
    GSP.append_box(m, _opts(material_id, bevel > 0), xf, dx, dy, dz, 0, 0, 0, CENTER)
    _bevel(m, min(bevel, 0.45 * min(dx, dy, dz)), material_id)
    return m


def box(part, slot, x0, x1, y0, y1, z0, z1, bevel=0.0, parent=None):
    """Axis-aligned box from min/max corners, optionally inside a parent frame."""
    x0, x1 = sorted((x0, x1))
    y0, y1 = sorted((y0, y1))
    z0, z1 = sorted((z0, z1))
    xf = unreal.Transform(location=V((x0 + x1) * .5, (y0 + y1) * .5, (z0 + z1) * .5))
    if parent:
        xf = compose(xf, parent)
    box_xf(part, slot, xf, x1 - x0, y1 - y0, z1 - z0, bevel)


def cylinder(part, slot, center, axis, radius, length, steps=32, parent=None, capped=True):
    """Cylinder centred on `center` running along `axis` ('x', 'y', 'z' or a vector)."""
    axes = {"x": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), "y": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "z": (X_AXIS, Y_AXIS, Z_AXIS)}
    fwd, right, up = axes[axis]
    xf = frame(center, fwd, right, up)
    if parent:
        xf = compose(xf, parent)
    m = unreal.DynamicMesh()
    GSP.append_cylinder(m, _opts(part.slot(slot)), IDENTITY, radius, length, steps, 0, capped, CENTER)
    part.append(m, xf)


def torus(part, slot, center, axis, major, minor, major_steps=64, minor_steps=12, parent=None):
    axes = {"x": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), "y": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "z": (X_AXIS, Y_AXIS, Z_AXIS)}
    fwd, right, up = axes[axis]
    xf = frame(center, fwd, right, up)
    if parent:
        xf = compose(xf, parent)
    m = unreal.DynamicMesh()
    GSP.append_torus(m, _opts(part.slot(slot)), IDENTITY, unreal.GeometryScriptRevolveOptions(),
                     major, minor, major_steps, minor_steps, CENTER)
    part.append(m, xf)


def signed_area(poly):
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))


def ccw(poly):
    return list(poly) if signed_area(poly) > 0 else list(reversed(poly))


# Local X -> world Y, local Y -> world Z, extrusion (local Z) -> world X.
_YZ_TO_X = ((0, 1, 0), (0, 0, 1), (1, 0, 0))


def extrude_x_mesh(material_id, poly_yz, x0, x1, bevel=0.0):
    """YZ polygon extruded along X from x0 to x1, as a standalone mesh."""
    m = unreal.DynamicMesh()
    xf = frame((x0, 0, 0), *_YZ_TO_X)
    GSP.append_simple_extrude_polygon(m, _opts(material_id, bevel > 0), xf,
                                      [V2(y, z) for y, z in ccw(poly_yz)], x1 - x0, 0, True, BASE)
    _bevel(m, bevel, material_id)
    return m


def extrude_x(part, slot, poly_yz, x0, x1, bevel=0.0, parent=None):
    m = extrude_x_mesh(part.slot(slot), poly_yz, x0, x1, bevel)
    part.append(m, parent or IDENTITY)


def revolve(part, slot, profile, radius, center, axis_dir, steps=128, parent=None):
    """Revolves a (radial offset, height) profile around an axis through `center`; height grows along axis_dir."""
    up = norm(axis_dir)
    fwd = norm(cross(up, (0, 0, 1))) if abs(up[2]) < 0.9 else (1, 0, 0)
    right = cross(up, fwd)
    xf = frame(center, fwd, right, up)
    if parent:
        xf = compose(xf, parent)
    m = unreal.DynamicMesh()
    GSP.append_revolve_polygon(m, _opts(part.slot(slot)), IDENTITY, [V2(u, v) for u, v in ccw(profile)],
                               unreal.GeometryScriptRevolveOptions(), radius, steps)
    part.append(m, xf)


def subtract(target, tool):
    o = unreal.GeometryScriptMeshBooleanOptions()
    GSB.apply_mesh_boolean(target, IDENTITY, tool, IDENTITY, unreal.GeometryScriptBooleanOperation.SUBTRACT, o)
    return target


def cylinder_mesh(material_id, center, axis, radius, length, steps=96):
    axes = {"x": ((0, 0, 1), (0, 1, 0), (-1, 0, 0)), "y": ((1, 0, 0), (0, 0, -1), (0, 1, 0)), "z": (X_AXIS, Y_AXIS, Z_AXIS)}
    m = unreal.DynamicMesh()
    GSP.append_cylinder(m, _opts(material_id), frame(center, *axes[axis]), radius, length, steps, 0, True, CENTER)
    return m


# --------------------------------------------------------------------------
# YZ polylines
# --------------------------------------------------------------------------
def outward_offset(pts, d, center=(0.0, 195.0), closed=False):
    """Offsets a YZ polyline by d along each segment's normal pointing away from `center`, with mitred joints."""
    n = len(pts)
    normals = []
    for i in range(n if closed else n - 1):
        a, b = pts[i], pts[(i + 1) % n]
        t = norm((b[0] - a[0], b[1] - a[1]))
        nv = (-t[1], t[0])
        mid = ((a[0] + b[0]) * .5 - center[0], (a[1] + b[1]) * .5 - center[1])
        if nv[0] * mid[0] + nv[1] * mid[1] < 0:
            nv = (-nv[0], -nv[1])
        normals.append(nv)
    out = []
    for i in range(n):
        if closed:
            n1, n2 = normals[i - 1], normals[i]
        else:
            n1, n2 = normals[max(i - 1, 0)], normals[min(i, len(normals) - 1)]
        s = 1.0 + n1[0] * n2[0] + n1[1] * n2[1]
        out.append((pts[i][0] + d * (n1[0] + n2[0]) / s, pts[i][1] + d * (n1[1] + n2[1]) / s))
    return out


def clip_ends_to_z(pts, z=0.0):
    """Slides the first and last points along their segments until they sit at height z."""
    def hit(a, b):
        t = (z - a[1]) / (b[1] - a[1])
        return (a[0] + t * (b[0] - a[0]), z)
    pts = list(pts)
    pts[0] = hit(pts[0], pts[1])
    pts[-1] = hit(pts[-1], pts[-2])
    return pts


def band(path, d_inner, d_outer, center=(0.0, 195.0), floor_clip=True):
    """Closed polygon between two outward offsets of an open path (a C-shaped ring section)."""
    inner = outward_offset(path, d_inner, center)
    outer = outward_offset(path, d_outer, center)
    if floor_clip:
        inner, outer = clip_ends_to_z(inner), clip_ends_to_z(outer)
    return inner + list(reversed(outer))


# --------------------------------------------------------------------------
# Baking
# --------------------------------------------------------------------------
def finish(mesh):
    so = unreal.GeometryScriptSplitNormalsOptions()
    so.split_by_opening_angle = True
    so.opening_angle_deg = 30.0
    GSN.compute_split_normals(mesh, so, unreal.GeometryScriptCalculateNormalsOptions())
    # 1 UV unit per metre, so textures can be layered on later without unwrapping.
    box_xf = unreal.Transform(scale=V(100, 100, 100))
    GSUV.set_mesh_u_vs_from_box_projection(mesh, 0, box_xf, unreal.GeometryScriptMeshSelection(), 2)


def bake(part, folder, materials, collision=True):
    """Writes the part to a static mesh asset (replacing any previous one) with named material slots."""
    finish(part.mesh)
    path = f"{folder}/{part.name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    opts.enable_recompute_normals = False
    opts.enable_recompute_tangents = True
    opts.enable_collision = collision
    opts.collision_mode = unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    sm, outcome = GSA.create_new_static_mesh_asset_from_mesh(part.mesh, path, opts)
    if not sm:
        raise RuntimeError(f"could not create {path}")
    slots = list(sm.static_materials)
    for i in range(len(slots)):
        name = part.slots[i] if i < len(part.slots) else f"Unused{i}"
        slots[i] = unreal.StaticMaterial(material_interface=materials.get(name), material_slot_name=name)
    sm.set_editor_property("static_materials", slots)
    EAL.save_loaded_asset(sm)
    log(f"baked {path} ({len(part.slots)} slots)")
    return sm
