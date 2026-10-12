"""Seeded gradient noise in pure Python (the editor's Python has no numpy), for terrain heights and rock shapes."""
import math
import random

_GRAD2 = [(math.cos(a), math.sin(a)) for a in (i * math.tau / 8 for i in range(8))]
_GRAD3 = [(1, 1, 0), (-1, 1, 0), (1, -1, 0), (-1, -1, 0), (1, 0, 1), (-1, 0, 1), (1, 0, -1), (-1, 0, -1),
          (0, 1, 1), (0, -1, 1), (0, 1, -1), (0, -1, -1)]


def _fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


class Perlin:
    """Classic gradient noise. noise2/noise3 return roughly -1..1."""

    def __init__(self, seed):
        p = list(range(256))
        random.Random(seed).shuffle(p)
        self.p = p + p

    def noise2(self, x, y):
        p = self.p
        xi, yi = math.floor(x), math.floor(y)
        xf, yf = x - xi, y - yi
        xi, yi = xi & 255, yi & 255
        u, v = _fade(xf), _fade(yf)

        def g(h, dx, dy):
            gx, gy = _GRAD2[h & 7]
            return gx * dx + gy * dy

        a, b = p[xi] + yi, p[xi + 1] + yi
        x0 = lerp(g(p[a], xf, yf), g(p[b], xf - 1, yf), u)
        x1 = lerp(g(p[a + 1], xf, yf - 1), g(p[b + 1], xf - 1, yf - 1), u)
        return lerp(x0, x1, v) * 1.4

    def noise3(self, x, y, z):
        p = self.p
        xi, yi, zi = math.floor(x), math.floor(y), math.floor(z)
        xf, yf, zf = x - xi, y - yi, z - zi
        xi, yi, zi = xi & 255, yi & 255, zi & 255
        u, v, w = _fade(xf), _fade(yf), _fade(zf)

        def g(h, dx, dy, dz):
            gx, gy, gz = _GRAD3[h % 12]
            return gx * dx + gy * dy + gz * dz

        a = p[xi] + yi
        aa, ab = p[a] + zi, p[a + 1] + zi
        b = p[xi + 1] + yi
        ba, bb = p[b] + zi, p[b + 1] + zi
        return lerp(lerp(lerp(g(p[aa], xf, yf, zf), g(p[ba], xf - 1, yf, zf), u),
                         lerp(g(p[ab], xf, yf - 1, zf), g(p[bb], xf - 1, yf - 1, zf), u), v),
                    lerp(lerp(g(p[aa + 1], xf, yf, zf - 1), g(p[ba + 1], xf - 1, yf, zf - 1), u),
                         lerp(g(p[ab + 1], xf, yf - 1, zf - 1), g(p[bb + 1], xf - 1, yf - 1, zf - 1), u), v), w)

    def fbm2(self, x, y, octaves=4, lacunarity=2.03, gain=0.5):
        total, amp = 0.0, 0.5
        for _ in range(octaves):
            total += amp * self.noise2(x, y)
            x, y, amp = x * lacunarity + 17.1, y * lacunarity + 5.3, amp * gain
        return total

    def fbm3(self, x, y, z, octaves=4, lacunarity=2.03, gain=0.5):
        total, amp = 0.0, 0.5
        for _ in range(octaves):
            total += amp * self.noise3(x, y, z)
            x, y, z, amp = x * lacunarity + 17.1, y * lacunarity + 5.3, z * lacunarity + 11.7, amp * gain
        return total
