"""The town's mesh kit: building types, trees, the landmark spire and a yacht.

Buildings are baked once at their nominal size (plan.SIZES) and scaled per instance; their walls start below
ground so they sit flush on uneven plots. Every building's first material slot is "Wall" and its second "Roof",
so instances can swap in a district's facade and roof materials. Facades and roofs carry no detail of their own:
the materials draw windows and roof colours in world space.
"""
import math

from ship.geo import Part

from . import layout, plan
from colony.geo import bake
from .geo import Builder, limb, sphere
from .util import ROOT, log

FOLDER = f"{ROOT}/Kit"
BASE = -1.5  # walls start this far below the plot


def _rect(hx, hy):
    return [(-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)]


def _octagon(h, chamfer):
    c = h - chamfer
    return [(-c, -h), (c, -h), (h, -c), (h, c), (c, h), (-c, h), (-h, c), (-h, -c)]


def _circle(r, n=32):
    return [(r * math.cos(math.tau * i / n), r * math.sin(math.tau * i / n)) for i in range(n)]


def _parapet(b, hx, hy, z0, z1, t=0.3):
    b.box("Wall", -hx, hx, -hy, -hy + t, z0, z1)
    b.box("Wall", -hx, hx, hy - t, hy, z0, z1)
    b.box("Wall", -hx, -hx + t, -hy + t, hy - t, z0, z1)
    b.box("Wall", hx - t, hx, -hy + t, hy - t, z0, z1)


def house():
    w, d, h = plan.SIZES["house"]
    b = Builder()
    eave = 6.2
    b.prism("Wall", _rect(w / 2, d / 2), BASE, eave, top=False)
    b.gable("Roof", "Wall", w / 2, d / 2, eave, h, 0.5)
    return b


def flat_house():
    w, d, h = plan.SIZES["flat"]
    b = Builder()
    roof = h - 0.6
    b.prism("Wall", _rect(w / 2, d / 2), BASE, roof, top_slot="Roof")
    _parapet(b, w / 2, d / 2, roof, h)
    b.box("Wall", w / 2 - 3.2, w / 2 - 0.6, -d / 2 + 0.6, -d / 2 + 3.0, roof, roof + 2.3)
    return b


def block():
    w, d, h = plan.SIZES["block"]
    b = Builder()
    roof = h - 0.6
    b.prism("Wall", _rect(w / 2, d / 2), BASE, roof, top_slot="Roof")
    _parapet(b, w / 2, d / 2, roof, h)
    b.box("Wall", -6.0, 2.0, -2.5, 2.5, roof, roof + 3.2)
    return b


def courtyard():
    w, _, h = plan.SIZES["courtyard"]
    o, i = w / 2, w / 2 - 12.0
    b = Builder()
    for x0, x1, y0, y1 in ((-o, o, i, o), (-o, o, -o, -i), (i, o, -i, i), (-o, -i, -i, i)):
        b.prism("Wall", [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], BASE, h, top_slot="Roof")
    return b


def terrace():
    w, d, h = plan.SIZES["terrace"]
    b = Builder()
    b.buf("Wall")
    for k in range(4):
        y0 = -d / 2 + k * d / 8
        b.prism("Wall", [(-w / 2, y0), (w / 2, y0), (w / 2, d / 2), (-w / 2, d / 2)], BASE, h * (k + 1) / 4,
                top_slot="Roof")
    return b


def tower():
    w, _, h = plan.SIZES["tower"]
    b = Builder()
    shaft = h - 5.0
    b.prism("Wall", _octagon(w / 2, 3.0), BASE, shaft, top_slot="Roof")
    b.prism("Wall", _octagon(w / 2 - 2.0, 2.4), shaft, h, top_slot="Roof")
    return b


def round_tower():
    w, _, h = plan.SIZES["round"]
    b = Builder()
    b.prism("Wall", _circle(w / 2), BASE, h, top_slot="Roof")
    # Planted terraces ringing it every few floors.
    z = 11.0
    while z < h - 4.0:
        b.prism("Wall", _circle(w / 2 + 1.6), z, z + 0.9, top_slot="Roof")
        z += 11.0
    return b


