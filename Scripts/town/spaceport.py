"""The spaceport's own meshes: the landing pad, the beacon over it, and the pier where the PWC-01 is moored.

Each is built about its own origin in metres and placed by the level: the pad at its centre, the beacon at its
mast's foot, the pier at its landward end, running south (-X).
"""
import math

from colony.geo import bake, frustum
from ship.geo import Part

from . import layout, shape
from .geo import Builder, limb, sphere
from .util import M, ROOT, log

FOLDER = f"{ROOT}/Spaceport"
BEAM_HEIGHT = 2600.0   # m: tall enough to pick out from well up the descent


def pad():
    """A round concrete pad with a gently sloped skirt, the ship's footprint and a hazard ring marked on it, and
    lights round the rim."""
    part = Part("SM_SpaceportPad")
    for slot in ("Concrete", "Deck", "PadLine", "PadMark", "PadLight"):
        part.slot(slot)
    top, r = layout.PAD_TOP, layout.PAD_RADIUS
    frustum(part, "Concrete", (r + 8.0) * M, r * M, (top - 3.0) * M, (top - 0.04) * M, steps=96)
    frustum(part, "Deck", (r - 0.6) * M, (r - 0.6) * M, (top - 0.3) * M, top * M, steps=96)
    b = Builder()
    # Hazard ring near the rim.
    ring = b.buf("PadMark")
    n = 96
    for k in range(n):
        a0, a1 = math.tau * k / n, math.tau * (k + 1) / n
        pts = [((r - 4.2) * math.cos(a), (r - 4.2) * math.sin(a)) for a in (a0, a1)] + \
              [((r - 3.2) * math.cos(a), (r - 3.2) * math.sin(a)) for a in (a1, a0)]
        ids = [ring.vert((x, y, top + 0.01)) for x, y in pts]
        ring.quad(ids[0], ids[1], ids[2], ids[3])
    # The ship's footprint, centred on the pad, nose north, with chevrons pointing the way in.
    half_l, half_w, line = 17.0, 6.0, 0.45
    for x0, x1, y0, y1 in ((-half_l, half_l, -half_w, -half_w + line), (-half_l, half_l, half_w - line, half_w),
                           (-half_l, -half_l + line, -half_w, half_w), (half_l - line, half_l, -half_w, half_w)):
        b.box("PadLine", x0, x1, y0, y1, top - 0.02, top + 0.015)
    for k in range(3):
        x = half_l + 3.0 + 2.2 * k
        for s in (-1.0, 1.0):
            b.prism("PadLine", [(x, 0.0), (x + 0.6, 0.0), (x - 1.6 + 0.6, s * 2.4), (x - 1.6, s * 2.4)][::int(s)],
                    top - 0.02, top + 0.015)
    # Rim lights.
    for k in range(24):
        a = math.tau * (k + 0.5) / 24
        x, y = (r - 1.2) * math.cos(a), (r - 1.2) * math.sin(a)
        b.box("PadLight", x - 0.25, x + 0.25, y - 0.25, y + 0.25, top - 0.02, top + 0.12)
    b.into(part)
    return part


def beacon():
    """A mast at the pad's edge, its lamp throwing a beam of light up into the sky."""
    part = Part("SM_SpaceportBeacon")
    for slot in ("BeaconMast", "PadLight", "Beam"):
        part.slot(slot)
    limb(part, "BeaconMast", (0.0, 0.0, -1.0), (0.0, 0.0, 16.0), 0.45, 0.3, steps=12)
    sphere(part, "PadLight", (0.0, 0.0, 16.6), 0.9, steps=14)
    b = Builder()
    beam = b.buf("Beam")
    sides, radius = 24, 4.0
    lo = [beam.vert((radius * math.cos(math.tau * k / sides), radius * math.sin(math.tau * k / sides), 17.5))
          for k in range(sides)]
    hi = [beam.vert((radius * 1.6 * math.cos(math.tau * k / sides), radius * 1.6 * math.sin(math.tau * k / sides),
                     BEAM_HEIGHT)) for k in range(sides)]
    for k in range(sides):
        j = (k + 1) % sides
        beam.quad(lo[k], lo[j], hi[j], hi[k])
    b.into(part)
    return part


def pier():
    """Plank deck on piles, a rail along its west side, bollards and a lamp at the end; built running south from
    its landward end."""
    port = shape.spaceport()
    (sx, _), (ex, _) = port["pier_start"], port["pier_end"]
    length = sx - ex
    part = Part("SM_SpaceportPier")
    for slot in ("BoatDeck", "Concrete", "Rail", "PadLight"):
        part.slot(slot)
    deck, half = layout.PIER_DECK, layout.PIER_WIDTH * 0.5
    b = Builder()
    b.box("BoatDeck", -length, 0.5, -half, half, deck - 0.35, deck)
    b.box("Concrete", -length - 0.4, -length, -half - 0.2, half + 0.2, deck - 0.6, deck + 0.05)
    # Rail on the west side; the east side stays open for mooring.
    x = -2.0
    while x > -length:
        b.box("Rail", x - 0.06, x + 0.06, -half + 0.05, -half + 0.17, deck, deck + 1.05)
        x -= 3.0
    b.box("Rail", -length, -1.0, -half + 0.03, -half + 0.19, deck + 1.0, deck + 1.1)
    b.into(part)
    x = -3.0
    while x > -length:
        for s in (-1.0, 1.0):
            limb(part, "Concrete", (x, s * (half - 0.3), -5.0), (x, s * (half - 0.3), deck - 0.3), 0.22, 0.2, steps=8)
        x -= 7.0
    for xb in (-length + 1.5, -length + 9.0, -length + 16.0):
        limb(part, "Rail", (xb, half - 0.45, deck), (xb, half - 0.45, deck + 0.5), 0.16, 0.18, steps=10)
    limb(part, "Rail", (-length + 0.8, -half + 0.4, deck), (-length + 0.8, -half + 0.4, deck + 3.2), 0.08, 0.06, steps=8)
    sphere(part, "PadLight", (-length + 0.8, -half + 0.4, deck + 3.35), 0.22, steps=10)
    return part


def mooring():
    """Where the PWC-01 waits, in metres, and the way it faces: beside the end of the pier, nose out to sea."""
    port = shape.spaceport()
    ex, ey = port["pier_end"]
    return (ex + 4.0, ey + layout.PIER_WIDTH * 0.5 + 2.4, 1.0), 180.0


def landing_point():
    """Where the arriving ship's origin comes to rest (less its gear) so the ship sits centred on the pad, nose north."""
    px, py = shape.spaceport()["pad"]
    return (px - layout.SHIP_MIDDLE, py, layout.PAD_TOP)


def build(materials):
    """Bakes the spaceport meshes; returns {"pad", "beacon", "pier"}: static meshes."""
    meshes = {
        "pad": bake(pad(), FOLDER, materials, collision=True, nanite=True, smooth_angle=30.0),
        "beacon": bake(beacon(), FOLDER, materials, collision=False, nanite=False, smooth_angle=60.0),
        "pier": bake(pier(), FOLDER, materials, collision=True, nanite=True, smooth_angle=30.0),
    }
    log("spaceport meshes ready")
    return meshes
