"""The basin the colony sits in: the ridge the camera stands on, dune fields, a flattened pad for the colony,
and ground rising toward the spires.

height() is a pure function of position, so rocks, boulders and the player start can all be set on the ground.
"""
import math

from ship.geo import Part

from . import layout
from .geo import bake, graded, heightfield
from .noise import Perlin, smoothstep
from .util import M, ROOT, log

FOLDER = f"{ROOT}/Terrain"

# Metres. Vertices are 6 m apart over the core (camera ridge to the tower bases) and spread out beyond it.
EXTENT_X = (-1500.0, 7600.0)
EXTENT_Y = (-5200.0, 5200.0)
CORE_X = (-700.0, 650.0)
CORE_Y = (-520.0, 620.0)
STEP = 6.0
GROWTH = 1.035

_BASIN = Perlin(11)
_DUNES = Perlin(23)


def _bump(x, y, cx, cy, rx, ry):
    dx, dy = (x - cx) / rx, (y - cy) / ry
    return math.exp(-(dx * dx + dy * dy))


def pad_distance(x, y):
    """1 on the edge of the colony pad, less inside it."""
    return math.hypot((x - layout.PAD_CENTRE[0]) / layout.PAD_RADII[0],
                      (y - layout.PAD_CENTRE[1]) / layout.PAD_RADII[1])


def height(x, y):
    """Ground height in metres at (x, y) in metres."""
    h = 6.0 * _BASIN.fbm2(x / 900.0, y / 900.0, 3)
    # Dune crests running across the wind, meandering, sharper on top than in the troughs.
    warp = 40.0 * _DUNES.fbm2(x / 300.0, y / 300.0, 2)
    crest = 1.0 - abs(math.sin(math.pi * (x * 0.8 + y * 0.6 + warp) / 70.0))
    h += 3.5 * crest ** 3 * (0.6 + 0.4 * _DUNES.noise2(x / 500.0, y / 500.0))
    # The ridge the camera stands on, and the dark mound in front of it on the left.
    h += 44.0 * _bump(x, y, -640.0, -40.0, 230.0, 330.0)
    h += 26.0 * _bump(x, y, -430.0, -170.0, 110.0, 120.0)
    # Rougher ground rising toward the spires and the far ranges.
    rise = smoothstep(700.0, 4500.0, x)
    if rise > 0.0:
        h += rise * (70.0 + 40.0 * _BASIN.fbm2(x / 600.0, y / 600.0, 4))
    return h * smoothstep(1.0, layout.PAD_BLEND, pad_distance(x, y))


def lowest_under(x, y, radius, samples=8):
    """Lowest ground height (m) under a circular footprint, so whatever stands there doesn't float on a slope."""
    pts = [(x, y)] + [(x + radius * math.cos(a), y + radius * math.sin(a))
                      for a in (i * math.tau / samples for i in range(samples))]
    return min(height(px, py) for px, py in pts)


def build(materials):
    xs = [x * M for x in graded(*EXTENT_X, *CORE_X, STEP, GROWTH)]
    ys = [y * M for y in graded(*EXTENT_Y, *CORE_Y, STEP, GROWTH)]
    log(f"terrain grid {len(xs)} x {len(ys)}")
    part = Part("SM_Terrain")
    heightfield(xs, ys, lambda x, y: height(x / M, y / M) * M).add_to(part, "Sand")
    return bake(part, FOLDER, materials, collision=True, nanite=True, smooth_angle=60.0)
