"""Swappable fixtures, authored in hardpoint space: +X out of the surface, +Y along the corridor, +Z up the
surface, origin at the centre of the recess opening. The recess floor is at X = -RECESS.
"""
import math

from . import geo
from .geo import Part, box, cylinder, torus
from .profile import EXTENTS, RECESS


class Fixture:
    def __init__(self, key, display, description, category, slots, part, lights=()):
        self.key = key
        self.display = display
        self.description = description
        self.category = category
        self.slots = slots
        self.part = part
        self.lights = lights  # (name, location, direction, width, height, intensity) in fixture space


def _half(slot, margin=2.0):
    w, h = EXTENTS[slot]
    return w * .5 - margin, h * .5 - margin


def rod_rack():
    p = Part("SM_Fx_RodRack")
    hy, hz = _half("Chamfer")
    box(p, "Panel", -RECESS, -7, -hy, hy, -hz, hz, bevel=1.0)
    box(p, "Structure", -7, -6.4, -hy + 12, hy - 12, -hz + 5, hz - 5, bevel=0.5)
    for y in (-hy + 8, hy - 8):
        box(p, "Metal", -RECESS, 3, y - 5, y + 5, -31, 31, bevel=1.5)
    for z in (-19.0, 0.0, 19.0):
        cylinder(p, "Chrome", (-1.5, 0, z), "y", 4.2, 2 * hy - 18, 40)
        for y in (-hy + 18, hy - 18):
            cylinder(p, "Metal", (-1.5, y, z), "y", 5.4, 3.0, 40)
    box(p, "LEDAmber", 3, 3.7, hy - 11, hy - 5, 22, 27, bevel=0.3)
    return Fixture("RodRack", "Conduit Rack", "Chrome coolant conduits on brackets.", "Utility",
                   ["Chamfer"], p)


def vent():
    p = Part("SM_Fx_Vent")
    hy, hz = _half("Chamfer")
    box(p, "Structure", -RECESS, -8, -hy, hy, -hz, hz)
    for y0, y1, z0, z1 in ((-hy, hy, hz - 6, hz), (-hy, hy, -hz, -hz + 6),
                           (-hy, -hy + 6, -hz + 6, hz - 6), (hy - 6, hy, -hz + 6, hz - 6)):
        box(p, "Hull", -RECESS, -1, y0, y1, z0, z1, bevel=1.2)
    a = math.radians(35)
    count = 10
    for i in range(count):
        z = -hz + 6 + (i + .5) * (2 * hz - 12) / count
        xf = geo.frame((-5.0, 0.0, z), (math.cos(a), 0, -math.sin(a)), (0, 1, 0))
        geo.box_xf(p, "Metal", xf, 1.2, 2 * hy - 12, 7.5, 0.4)
    box(p, "Metal", -6, -2, -1.5, 1.5, -hz + 6, hz - 6, bevel=0.4)
    return Fixture("Vent", "Air Return", "Louvred air return grille.", "Utility", ["Chamfer"], p)


def console():
    p = Part("SM_Fx_Console")
    hy, hz = _half("Wall")
    box(p, "Panel", -RECESS, -8, -hy, hy, -hz, hz)
    # Screen unit
    box(p, "Hull", -RECESS, 4, -92, -10, -38, 40, bevel=2.0)
    box(p, "Structure", 4, 4.6, -86, -16, -30, 34, bevel=0.4)
    box(p, "Screen", 4.6, 4.9, -84, -18, -28, 32)
    # Control unit with a key grid
    box(p, "Hull", -RECESS, 5, -2, 92, -42, 0, bevel=2.0)
    lit = {(2, 0): "LEDAmber", (2, 1): "LEDAmber", (0, 5): "LEDAmber", (1, 3): "LED"}
    for row in range(3):
        for col in range(6):
            y, z = 5 + col * 14, -36 + row * 11
            box(p, lit.get((row, col), "Metal"), 5, 6.4, y, y + 10, z, z + 7, bevel=0.6)
    # Status lamps and the latch rods
    box(p, "Structure", -8, -5.5, -2, 92, 8, 20, bevel=0.6)
    for i in range(7):
        box(p, "LEDGreen" if i == 5 else "LEDAmber", -5.5, -4.8, 4 + i * 12, 8 + i * 12, 12.5, 15.5, bevel=0.3)
    for y in (16, 84):
        box(p, "Metal", -8, 0.5, y - 3, y + 3, 25, 43, bevel=0.8)
    for z in (30.0, 38.0):
        cylinder(p, "Chrome", (-2.0, 50, z), "y", 1.8, 66, 24)
    return Fixture("Console", "Systems Console", "Status display with a control keypad.", "Console",
                   ["Wall"], p)


