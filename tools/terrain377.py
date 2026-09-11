"""377 procedural terrain heights, transcribed from javaclient World.java (method32/11/26/23/24).

A .jm2 tile with no explicit `h` is NOT flat and is not height 0 - the client generates it with this
perlin function, keyed on the ABSOLUTE world tile plus two constants, and an offline check that
treats those tiles as unknown can only refuse to answer. This makes them answerable.

Height in world units = -h * 8 for an explicit `h` byte and -vertex_height(...) * 8 otherwise, so the
two are directly comparable as the raw byte.
"""
import math

# Pix3D.cosTable: 2048 entries of cos over a full turn, 16.16 fixed point.
COS = [int(65536.0 * math.cos(i * 0.0030679615)) for i in range(2048)]

def _i32(v):
    v &= 0xFFFFFFFF
    return v - 0x100000000 if v & 0x80000000 else v

def noise(x, z):                                   # World.method23
    v2 = _i32(z * 57 + x)
    v3 = _i32(_i32(v2 << 13) ^ v2)
    v4 = _i32(_i32(_i32(_i32(v3 * v3) * 15731 + 789221) * v3) + 1376312589) & 0x7FFFFFFF
    return (v4 >> 19) & 0xFF

def smooth(x, z):                                  # World.method26
    corners = noise(x-1, z-1) + noise(x+1, z-1) + noise(x-1, z+1) + noise(x+1, z+1)
    sides = noise(x-1, z) + noise(x+1, z) + noise(x, z-1) + noise(x, z+1)
    return noise(x, z) // 4 + corners // 16 + sides // 8

def interp(a, b, x, scale):                        # World.method24
    f = (65536 - COS[x * 1024 // scale]) >> 1
    return ((65536 - f) * a >> 16) + (b * f >> 16)

def perlin(x, z, scale):                           # World.method11
    x2, xr = x // scale, x & (scale - 1)
    z2, zr = z // scale, z & (scale - 1)
    a = interp(smooth(x2, z2), smooth(x2 + 1, z2), xr, scale)
    b = interp(smooth(x2, z2 + 1), smooth(x2 + 1, z2 + 1), xr, scale)
    return interp(a, b, zr, scale)

def vertex_height(x, z):                           # World.method32
    v = (perlin(x + 45365, z + 91923, 4) - 128
         + ((perlin(x + 10294, z + 37821, 2) - 128) >> 1)
         + ((perlin(x, z, 1) - 128) >> 2))
    v = int(v * 0.3) + 35
    return 10 if v < 10 else (60 if v > 60 else v)

def height_of(abs_x, abs_z):
    """The `h` byte the client would use for a tile with no explicit height, at absolute world x/z.
    World.java: -method32(localX + 932731 + originX, localZ + 556238 + originZ) * 8."""
    return vertex_height(abs_x + 932731, abs_z + 556238)
