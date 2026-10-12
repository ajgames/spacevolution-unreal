"""The corridor cross-section and the builders every corridor-type module shares.

All corridor modules are authored to one grid cell (CELL x CELL, centred on the actor, deck at Z = 0) and share
this octagonal profile, so any two corridor openings line up. Ribs straddle bay boundaries; at a module's open
ends each module carries half a rib, so neighbours always meet as one full rib whichever way they're rotated.
"""
import math

import unreal

from . import geo
from .geo import X_AXIS, box, cross, norm

CELL = 600.0
HALF_CELL = CELL / 2

# Visible inner surface, right half, (Y, Z) from the floor corner up to the ceiling corner.
LOWER = ((165.0, 0.0), (240.0, 100.0))
WALL = ((240.0, 100.0), (240.0, 270.0))
UPPER = ((240.0, 270.0), (150.0, 390.0))
CEILING_Z = 390.0
# Rib path across the whole section, left floor corner over the ceiling to the right floor corner.
RIB_PATH = [(-165.0, 0.0), (-240.0, 100.0), (-240.0, 270.0), (-150.0, 390.0),
            (150.0, 390.0), (240.0, 270.0), (240.0, 100.0), (165.0, 0.0)]
OCTAGON = [(165.0, 0.0), (240.0, 100.0), (240.0, 270.0), (150.0, 390.0),
           (-150.0, 390.0), (-240.0, 270.0), (-240.0, 100.0), (-165.0, 0.0)]

PANEL = 12.0      # panel thickness: visible surface back to the structural skin
RECESS = 10.0     # depth of hardpoint recesses
SEAM = 1.5        # gap between panels
SKIN = 30.0       # structural skin thickness behind the panels
RIB = 20.0        # half a rib's width along X
RIB_DEPTH = 18.0  # how far a rib stands proud of the panels

# Hardpoint openings, (along corridor, up the surface) in cm. Fixtures are authored to fit these.
EXTENTS = {"Chamfer": (210.0, 80.0), "Wall": (200.0, 100.0), "Ceiling": (220.0, 180.0), "Floor": (140.0, 120.0)}


class Face:
    """A flat strip of the corridor wall between two profile points. side=-1 mirrors it onto the left."""

    def __init__(self, ab, side=1):
        (ay, az), (by, bz) = ab
        self.side = side
        self.a = (ay * side, az)
        b = (by * side, bz)
        self.length = math.hypot(b[0] - self.a[0], b[1] - self.a[1])
        ty, tz = (b[0] - self.a[0]) / self.length, (b[1] - self.a[1]) / self.length
        self.t = (0.0, ty, tz)
        ny, nz = -tz, ty
        mid = ((self.a[0] + b[0]) * .5, (self.a[1] + b[1]) * .5 - 195.0)
        if ny * mid[0] + nz * mid[1] > 0:
            ny, nz = -ny, -nz
        self.n = (0.0, ny, nz)  # points into the corridor

    def point(self, t, x, depth=0.0):
        """Point `t` along the face at corridor position x, pushed `depth` into the wall."""
        return (x, self.a[0] + t * self.t[1] - depth * self.n[1], self.a[1] + t * self.t[2] - depth * self.n[2])

    def panel(self, part, slot, x0, x1, t0, t1, d0=0.0, d1=PANEL, bevel=1.5):
        if x1 - x0 < 1 or t1 - t0 < 1:
            return
        xf = geo.frame(self.point((t0 + t1) * .5, (x0 + x1) * .5, (d0 + d1) * .5), X_AXIS, self.t)
        geo.box_xf(part, slot, xf, x1 - x0, t1 - t0, d1 - d0, bevel)

    def mount(self, t, x):
        """Hardpoint frame on the surface: +X out of the wall, +Z up the face."""
        return geo.frame(self.point(t, x), self.n, (float(self.side), 0.0, 0.0))


def floor_mount(x):
    return geo.frame((x, 0.0, 0.0), (0, 0, 1), X_AXIS)


def ceiling_mount(x):
    return geo.frame((x, 0.0, CEILING_Z), (0, 0, -1), X_AXIS)