def locker():
    p = Part("SM_Fx_Locker")
    hy, hz = _half("Wall")
    box(p, "Structure", -RECESS, -8, -hy, hy, -hz, hz)
    for s in (-1, 1):
        box(p, "Hull", -RECESS, 1, s * 1.0, s * (hy - 1), -hz + 1, hz - 1, bevel=1.5)
        yc = s * 11
        box(p, "Structure", 0.6, 1.3, yc - 3.5, yc + 3.5, -20, 20, bevel=0.5)
        cylinder(p, "Chrome", (3.0, yc, 0), "z", 1.2, 32, 16)
        for z in (-15, 15):
            box(p, "Metal", 0.8, 3.2, yc - 1.5, yc + 1.5, z - 2, z + 2, bevel=0.3)
        box(p, "Panel", 0.8, 1.3, s * 34, s * 76, 26, 34, bevel=0.3)
        box(p, "LEDGreen", 1.0, 1.6, s * 84, s * 90, 36, 39, bevel=0.3)
    return Fixture("Locker", "Storage Locker", "Twin-door wall locker.", "Storage", ["Wall"], p)


def ceiling_fan():
    p = Part("SM_Fx_CeilingFan")
    hy, hz = _half("Ceiling")
    box(p, "Structure", -RECESS, -9, -hy, hy, -hz, hz)
    hull = p.slot("Hull")
    plate = geo.box_mesh(hull, -RECESS, -4, -hy, hy, -hz, hz, bevel=1.5)
    for yc in (-52, 52):
        geo.subtract(plate, geo.cylinder_mesh(hull, (-7, yc, 0), "x", 44, 20, 96))
    p.append(plate)
    for yc in (-52.0, 52.0):
        cylinder(p, "Structure", (-8.6, yc, 0), "x", 44, 1.0, 64)
        for r, minor in ((41.0, 1.6), (29.0, 1.1), (17.0, 1.0)):
            torus(p, "Chrome", (-6.0, yc, 0), "x", r, minor, 64, 10)
        for k in range(8):
            a = k * math.pi / 4
            xf = geo.frame((-6.0, yc + 26 * math.cos(a), 26 * math.sin(a)), (1, 0, 0), (0, math.cos(a), math.sin(a)))
            geo.box_xf(p, "Metal", xf, 1.6, 30, 1.6, 0.3)
        cylinder(p, "Metal", (-6.0, yc, 0), "x", 8, 4, 32)
        for k in range(5):
            a = k * 2 * math.pi / 5
            xf = geo.frame((-8.0, yc + 22 * math.cos(a), 22 * math.sin(a)), (1, 0, 0.0), (0, -math.sin(a), math.cos(a)))
            geo.box_xf(p, "Panel", xf, 0.8, 14, 34, 0.2)
    for y in (-hy + 7, 0.0, hy - 7):
        for z in (-hz + 7, hz - 7):
            cylinder(p, "Metal", (-3.6, y, z), "x", 1.8, 1.2, 16)
    return Fixture("CeilingFan", "Air Handler", "Twin circulation fans behind a service hatch.", "Utility",
                   ["Ceiling"], p)