def pavilion():
    w, d, h = plan.SIZES["pavilion"]
    b = Builder()
    b.prism("Wall", _rect(w / 2 - 1.0, d / 2 - 1.0), BASE, h - 1.4, top_slot="Roof")
    b.prism("Wall", _rect(w / 2 + 2.0, d / 2 + 2.0), h - 1.4, h, top_slot="Roof")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * (w / 2 + 1.0), sy * (d / 2 + 1.0)
            b.box("Wall", x - 0.3, x + 0.3, y - 0.3, y + 0.3, BASE, h - 1.4)
    return b


def landmark():
    """The spire in the canal junction: a glass three-sided needle on white ribs, on a round podium."""
    height = layout.LANDMARK[2]
    part = Part("SM_Landmark")
    b = Builder()
    b.buf("Spire")
    corners = [(26.0 * math.cos(a), 26.0 * math.sin(a)) for a in (math.radians(d) for d in (90.0, 210.0, 330.0))]
    apex = (0.0, 0.0, height)
    g = b.buf("SpireGlass")
    for i in range(3):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 3]
        g.tri(g.vert((x0, y0, 6.0)), g.vert((x1, y1, 6.0)), g.vert(apex))
    b.prism("Spire", _circle(40.0, 64), -2.0, 3.0, top_slot="Spire")
    b.prism("SpireGlass", _circle(36.0, 64), 3.0, 6.0, top=False)
    b.prism("Spire", _circle(37.0, 64), 6.0, 7.0, top_slot="Spire")
    b.into(part)
    for x, y in corners:
        limb(part, "Spire", (x * 1.04, y * 1.04, 0.0), (0.0, 0.0, height + 6.0), 1.6, 0.25, steps=10)
    z = 18.0
    while z < height - 12.0:
        k = 1.0 - (z - 6.0) / (height - 6.0)
        ring = [(x * k * 1.02, y * k * 1.02, z) for x, y in corners]
        for i in range(3):
            limb(part, "Spire", ring[i], ring[(i + 1) % 3], 0.5 * k + 0.15, steps=8)
        z += 14.0
    sphere(part, "SpireLight", (0.0, 0.0, height + 2.0), 1.4, steps=12)
    return part


def _trunk(part, slot, top, radius):
    limb(part, slot, (0.0, 0.0, -0.6), top, radius, radius * 0.65, steps=10)


def broadleaf(kind):
    """Tropical broadleaf trees: a wide umbrella crown, a round one and a tall columnar one."""
    part = Part(f"SM_Tree_{kind}")
    part.slot("Trunk")
    part.slot("Leaves")
    b = Builder()
    if kind == "broad1":
        _trunk(part, "Trunk", (0.0, 0.0, 6.8), 0.45)
        limb(part, "Trunk", (0.0, 0.0, 5.0), (2.4, 1.0, 7.4), 0.24, 0.12, steps=8)
        limb(part, "Trunk", (0.0, 0.0, 5.4), (-2.0, -1.6, 7.6), 0.22, 0.12, steps=8)
        b.blob("Leaves", (0.0, 0.0, 8.4), (5.4, 5.0, 2.3), 11, flatten_bottom=0.4)
        b.blob("Leaves", (2.6, 1.4, 7.9), (3.0, 2.8, 1.8), 12, flatten_bottom=0.3)
        b.blob("Leaves", (-2.3, -1.8, 8.0), (2.8, 3.0, 1.7), 13, flatten_bottom=0.3)
    elif kind == "broad2":
        _trunk(part, "Trunk", (0.0, 0.0, 4.6), 0.32)
        b.blob("Leaves", (0.0, 0.0, 6.6), (3.5, 3.4, 3.1), 21)
        b.blob("Leaves", (1.2, -0.8, 8.6), (2.2, 2.2, 1.9), 22)
    else:
        _trunk(part, "Trunk", (0.0, 0.0, 4.0), 0.3)
        b.blob("Leaves", (0.0, 0.0, 8.0), (2.6, 2.5, 5.0), 31, bump=0.18)
        b.blob("Leaves", (0.3, 0.2, 12.2), (1.6, 1.6, 2.2), 32)
    b.into(part)
    return part


