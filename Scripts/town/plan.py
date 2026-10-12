"""Where every building, tree and bridge goes: a pure function of the layout, in metres.

Each district is laid out on a street grid turned to its own angle (or on rings round its centre), keeping clear
of its beach and green buffer. Blocks are filled according to the district's style; some become parks. Trees
fill the buffers, parks and islets, line the streets, and palms stand along the beaches.

No unreal imports: this runs outside the editor too, for layout previews.
"""
import math
import random
import zlib

from colony.noise import Perlin, smoothstep

from . import layout, shape

# Nominal mesh sizes in metres (along X, along Y, height); instances are scaled from these.
SIZES = {
    "house": (10.0, 8.0, 9.0), "flat": (10.0, 8.0, 7.0), "block": (30.0, 14.0, 21.0),
    "courtyard": (42.0, 42.0, 18.0), "terrace": (36.0, 20.0, 30.0), "tower": (22.0, 22.0, 80.0),
    "round": (24.0, 24.0, 60.0), "pavilion": (40.0, 28.0, 9.0),
}

# style: grid pitch (m), street width (m), share of blocks left as parks, layout ("grid" or "rings")
STYLES = {
    "village":       (34.0, 6.0, 0.07, "grid"),
    "village_white": (36.0, 7.0, 0.08, "grid"),
    "mixed":         (40.0, 8.0, 0.08, "grid"),
    "midrise":       (62.0, 12.0, 0.14, "rings"),
    "towers":        (70.0, 14.0, 0.12, "grid"),
    "towers_green":  (74.0, 14.0, 0.18, "rings"),
    "campus":        (74.0, 14.0, 0.22, "grid"),
}

_CLEARING = Perlin(201)


class Plan:
    def __init__(self):
        self.buildings = []   # (kind, facade, roof, x, y, z, yaw deg, sx, sy, sz)
        self.trees = []       # (kind, x, y, z, yaw deg, scale)
        self.bridges = []     # ((x, y, z), (x, y, z), mid-span deck height)
        self.clear = []       # ((x, y, z), (x, y, z), radius): ground kept free of trees and buildings

    def building(self, kind, facade, roof, x, y, yaw, w, d, h):
        nx, ny, nz = SIZES[kind]
        z = shape.lowest_under(x, y, 0.45 * min(w, d)) - 0.3
        self.buildings.append((kind, facade, roof, x, y, z, math.degrees(yaw), w / nx, d / ny, h / nz))

    def tree(self, kind, x, y, scale, rng, sink=0.4):
        self.trees.append((kind, x, y, shape.height(x, y) - sink, rng.uniform(0.0, 360.0), scale))


def _seed(name):
    return zlib.crc32(name.encode())


def _broadleaf(rng):
    return rng.choice(("broad1", "broad1", "broad2", "broad3"))


def _interior(lobe):
    """How far in from the coast the town starts in this district."""
    return layout.BEACH_WIDTH + layout.BUFFER_WIDTH.get(lobe.style, 40.0)


def _owns(lobe, x, y, margin):
    """True if (x, y) is in this district at least `margin` metres in from where its town starts."""
    d, nearest, _ = shape.islands(x, y)
    return nearest is lobe and d < -(_interior(lobe) + margin) and shape.mainland_distance(x, y) > 50.0


def _blocks(lobe, pitch, kind):
    """Block centres and their street-aligned yaw (radians) for a district."""
    out = []
    if kind == "grid":
        yaw = math.radians(lobe.rotation + 8.0 * (_seed(lobe.name) % 5 - 2))
        c, s = math.cos(yaw), math.sin(yaw)
        n = int(lobe.reach / pitch) + 2
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                u, v = (i + 0.5) * pitch, (j + 0.5) * pitch
                out.append((lobe.x + u * c - v * s, lobe.y + u * s + v * c, yaw))
    else:
        # Rings round a central green, each block facing the centre.
        r = pitch * 1.2
        while r < lobe.reach:
            count = max(int(math.tau * r / pitch), 6)
            phase = (r / pitch) * 0.37
            for k in range(count):
                a = math.tau * (k + phase) / count
                out.append((lobe.x + r * math.cos(a), lobe.y + r * math.sin(a), a))
            r += pitch
    return out