# --------------------------------------------------------------------------
# Component specs collected while building, turned into Blueprint components later
# --------------------------------------------------------------------------
class Spec:
    def __init__(self):
        self.parts = []
        self.components = []

    def mesh(self, name, part, xf=None, scale=(1, 1, 1), movable=False):
        self.components.append({"kind": "mesh", "name": name, "part": part.name,
                                "xf": xf or unreal.Transform(), "scale": scale, "movable": movable})

    def camera(self, name, location, field_of_view):
        """Camera looking along the module's +X, e.g. a viewpoint the player controller can blend to."""
        self.components.append({"kind": "camera", "name": name,
                                "xf": unreal.Transform(location=unreal.Vector(*location)), "fov": field_of_view})

    def trigger(self, name, center, half_extent):
        """Overlap volume (pawns only matter to the components that listen to it)."""
        self.components.append({"kind": "box", "name": name, "xf": unreal.Transform(location=unreal.Vector(*center)),
                                "extent": half_extent})

    def door(self, name, leaves, trigger, lamp=None, open_slot=None, closed_slot=None, locked=False, seconds=0.7,
             sounds=None):
        """Door driven by UShipSlidingDoorComponent. leaves: [(component name, open offset[, open rotation as
        (pitch, yaw, roll)])]. With no trigger it only moves when told to; a locked one waits to be unlocked.
        sounds: (open, close) takes under /Game/Audio/SFX, audio.DOOR by default."""
        self.components.append({"kind": "door", "name": name, "leaves": leaves, "trigger": trigger,
                                "lamp": lamp, "open_slot": open_slot, "closed_slot": closed_slot, "locked": locked,
                                "seconds": seconds, "sounds": sounds})

    def light(self, name, origin, direction, width, height, intensity, shadows=True,
              color=(242, 247, 255), along=X_AXIS, barn=60.0, radius=700.0):
        """Rect light at origin shining along `direction`, its long edge running `along`."""
        d = norm(direction)
        along = norm(geo.sub(along, geo.mul(d, sum(a * b for a, b in zip(along, d)))))
        self.components.append({"kind": "rect", "name": name, "xf": geo.frame(origin, d, along),
                                "width": width, "height": height, "intensity": intensity,
                                "shadows": shadows, "color": color, "barn": barn, "radius": radius})

    def hardpoint(self, name, xf, slot, default):
        self.components.append({"kind": "hardpoint", "name": name, "xf": xf, "slot": slot,
                                "extent": EXTENTS[slot], "default": default})


# --------------------------------------------------------------------------
# Shared builders
# --------------------------------------------------------------------------
def structure(part, x0, x1):
    """Dark structural skin behind the panels, both halves of the section, from x0 to x1."""
    half = [(0.0, 0.0), LOWER[0], LOWER[1], WALL[1], UPPER[1], (0.0, CEILING_Z)]
    for side in (1, -1):
        pts = [(y * side, z) for y, z in half]
        inner = geo.outward_offset(pts, PANEL)
        outer = geo.outward_offset(pts, PANEL + SKIN)
        geo.extrude_x(part, "Structure", inner + list(reversed(outer)), x0, x1)


def framed_recess(part, face, ux0, ux1, xc, t_lo, t_hi, r0, r1, rx):
    """Panels framing a hardpoint recess: full-length strips above and below, short strips at the ends."""
    g = SEAM * .5
    for t0, t1 in ((t_lo, r0 - g), (r1 + g, t_hi)):
        face.panel(part, "Hull", ux0, xc - g, t0, t1)
        face.panel(part, "Hull", xc + g, ux1, t0, t1)
    face.panel(part, "Hull", ux0, xc - rx - g, r0 + g, r1 - g)
    face.panel(part, "Hull", xc + rx + g, ux1, r0 + g, r1 - g)
    face.panel(part, "Panel", xc - rx, xc + rx, r0, r1, RECESS, PANEL, bevel=0.0)


def coves(part, x0, x1):
    """Glowing LED strips along the floor edges and the ceiling corners."""
    for side in (1, -1):
        box(part, "LED", x0, x1, side * 148, side * 161, -PANEL, -2.5)
        box(part, "LED", x0, x1, side * 131, side * 147, CEILING_Z + 2, CEILING_Z + PANEL)


def cove_lights(spec, prefix, xc, length, shadows=True, ceiling=22.0, floor=4.0):
    for side, s in ((1, "R"), (-1, "L")):
        spec.light(f"{prefix}_CoveLight{s}", (xc, side * 139, CEILING_Z - 1.5), (0, -side * 0.35, -1),
                   length, 14, ceiling, shadows)
        spec.light(f"{prefix}_FloorLight{s}", (xc, side * 155, -1.0), (0, -side * 0.6, 1),
                   length, 10, floor, False, radius=450.0)