def palm():
    part = Part("SM_Tree_palm")
    part.slot("PalmTrunk")
    part.slot("PalmLeaves")
    lean, height, segments = 1.8, 9.5, 8
    pts = [(lean * (t / segments) ** 2, 0.0, -0.4 + height * t / segments) for t in range(segments + 1)]
    for i, (a, c) in enumerate(zip(pts, pts[1:])):
        r = 0.27 - 0.08 * i / segments
        limb(part, "PalmTrunk", a, c, r, r - 0.01, steps=8)
    top = pts[-1]
    b = Builder()
    fronds = 10
    for k in range(fronds):
        a = math.tau * k / fronds + 0.3 * math.sin(k * 2.1)
        dx, dy = math.cos(a), math.sin(a)
        sx, sy = -dy, dx
        length = 4.4 + 0.6 * math.sin(k * 1.7)
        rise = 1.4 if k % 2 else 0.9
        left, mid, right = [], [], []
        for s in (i / 6 for i in range(7)):
            cx = top[0] + dx * length * s
            cy = top[1] + dy * length * s
            cz = top[2] + rise * s - 3.2 * s * s
            w = 0.95 * math.sin(math.pi * min(s, 0.98)) ** 0.7 + 0.04
            mid.append((cx, cy, cz))
            left.append((cx + sx * w, cy + sy * w, cz - 0.3 * w))
            right.append((cx - sx * w, cy - sy * w, cz - 0.3 * w))
        b.ribbon("PalmLeaves", left, mid)
        b.ribbon("PalmLeaves", mid, right)
    b.into(part)
    sphere(part, "PalmTrunk", (top[0], top[1], top[2] - 0.3), 0.45, steps=10)
    return part


def yacht():
    """A 14 m motor yacht, for the canals and the bay."""
    part = Part("SM_Yacht")
    b = Builder()
    sections = []
    for x, hw, keel, deck in ((-7.0, 2.0, -0.5, 1.3), (-4.0, 2.3, -0.9, 1.4), (0.0, 2.3, -1.0, 1.5),
                              (3.5, 1.9, -0.8, 1.7), (6.0, 1.0, -0.3, 1.9), (7.2, 0.05, 0.6, 2.0)):
        sections.append([(x, 0.0, keel), (x, hw * 0.75, keel + 0.35), (x, hw, deck - 0.2), (x, hw * 0.92, deck),
                         (x, -hw * 0.92, deck), (x, -hw, deck - 0.2), (x, -hw * 0.75, keel + 0.35)])
    # Sections run along +X; each ring goes counter-clockwise seen from the bow.
    b.loft("BoatHull", sections)
    b.box("BoatDeck", -6.6, 5.0, -1.9, 1.9, 1.3, 1.45)
    b.prism("BoatHull", [(-4.5, -1.5), (1.5, -1.5), (3.0, 0.0), (1.5, 1.5), (-4.5, 1.5)], 1.45, 3.4)
    b.prism("BoatHull", [(-3.5, -1.3), (0.5, -1.3), (1.5, 0.0), (0.5, 1.3), (-3.5, 1.3)], 3.4, 4.6)
    b.box("SpireGlass", -4.0, 2.2, -1.52, 1.52, 2.2, 2.9)
    b.into(part)
    return part


BUILDINGS = {"house": house, "flat": flat_house, "block": block, "courtyard": courtyard, "terrace": terrace,
             "tower": tower, "round": round_tower, "pavilion": pavilion}


def build(materials):
    """Bakes the kit; returns {kind: static mesh} for every building and tree kind, plus "landmark" and "yacht"."""
    defaults = dict(materials)
    defaults["Wall"] = materials["Facade_White"]
    defaults["Roof"] = materials["Roof_Flat"]
    kit = {}
    for kind, fn in BUILDINGS.items():
        part = Part(f"SM_Bldg_{kind}")
        part.slot("Wall")
        part.slot("Roof")
        fn().into(part)
        kit[kind] = bake(part, FOLDER, defaults, collision=True, nanite=True, smooth_angle=20.0)
    for kind in ("broad1", "broad2", "broad3"):
        kit[kind] = bake(broadleaf(kind), FOLDER, materials, collision=False, nanite=True, smooth_angle=80.0)
    kit["palm"] = bake(palm(), FOLDER, materials, collision=False, nanite=True, smooth_angle=60.0)
    kit["landmark"] = bake(landmark(), FOLDER, materials, collision=True, nanite=True, smooth_angle=30.0)
    kit["yacht"] = bake(yacht(), FOLDER, materials, collision=True, nanite=True, smooth_angle=35.0)
    log(f"kit: {len(kit)} meshes")
    return kit
