"""The arriving ship's outer hull: a white shell round the kit's modules, with engine nacelles, fins and landing
skids, cut through for the porthole at the bow and the hatchway at the stern.

Built for the layout ship.level lays out (entry, three corridors, observation end along +X): the kit's modules are
interiors, and this is what's seen of the ship from outside. A different layout needs a different hull.

Metres in the ship's own space (X forward, Z up, origin on the entry module's deck), except where the ship kit's
helpers work in cm.
"""
import math

from colony.geo import bake
from ship import geo as ship_geo
from ship import modules as ship_modules
from ship.geo import Part
from town.geo import Builder, limb, sphere
from .util import EAL, ROOT, log

FOLDER = f"{ROOT}/Meshes"
SLOTS = ("Hull", "Trim", "Structure", "Metal", "LED", "LEDAmber")
SHIP_MATERIALS = "/Game/Ship/Materials"

BELLY = -0.55
GEAR = 0.80                      # skid feet below the deck: UShipFlightComponent::GearHeight
STERN, BOW = -3.30, 25.55
WALL = 0.10                      # shell thickness
# (x, half width, top): stern to bow
STATIONS = [(STERN, 3.00, 4.30), (-2.55, 3.45, 4.78), (23.90, 3.50, 4.86), (24.90, 3.45, 4.92), (25.25, 3.38, 4.84),
            (BOW, 3.18, 4.62)]
WINDOW_Z = ship_modules.WINDOW_Z / 100.0
WINDOW_HOLE = (ship_modules.WINDOW_R + 12.0) / 100.0
NACELLE_Y, NACELLE_Z = 4.65, 1.90
NACELLE = [(-5.60, 0.62), (-5.45, 0.80), (-4.70, 0.88), (4.00, 0.88), (6.30, 0.62), (7.10, 0.28)]
SKID_Y = 2.30


def _ring(x, w, t, b=BELLY):
    """Hull cross-section at x: flat belly, full flanks, a rounded back. Counter-clockwise seen from the bow."""
    right = [(0.72 * w, b), (w, b + 1.05), (w, 0.52 * t), (0.88 * w, 0.83 * t), (0.55 * w, 0.995 * t)]
    return ([(x, 0.0, b)] + [(x, y, z) for y, z in right] + [(x, 0.0, t + 0.08)]
            + [(x, -y, z) for y, z in reversed(right)])


def _lerp_station(x):
    for (x0, w0, t0), (x1, w1, t1) in zip(STATIONS, STATIONS[1:]):
        if x0 <= x <= x1:
            k = (x - x0) / (x1 - x0)
            return w0 + (w1 - w0) * k, t0 + (t1 - t0) * k
    return STATIONS[-1][1:]


def _solid(sections, slot="Hull"):
    """A closed loft as a mesh of its own (slots numbered as in the finished hull), for booleans."""
    part = Part("tmp")
    for s in SLOTS:
        part.slot(s)
    b = Builder()
    b.loft(slot, sections)
    b.into(part)
    return part.mesh


def shell():
    """The hull as a thin shell with solid end walls, the hatchway and porthole cut through."""
    trim = SLOTS.index("Trim")
    outer = _solid([_ring(x, w, t) for x, w, t in STATIONS])
    inner = _solid([_ring(min(max(x, STERN + WALL), BOW - WALL), w - WALL, t - WALL, BELLY + WALL) for x, w, t in STATIONS])
    ship_geo.subtract(outer, inner)
    # Solid at the stern round the hatchway, and at the bow round the porthole, so both read as deep openings.
    stern = _solid([_ring(STERN, *_lerp_station(STERN)), _ring(-3.00, *_lerp_station(STERN))])
    bow = _solid([_ring(25.22, *_lerp_station(25.22)), _ring(BOW, *_lerp_station(BOW))])
    hatchway = ship_geo.extrude_x_mesh(trim, ship_geo.outward_offset(ship_modules.HATCH, 3.0, (0.0, 116.0), closed=True),
                                       STERN * 100 - 20, -285.0)
    porthole = ship_geo.cylinder_mesh(trim, (BOW * 100 - 15, 0.0, WINDOW_Z * 100), "x", WINDOW_HOLE * 100, 120.0, 128)
    for mesh in (outer, stern):
        ship_geo.subtract(mesh, hatchway)
    for mesh in (outer, bow):
        ship_geo.subtract(mesh, porthole)
    return outer, stern, bow


def nacelle(b, part, side):
    y = side * NACELLE_Y
    sections = []
    for x, r in NACELLE:
        sections.append([(x, y + r * math.cos(a), NACELLE_Z + r * math.sin(a)) for a in (k * math.tau / 20 for k in range(20))])
    b.loft("Hull", sections)
    # Pylon to the hull, and a fin on top.
    b.box("Trim", -3.0, 3.0, *sorted((side * 3.30, side * 4.00)), 1.65, 2.15)
    b.ribbon("Hull", [(-1.6, y, NACELLE_Z + 0.8), (-4.3, y, NACELLE_Z + 2.3)], [(-5.2, y, NACELLE_Z + 0.8), (-5.6, y, NACELLE_Z + 2.3)])
    # Exhaust glow, its ring, and a nav light on the nose.
    limb(part, "LED", (-5.66, y, NACELLE_Z), (-5.60, y, NACELLE_Z), 0.55, 0.55, steps=24)
    ship_geo.torus(part, "Metal", (-558.0, y * 100, NACELLE_Z * 100), "x", 64.0, 6.0, 40, 8)
    sphere(part, "LEDAmber", (7.15, y, NACELLE_Z), 0.12, steps=10)


def build():
    part = Part("SM_ArrivalShipHull")
    for s in SLOTS:
        part.slot(s)
    for mesh in shell():
        part.append(mesh)
    b = Builder()
    for side in (-1.0, 1.0):
        nacelle(b, part, side)
        y = side * SKID_Y
        b.box("Metal", -1.6, 23.8, y - 0.11, y + 0.11, -GEAR, -GEAR + 0.12)
        for x in (-0.6, 7.6, 15.6, 22.6):
            b.box("Trim", x - 0.08, x + 0.08, y - 0.08, y + 0.08, -GEAR + 0.1, BELLY + 0.1)
    b.into(part)
    # Seams round the hull where the modules meet: thin rings standing just proud of the skin (hollow, or they'd
    # wall off the corridor inside).
    for x in (2.97, 8.97, 14.97, 20.97):
        w, t = _lerp_station(x)
        seam = _solid([_ring(x, w + 0.012, t + 0.012, BELLY - 0.012), _ring(x + 0.08, w + 0.012, t + 0.012, BELLY - 0.012)],
                      "Trim")
        ship_geo.subtract(seam, _solid([_ring(x - 0.1, w - 0.05, t - 0.05, BELLY + 0.05),
                                        _ring(x + 0.18, w - 0.05, t - 0.05, BELLY + 0.05)]))
        part.append(seam)
    sphere(part, "LEDAmber", (12.0, 0.0, 4.95), 0.14, steps=10)
    materials = {s: EAL.load_asset(f"{SHIP_MATERIALS}/MI_Ship_{s}") for s in SLOTS}
    mesh = bake(part, FOLDER, materials, collision=True, nanite=False, smooth_angle=35.0)
    log("outer hull baked")
    return mesh
