"""Mesh building on top of the ship kit's Geometry Script helpers: raw vertex/triangle buffers, geodesic domes,
strut frames and Nanite baking.

Coordinates here are in cm, like the ship kit.
"""
import math

import unreal

from ship.geo import BASE, GSA, GSE, GSN, GSP, GSUV, IDENTITY, _opts, cross, norm, sub
from .util import EAL, V, log


class Buffers:
    """Vertex and triangle lists that become one material slot of a Part.

    Triangles are given counter-clockwise seen from the side they face (the right-hand rule). Geometry Script
    winds the other way, so they're flipped on the way in.
    """

    def __init__(self):
        self.verts = []
        self.tris = []

    def vert(self, p):
        self.verts.append(p)
        return len(self.verts) - 1

    def tri(self, a, b, c):
        self.tris.append((a, c, b))

    def quad(self, a, b, c, d):
        self.tri(a, b, c)
        self.tri(a, c, d)

    def add_to(self, part, slot, xf=None):
        if not self.tris:
            return
        b = unreal.GeometryScriptSimpleMeshBuffers()
        b.vertices = [V(*p) for p in self.verts]
        b.triangles = [unreal.IntVector(*t) for t in self.tris]
        m = unreal.DynamicMesh()
        GSE.append_buffers_to_mesh(m, b, part.slot(slot))
        part.append(m, xf or IDENTITY)


def graded(lo, hi, core_lo, core_hi, step, growth):
    """Sorted coordinates from lo to hi: evenly spaced by `step` inside the core, spacing growing by `growth` per
    step outside it, so a big terrain only spends its vertices where the camera looks closely."""
    xs = []
    x = core_lo
    while x < core_hi:
        xs.append(x)
        x += step
    xs.append(core_hi)
    s, x = step, core_hi
    while x < hi:
        s *= growth
        x = min(x + s, hi)
        xs.append(x)
    s, x = step, core_lo
    while x > lo:
        s *= growth
        x = max(x - s, lo)
        xs.insert(0, x)
    return xs


def heightfield(xs, ys, height_cm):
    """Grid over xs by ys (cm) with heights from height_cm(x, y), as Buffers."""
    buf = Buffers()
    nx, ny = len(xs), len(ys)
    for x in xs:
        for y in ys:
            buf.vert((x, y, height_cm(x, y)))
    for i in range(nx - 1):
        for j in range(ny - 1):
            a, b = i * ny + j, (i + 1) * ny + j
            # Faces up: +X then +Y is counter-clockwise seen from above.
            buf.quad(a, b, b + 1, a + 1)
    return buf


def geodesic_hemisphere(radius, frequency):
    """A hemisphere split into five triangular sectors from the apex down, each subdivided `frequency` times,
    so it has a flat rim on the ground. Returns (vertices, triangles, edges); triangles face outward."""
    verts = [(0.0, 0.0, radius)]
    rings = [[0]]
    for j in range(1, frequency + 1):
        polar = (math.pi / 2) * j / frequency
        ring = []
        for i in range(5 * j):
            az = math.tau * i / (5 * j)
            verts.append((radius * math.sin(polar) * math.cos(az), radius * math.sin(polar) * math.sin(az),
                          radius * math.cos(polar)))
            ring.append(len(verts) - 1)
        rings.append(ring)
    tris = []
    for j in range(frequency):
        upper, lower = rings[j], rings[j + 1]
        for s in range(5):
            for t in range(j + 1):
                a = lower[(s * (j + 1) + t) % len(lower)]
                b = lower[(s * (j + 1) + t + 1) % len(lower)]
                c = upper[(s * j + t) % len(upper)]
                tris.append((a, b, c))
            for t in range(j):
                a = upper[(s * j + t) % len(upper)]
                b = lower[(s * (j + 1) + t + 1) % len(lower)]
                c = upper[(s * j + t + 1) % len(upper)]
                tris.append((a, b, c))
    edges = set()
    for a, b, c in tris:
        for e in ((a, b), (b, c), (c, a)):
            edges.add((min(e), max(e)))
    return verts, tris, sorted(edges)


def strut(buf, a, b, width, depth):
    """Square-section beam from a to b, its depth along the outward radial direction of their midpoint."""
    t = norm(sub(b, a))
    mid = tuple((p + q) * 0.5 for p, q in zip(a, b))
    n = norm(mid)
    s = norm(cross(t, n))
    n = cross(s, t)
    corners = []
    for end in (a, b):
        for du, dv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            corners.append(buf.vert(tuple(end[k] + s[k] * du * width * 0.5 + n[k] * dv * depth * 0.5
                                          for k in range(3))))
    # The corners run counter-clockwise about -t, so each end cap and side quad faces outward in this order.
    a0, b0 = corners[:4], corners[4:]
    for k in range(4):
        k1 = (k + 1) % 4
        buf.quad(a0[k], b0[k], b0[k1], a0[k1])
    buf.quad(a0[0], a0[1], a0[2], a0[3])
    buf.quad(b0[3], b0[2], b0[1], b0[0])


def frustum(part, slot, r0, r1, z0, z1, centre=(0.0, 0.0), steps=64):
    """Capped truncated cone on a vertical axis, from radius r0 at height z0 to r1 at z1 (all in cm)."""
    m = unreal.DynamicMesh()
    GSP.append_cone(m, _opts(part.slot(slot)), unreal.Transform(location=V(centre[0], centre[1], z0)),
                    r0, max(r1, 0.5), z1 - z0, steps, 1, True, BASE)
    part.append(m)


def bake(part, folder, materials, collision=True, nanite=False, smooth_angle=30.0, box_uvs=True):
    """Writes the part to a static mesh asset (replacing any previous one) with named material slots.
    box_uvs=False keeps the part's own UVs instead of projecting new ones."""
    so = unreal.GeometryScriptSplitNormalsOptions()
    so.split_by_opening_angle = True
    so.opening_angle_deg = smooth_angle
    GSN.compute_split_normals(part.mesh, so, unreal.GeometryScriptCalculateNormalsOptions())
    if box_uvs:
        # 1 UV unit per metre; the colony materials are world-space, but this keeps the meshes texturable.
        GSUV.set_mesh_u_vs_from_box_projection(part.mesh, 0, unreal.Transform(scale=V(100, 100, 100)),
                                               unreal.GeometryScriptMeshSelection(), 2)
    path = f"{folder}/{part.name}"
    if EAL.does_asset_exist(path):
        EAL.delete_asset(path)
    opts = unreal.GeometryScriptCreateNewStaticMeshAssetOptions()
    opts.enable_recompute_normals = False
    opts.enable_recompute_tangents = True
    opts.enable_collision = collision
    opts.collision_mode = unreal.CollisionTraceFlag.CTF_USE_COMPLEX_AS_SIMPLE
    opts.enable_nanite = nanite
    sm, outcome = GSA.create_new_static_mesh_asset_from_mesh(part.mesh, path, opts)
    if not sm:
        raise RuntimeError(f"could not create {path}")
    slots = list(sm.static_materials)
    for i in range(len(slots)):
        name = part.slots[i] if i < len(part.slots) else f"Unused{i}"
        slots[i] = unreal.StaticMaterial(material_interface=materials.get(name), material_slot_name=name)
    sm.set_editor_property("static_materials", slots)
    EAL.save_loaded_asset(sm)
    log(f"baked {path} ({len(part.slots)} slots{', Nanite' if nanite else ''})")
    return sm
