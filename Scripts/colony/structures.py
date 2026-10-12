"""Colony buildings: geodesic domes, the round terminal, the towers, and the low-rise blocks and tubes between them.

Built in metres and converted to cm. Domes are baked once at a nominal size and scaled per placement; towers
are baked one per placement since their caps shouldn't stretch; the blocks are baked in place as one mesh.
"""
import math
import random

import unreal

from ship.geo import Part, box_xf, frame

from . import layout, terrain
from .geo import Buffers, bake, frustum, geodesic_hemisphere, strut
from .util import M, ROOT, log

FOLDER = f"{ROOT}/Structures"

DOME_DIAMETER = 100.0   # m, the size SM_Dome is baked at
DOME_FREQUENCY = 14     # panel rows from the rim to the apex
STRUT = (0.35, 0.6)     # m, width and depth of the frame members; about a pixel wide from the hero camera
PLINTH_H = 3.0          # m, the ring wall the glass sits on

# Tower sections, stacked from the ground: (radius at bottom, radius at top, height from, height to, slot),
# radii as a fraction of the tower's radius and heights as a fraction of its height.
TOWER_STYLES = {
    "spire": [(1.5, 1.5, 0.0, 0.03, "Concrete"), (1.0, 1.0, 0.03, 0.56, "TowerMetal"),
              (1.1, 1.1, 0.56, 0.575, "TowerDark"), (0.95, 0.95, 0.575, 0.80, "TowerMetal"),
              (1.02, 1.02, 0.80, 0.81, "TowerDark"), (0.86, 0.86, 0.81, 0.88, "TowerDark"),
              (0.88, 0.5, 0.88, 0.93, "TowerMetal"), (0.5, 0.15, 0.93, 0.96, "TowerDark"),
              (0.06, 0.04, 0.96, 1.0, "TowerMetal")],
    "capped": [(1.4, 1.4, 0.0, 0.04, "Concrete"), (1.0, 1.0, 0.04, 0.80, "TowerMetal"),
               (1.06, 1.06, 0.80, 0.82, "TowerDark"), (0.97, 0.97, 0.82, 0.90, "TowerDark"),
               (1.0, 0.92, 0.90, 0.93, "TowerDark"), (0.92, 0.70, 0.93, 0.96, "TowerDark"),
               (0.70, 0.35, 0.96, 0.985, "TowerDark"), (0.35, 0.02, 0.985, 1.0, "TowerDark")],
    "stepped": [(1.6, 1.6, 0.0, 0.04, "Concrete"), (1.25, 1.25, 0.04, 0.32, "TowerMetal"),
                (1.3, 1.3, 0.32, 0.335, "TowerDark"), (1.0, 1.0, 0.335, 0.62, "TowerMetal"),
                (1.05, 1.05, 0.62, 0.635, "TowerDark"), (0.78, 0.78, 0.635, 0.86, "TowerMetal"),
                (0.8, 0.8, 0.86, 0.875, "TowerDark"), (0.55, 0.55, 0.875, 0.94, "TowerDark"),
                (0.55, 0.1, 0.94, 0.97, "TowerMetal"), (0.05, 0.03, 0.97, 1.0, "TowerMetal")],
}
TOWER_RIBS = 10         # dark vertical ribs round every long metal section
RIB_MIN_LENGTH = 30.0   # m


def _box(part, slot, centre, x_axis, size, bevel=0.3):
    """Box in metres, its local X along x_axis (horizontal), sized (along, across, up)."""
    xf = frame(tuple(c * M for c in centre), x_axis, (-x_axis[1], x_axis[0], 0.0))
    box_xf(part, slot, xf, size[0] * M, size[1] * M, size[2] * M, bevel * M)


