"""The shape of the land: signed distance to the coast, terrain height and land use, as pure functions of position
in metres, so the terrain, the building and tree placement and the wave calm zones all agree.

Districts are wobbly ellipses. Wherever two of them meet, a canal is carved along the line halfway between their
coasts, which packs them together like lily pads. The mainland is everything north of a wiggling coast line.

No unreal imports: this runs outside the editor too, for layout previews.
"""
import math

from colony.noise import Perlin, smoothstep

from . import layout

_TABLE = 720
_CANAL = Perlin(101)
_PLATEAU = Perlin(102)
_HILLS = Perlin(103)
_COAST = Perlin(104)
_BEACH = Perlin(105)


class Lobe:
    """A district or islet: an ellipse whose radius wobbles round the coast."""

    def __init__(self, name, x, y, rx, ry, rotation, style, seed, wobble):
        self.name, self.x, self.y, self.rx, self.ry, self.style = name, x, y, rx, ry, style
        self.rotation = rotation
        a = math.radians(rotation)
        self.cos, self.sin = math.cos(a), math.sin(a)
        n = Perlin(seed * 31 + 7)
        # Sampled on a circle in noise space, so the coast closes on itself without a seam.
        self.table = [1.0 + wobble * 1.8 * n.fbm2(1.7 * math.cos(t), 1.7 * math.sin(t), 3)
                      for t in (i * math.tau / _TABLE for i in range(_TABLE))]
        self.reach = max(rx, ry) * (1.0 + 2.0 * wobble)

    def local(self, x, y):
        dx, dy = x - self.x, y - self.y
        return dx * self.cos + dy * self.sin, -dx * self.sin + dy * self.cos

    def world(self, u, v):
        return self.x + u * self.cos - v * self.sin, self.y + u * self.sin + v * self.cos

    def edge(self, angle):
        """Distance from the centre to the coast along a local-frame angle."""
        c, s = math.cos(angle), math.sin(angle)
        f = (angle / math.tau) % 1.0 * _TABLE
        i = int(f)
        k = self.table[i % _TABLE] + (self.table[(i + 1) % _TABLE] - self.table[i % _TABLE]) * (f - i)
        return k / math.sqrt((c / self.rx) ** 2 + (s / self.ry) ** 2)

    def distance(self, x, y):
        """Roughly the signed distance to this lobe's coast: negative inside."""
        u, v = self.local(x, y)
        r = math.hypot(u, v)
        if r < 1e-6:
            return -min(self.rx, self.ry)
        return r - self.edge(math.atan2(v, u))


def _lobes():
    out = [Lobe(name, x, y, rx, ry, rot, style, seed, layout.COAST_WOBBLE)
           for name, (x, y, rx, ry, rot, style, seed) in layout.LOBES.items()]
    lx, ly, _ = layout.LANDMARK
    out.append(Lobe("Plaza", lx, ly, layout.LANDMARK_PLAZA, layout.LANDMARK_PLAZA, 0.0, "plaza", 50, 0.0))
    for i, (x, y, r, style) in enumerate(layout.ISLETS):
        out.append(Lobe(f"Islet{i}", x, y, r, r * 0.85, i * 47.0, style, 60 + i, 0.12))
    return out


LOBES = _lobes()
BY_NAME = {lobe.name: lobe for lobe in LOBES}
DISTRICTS = [lobe for lobe in LOBES if lobe.name in layout.LOBES]


def islands(x, y):
    """(signed distance to the nearest island coast in m, that lobe, how much of it is a canal bank 0..1)."""
    best, second, nearest = 1e9, 1e9, None
    for lobe in LOBES:
        # Far outside its reach a lobe can't be the nearest or second nearest that matters.
        rough = math.hypot(x - lobe.x, y - lobe.y) - lobe.reach
        if rough > second:
            continue
        d = lobe.distance(x, y)
        if d < best:
            best, second, nearest = d, best, lobe
        elif d < second:
            second = d
    canal = layout.CANAL_HALF_WIDTH + layout.CANAL_WOBBLE * _CANAL.noise2(x / 140.0, y / 140.0)
    # Half the difference between the two nearest coast distances is about the distance to the line between them.
    cut = canal - 0.5 * (second - best)
    bank = smoothstep(-25.0, 5.0, cut - best)
    return max(best, cut), nearest, bank


def mainland_coast_x(y):
    """The mainland coast: bays and headlands, curving south on the far right."""
    a, b, south = layout.MAINLAND_RIGHT_CURVE
    return (layout.MAINLAND_COAST + 160.0 * math.sin(y / 900.0 + 0.6) + 260.0 * _COAST.fbm2(y / 1400.0, 0.3, 3)
            + 60.0 * _COAST.fbm2(y / 260.0, 4.1, 2) - south * smoothstep(a, b, y))


def mainland_distance(x, y):
    """Signed distance to the mainland coast: negative inland. Its south coast faces the town; the rest of it
    rounds off into the sea before the terrain ends."""
    north, half = layout.MAINLAND_EXTENT
    wobble = 350.0 * _COAST.fbm2(x / 2600.0 + 3.1, y / 2600.0, 3)
    return max((mainland_coast_x(y) - x) * 0.9, abs(y) - half + wobble, x - north + wobble)


def valley(y):
    """1 in the middle of the town-filled valley on the mainland, falling to 0 under the massifs."""
    return math.exp(-((y - layout.VALLEY_Y) / layout.VALLEY_WIDTH) ** 2)


def beach_width(x, y, bank):
    """Sand between the water and the grass: wide on some stretches of coast, gone on others (the green buffer
    runs down to the water there), and narrow along the canals."""
    open_coast = layout.BEACH_WIDTH * (0.15 + 0.85 * smoothstep(-0.3, 0.2, _BEACH.fbm2(x / 520.0, y / 520.0, 2)))
    return open_coast + (5.0 - open_coast) * bank


