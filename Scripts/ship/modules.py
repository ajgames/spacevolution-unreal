"""Structural modules. Each returns a Spec: the meshes to bake and the Blueprint components to create."""
import math

import unreal

from . import audio, geo
from .geo import Part, box, cylinder, torus
from .profile import (CEILING_Z, HALF_CELL, OCTAGON, PANEL, RIB, SKIN, Spec, bay, half_width_at, plain_section,
                      rib, structure, threshold)


class Module:
    def __init__(self, key, display, description, category, connectors, spec):
        self.key = key
        self.display = display
        self.description = description
        self.category = category
        self.connectors = connectors  # (face, type) on the origin cell
        self.spec = spec


def _at(x, yaw=0.0):
    return unreal.Transform(location=unreal.Vector(x, 0, 0), rotation=unreal.Rotator(roll=0.0, pitch=0.0, yaw=yaw))


def ribs():
    full = Part("SM_Rib_Full")
    rib(full, -RIB, RIB, -13, 13)
    half = Part("SM_Rib_Half")
    rib(half, 0, RIB, 0, 13)
    return full, half


def _open_end(spec, half, x_front=None, x_back=None):
    """Half ribs on the module's open ends; the neighbour supplies the other half."""
    if x_back is not None:
        spec.mesh("RibBack", half, _at(x_back))
    if x_front is not None:
        spec.mesh("RibFront", half, _at(x_front, 180.0))


# --------------------------------------------------------------------------
# Corridor
# --------------------------------------------------------------------------
CORRIDOR_DEFAULTS = (
    {"LowerL": "RodRack", "LowerR": "RodRack", "WallL": "Console", "WallR": "Locker",
     "UpperL": "RodRack", "UpperR": "RodRack", "Ceiling": "CeilingFan", "Floor": "FloorHatch"},
    {"LowerL": "Vent", "LowerR": "Vent", "WallL": "Locker", "WallR": "Console",
     "UpperL": "RodRack", "UpperR": "RodRack", "Ceiling": "CeilingLight", "Floor": "FloorGrate"},
)


def corridor(full, half):
    spec = Spec()
    shell = Part("SM_Corridor_Shell")
    structure(shell, -HALF_CELL, HALF_CELL)
    for x0, x1 in ((-HALF_CELL, -HALF_CELL + RIB), (-RIB, RIB), (HALF_CELL - RIB, HALF_CELL)):
        threshold(shell, x0, x1)
    bay(shell, spec, "B0", -HALF_CELL + RIB, -RIB, CORRIDOR_DEFAULTS[0])
    bay(shell, spec, "B1", RIB, HALF_CELL - RIB, CORRIDOR_DEFAULTS[1])
    spec.parts.append(shell)
    spec.mesh("Shell", shell)
    spec.mesh("RibMid", full)
    _open_end(spec, half, x_front=HALF_CELL, x_back=-HALF_CELL)
    return Module("Corridor", "Corridor", "Straight corridor section with two equipment bays.", "Corridor",
                  (("Forward", "Corridor"), ("Back", "Corridor")), spec)


# --------------------------------------------------------------------------
# Observation end: one bay, a short vestibule and a bulkhead with a porthole
# --------------------------------------------------------------------------
BULKHEAD_X = 60.0
WINDOW_Z = 200.0
WINDOW_R = 145.0
GLASS_X = BULKHEAD_X + 35.0
OBSERVATION_DEFAULTS = {"LowerL": "RodRack", "LowerR": "RodRack", "WallL": "Console", "WallR": "Console",
                        "UpperL": "RodRack", "UpperR": "RodRack", "Ceiling": "CeilingFan", "Floor": "FloorHatch"}


def _bulkhead_plug(part, x0, x1, hole):
    """Wall filling the section between x0 and x1, keyed into the structural skin, with `hole` cut through it."""
    wall = geo.extrude_x_mesh(part.slot("Panel"), geo.outward_offset(OCTAGON, PANEL + 2, closed=True), x0, x1)
    geo.subtract(wall, hole)
    part.append(wall)