def _fill_block(plan, lobe, x, y, yaw, size, rng, gradient):
    """Buildings for one block of a district. gradient 0..1 runs from the district's quiet edge to its busy core."""
    style = lobe.style
    c, s = math.cos(yaw), math.sin(yaw)

    def at(u, v):
        return x + u * c - v * s, y + u * s + v * c

    if style in ("village", "village_white") or (style == "mixed" and gradient < 0.55):
        white = style != "village"
        if rng.random() < (0.12 if white else 0.06):
            # A mid-rise among the houses.
            plan.building("block", "White", "Flat", x, y, yaw, size * 0.85, size * 0.5, rng.uniform(14, 24))
            return
        lot = size / 2.0
        for du in (-0.5, 0.5):
            for dv in (-0.5, 0.5):
                if rng.random() < 0.08:
                    continue
                px, py = at(du * lot + rng.uniform(-1, 1), dv * lot + rng.uniform(-1, 1))
                w, d = lot * rng.uniform(0.62, 0.85), lot * rng.uniform(0.55, 0.8)
                floors = rng.choice((2, 2, 3, 3, 3, 4)) if not white else rng.choice((2, 3, 3, 4, 5))
                if white and rng.random() < 0.75:
                    plan.building("flat", "White" if rng.random() < 0.8 else "Village", "Flat",
                                  px, py, yaw, w, d, floors * 3.3 + 0.6)
                else:
                    plan.building("house", "Village", "Terracotta", px, py, yaw + rng.choice((0.0, math.pi / 2)),
                                  w, d, floors * 3.1 + 2.6)
        return

    if style == "mixed" or style == "towers":
        tall = gradient if style == "mixed" else 0.4 + 0.6 * gradient
        if rng.random() < 0.3 + 0.4 * tall:
            h = rng.uniform(38, 62) + 60 * tall * rng.uniform(0.3, 1.0)
            fx, fy = at(rng.uniform(-3, 3), rng.uniform(-3, 3))
            plan.building("tower", "Tower", "Flat", fx, fy, yaw, rng.uniform(18, 24), rng.uniform(18, 24), h)
            # Podium along one side.
            px, py = at(0.0, size * 0.32)
            plan.building("block", "White", "Green", px, py, yaw, size * 0.8, size * 0.25, rng.uniform(7, 11))
        else:
            for dv in (-0.27, 0.27):
                px, py = at(0.0, dv * size)
                plan.building("block", "White", "Flat", px, py, yaw, size * 0.82, size * 0.32, rng.uniform(18, 34))
        return

    if style == "towers_green":
        r = rng.random()
        if r < 0.4:
            plan.building("terrace", "White", "Green", x, y, yaw, size * 0.62, size * 0.42, rng.uniform(28, 48) + 30 * gradient)
        elif r < 0.75:
            plan.building("round", "Tower", "Green", x, y, yaw, 24, 24, rng.uniform(50, 75) + 45 * gradient)
        else:
            plan.building("tower", "Tower", "Green", x, y, yaw, 22, 22, rng.uniform(60, 90) + 40 * gradient)
        return

    if style == "midrise":
        r = rng.random()
        if r < 0.35:
            plan.building("courtyard", "White", "Green", x, y, yaw, size * 0.72, size * 0.72, rng.uniform(15, 24))
        elif r < 0.65:
            for dv in (-0.24, 0.24):
                px, py = at(0.0, dv * size)
                plan.building("block", "White", "Flat", px, py, yaw, size * 0.78, size * 0.26, rng.uniform(15, 30))
        else:
            plan.building("terrace", "White", "Green", x, y, yaw, size * 0.62, size * 0.36, rng.uniform(18, 32))
        return

    if style == "campus":
        n = rng.choice((1, 2, 2))
        for k in range(n):
            px, py = at(rng.uniform(-0.15, 0.15) * size, (k - (n - 1) / 2) * size * 0.5)
            r = rng.random()
            if r < 0.45:
                plan.building("pavilion", "Timber", "Green", px, py, yaw + rng.uniform(-0.2, 0.2),
                              rng.uniform(24, 34), rng.uniform(14, 20), rng.uniform(8, 13))
            elif r < 0.8:
                plan.building("block", "White", "Green", px, py, yaw, rng.uniform(24, 34), rng.uniform(11, 14), rng.uniform(12, 26))
            else:
                plan.building("terrace", "White", "Green", px, py, yaw, rng.uniform(26, 34), rng.uniform(14, 18), rng.uniform(15, 28))
        # Trees round the buildings.
        for _ in range(7):
            tx, ty = at(rng.uniform(-0.5, 0.5) * size, rng.uniform(-0.5, 0.5) * size)
            if all(math.hypot(tx - b[3], ty - b[4]) > 22 for b in plan.buildings[-n:]):
                plan.tree(_broadleaf(rng), tx, ty, rng.uniform(0.8, 1.3), rng)


def _park(plan, x, y, yaw, size, rng):
    for _ in range(int(size * size / 140.0)):
        u, v = rng.uniform(-0.5, 0.5) * size, rng.uniform(-0.5, 0.5) * size
        c, s = math.cos(yaw), math.sin(yaw)
        plan.tree(_broadleaf(rng), x + u * c - v * s, y + u * s + v * c, rng.uniform(0.8, 1.4), rng)


