"""The ground: one heightfield over the islands, the seabed round them and the mainland hills across the bay.

Vertices are 8 m apart over the town and spread out toward the horizon. Each carries its land use in UV channel 1
(urban share, forest share) for the ground material.
"""
from colony.geo import bake, graded
from ship.geo import Part

from . import shape
from .geo import LandBuffers
from .util import M, ROOT, log

FOLDER = f"{ROOT}/Terrain"

# Metres.
EXTENT_X = (-9000.0, 12000.0)
EXTENT_Y = (-11000.0, 11000.0)
CORE_X = (-2350.0, 2400.0)
CORE_Y = (-3150.0, 3450.0)
STEP = 8.0
GROWTH = 1.035


def build(materials):
    xs = graded(*EXTENT_X, *CORE_X, STEP, GROWTH)
    ys = graded(*EXTENT_Y, *CORE_Y, STEP, GROWTH)
    log(f"terrain grid {len(xs)} x {len(ys)}")
    buf = LandBuffers()
    for x in xs:
        for y in ys:
            h, urban, _, forest = shape.sample(x, y)
            buf.vert((x * M, y * M, h * M))
            buf.uv1.append((urban, forest))
    ny = len(ys)
    for i in range(len(xs) - 1):
        for j in range(ny - 1):
            a, b = i * ny + j, (i + 1) * ny + j
            buf.quad(a, b, b + 1, a + 1)
    part = Part("SM_TownTerrain")
    buf.add_to(part, "Ground")
    return bake(part, FOLDER, materials, collision=True, nanite=True, smooth_angle=70.0)
