"""Mesh helpers for the town, in metres: vertical prisms, gable roofs, noisy blobs, limbs between two points and
lofts through cross-sections. Everything lands in a ship-kit Part in cm.
"""
import math

import unreal

from colony.geo import Buffers
from colony.noise import Perlin
from ship.geo import BASE, CENTER, GSE, GSP, GSUV, IDENTITY, _opts, cross, frame, norm, sub
from .util import M, V, V2


class LandBuffers(Buffers):
    """Buffers whose vertices also carry a UV1 value each (the ground material reads land use from it)."""

    def __init__(self):
        super().__init__()
        self.uv1 = []

    def add_to(self, part, slot, xf=None):
        if not self.tris:
            return
        b = unreal.GeometryScriptSimpleMeshBuffers()
        b.vertices = [V(*p) for p in self.verts]
        # UV layers are only taken in order from UV0, so it needs filling too; baking box-projects it anyway.
        b.uv0 = [V2(0.0, 0.0)] * len(self.verts)
        b.uv1 = [V2(*t) for t in self.uv1]
        b.triangles = [unreal.IntVector(*t) for t in self.tris]
        m = unreal.DynamicMesh()
        GSE.append_buffers_to_mesh(m, b, part.slot(slot))
        # The part's mesh needs a second layer too, or appending drops it.
        GSUV.set_num_uv_sets(part.mesh, 2)
        part.append(m, xf or IDENTITY)


class UVBuffers(Buffers):
    """Buffers whose vertices carry their own UV0 (for meshes whose material reads UVs)."""

    def __init__(self):
        super().__init__()
        self.uv0 = []

    def add_to(self, part, slot, xf=None):
        if not self.tris:
            return
        b = unreal.GeometryScriptSimpleMeshBuffers()
        b.vertices = [V(*p) for p in self.verts]
        b.uv0 = [V2(*t) for t in self.uv0]
        b.triangles = [unreal.IntVector(*t) for t in self.tris]
        m = unreal.DynamicMesh()
        GSE.append_buffers_to_mesh(m, b, part.slot(slot))
        part.append(m, xf or IDENTITY)


class Builder:
    """Collects triangles per material slot in metres, then adds them all to a Part in cm."""

    def __init__(self):
        self.slots = {}

    def buf(self, slot):
        if slot not in self.slots:
            self.slots[slot] = Buffers()
        return self.slots[slot]

    def into(self, part):
        for slot, buf in self.slots.items():
            buf.verts = [(x * M, y * M, z * M) for x, y, z in buf.verts]
            buf.add_to(part, slot)
        self.slots = {}

    def box(self, slot, x0, x1, y0, y1, z0, z1):
        self.prism(slot, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], z0, z1)

    def prism(self, slot, poly, z0, z1, top=True, bottom=False, top_slot=None):
        """Vertical prism over a convex polygon given counter-clockwise seen from above."""
        b = self.buf(slot)
        lo = [b.vert((x, y, z0)) for x, y in poly]
        hi = [b.vert((x, y, z1)) for x, y in poly]
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            b.quad(lo[i], lo[j], hi[j], hi[i])
        if top:
            t = self.buf(top_slot or slot)
            ids = [t.vert((x, y, z1)) for x, y in poly]
            for i in range(1, n - 1):
                t.tri(ids[0], ids[i], ids[i + 1])
        if bottom:
            for i in range(1, n - 1):
                b.tri(lo[0], lo[i + 1], lo[i])

    def gable(self, roof_slot, wall_slot, hl, hw, eave, ridge, overhang):
        """Pitched roof along X over a 2hl x 2hw footprint, its gable ends in the wall slot."""
        r, w = self.buf(roof_slot), self.buf(wall_slot)
        x0, x1, y = -hl - overhang, hl + overhang, hw + overhang
        drop = overhang * (ridge - eave) / hw
        e = eave - drop
        r.quad(r.vert((x0, -y, e)), r.vert((x1, -y, e)), r.vert((x1, 0.0, ridge)), r.vert((x0, 0.0, ridge)))
        r.quad(r.vert((x1, y, e)), r.vert((x0, y, e)), r.vert((x0, 0.0, ridge)), r.vert((x1, 0.0, ridge)))
        # Soffits under the overhang.
        w.quad(w.vert((x0, -y, e)), w.vert((x0, y, e)), w.vert((x1, y, e)), w.vert((x1, -y, e)))
        for x, sign in ((hl, 1.0), (-hl, -1.0)):
            w.tri(w.vert((x, -hw * sign, eave)), w.vert((x, hw * sign, eave)), w.vert((x, 0.0, ridge)))

    def blob(self, slot, centre, radii, seed, bump=0.22, rings=9, segments=16, flatten_bottom=0.0):
        """Lumpy ellipsoid: a UV sphere whose radius is pushed about by noise."""
        b = self.buf(slot)
        noise = Perlin(seed)
        cx, cy, cz = centre
        rx, ry, rz = radii

        def point(u, v, w):
            k = 1.0 + bump * noise.fbm3(u * 1.6 + seed, v * 1.6, w * 1.6, 2)
            z = w * k
            if w < 0.0:
                z *= 1.0 - flatten_bottom
            return (cx + u * k * rx, cy + v * k * ry, cz + z * rz)

        top = b.vert(point(0.0, 0.0, 1.0))
        bottom = b.vert(point(0.0, 0.0, -1.0))
        ring_ids = []
        for i in range(1, rings):
            phi = math.pi * i / rings
            ring_ids.append([b.vert(point(math.sin(phi) * math.cos(t), math.sin(phi) * math.sin(t), math.cos(phi)))
                             for t in (math.tau * j / segments for j in range(segments))])
        for j in range(segments):
            k = (j + 1) % segments
            b.tri(top, ring_ids[0][j], ring_ids[0][k])
            b.tri(bottom, ring_ids[-1][k], ring_ids[-1][j])
            for upper, lower in zip(ring_ids, ring_ids[1:]):
                b.quad(upper[j], lower[j], lower[k], upper[k])

    def loft(self, slot, sections, cap_start=True, cap_end=True):
        """Skin through closed cross-sections (equal point counts, each counter-clockwise about the direction of
        travel seen from ahead, i.e. from the next section looking back)."""
        b = self.buf(slot)
        ids = [[b.vert(p) for p in s] for s in sections]
        n = len(sections[0])
        for a, c in zip(ids, ids[1:]):
            for i in range(n):
                j = (i + 1) % n
                b.quad(a[i], a[j], c[j], c[i])
        if cap_start:
            for i in range(1, n - 1):
                b.tri(ids[0][0], ids[0][i + 1], ids[0][i])
        if cap_end:
            for i in range(1, n - 1):
                b.tri(ids[-1][0], ids[-1][i], ids[-1][i + 1])

    def ribbon(self, slot, left, right):
        """Two-sided strip between two polylines (a leaf, a fin)."""
        b = self.buf(slot)
        l = [b.vert(p) for p in left]
        r = [b.vert(p) for p in right]
        for i in range(len(left) - 1):
            b.quad(l[i], r[i], r[i + 1], l[i + 1])
            b.quad(l[i + 1], r[i + 1], r[i], l[i])


