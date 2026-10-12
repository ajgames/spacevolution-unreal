"""Bridges over the canals and across the bay, baked in place as one mesh.

Each deck arches from one landing to the other, high enough mid-span to ride under, with parapets and piers
down to the canal or sea floor.
"""
import math

from colony.geo import bake
from ship.geo import Part

from . import layout, shape
from .geo import Builder
from .util import ROOT, log

FOLDER = f"{ROOT}/Bridges"
THICKNESS = 1.3
PARAPET = (0.35, 1.0)   # thickness, height above the deck
PIER_SPACING = 42.0


def _deck_height(a, b, mid, t):
    base = a + (b - a) * t
    return base + (mid - base) * math.sin(math.pi * t)


def bridge(builder, start, end, mid):
    (ax, ay, az), (bx, by, bz) = start, end
    length = math.hypot(bx - ax, by - ay)
    dx, dy = (bx - ax) / length, (by - ay) / length
    rx, ry = -dy, dx
    half = layout.BRIDGE_WIDTH * 0.5
    stations = max(int(length / 6.0), 12)
    points = []
    for i in range(stations + 1):
        t = i / stations
        points.append((ax + dx * length * t, ay + dy * length * t, _deck_height(az + 0.25, bz + 0.25, mid, t)))

    def section(p, w0, w1, z0, z1):
        x, y, z = p
        # Counter-clockwise seen from ahead: up the right side, across the top, down the left.
        return [(x + rx * w1, y + ry * w1, z + z0), (x + rx * w1, y + ry * w1, z + z1),
                (x + rx * w0, y + ry * w0, z + z1), (x + rx * w0, y + ry * w0, z + z0)]

    builder.loft("Concrete", [section(p, -half, half, -THICKNESS, 0.0) for p in points])
    t, h = PARAPET
    builder.loft("Concrete", [section(p, half - t, half, 0.0, h) for p in points])
    builder.loft("Concrete", [section(p, -half, -half + t, 0.0, h) for p in points])
    deck = builder.buf("Deck")
    left = [deck.vert((x - rx * (half - t), y - ry * (half - t), z + 0.02)) for x, y, z in points]
    right = [deck.vert((x + rx * (half - t), y + ry * (half - t), z + 0.02)) for x, y, z in points]
    for i in range(stations):
        deck.quad(left[i], left[i + 1], right[i + 1], right[i])

    # Piers wherever the deck crosses water.
    s = PIER_SPACING * 0.5
    while s < length - 10.0:
        x, y = ax + dx * s, ay + dy * s
        ground = shape.height(x, y)
        if ground < -0.3:
            z = _deck_height(az + 0.25, bz + 0.25, mid, s / length) - THICKNESS
            hl, hw = 0.9, half - 1.5
            poly = [(x + dx * sx * hl + rx * sy * hw, y + dy * sx * hl + ry * sy * hw)
                    for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            # Ordered round the rectangle; flip if it came out clockwise.
            area = sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(poly, poly[1:] + poly[:1]))
            builder.prism("Concrete", poly if area > 0 else poly[::-1], ground - 1.0, z, top=False)
        s += PIER_SPACING


def build(plan, materials):
    part = Part("SM_Bridges")
    part.slot("Concrete")
    part.slot("Deck")
    b = Builder()
    for start, end, mid in plan.bridges:
        bridge(b, start, end, mid)
    b.into(part)
    log(f"{len(plan.bridges)} bridges")
    return bake(part, FOLDER, materials, collision=True, nanite=True, smooth_angle=40.0)