def observation_end(full, half):
    spec = Spec()
    shell = Part("SM_ObsEnd_Shell")
    structure(shell, -HALF_CELL, BULKHEAD_X + 5)
    threshold(shell, -HALF_CELL, -HALF_CELL + RIB)
    threshold(shell, -RIB, RIB)
    bay(shell, spec, "B0", -HALF_CELL + RIB, -RIB, OBSERVATION_DEFAULTS)
    plain_section(shell, RIB, BULKHEAD_X, tuck_lo=10)

    # Bulkhead: dark keyed plug, white face plate proud of it, porthole through both.
    _bulkhead_plug(shell, BULKHEAD_X, BULKHEAD_X + 50,
                   geo.cylinder_mesh(shell.slot("Panel"), (BULKHEAD_X + 25, 0, WINDOW_Z), "x", WINDOW_R, 80, 128))
    plate_outline = geo.outward_offset(OCTAGON, -16, closed=True)
    plate_hole = WINDOW_R + 36
    plate = geo.extrude_x_mesh(shell.slot("Hull"), plate_outline, BULKHEAD_X - 4, BULKHEAD_X + 1, bevel=1.5)
    geo.subtract(plate, geo.cylinder_mesh(shell.slot("Hull"), (BULKHEAD_X, 0, WINDOW_Z), "x", plate_hole, 20, 128))
    shell.append(plate)
    # Horizontal service seams across the face plate, from the porthole out to the plate edge.
    for z in (85.0, 315.0):
        y0 = math.sqrt(plate_hole ** 2 - (z - WINDOW_Z) ** 2) + 3
        y1 = half_width_at(plate_outline, z) - 3
        for s in (-1, 1):
            box(shell, "Structure", BULKHEAD_X - 4.3, BULKHEAD_X - 3.6, s * y0, s * y1, z - 0.8, z + 0.8)
    # Gasket at the glass and the outer hull skin around the opening.
    torus(shell, "Rubber", (GLASS_X, 0, WINDOW_Z), "x", WINDOW_R, 2.5, 128, 12)
    skin = geo.extrude_x_mesh(shell.slot("Hull"), geo.outward_offset(OCTAGON, PANEL + SKIN + 40, closed=True),
                              BULKHEAD_X + 50, BULKHEAD_X + 70)
    geo.subtract(skin, geo.cylinder_mesh(shell.slot("Hull"), (BULKHEAD_X + 60, 0, WINDOW_Z), "x", WINDOW_R + 12, 40, 128))
    shell.append(skin)

    bezel = Part("SM_ObsEnd_Bezel")
    face = BULKHEAD_X - 4
    # (radial offset from the opening, height toward the corridor)
    geo.revolve(bezel, "Hull", [(0, -4), (33, -4), (33, 8), (29, 12), (18, 14), (14, 18), (3, 18), (0, 15)],
                WINDOW_R, (face, 0, WINDOW_Z), (-1, 0, 0), 160)
    torus(bezel, "Chrome", (face - 16.6, 0, WINDOW_Z), "x", WINDOW_R + 1.6, 1.7, 160, 12)
    for k in range(16):
        a = (k + .5) * 2 * math.pi / 16
        r = WINDOW_R + 24
        cylinder(bezel, "Metal", (face - 13.0, r * math.cos(a), WINDOW_Z + r * math.sin(a)), "x", 1.9, 2.0, 12)

    glass = Part("SM_ObsEnd_Glass")
    cylinder(glass, "Glass", (GLASS_X, 0, WINDOW_Z), "x", WINDOW_R + 1, 1.0, 128)

    spec.parts += [shell, bezel, glass]
    spec.mesh("Shell", shell)
    spec.mesh("Bezel", bezel)
    spec.mesh("Glass", glass)
    spec.mesh("RibMid", full)
    _open_end(spec, half, x_back=-HALF_CELL)
    for side, s in ((1, "R"), (-1, "L")):
        spec.light(f"Vestibule_Wash{s}", (35.0, side * 139, CEILING_Z - 1.5), (0.55, -side * 0.35, -1), 40, 14, 18.0)
    # Helm viewpoint: where the pilot's view glides to, framed on the porthole.
    spec.camera("HelmView", (-190.0, 0.0, WINDOW_Z - 5.0), 80.0)
    return Module("ObservationEnd", "Observation Bulkhead", "Corridor end with a viewing porthole.", "Bulkhead",
                  (("Back", "Corridor"),), spec)


# --------------------------------------------------------------------------
# Entry: a sealed door bulkhead, a short vestibule and one bay
# --------------------------------------------------------------------------
DOOR_X = -60.0
DOOR_PATH = [(-90.0, 0.0), (-90.0, 215.0), (-55.0, 250.0), (55.0, 250.0), (90.0, 215.0), (90.0, 0.0)]
DOOR_CENTER = (0.0, 125.0)
ENTRY_DEFAULTS = {"LowerL": "Vent", "LowerR": "Vent", "WallL": "Locker", "WallR": "Locker",
                  "UpperL": "RodRack", "UpperR": "RodRack", "Ceiling": "CeilingLight", "Floor": "FloorHatch"}


