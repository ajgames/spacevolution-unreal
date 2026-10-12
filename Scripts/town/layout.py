"""Where everything goes, in metres.

World origin is the landmark spire in the canal junction at sea level. X runs north, away from the hero camera
toward the mainland hills; Y runs east, to its right. The town is a cluster of lily-pad districts (lobes)
separated by canals, ringed by beaches and green buffers, after BIG's BiodiverCity masterplan for Penang.

Positions were fitted to the reference aerial render: features picked off the 16:9 frame and projected onto the
sea through a camera 2 km up, pitched 30 degrees down with a 62 degree horizontal field of view.
"""

CAMERA = (-3800.0, 0.0, 2000.0)
CAMERA_PITCH = -30.0
FOCAL_MM = 30.0                     # 62 degrees across a 36 x 20.25 mm (16:9) back

SUN_ELEVATION = 22.0                # degrees above the horizon
SUN_YAW = 68.0                      # direction the light travels: from the west-south-west, as in the reference
SUN_LUX = 10.0

SEA_DEPTH = 55.0                    # open-sea floor, metres below sea level

# Districts: name -> (centre x, centre y, radius x, radius y, rotation degrees, style, seed).
# Radii are of the ellipse before the coast wobble; canals are carved wherever two districts meet.
LOBES = {
    "WestTowers":  (420.0, -2480.0, 340.0, 360.0, 10.0, "towers", 1),
    "WestRound":   (-140.0, -2000.0, 350.0, 360.0, 0.0, "midrise", 2),
    "WestCampus":  (460.0, -1760.0, 320.0, 400.0, -10.0, "campus", 3),
    "Harbour":     (-480.0, -1080.0, 560.0, 470.0, 15.0, "village_white", 4),
    "NorthTowers": (420.0, -700.0, 470.0, 600.0, 5.0, "towers_green", 5),
    "Central":     (-1000.0, -320.0, 600.0, 560.0, -15.0, "mixed", 6),
    "Crescent":    (-560.0, 560.0, 480.0, 420.0, 20.0, "midrise", 7),
    "TechPark":    (380.0, 960.0, 620.0, 720.0, 10.0, "campus", 8),
    "EastTown":    (-1080.0, 1700.0, 640.0, 640.0, 25.0, "village", 9),
    "EastGreen":   (-280.0, 2150.0, 380.0, 400.0, 0.0, "campus", 10),
    "FarEast":     (-1700.0, 2700.0, 520.0, 520.0, -20.0, "village", 11),
}
COAST_WOBBLE = 0.09                 # coast irregularity, as a fraction of the radius
CANAL_HALF_WIDTH = 30.0             # metres either side of the line where two districts meet
CANAL_WOBBLE = 10.0

# Islets: (x, y, radius, style)
ISLETS = [
    (-1560.0, -820.0, 150.0, "spaceport"),
    (-420.0, -1640.0, 55.0, "wild"),
    (-1230.0, 760.0, 70.0, "wild"),
    (-1450.0, 900.0, 45.0, "wild"),
    (-1700.0, 1120.0, 60.0, "beach"),
    (-1950.0, 1420.0, 55.0, "beach"),
    (-1180.0, 180.0, 40.0, "wild"),
    (-700.0, 1330.0, 32.0, "wild"),
]

# Coast profile, metres: beach width, green buffer width (beach edge to the first buildings), plateau height.
BEACH_WIDTH = 26.0
BEACH_TOP = 1.8
PLATEAU = 3.4
BUFFER_WIDTH = {"towers": 55.0, "towers_green": 60.0, "midrise": 50.0, "campus": 70.0, "village": 40.0,
                "village_white": 45.0, "mixed": 45.0}
SHELF_WIDTH = 45.0                  # shallow turquoise shelf beyond the beach
SHELF_DEPTH = 3.5

# The spaceport, where arriving ships land: on the first islet, south of Central. A pad, a beacon that shows from
# high up, a terminal and a hangar, and a pier where the PWC-01 waits.
SPACEPORT_ISLET = 0
PAD_OFFSET = (-55.0, 0.0)           # pad centre from the islet's centre: toward the pier
PAD_RADIUS = 36.0
PAD_TOP = 5.2
SHIP_MIDDLE = 12.2                  # the arriving ship's middle, ahead of its origin (the entry module)
BEACON_OFFSET = (14.0, 32.0)        # beacon mast from the pad centre
PIER_DECK = 1.7                     # deck height above the sea
PIER_SEAWARD = 40.0                 # how far the pier runs out past the waterline
PIER_WIDTH = 4.0

# Mainland across the bay: coast line x = MAINLAND_COAST + wiggle, curving south on the far right. It's an island
# itself (Penang), ending before the terrain does, so it looks whole from orbit.
MAINLAND_COAST = 1550.0
MAINLAND_RIGHT_CURVE = (1900.0, 3400.0, 1100.0)   # from y, to y, how far south the coast comes
VALLEY_Y = 300.0                    # the town-filled valley between the two massifs
VALLEY_WIDTH = 1000.0
PEAK_HEIGHT = 820.0
MAINLAND_EXTENT = (10300.0, 8600.0)  # its north coast, and how far east and west it reaches

LANDMARK = (0.0, 0.0, 150.0)        # x, y, height
LANDMARK_PLAZA = 70.0               # radius of the round plaza islet it stands on

# Bridges: pairs of districts (or "Plaza", or "Mainland") joined across the canals.
BRIDGES = [
    ("Plaza", "NorthTowers"), ("Plaza", "Central"), ("Plaza", "Crescent"), ("Plaza", "TechPark"),
    ("WestTowers", "WestCampus"), ("WestTowers", "WestRound"), ("WestRound", "WestCampus"),
    ("WestRound", "Harbour"), ("WestCampus", "NorthTowers"), ("Harbour", "NorthTowers"), ("Harbour", "Central"),
    ("Central", "Crescent"), ("Crescent", "TechPark"), ("Crescent", "EastTown"), ("TechPark", "EastGreen"),
    ("EastTown", "EastGreen"), ("EastTown", "FarEast"), ("TechPark", "Mainland"),
]
BRIDGE_CLEARANCE = 9.0              # deck height over the water at mid-span
BRIDGE_WIDTH = 12.0

# Ocean swell: (direction of travel in degrees from +X toward +Y, wavelength m, amplitude m). Rolls in from
# the open sea in the south toward the town.
WAVES = [
    (12.0, 110.0, 1.5), (-22.0, 72.0, 0.9), (38.0, 50.0, 0.6), (-48.0, 34.0, 0.38),
    (4.0, 23.0, 0.25), (68.0, 15.0, 0.13), (-76.0, 10.0, 0.08), (28.0, 6.5, 0.05),
]
WAVE_STEEPNESS = 0.55
CALM_FLOOR = 0.1                    # fraction of the swell left in the canals and against the beaches
CALM_MARGIN = (40.0, 520.0)         # calm zone radii beyond a district's radius: still water, full swell

# The rider starts out at sea, south of the town, facing it.
PLAYER_START = (-2700.0, -300.0, 5.0)
PLAYER_YAW = 15.0