def sea_floor(d):
    """Depth profile seaward of a coast, d metres out."""
    shelf = layout.SHELF_WIDTH
    if d < shelf:
        return -layout.SHELF_DEPTH * smoothstep(0.0, shelf, d) ** 0.6
    return -layout.SHELF_DEPTH - (layout.SEA_DEPTH - layout.SHELF_DEPTH) * smoothstep(shelf, shelf + 180.0, d)


def island_height(x, y, d, bank):
    if d >= 0.0:
        canal_floor = -2.6 * smoothstep(0.0, 9.0, d)
        return sea_floor(d) + (canal_floor - sea_floor(d)) * bank
    s = -d
    beach = max(beach_width(x, y, bank), 4.0)
    if s < beach:
        return layout.BEACH_TOP * s / beach
    rise = smoothstep(beach, beach + 14.0, s)
    lift = 0.4 * _PLATEAU.fbm2(x / 160.0, y / 160.0, 2) + 1.6 * smoothstep(60.0, 400.0, s)
    return layout.BEACH_TOP + (layout.PLATEAU - layout.BEACH_TOP + lift) * rise


def mainland_height(x, y, dm):
    if dm >= 0.0:
        return sea_floor(dm)
    s = -dm
    v = valley(y)
    plain = mainland_plain(y)
    h = 3.5 * smoothstep(0.0, 12.0, s) + 6.0 * smoothstep(0.0, plain, s)
    # Steep forested hills straight behind the coastal plain, lower where the valley opens up.
    rise = smoothstep(plain * 0.8, plain + 1500.0, s)
    if rise > 0.0:
        ridges = 1.0 - abs(_HILLS.fbm2(x / 1300.0, y / 1300.0, 4))
        h += layout.PEAK_HEIGHT * (1.0 - 0.55 * v) * rise * (0.2 + 0.8 * ridges ** 1.4)
        h += 22.0 * rise * _HILLS.fbm2(x / 150.0, y / 150.0, 3)
    return h


def mainland_plain(y):
    """Depth of the flat coastal strip the mainland town sits on."""
    return 160.0 + 1200.0 * valley(y)


def height(x, y):
    """Terrain height in metres at (x, y) in metres."""
    d, _, bank = islands(x, y)
    dm = mainland_distance(x, y)
    if dm < d:
        return mainland_height(x, y, dm)
    return island_height(x, y, d, bank)


def lowest_under(x, y, radius, samples=8):
    """Lowest ground under a circular footprint, so whatever stands there doesn't float on a slope."""
    pts = [(x, y)] + [(x + radius * math.cos(a), y + radius * math.sin(a))
                      for a in (i * math.tau / samples for i in range(samples))]
    return min(height(px, py) for px, py in pts)


URBAN = {"towers": 0.55, "towers_green": 0.45, "midrise": 0.5, "campus": 0.25, "village": 0.62,
         "village_white": 0.6, "mixed": 0.6, "plaza": 1.0, "spaceport": 0.8, "wild": 0.0, "beach": 0.0}


def land_use(x, y):
    """(urban, green, forest) weights for the ground material; they sum to 1."""
    return sample(x, y)[1:]


def sample(x, y):
    """(height m, urban, green, forest) in one pass, for the terrain mesh."""
    d, lobe, bank = islands(x, y)
    dm = mainland_distance(x, y)
    if dm < d:
        h = mainland_height(x, y, dm)
        town = mainland_town(y, -dm)
        return h, town * 0.6, town * 0.4, 1.0 - town
    h = island_height(x, y, d, bank)
    if lobe is None or d > 0.0:
        return h, 0.0, 1.0, 0.0
    buffer = layout.BEACH_WIDTH + layout.BUFFER_WIDTH.get(lobe.style, 30.0)
    urban = URBAN.get(lobe.style, 0.0) * smoothstep(buffer - 8.0, buffer + 4.0, -d)
    return h, urban, 1.0 - urban, 0.0


def mainland_town(y, s):
    """How built-up the mainland is s metres in from its coast: the coastal plain, densest in the valley."""
    plain = mainland_plain(y)
    return (1.0 - smoothstep(plain * 0.85, plain * 1.05, s)) * smoothstep(5.0, 25.0, s) * (0.55 + 0.45 * valley(y))


def spaceport():
    """The spaceport's layout in metres: islet centre, pad centre, and the pier's two ends. The pier runs south from
    where the ground has fallen to its deck height, out past the waterline."""
    islet = BY_NAME[f"Islet{layout.SPACEPORT_ISLET}"]
    cx, cy = islet.x, islet.y
    pad = (cx + layout.PAD_OFFSET[0], cy + layout.PAD_OFFSET[1])
    # Walk south to the waterline, then back up the beach to deck height.
    x = cx
    while islet.distance(x, cy) < 0.0:
        x -= 1.0
    coast = x
    while height(x, cy) < layout.PIER_DECK - 0.1 and x < cx:
        x += 1.0
    return {"islet": (cx, cy), "pad": pad, "pier_start": (x, cy), "pier_end": (coast - layout.PIER_SEAWARD, cy)}


def calm_zones():
    """(x, y, inner, outer) in metres: sheltered water round each district and islet, and along the mainland."""
    inner, outer = layout.CALM_MARGIN
    zones = [(lobe.x, lobe.y, lobe.reach + inner, lobe.reach + outer)
             for lobe in LOBES if lobe.name in layout.LOBES]
    for y in (-3000.0, -1500.0, 0.0, 1500.0, 3000.0):
        zones.append((mainland_coast_x(y) + 400.0, y, 500.0, 1100.0))
    return zones