def _street_trees(plan, x, y, yaw, size, street, rng, gardens=0):
    c, s = math.cos(yaw), math.sin(yaw)
    half = size * 0.5 + street * 0.5
    for u, v in ((-half, -half), (half, -half), (0.0, -half), (-half, 0.0)):
        if rng.random() < 0.7:
            plan.tree(_broadleaf(rng), x + u * c - v * s, y + u * s + v * c, rng.uniform(0.55, 0.8), rng)
    # Garden trees in the gaps between buildings, along the block's middle lines.
    for _ in range(gardens):
        u, v = rng.choice(((rng.uniform(-0.45, 0.45), 0.0), (0.0, rng.uniform(-0.45, 0.45))))
        plan.tree(_broadleaf(rng), x + (u * c - v * s) * size, y + (u * s + v * c) * size, rng.uniform(0.5, 0.85), rng)


def districts(plan):
    for lobe in shape.DISTRICTS:
        pitch, street, parks, kind = STYLES[lobe.style]
        rng = random.Random(_seed(lobe.name))
        size = pitch - street
        for x, y, yaw in _blocks(lobe, pitch, kind):
            if not _owns(lobe, x, y, size * 0.45):
                continue
            # Busy core toward the landmark for mixed districts, toward the centre for the rest.
            if lobe.style == "mixed":
                lx, ly, _ = layout.LANDMARK
                to = math.hypot(lobe.x - lx, lobe.y - ly)
                gradient = smoothstep(-0.6, 0.7, ((x - lobe.x) * (lx - lobe.x) + (y - lobe.y) * (ly - lobe.y)) / (to * lobe.reach))
            else:
                gradient = 1.0 - smoothstep(0.0, lobe.reach * 0.9, math.hypot(x - lobe.x, y - lobe.y))
            if rng.random() < parks:
                _park(plan, x, y, yaw, size, rng)
                continue
            _fill_block(plan, lobe, x, y, yaw, size, rng, gradient)
            if lobe.style != "campus":
                _street_trees(plan, x, y, yaw, size, street, rng, gardens=2 if size < 40 else 4)


def greenery(plan):
    """Trees through every district's green buffer and over the islets, palms along the beaches."""
    rng = random.Random(77)
    spacing = 9.0
    for lobe in shape.LOBES:
        if lobe.style == "plaza":
            continue
        n = int(lobe.reach / spacing) + 2
        inner = _interior(lobe) if lobe.name in layout.LOBES else 1e9
        for i in range(-n, n + 1):
            for j in range(-n, n + 1):
                x = lobe.x + (i + rng.uniform(-0.4, 0.4)) * spacing
                y = lobe.y + (j + rng.uniform(-0.4, 0.4)) * spacing
                ld = lobe.distance(x, y)
                if ld > 0.0 or ld < -(inner + 10.0):
                    continue
                d, nearest, bank = shape.islands(x, y)
                if nearest is not lobe or d > -2.0 or d < -inner + 4.0:
                    continue
                if shape.mainland_distance(x, y) < 50.0:
                    continue
                beach = max(shape.beach_width(x, y, bank), 4.0)
                if -d < beach:
                    # On the sand: the odd palm near the top of the beach.
                    if -d > beach - 7.0 and bank < 0.3 and rng.random() < 0.18:
                        plan.tree("palm", x, y, rng.uniform(0.85, 1.25), rng, sink=0.2)
                    continue
                # Clearings, so the buffer reads as a park rather than a wall of trees.
                if _CLEARING.fbm2(x / 90.0, y / 90.0, 2) < -0.18 or rng.random() < 0.25:
                    continue
                kind = "palm" if (-d < beach + 10.0 and rng.random() < 0.35) else _broadleaf(rng)
                plan.tree(kind, x, y, rng.uniform(0.75, 1.35), rng)


def spaceport(plan):
    """A terminal and a hangar beside the pad; the pad itself and the pier are their own meshes."""
    port = shape.spaceport()
    px, py = port["pad"]
    plan.building("block", "Tower", "Flat", px + 30.0, py + 58.0, 0.0, 34.0, 14.0, 10.0)
    plan.building("pavilion", "White", "Green", px + 28.0, py - 60.0, 0.0, 40.0, 24.0, 12.0)
    # Keep the pad, the walk from the ramp to the pier, and the pier clear.
    (sx, sy), (ex, ey) = port["pier_start"], port["pier_end"]
    plan.clear.append(((px, py, 0.0), (px, py, 0.0), layout.PAD_RADIUS + 12.0))
    plan.clear.append(((px, py, 0.0), (sx, sy, 0.0), 7.0))
    plan.clear.append(((sx, sy, 0.0), (ex, ey, 0.0), 7.0))
    bx, by = layout.BEACON_OFFSET
    plan.clear.append(((px + bx, py + by, 0.0), (px + bx, py + by, 0.0), 6.0))


