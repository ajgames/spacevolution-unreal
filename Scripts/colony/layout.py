"""Where everything goes, in metres.

World origin is the middle of the colony at ground level; X runs away from the hero camera toward the rock
spires, Y to its right. The camera stands on a ridge 600 m back from the colony, 58 m above the basin floor,
and the sun sits low on the left.

Positions were fitted to the reference painting: each element's screen position and size in the 3:2 frame,
seen through a 35 mm lens on a 36 x 24 mm back, converted to a distance and offset from the camera.
"""

CAMERA = (-600.0, 0.0, 58.0)
CAMERA_PITCH = -1.0
FOCAL_MM = 35.0                     # ~54 degrees horizontal on the 36 mm back
PLAYER_START = (-575.0, -40.0)      # on the ridge beside the camera; the height comes from the terrain

SUN_ELEVATION = 9.0                 # degrees above the horizon
SUN_AZIMUTH = -42.0                 # degrees from the camera's view axis; negative is to the left. Just out of
                                    # frame, so its glow fills the top-left and it rakes across the spires' left faces
SUN_LUX = 10.0

# Flat elliptical pad the colony is built on: centre, radii, and how far out (as a multiple of the radii) the
# ground blends back to natural terrain.
PAD_CENTRE = (70.0, 70.0)
PAD_RADII = (470.0, 380.0)
PAD_BLEND = 1.3

# name: (x, y, diameter)
DOMES = {
    "West": (-194.0, -120.0, 110.0),
    "North": (100.0, -80.0, 125.0),
    "East": (-116.0, 113.0, 86.0),
}

# The low round terminal in the foreground: (x, y, diameter)
TERMINAL = (-267.0, 28.0, 104.0)

# (x, y, height, radius, style)
TOWERS = [
    (280.0, 30.0, 187.0, 16.0, "capped"),
    (360.0, 57.0, 241.0, 13.0, "spire"),
    (300.0, 152.0, 241.0, 14.0, "spire"),
    (220.0, 171.0, 78.0, 22.0, "capped"),
    (280.0, 229.0, 194.0, 18.0, "stepped"),
    (350.0, 297.0, 259.0, 22.0, "spire"),
]

# Rock formations: (shape, x, y, height, base radius, yaw degrees)
ROCKS = [
    # The two hero spires left of the towers.
    ("Fin", 1600.0, -355.0, 480.0, 190.0, 20.0),
    ("FinHook", 2000.0, -122.0, 575.0, 175.0, -35.0),
    # Low spur behind the towers.
    ("Butte", 1400.0, 292.0, 190.0, 120.0, 10.0),
    # The massif on the right: a main peak with shoulders around it.
    ("Fin", 1800.0, 950.0, 580.0, 230.0, 60.0),
    ("FinHook", 1650.0, 720.0, 400.0, 160.0, 110.0),
    ("Fin", 2050.0, 1180.0, 500.0, 210.0, -70.0),
    ("Butte", 1450.0, 1280.0, 330.0, 240.0, 30.0),
    ("Butte", 1250.0, 860.0, 160.0, 170.0, -15.0),
    # Ridge left of the hero spires, and the left edge of frame.
    ("Butte", 2300.0, -900.0, 170.0, 300.0, 5.0),
    ("FinHook", 2600.0, -1500.0, 380.0, 260.0, 140.0),
    # Far ranges, faded by haze.
    ("Mesa", 4400.0, -2600.0, 520.0, 900.0, 15.0),
    ("Mesa", 5600.0, -300.0, 380.0, 1200.0, 40.0),
    ("Fin", 3800.0, 600.0, 430.0, 380.0, 80.0),
    ("Mesa", 5800.0, 2600.0, 450.0, 1100.0, -20.0),
    ("Butte", 3200.0, 2300.0, 480.0, 600.0, 0.0),
    ("Fin", 4200.0, -1200.0, 560.0, 420.0, 200.0),
    # Foreground outcrops below the camera, in shadow.
    ("Butte", -470.0, 95.0, 14.0, 22.0, 30.0),
    ("Butte", -500.0, 150.0, 9.0, 15.0, 75.0),
    ("Butte", -430.0, -175.0, 12.0, 26.0, 10.0),
]

# Scattered boulders on the basin floor between the camera ridge and the spires.
BOULDER_SEED = 7
BOULDER_COUNT = 70
BOULDER_AREA = ((-450.0, 1500.0), (-1400.0, 1600.0))  # x range, y range
