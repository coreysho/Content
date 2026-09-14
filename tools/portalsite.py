#!/usr/bin/env python3
"""Find somewhere a five-tile house portal can actually stand, on a 377 map square.

Written for the Relocate round, and it exists because of what siting the FIRST portal cost: five
placements shipped before one looked right, because a 377 loc sits at ONE height with the ground
running through it, and the OSRS portal tile in Rimmington falls h35 to h12 across exactly the five
tiles the portal needs. See claude/poh-portal-placement.md. Guessing a tile in five more towns would
have repeated that five more times.

A tile with no explicit `h` in the .jm2 is NOT flat and NOT unknown - the client generates it, and
tools/terrain377.py is that function transcribed, so every tile here has a height.

    python3 tools/portalsite.py                 # every town in TOWNS
    python3 tools/portalsite.py Yanille         # one of them, with the height map

What it will not do is tell you which candidate looks right. That is a question only someone standing
there can answer - ::~pohportal <rot> drops a real one at your feet for three minutes.
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))
from terrain377 import height_of

MAX_SPREAD = 4       # the same quarter-tile the battery's group 21 enforces
# The town path, per town, by overlay id out of scripts/_unpack/377/all.flo. It is NOT the same
# overlay everywhere and assuming it was is why this first reported nothing for three of the six:
#   10 darkstone (the dirt road)   26 oldbrick (Pollnivneach's paving)
#   88 viking_mud_overlay          25 sand_rock / 22 l_brownfloor1_bump (Brimhaven)
# A portal may not stand ON the dirt road - a five-wide loc across it severs the path - but it may
# stand on a town's broad paving, which is what a plaza is for.
NEVER_ON = {10}
PORTAL_W, PORTAL_L = 5, 2
# Shapes that put something solid on a tile: walls 0-3, diagonal wall 9, and the two ground-object
# shapes 10 and 11. Wall decorations (4-8) and roof pieces (12-21) hang above it; 22 is ground decor.
SOLID = {0, 1, 2, 3, 9, 10, 11}

# (name, map square, the OSRS portal tile as a local coord - used only as the anchor to search around)
TOWNS = [
    ('Rimmington',   46, 50,  9, 24, {10}),
    ('Taverley',     45, 53,  4, 60, {10, 16, 22}),
    ('Pollnivneach', 52, 46, 12, 59, {26}),
    ('Rellekka',     41, 56, 46, 46, {88, 89}),
    ('Brimhaven',    43, 49,  6, 42, {25, 22}),
    ('Yanille',      39, 48, 48, 24, {10}),
]

def load(mx, mz):
    path = os.path.join(C, 'maps', 'm%d_%d.jm2' % (mx, mz))
    txt = open(path).read()
    tiles, locs = {}, {}
    sec = None
    for line in txt.split('\n'):
        if line.startswith('===='):
            sec = line.strip('= ').strip(); continue
        if ':' not in line:
            continue
        head, data = line.split(':', 1)
        parts = head.split()
        if len(parts) != 3:
            continue
        lv, x, z = (int(v) for v in parts)
        if lv != 0:
            continue
        if sec == 'MAP':
            h = re.search(r'(?:^| )h(\d+)', data)
            o = re.search(r'(?:^| )o(\d+)', data)
            f = re.search(r'(?:^| )f(\d+)', data)
            tiles[(x, z)] = (int(h.group(1)) if h else None,
                             int(o.group(1)) if o else 0,
                             int(f.group(1)) if f else 0)
        elif sec == 'LOC':
            # "lv x z: id shape rot" - shape defaults to 10, rot to 0.
            bits = data.split()
            shape = int(bits[1]) if len(bits) > 1 else 10
            locs.setdefault((x, z), []).append((int(bits[0]), shape))
    return tiles, locs

def square(mx, mz):
    tiles, locs = load(mx, mz)
    def ground(x, z):
        t = tiles.get((x, z))
        if t and t[0] is not None:
            return t[0]
        return height_of(mx * 64 + x, mz * 64 + z)
    def overlay(x, z):
        t = tiles.get((x, z)); return t[1] if t else 0
    def flag(x, z):
        t = tiles.get((x, z)); return t[2] if t else 0
    return ground, overlay, flag, locs

def footprint(x, z, angle):
    """loc_add anchors at the south-west corner and width/length SWAP on an odd angle."""
    w, l = (PORTAL_W, PORTAL_L) if angle % 2 == 0 else (PORTAL_L, PORTAL_W)
    return [(x + dx, z + dz) for dx in range(w) for dz in range(l)]

def sites(mx, mz, ax, az, paths, radius=14):
    ground, overlay, flag, locs = square(mx, mz)
    out = []
    for x in range(max(0, ax - radius), min(64, ax + radius)):
        for z in range(max(0, az - radius), min(64, az + radius)):
            for angle in range(4):
                fp = footprint(x, z, angle)
                if any(not (0 <= a < 64 and 0 <= b < 64) for a, b in fp):
                    continue
                # Only SOLID locs disqualify a tile. Half the ground in these towns is covered in
                # locs - grass tufts, twigs, dug-up soil - and every one of them is shape 22 ground
                # decor, which does not block (GameMap.changeLocCollision only calls changeFloor for
                # active=1). Filtering on "any loc at all" rejected all 2,576 placements in
                # Rimmington, including the tile the portal is standing on today.
                if any(sh in SOLID for t in fp for _, sh in locs.get(t, ())):
                    continue
                if any(flag(a, b) & 1 for a, b in fp):
                    continue
                if any(overlay(a, b) in NEVER_ON for a, b in fp):
                    continue      # a five-wide loc across the dirt road severs the path
                hs = [ground(a, b) for a, b in fp]
                spread = max(hs) - min(hs)
                if spread > MAX_SPREAD:
                    continue
                # it should be ON the road, not in a field three streets away
                near = min((abs(a - x) + abs(b - z)
                            for a in range(max(0, x - 6), min(64, x + 7))
                            for b in range(max(0, z - 6), min(64, z + 7))
                            if overlay(a, b) in paths), default=99)
                if near > 5:
                    continue
                dist = abs(x - ax) + abs(z - az)
                out.append((spread * 3 + near * 2 + dist, spread, near, dist, x, z, angle))
    out.sort()
    return out

def heightmap(mx, mz, ax, az, paths, r=7):
    ground, overlay, flag, locs = square(mx, mz)
    print('      ' + ''.join('%4d' % x for x in range(ax - r, ax + r + 1)))
    for z in range(az + r, az - r - 1, -1):
        row = ''
        for x in range(ax - r, ax + r + 1):
            if not (0 <= x < 64 and 0 <= z < 64):
                row += '   .'; continue
            solid = any(sh in SOLID for _, sh in locs.get((x, z), ()))
            mark = '/' if overlay(x, z) in paths else ('*' if solid else ' ')
            row += '%s%3d' % (mark, ground(x, z))
        print('z%-4d %s' % (z, row))
    print('  / = the town path, * = something solid already stands here')

def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    for name, mx, mz, ax, az, paths in TOWNS:
        if want and want.lower() != name.lower():
            continue
        found = sites(mx, mz, ax, az, paths)
        print('\n=== %s  m%d_%d  anchor %d,%d (abs %d,%d) - %d candidate placements'
              % (name, mx, mz, ax, az, mx * 64 + ax, mz * 64 + az, len(found)))
        for _, spread, near, dist, x, z, angle in found[:6]:
            print('    %2d,%-2d angle %d   spread %d   %d from the road   %2d from the anchor'
                  % (x, z, angle, spread, near, dist))
        if want:
            print()
            heightmap(mx, mz, ax, az, paths)

if __name__ == '__main__':
    main()