def door_leaf():
    """Left door leaf; the right one is the same mesh mirrored. Front face at +X, seam at Y = 0."""
    p = Part("SM_Entry_DoorLeaf")
    geo.extrude_x(p, "Hull", [(-0.75, 0.0), (-90.0, 0.0), (-90.0, 215.0), (-55.0, 250.0), (-0.75, 250.0)],
                  -6, 6, bevel=1.5)
    for z in (78.0, 160.0):
        box(p, "Structure", 5.6, 6.2, -84, -8, z, z + 2.5)
    box(p, "Trim", 6, 8, -78, -14, 92, 148, bevel=1.0)
    box(p, "Structure", 5.8, 6.4, -34, -20, 172, 226, bevel=0.5)
    box(p, "LEDAmber", 6, 6.6, -7, -3, 112, 138, bevel=0.3)
    return p


AIRLOCK_PATH = [(-110.0, 0.0), (-110.0, 225.0), (-75.0, 262.0), (75.0, 262.0), (110.0, 225.0), (110.0, 0.0)]
AIRLOCK_CENTER = (0.0, 130.0)
AIRLOCK_BACK = -290.0              # inner face of the outer hatch wall
AIRLOCK_FRONT = DOOR_X - 50.0      # back face of the door bulkhead
HATCH = [(-62.0, 12.0), (62.0, 12.0), (76.0, 26.0), (76.0, 206.0), (62.0, 220.0), (-62.0, 220.0), (-76.0, 206.0),
         (-76.0, 26.0)]
DOOR_TRAVEL = 91.0
HATCH_HINGE_Z = 12.0               # the hatch's foot, which it swings down about to become the boarding ramp
RAMP_PITCH = 117.0                 # opened, the ramp's far edge rests on the ground 80 cm below the deck


def _hazard_band(part, x0, x1, y0, y1, z0, z1, stripe=7.0):
    """Yellow band on a wall facing +X with black diagonal stripes, from y0..y1 and z0..z1."""
    box(part, "Hazard", x0, x1, y0, y1, z0, z1)
    h = z1 - z0
    y = y0 + stripe
    while y + stripe + h <= y1:
        geo.extrude_x(part, "Structure", [(y, z0), (y + stripe, z0), (y + stripe + h, z1), (y + h, z1)], x1, x1 + 0.3)
        y += 2 * stripe


