"""Sandstone rock formations: tall pointed fins, flat-topped buttes and wide mesas.

Each shape is baked once at a nominal size and scaled per placement. A shape is a lathe-like stack of rings
following a height/radius profile, stretched into an oval, leaning, and broken up with noise: low-frequency
lumps for an irregular silhouette, vertical gullies, and shallow ledges at the strata. The layer colours come
from the world-space rock material, so every formation shares the same strata heights.

These are stand-ins: swapping a shape for a Fab/Megascans cliff only changes which mesh a placement uses.
"""
import math
import random

from ship.geo import Part

from . import layout, terrain
from .geo import Buffers, bake
from .noise import Perlin, smoothstep
from .util import M, ROOT, log

FOLDER = f"{ROOT}/Rocks"

NOMINAL_H = 500.0  # m: the height a profile's 1.0 maps to
NOMINAL_R = 200.0  # m: the base radius a profile's 1.0 maps to
RINGS = 170
SEGMENTS = 128

# profile: (height fraction, radius fraction) from the base up; the last point closes the top.
# aspect stretches the cross-section along local X, lean pushes the top along +X (fraction of height),
# wobble lets the centre line wander with height (fraction of the base radius), so spires curve and kink;
# lumps / gullies / ledges are displacement strengths relative to the local radius.
SHAPES = {
    "Fin": dict(seed=3, aspect=1.7, lean=0.06, wobble=0.12, lumps=0.42, gullies=0.18, ledges=0.06,
                profile=[(0.0, 1.0), (0.04, 0.68), (0.15, 0.50), (0.45, 0.34), (0.75, 0.17), (0.93, 0.05),
                         (1.0, 0.0)]),
    "FinHook": dict(seed=9, aspect=1.4, lean=0.14, wobble=0.15, lumps=0.45, gullies=0.20, ledges=0.06,
                    profile=[(0.0, 1.0), (0.05, 0.66), (0.20, 0.46), (0.55, 0.30), (0.82, 0.14), (0.95, 0.04),
                             (1.0, 0.0)]),
    "Butte": dict(seed=17, aspect=1.3, lean=0.0, wobble=0.05, lumps=0.38, gullies=0.16, ledges=0.05,
                  profile=[(0.0, 1.0), (0.10, 0.74), (0.70, 0.62), (0.80, 0.52), (0.83, 0.25), (0.84, 0.0)]),
    "Mesa": dict(seed=29, aspect=2.2, lean=0.0, wobble=0.03, lumps=0.30, gullies=0.12, ledges=0.05,
                 profile=[(0.0, 1.0), (0.18, 0.84), (0.86, 0.76), (0.91, 0.68), (0.93, 0.30), (0.94, 0.0)]),
}
BAND_M = 14.0  # ledge spacing at nominal size


def _rings(profile):
    """(radius m, height m) samples evenly spaced along the profile's length, so flat caps get rings too."""
    pts = [(r * NOMINAL_R, h * NOMINAL_H) for h, r in profile]
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    total = sum(seg)
    out, i, acc = [], 0, 0.0
    for k in range(RINGS + 1):
        d = total * k / RINGS
        while i < len(seg) - 1 and acc + seg[i] < d:
            acc += seg[i]
            i += 1
        t = min((d - acc) / seg[i], 1.0) if seg[i] else 0.0
        (r0, z0), (r1, z1) = pts[i], pts[i + 1]
        out.append((r0 + (r1 - r0) * t, z0 + (z1 - z0) * t))
    return out


def shape_part(name, spec):
    noise = Perlin(spec["seed"])
    top = spec["profile"][-1][0] * NOMINAL_H
    buf = Buffers()
    ring_ids = []
    for r, z in _rings(spec["profile"])[:-1]:
        cx = spec["lean"] * NOMINAL_H * (z / top) ** 2 + spec["wobble"] * NOMINAL_R * noise.fbm2(z / 140.0, 0.5, 2)
        cy = spec["wobble"] * NOMINAL_R * noise.fbm2(z / 140.0, 7.5, 2)
        ids = []
        for j in range(SEGMENTS):
            a = math.tau * j / SEGMENTS
            ux, uy = math.cos(a), math.sin(a)
            lump = noise.fbm3(ux * 1.2, uy * 1.2, z / 110.0, 4)
            gully = abs(noise.noise3(ux * 7.0, uy * 7.0, z / 220.0 + 3.7)) + 0.5 * abs(
                noise.noise3(ux * 16.0, uy * 16.0, z / 90.0 + 1.3))
            ledge = smoothstep(0.78, 1.0, (z / BAND_M + 0.6 * lump) % 1.0)
            k = max(1.0 + spec["lumps"] * lump - spec["gullies"] * gully - spec["ledges"] * ledge, 0.25)
            ids.append(buf.vert(((cx + ux * r * k * spec["aspect"]) * M, (cy + uy * r * k) * M, z * M)))
        ring_ids.append(ids)
    tip_cx = spec["lean"] * NOMINAL_H + spec["wobble"] * NOMINAL_R * noise.fbm2(top / 140.0, 0.5, 2)
    tip_cy = spec["wobble"] * NOMINAL_R * noise.fbm2(top / 140.0, 7.5, 2)
    tip = buf.vert((tip_cx * M, tip_cy * M, top * M))
    base = buf.vert((0.0, 0.0, 0.0))
    n = SEGMENTS
    for lo, hi in zip(ring_ids, ring_ids[1:]):
        for j in range(n):
            buf.quad(lo[j], lo[(j + 1) % n], hi[(j + 1) % n], hi[j])
    for j in range(n):
        buf.tri(ring_ids[-1][j], ring_ids[-1][(j + 1) % n], tip)
        buf.tri(base, ring_ids[0][(j + 1) % n], ring_ids[0][j])
    part = Part(f"SM_Rock_{name}")
    buf.add_to(part, "Rock")
    return part


def build(materials):
    """Bakes every shape; returns {shape name: static mesh}."""
    meshes = {}
    for name, spec in SHAPES.items():
        meshes[name] = bake(shape_part(name, spec), FOLDER, materials, collision=True, nanite=True,
                            smooth_angle=50.0)
    return meshes


def top_fraction(shape):
    return SHAPES[shape]["profile"][-1][0]


def placements():
    """(shape, location cm, yaw, scale) for every formation and boulder."""
    out = []

    def place(shape, x, y, h, radius, yaw):
        sxy = radius / NOMINAL_R
        sz = h / (top_fraction(shape) * NOMINAL_H)
        # Sink the base so the flared foot meets the ground on its lowest side.
        z = terrain.lowest_under(x, y, radius * 0.8) - 0.04 * h
        out.append((shape, (x * M, y * M, z * M), yaw, (sxy, sxy, sz)))

    for shape, x, y, h, radius, yaw in layout.ROCKS:
        place(shape, x, y, h, radius, yaw)

    rng = random.Random(layout.BOULDER_SEED)
    (x0, x1), (y0, y1) = layout.BOULDER_AREA
    cam_x, cam_y, _ = layout.CAMERA
    placed = 0
    while placed < layout.BOULDER_COUNT:
        x, y = rng.uniform(x0, x1), rng.uniform(y0, y1)
        if terrain.pad_distance(x, y) < 1.4 or math.hypot(x - cam_x, y - cam_y) < 120.0:
            continue
        h = rng.uniform(2.0, 9.0) * (1.0 + 2.0 * smoothstep(800.0, 1500.0, x))
        place("Butte", x, y, h, h * rng.uniform(0.9, 1.8), rng.uniform(0, 360))
        placed += 1
    log(f"{len(out)} rock placements")
    return out