def basis(direction):
    """Frame axes (x, y, z) with z along direction."""
    z = norm(direction)
    helper = (0.0, 0.0, 1.0) if abs(z[2]) < 0.9 else (1.0, 0.0, 0.0)
    x = norm(cross(helper, z))
    y = cross(z, x)
    return x, y, z


def limb(part, slot, a, b, r0, r1=None, steps=12, capped=True):
    """Tapered cylinder (cone frustum) from a to b, in metres, radii r0 at a and r1 at b."""
    r1 = r0 if r1 is None else r1
    d = sub(b, a)
    length = math.sqrt(sum(c * c for c in d))
    x, y, z = basis(d)
    xf = frame(tuple(c * M for c in a), x, y, z)
    m = unreal.DynamicMesh()
    GSP.append_cone(m, _opts(part.slot(slot)), IDENTITY, r0 * M, max(r1 * M, 0.2), length * M, steps, 1, capped, BASE)
    part.append(m, xf)


def capsule(part, slot, a, b, radius, steps=12):
    d = sub(b, a)
    length = math.sqrt(sum(c * c for c in d))
    x, y, z = basis(d)
    mid = tuple((p + q) * 0.5 * M for p, q in zip(a, b))
    m = unreal.DynamicMesh()
    GSP.append_capsule(m, _opts(part.slot(slot)), IDENTITY, radius * M, length * M, steps // 2, steps, 1, CENTER)
    part.append(m, frame(mid, x, y, z))


def sphere(part, slot, centre, radius, steps=16, scale=(1.0, 1.0, 1.0)):
    m = unreal.DynamicMesh()
    xf = unreal.Transform(location=V(*(c * M for c in centre)), scale=V(*scale))
    GSP.append_sphere_lat_long(m, _opts(part.slot(slot)), IDENTITY, radius * M, steps, steps, CENTER)
    part.append(m, xf)


def torus(part, slot, centre, major, minor, major_steps=48, minor_steps=10):
    m = unreal.DynamicMesh()
    GSP.append_torus(m, _opts(part.slot(slot)), IDENTITY, unreal.GeometryScriptRevolveOptions(),
                     major * M, minor * M, major_steps, minor_steps, CENTER)
    part.append(m, unreal.Transform(location=V(*(c * M for c in centre))))