def airlock(shell):
    """Small chamber behind the pressure door, ending in the outer hatch. Returns the hatch, a part of its own."""
    x0, x1 = AIRLOCK_BACK, AIRLOCK_FRONT
    geo.extrude_x(shell, "Structure", geo.band(AIRLOCK_PATH, PANEL, PANEL + SKIN, AIRLOCK_CENTER), -HALF_CELL, x1)
    box(shell, "Structure", -HALF_CELL, x1, -110 - PANEL - SKIN, 110 + PANEL + SKIN, -PANEL - SKIN, -PANEL)
    # Wall lining in three panels, with frame rings over the seams.
    for a, b in ((x0 + 2, -233.0), (-231.5, -167.5), (-166.0, x1 - 2)):
        geo.extrude_x(shell, "Hull", geo.band(AIRLOCK_PATH, 0, PANEL, AIRLOCK_CENTER), a, b, bevel=1.5)
    for xc in (-232.25, -166.75):
        geo.extrude_x(shell, "Trim", geo.band(AIRLOCK_PATH, -8, PANEL, AIRLOCK_CENTER), xc - 4, xc + 4, bevel=1.5)
    for a, b in ((x0 + 2, -200.75), (-199.25, x1 - 2)):
        box(shell, "Floor", a, b, -109.25, 109.25, -PANEL, 0.0, bevel=1.2)
    # Hazard strip on the deck in front of the outer hatch.
    box(shell, "Hazard", x0 + 2, x0 + 14, -108, 108, -0.1, 0.15)
    for k in range(-7, 8):
        xf = geo.frame((x0 + 8, k * 14.0, 0.2), (0.7071, 0.7071, 0), (-0.7071, 0.7071, 0))
        geo.box_xf(shell, "Structure", xf, 3.5, 13.0, 0.3)
    # Handrails along both walls and a cycle console on the right.
    for s in (-1, 1):
        cylinder(shell, "Chrome", (-200.0, s * 104.0, 100.0), "x", 1.8, 150.0, 20)
        for xb in (-262.0, -138.0):
            box(shell, "Metal", xb - 2, xb + 2, s * 104.0, s * 110.0, 97.0, 103.0, bevel=0.5)
    box(shell, "Hull", -225, -185, 101, 110, 108, 162, bevel=1.5)
    box(shell, "Structure", -222, -188, 100.5, 101, 126, 158, bevel=0.3)
    box(shell, "Screen", -220, -190, 100.2, 100.5, 128, 156)
    cylinder(shell, "LEDAmber", (-205.0, 100.4, 116.0), "y", 4.0, 1.6, 20)
    # Ceiling light panel.
    box(shell, "LEDSoft", -258, -142, -42, 42, 258.5, 262.0, bevel=0.6)

    # Outer hatch wall with the hatchway through it, and its frame.
    end = geo.extrude_x_mesh(shell.slot("Panel"), geo.outward_offset(AIRLOCK_PATH, PANEL + 2, AIRLOCK_CENTER, closed=True),
                             -HALF_CELL, x0)
    geo.subtract(end, geo.extrude_x_mesh(shell.slot("Panel"), HATCH, -HALF_CELL - 5, x0 + 5))
    shell.append(end)
    frame = geo.extrude_x_mesh(shell.slot("Trim"), geo.outward_offset(HATCH, 16, (0.0, 116.0), closed=True), x0, x0 + 12,
                               bevel=1.5)
    geo.subtract(frame, geo.extrude_x_mesh(shell.slot("Trim"), HATCH, x0 - 5, x0 + 20))
    shell.append(frame)
    box(shell, "LEDAmber", x0, x0 + 4, -12, 12, 239.0, 245.0, bevel=0.5)

    # The hatch itself: its own part, pivoting on its foot, so it can swing down outward into a boarding ramp.
    # Its inner face, with the wheel and the bars, becomes the ramp's top, the bars cleats underfoot.
    hatch = Part("SM_Entry_Hatch")
    geo.extrude_x(hatch, "Hull", geo.outward_offset(HATCH, -1.0, (0.0, 116.0), closed=True), x0, x0 + 7, bevel=2.0)
    seal = geo.extrude_x_mesh(hatch.slot("Rubber"), geo.outward_offset(HATCH, 2.5, (0.0, 116.0), closed=True), x0 - 0.5, x0 + 1)
    geo.subtract(seal, geo.extrude_x_mesh(hatch.slot("Rubber"), geo.outward_offset(HATCH, -1.5, (0.0, 116.0), closed=True),
                                          x0 - 2, x0 + 3))
    hatch.append(seal)
    hx = x0 + 7
    torus(hatch, "Chrome", (hx + 3, 0.0, 116.0), "x", 17.0, 1.8, 48, 10)
    cylinder(hatch, "Metal", (hx + 2, 0.0, 116.0), "x", 4.5, 4.0, 24)
    for a in (90.0, 210.0, 330.0):
        r = math.radians(a)
        xf = geo.frame((hx + 3, 8.5 * math.cos(r), 116.0 + 8.5 * math.sin(r)), (1, 0, 0), (0, math.cos(r), math.sin(r)))
        geo.box_xf(hatch, "Chrome", xf, 2.0, 15.0, 2.0, 0.4)
    for z in (60.0, 172.0):
        cylinder(hatch, "Chrome", (hx + 2.2, 0.0, z), "y", 2.2, 112.0, 20)
        for s in (-1, 1):
            box(hatch, "Metal", hx - 0.5, hx + 5, s * 58 - 3, s * 58 + 3, z - 5, z + 5, bevel=0.6)
    _hazard_band(hatch, hx - 0.2, hx + 0.2, -56, 56, 22.0, 32.0)
    _hazard_band(hatch, hx - 0.2, hx + 0.2, -56, 56, 198.0, 208.0)
    unreal.GeometryScript_MeshTransforms.translate_mesh(hatch.mesh, unreal.Vector(-x0, 0.0, -HATCH_HINGE_Z))
    # Frame round the pressure door on the airlock side.
    geo.extrude_x(shell, "Hull", geo.band(DOOR_PATH, -2, 12, DOOR_CENTER), x1 - 8, x1, bevel=1.5)
    return hatch