def _block(part, x, y, z, yaw, depth, width, height):
    """Low building with a lit window band and a rooftop plant box."""
    ax = (math.cos(yaw), math.sin(yaw), 0.0)
    _box(part, "Hull", (x, y, z + height * 0.5), ax, (depth, width, height))
    _box(part, "WindowWarm", (x, y, z + height * 0.55), ax, (depth + 0.2, width + 0.2, min(1.0, height * 0.15)), 0.05)
    _box(part, "TowerDark", (x, y, z + height + 0.6), ax, (depth * 0.4, width * 0.3, 1.2))


def dome():
    part = Part("SM_Dome")
    rad = DOME_DIAMETER * 0.5
    # Platform and plinth, with a lit window band round the plinth.
    frustum(part, "Concrete", rad * 1.18 * M, rad * 1.16 * M, 0.0, 1.0 * M, steps=128)
    frustum(part, "Concrete", rad * 1.03 * M, rad * 1.03 * M, 1.0 * M, PLINTH_H * M, steps=128)
    frustum(part, "WindowWarm", rad * 1.035 * M, rad * 1.035 * M, 1.5 * M, 2.4 * M, steps=128)
    # Glass shell with the frame just outside it, both built centred on the origin and lifted onto the plinth.
    lift = unreal.Transform(location=unreal.Vector(0.0, 0.0, PLINTH_H * M))
    verts, tris, edges = geodesic_hemisphere(rad * M, DOME_FREQUENCY)
    glass = Buffers()
    glass.verts = [tuple(c * 0.995 for c in p) for p in verts]
    for t in tris:
        glass.tri(*t)
    glass.add_to(part, "DomeGlass", lift)
    beams = Buffers()
    for a, b in edges:
        strut(beams, verts[a], verts[b], STRUT[0] * M, STRUT[1] * M)
    beams.add_to(part, "Frame", lift)
    # Interior: a ring of low buildings round a central hall, their windows glowing through the glass.
    rng = random.Random(5)
    for i in range(9):
        a = math.tau * i / 9 + rng.uniform(-0.12, 0.12)
        rr = rad * rng.uniform(0.45, 0.62)
        _block(part, rr * math.cos(a), rr * math.sin(a), PLINTH_H, a,
               rng.uniform(6, 9), rng.uniform(10, 16), rng.uniform(5, 11))
    hall = rad * 0.22
    frustum(part, "Hull", hall * M, hall * 0.85 * M, PLINTH_H * M, (PLINTH_H + 16) * M)
    for z in (5.0, 10.0):
        frustum(part, "WindowWarm", hall * 0.97 * M, hall * 0.92 * M, (PLINTH_H + z) * M, (PLINTH_H + z + 1.2) * M)
    frustum(part, "TowerDark", hall * 0.85 * M, hall * 0.3 * M, (PLINTH_H + 16) * M, (PLINTH_H + 20) * M)
    return part


def terminal():
    r = layout.TERMINAL[2] * 0.5
    part = Part("SM_Terminal")
    frustum(part, "Concrete", r * 1.25 * M, r * 1.22 * M, 0.0, 0.8 * M, steps=128)
    frustum(part, "Hull", r * M, r * M, 0.8 * M, 4.0 * M, steps=128)
    frustum(part, "WindowWarm", r * 1.005 * M, r * 1.005 * M, 4.0 * M, 5.6 * M, steps=128)
    frustum(part, "TowerMetal", r * 1.02 * M, r * 0.62 * M, 5.6 * M, 9.0 * M, steps=128)
    frustum(part, "TowerDark", r * 0.62 * M, r * 0.40 * M, 9.0 * M, 11.0 * M, steps=96)
    frustum(part, "Frame", r * 0.40 * M, r * 0.36 * M, 11.0 * M, 11.6 * M, steps=96)
    for i in range(24):
        a = math.tau * i / 24
        _box(part, "WindowWarm", (r * 1.2 * math.cos(a), r * 1.2 * math.sin(a), 1.0),
             (math.cos(a), math.sin(a), 0.0), (0.6, 2.0, 0.4), 0.05)
    return part