def bay(part, spec, prefix, x0, x1, defaults, lights=True):
    """One bay between rib faces x0..x1: framed recesses on every surface, coves, lights and 8 hardpoints."""
    xc = (x0 + x1) * .5
    ux0, ux1 = x0 - 10, x1 + 10  # panels tuck under the ribs
    g = SEAM * .5
    rx_ch, rt_ch = EXTENTS["Chamfer"][0] * .5, EXTENTS["Chamfer"][1]
    rx_w, rt_w = EXTENTS["Wall"][0] * .5, EXTENTS["Wall"][1]

    for side, s in ((1, "R"), (-1, "L")):
        low, wall, up = Face(LOWER, side), Face(WALL, side), Face(UPPER, side)
        framed_recess(part, low, ux0, ux1, xc, 6, low.length - 3, 22, 22 + rt_ch, rx_ch)
        framed_recess(part, wall, ux0, ux1, xc, 3, wall.length - 3, 35, 35 + rt_w, rx_w)
        framed_recess(part, up, ux0, ux1, xc, 3, up.length - 3, 35, 35 + rt_ch, rx_ch)
        spec.hardpoint(f"{prefix}_Lower{s}", low.mount(22 + rt_ch * .5, xc), "Chamfer", defaults.get(f"Lower{s}"))
        spec.hardpoint(f"{prefix}_Wall{s}", wall.mount(35 + rt_w * .5, xc), "Wall", defaults.get(f"Wall{s}"))
        spec.hardpoint(f"{prefix}_Upper{s}", up.mount(35 + rt_ch * .5, xc), "Chamfer", defaults.get(f"Upper{s}"))

        # Ceiling side flats and floor side plates (split at mid-bay).
        box(part, "Hull", ux0, ux1, side * (90 + g), side * 128.5, CEILING_Z, CEILING_Z + PANEL, bevel=1.5)
        for a, b in ((x0 + g, xc - g), (xc + g, x1 - g)):
            box(part, "Floor", a, b, side * (60 + g), side * 145, -PANEL, 0, bevel=1.2)

    # Floor centre around the hatch recess.
    fx, fy = EXTENTS["Floor"][0] * .5, EXTENTS["Floor"][1] * .5
    box(part, "Floor", x0 + g, xc - fx - g, -fy, fy, -PANEL, 0, bevel=1.2)
    box(part, "Floor", xc + fx + g, x1 - g, -fy, fy, -PANEL, 0, bevel=1.2)
    box(part, "Panel", xc - fx, xc + fx, -fy, fy, -PANEL, -RECESS)
    spec.hardpoint(f"{prefix}_Floor", floor_mount(xc), "Floor", defaults.get("Floor"))

    # Ceiling centre around the service hatch recess.
    cx, cy = EXTENTS["Ceiling"][0] * .5, EXTENTS["Ceiling"][1] * .5
    box(part, "Hull", ux0, xc - cx - g, -cy, cy, CEILING_Z, CEILING_Z + PANEL, bevel=1.5)
    box(part, "Hull", xc + cx + g, ux1, -cy, cy, CEILING_Z, CEILING_Z + PANEL, bevel=1.5)
    box(part, "Panel", xc - cx, xc + cx, -cy, cy, CEILING_Z + RECESS, CEILING_Z + PANEL)
    spec.hardpoint(f"{prefix}_Ceiling", ceiling_mount(xc), "Ceiling", defaults.get("Ceiling"))

    coves(part, x0 + 1, x1 - 1)
    if lights:
        cove_lights(spec, prefix, xc, x1 - x0 - 20)


def plain_section(part, x0, x1, tuck_lo=0.0, tuck_hi=0.0):
    """Unbroken panels on every surface of the clear span x0..x1, for short vestibules.
    Walls and ceiling extend by tuck_lo/tuck_hi to slide under an adjacent rib; the floor stops at the rib's threshold."""
    g = SEAM * .5
    wx0, wx1 = x0 - tuck_lo, x1 + tuck_hi
    for side in (1, -1):
        for ab in (LOWER, WALL, UPPER):
            f = Face(ab, side)
            f.panel(part, "Hull", wx0, wx1, 6 if ab is LOWER else 3, f.length - 3)
        box(part, "Hull", wx0, wx1, side * g, side * 128.5, CEILING_Z, CEILING_Z + PANEL, bevel=1.5)
        box(part, "Floor", x0 + g, x1 - g, side * g, side * 145, -PANEL, 0, bevel=1.2)
    coves(part, x0 + 1, x1 - 1)


def half_width_at(poly, z):
    """Half width of a closed, symmetric YZ polygon at height z."""
    hits = [abs(a[0] + (z - a[1]) * (b[0] - a[0]) / (b[1] - a[1]))
            for a, b in zip(poly, poly[1:] + poly[:1]) if a[1] != b[1] and min(a[1], b[1]) <= z <= max(a[1], b[1])]
    return max(hits)


def threshold(part, x0, x1):
    """Brushed metal plate across the floor under a rib, with two inlaid grip lines."""
    box(part, "Metal", x0, x1, -150, 150, -PANEL, 0, bevel=0.8)
    xm = (x0 + x1) * .5
    for dx in (-6, 6):
        if x0 < xm + dx < x1:
            box(part, "Structure", xm + dx - 1, xm + dx + 1, -140, 140, -0.4, 0.15)


def rib(part, x0, x1, lip0, lip1):
    """Structural frame ring standing proud of the panels (x0..x1), with a narrower stepped lip (lip0..lip1)."""
    geo.extrude_x(part, "Hull", geo.band(RIB_PATH, -RIB_DEPTH, PANEL), x0, x1, bevel=2.0)
    geo.extrude_x(part, "Trim", geo.band(RIB_PATH, -RIB_DEPTH - 8, -RIB_DEPTH + 2), lip0, lip1, bevel=1.5)