def ceiling_light():
    p = Part("SM_Fx_CeilingLight")
    hy, hz = _half("Ceiling")
    box(p, "Structure", -RECESS, -8, -hy, hy, -hz, hz)
    box(p, "LEDSoft", -8.5, -4.0, -hy + 9, hy - 9, -hz + 9, hz - 9, bevel=0.8)
    for y0, y1, z0, z1 in ((-hy, hy, hz - 9, hz), (-hy, hy, -hz, -hz + 9),
                           (-hy, -hy + 9, -hz + 9, hz - 9), (hy - 9, hy, -hz + 9, hz - 9)):
        box(p, "Hull", -RECESS, -2, y0, y1, z0, z1, bevel=1.2)
    for y in (-34.0, 34.0):
        box(p, "Hull", -RECESS, -2.5, y - 1.5, y + 1.5, -hz + 9, hz - 9, bevel=0.5)
    return Fixture("CeilingLight", "Light Panel", "Diffused overhead light panel.", "Lighting", ["Ceiling"], p,
                   lights=(("Panel", (-2.0, 0, 0), (1, 0, 0), 2 * hy - 20, 2 * hz - 20, 14.0),))


def floor_hatch():
    p = Part("SM_Fx_FloorHatch")
    hy, hz = _half("Floor", 1.0)
    box(p, "Floor", -RECESS, -0.2, -hy, hy, -hz, hz, bevel=1.2)
    for y0, y1, z0, z1 in ((-hy + 9, hy - 9, hz - 10, hz - 9), (-hy + 9, hy - 9, -hz + 9, -hz + 10),
                           (-hy + 9, -hy + 10, -hz + 10, hz - 10), (hy - 10, hy - 9, -hz + 10, hz - 10)):
        box(p, "Structure", -0.5, 0.0, y0, y1, z0, z1)
    for y in (-40.0, 40.0):
        box(p, "Structure", -0.6, 0.05, y - 12, y + 12, -5, 5, bevel=0.6)
        box(p, "Metal", -0.4, 0.3, y - 10, y + 10, -0.8, 0.8, bevel=0.2)
    for y in (-hy + 5, hy - 5):
        for z in (-hz + 5, 0.0, hz - 5):
            cylinder(p, "Metal", (-0.1, y, z), "x", 1.6, 0.8, 12)
    return Fixture("FloorHatch", "Service Hatch", "Floor access hatch with recessed lifting handles.",
                   "Floor", ["Floor"], p)


def floor_grate():
    p = Part("SM_Fx_FloorGrate")
    hy, hz = _half("Floor", 1.0)
    box(p, "Structure", -RECESS, -9, -hy, hy, -hz, hz)
    box(p, "LED", -9.4, -8.6, -hy + 12, hy - 12, -2.0, 2.0)
    for y0, y1, z0, z1 in ((-hy, hy, hz - 5, hz), (-hy, hy, -hz, -hz + 5),
                           (-hy, -hy + 5, -hz + 5, hz - 5), (hy - 5, hy, -hz + 5, hz - 5)):
        box(p, "Metal", -6, -0.1, y0, y1, z0, z1, bevel=0.6)
    bars = 15
    for i in range(bars):
        z = -hz + 8 + i * (2 * hz - 16) / (bars - 1)
        box(p, "Metal", -4.5, -0.1, -hy + 5, hy - 5, z - 0.9, z + 0.9, bevel=0.3)
    for y in (-34.0, 0.0, 34.0):
        box(p, "Metal", -5.5, -1.5, y - 1, y + 1, -hz + 5, hz - 5)
    return Fixture("FloorGrate", "Floor Grating", "Open grating over a lit service trench.", "Floor",
                   ["Floor"], p)


ALL = (rod_rack, vent, console, locker, ceiling_fan, ceiling_light, floor_hatch, floor_grate)