def entry(full, half):
    spec = Spec()
    shell = Part("SM_Entry_Shell")
    structure(shell, DOOR_X - 5, HALF_CELL)
    threshold(shell, -RIB, RIB)
    threshold(shell, HALF_CELL - RIB, HALF_CELL)
    bay(shell, spec, "B0", RIB, HALF_CELL - RIB, ENTRY_DEFAULTS)
    plain_section(shell, DOOR_X, -RIB, tuck_hi=10)

    _bulkhead_plug(shell, DOOR_X - 50, DOOR_X,
                   geo.extrude_x_mesh(shell.slot("Panel"), DOOR_PATH, DOOR_X - 60, DOOR_X + 10))
    plate = geo.extrude_x_mesh(shell.slot("Hull"), geo.outward_offset(OCTAGON, -16, closed=True),
                               DOOR_X - 1, DOOR_X + 4, bevel=1.5)
    geo.subtract(plate, geo.extrude_x_mesh(shell.slot("Hull"),
                                           geo.outward_offset(DOOR_PATH, 18, DOOR_CENTER, closed=True),
                                           DOOR_X - 5, DOOR_X + 10))
    shell.append(plate)
    # Door frame with an inner bead and lit jambs; the header lamp is its own component so it can change colour.
    geo.extrude_x(shell, "Hull", geo.band(DOOR_PATH, -2, 16, DOOR_CENTER), DOOR_X, DOOR_X + 16, bevel=2.0)
    geo.extrude_x(shell, "Trim", geo.band(DOOR_PATH, 3, 10, DOOR_CENTER), DOOR_X + 16, DOOR_X + 19, bevel=1.0)
    for s in (-1, 1):
        box(shell, "LED", DOOR_X + 16, DOOR_X + 16.8, s * 102, s * 104.5, 12, 200)
    # Door control panel beside the frame.
    box(shell, "Hull", DOOR_X + 4, DOOR_X + 11, 134, 168, 100, 168, bevel=1.5)
    box(shell, "Structure", DOOR_X + 11, DOOR_X + 11.5, 138, 164, 128, 162, bevel=0.3)
    box(shell, "Screen", DOOR_X + 11.5, DOOR_X + 11.8, 140, 162, 130, 160)
    cylinder(shell, "LEDGreen", (DOOR_X + 12, 151, 114), "x", 5.5, 2.0, 24)
    torus(shell, "Metal", (DOOR_X + 11.5, 151, 114), "x", 6.6, 0.9, 32, 8)
    hatch = airlock(shell)

    lamp = Part("SM_Entry_DoorLamp")
    box(lamp, "LEDAmber", DOOR_X + 16, DOOR_X + 16.8, -26, 26, 261.5, 264)

    leaf = door_leaf()
    spec.parts += [shell, leaf, lamp, hatch]
    spec.mesh("Shell", shell)
    # The leaf has a name of its own: "Hatch" belongs to the door component, which AShip opens on landing.
    spec.mesh("HatchLeaf", hatch, unreal.Transform(location=unreal.Vector(AIRLOCK_BACK, 0.0, HATCH_HINGE_Z)), movable=True)
    spec.mesh("DoorL", leaf, _at(DOOR_X - 34), movable=True)
    spec.mesh("DoorR", leaf, _at(DOOR_X - 34), scale=(1, -1, 1), movable=True)
    spec.mesh("DoorLamp", lamp)
    spec.mesh("RibMid", full)
    _open_end(spec, half, x_front=HALF_CELL)
    spec.trigger("DoorTrigger", (-90.0, 0.0, 125.0), (165.0, 130.0, 125.0))
    spec.door("Door", [("DoorL", (0.0, -DOOR_TRAVEL, 0.0)), ("DoorR", (0.0, DOOR_TRAVEL, 0.0))],
              trigger="DoorTrigger", lamp="DoorLamp", open_slot="LEDGreen", closed_slot="LEDAmber")
    # The outer hatch stays shut and locked until the ship is down (AShip opens it on landing).
    spec.door("Hatch", [("HatchLeaf", (0.0, 0.0, 0.0), (RAMP_PITCH, 0.0, 0.0))], trigger=None, locked=True, seconds=3.0,
              sounds=audio.HATCH)
    for side, s in ((1, "R"), (-1, "L")):
        spec.light(f"Vestibule_Wash{s}", (-35.0, side * 139, CEILING_Z - 1.5), (-0.55, -side * 0.35, -1), 40, 14, 18.0)
    spec.light("Airlock_Light", (-200.0, 0.0, 257.0), (0, 0, -1), 110, 80, 16.0, radius=450.0)
    spec.light("Airlock_Beacon", (AIRLOCK_BACK + 6, 0.0, 236.0), (1, 0, -0.6), 20, 6, 6.0, shadows=False,
               color=(255, 140, 30), radius=300.0)
    return Module("Entry", "Entry Bulkhead", "Corridor start: pressure door into an airlock.", "Bulkhead",
                  (("Forward", "Corridor"), ("Back", "Door")), spec)