def mainland(plan):
    """The old town along the mainland's coastal plain, thickest in the valley between the hills."""
    rng = random.Random(123)
    pitch = 30.0
    y = -7000.0
    while y < 7000.0:
        coast = shape.mainland_coast_x(y)
        depth = shape.mainland_plain(y)
        s = 25.0
        while s < depth:
            density = shape.mainland_town(y, s)
            x, yy = coast + s + rng.uniform(-6, 6), y + rng.uniform(-6, 6)
            if rng.random() < density * 0.9 and shape.mainland_distance(x, yy) < -15.0:
                yaw = math.radians(rng.choice((0.0, 90.0)) + rng.uniform(-8, 8))
                if rng.random() < 0.06 * (0.3 + shape.valley(y)):
                    plan.building("block", "White", "Flat", x, yy, yaw, rng.uniform(20, 28), rng.uniform(11, 14),
                                  rng.uniform(15, 40))
                elif rng.random() < 0.55:
                    plan.building("house", "Village", "Terracotta", x, yy, yaw, rng.uniform(8, 13), rng.uniform(7, 10),
                                  rng.choice((2, 2, 3, 3, 4)) * 3.1 + 2.6)
                else:
                    plan.building("flat", "Village" if rng.random() < 0.5 else "White", "Flat", x, yy, yaw,
                                  rng.uniform(8, 13), rng.uniform(7, 10), rng.choice((2, 3, 3, 4)) * 3.3 + 0.6)
            elif rng.random() < 0.15:
                plan.tree(_broadleaf(rng), x, yy, rng.uniform(0.8, 1.3), rng)
            s += pitch
        y += pitch


def _land_end(start, toward, owner):
    """Walks from `start` toward `toward` until just before the coast of `owner`, 25 m short of the water."""
    (x0, y0), (x1, y1) = start, toward
    length = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / length, (y1 - y0) / length
    t, last = 0.0, (x0, y0)
    while t < length:
        x, y = x0 + ux * t, y0 + uy * t
        d, nearest, _ = shape.islands(x, y)
        on_land = (nearest is owner and d < -6.0) if owner is not None else shape.mainland_distance(x, y) < -6.0
        if not on_land and t > 0.0:
            return last
        if on_land:
            last = (x, y)
        t += 4.0
    return last


def bridges(plan):
    for a_name, b_name in layout.BRIDGES:
        a = shape.BY_NAME[a_name]
        if b_name == "Mainland":
            target = (shape.mainland_coast_x(a.y) + 300.0, a.y)
            b = None
        else:
            b = shape.BY_NAME[b_name]
            target = (b.x, b.y)
        pa = _land_end((a.x, a.y), target, a)
        # From the far side back toward a, landing on b (or the mainland).
        if b is None:
            pb = pa
            for t in range(0, 3000, 4):
                p = (pa[0] + t, pa[1])
                if shape.mainland_distance(*p) < -6.0:
                    pb = p
                    break
        else:
            pb = _land_end((b.x, b.y), pa, b)
        span = math.hypot(pb[0] - pa[0], pb[1] - pa[1])
        za, zb = shape.height(*pa), shape.height(*pb)
        mid = layout.BRIDGE_CLEARANCE + 2.0 + min(span / 120.0, 4.0)
        plan.bridges.append(((pa[0], pa[1], za), (pb[0], pb[1], zb), mid))


def _segment_distance(px, py, a, b):
    (ax, ay, _), (bx, by, _) = a, b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / max(dx * dx + dy * dy, 1e-6)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def make():
    plan = Plan()
    districts(plan)
    spaceport(plan)
    mainland(plan)
    greenery(plan)
    bridges(plan)
    # Keep the bridge decks and their landings clear, and the spaceport's open ground.
    def clear(x, y, margin):
        return (all(_segment_distance(x, y, a, b) > margin for a, b, _ in plan.bridges)
                and all(_segment_distance(x, y, a, b) > r for a, b, r in plan.clear))
    plan.trees = [t for t in plan.trees if clear(t[1], t[2], 10.0)]
    plan.buildings = [b for b in plan.buildings
                      if clear(b[3], b[4], layout.BRIDGE_WIDTH * 0.5 + 0.5 * max(SIZES[b[0]][0] * b[7], SIZES[b[0]][1] * b[8]))]
    lx, ly, _ = layout.LANDMARK
    plan.trees = [t for t in plan.trees if math.hypot(t[1] - lx, t[2] - ly) > 30.0]
    return plan