def tower(index, height, radius, style):
    part = Part(f"SM_Tower_{index}")
    for r0, r1, z0, z1, slot in TOWER_STYLES[style]:
        frustum(part, slot, r0 * radius * M, r1 * radius * M, z0 * height * M, z1 * height * M)
        length = (z1 - z0) * height
        if slot == "TowerMetal" and r0 == r1 and length > RIB_MIN_LENGTH:
            for k in range(TOWER_RIBS):
                a = math.tau * (k + 0.5) / TOWER_RIBS
                rr = r0 * radius + 0.15
                _box(part, "TowerDark", (rr * math.cos(a), rr * math.sin(a), (z0 + z1) * 0.5 * height),
                     (math.cos(a), math.sin(a), 0.0), (0.5, 0.9, length), 0.1)
    return part


def blocks():
    """Low-rise buildings round the domes and towers, and the tubes linking the domes, baked in world space."""
    part = Part("SM_ColonyBlocks")
    rng = random.Random(41)
    domes = layout.DOMES
    tx, ty, tdia = layout.TERMINAL
    taken = [(x, y, d * 0.5 * 1.2) for x, y, d in domes.values()] + [(tx, ty, tdia * 0.65)]
    taken += [(x, y, r * 1.6) for x, y, _, r, _ in layout.TOWERS]

    def free(x, y, size):
        return terrain.pad_distance(x, y) < 0.95 and all(math.hypot(x - ox, y - oy) > orad + size
                                                         for ox, oy, orad in taken)

    def scatter(cx, cy, r_min, r_max, count, sizes):
        for _ in range(count):
            a, rr = rng.uniform(0.0, math.tau), rng.uniform(r_min, r_max)
            x, y = cx + rr * math.cos(a), cy + rr * math.sin(a)
            depth, width, height = (rng.uniform(*s) for s in sizes)
            if free(x, y, max(depth, width) * 0.5):
                _block(part, x, y, 0.0, a, depth, width, height)
                taken.append((x, y, max(depth, width) * 0.55))

    for x, y, d in domes.values():
        scatter(x, y, d * 0.65, d * 0.95, 16, ((7, 12), (12, 28), (4, 9)))
    for x, y, _, r, _ in layout.TOWERS:
        scatter(x, y, r * 1.9, r * 3.2, 6, ((8, 14), (10, 22), (6, 14)))
    scatter(70.0, 70.0, 0.0, 420.0, 40, ((4, 7), (5, 9), (3, 5)))

    # Tubes from rim to rim.
    hubs = {name: (x, y, d * 0.5 * 1.16) for name, (x, y, d) in domes.items()}
    hubs["Terminal"] = (tx, ty, tdia * 0.5 * 1.2)
    for a, b in (("West", "East"), ("West", "North"), ("East", "North"), ("Terminal", "East"), ("Terminal", "West")):
        (ax, ay, ar), (bx, by, br) = hubs[a], hubs[b]
        length = math.hypot(bx - ax, by - ay)
        ux, uy = (bx - ax) / length, (by - ay) / length
        span = length - ar - br
        mid = (ax + ux * (ar + span * 0.5), ay + uy * (ar + span * 0.5), 2.5)
        _box(part, "Hull", mid, (ux, uy, 0.0), (span + 1.0, 5.0, 5.0), 2.2)
    log(f"colony blocks: {len(taken)} footprints")
    return part


def build(materials):
    """Bakes the kit; returns {"dome": mesh, "terminal": mesh, "towers": [mesh], "blocks": mesh}."""
    kit = {
        "dome": bake(dome(), FOLDER, materials),
        "terminal": bake(terminal(), FOLDER, materials),
        "towers": [bake(tower(i, h, r, style), FOLDER, materials)
                   for i, (_, _, h, r, style) in enumerate(layout.TOWERS)],
        "blocks": bake(blocks(), FOLDER, materials),
    }
    return kit
