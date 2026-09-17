"""The Barrows tunnels as a graph, read off maps/m55_151.jm2.

Old School randomises WHICH DOORS OPEN on every run, and the only thing that must always be true is
that the chest can still be reached from the ladder the player came in by. Generating that inside
the script would mean a flood fill in RuneScript; instead the work is done here, offline, against
the map itself, and the answers ship as a table in barrows.enum.

Two entry points, and the battery uses the second:

    python3 tools/barrowsmaze.py            print the graph and regenerate the table
    from barrowsmaze import tunnel, solves  re-verify a mask against the map

A mask is sixteen bits, one per gate a-p, LOW BIT = gate a, and a SET bit means that gate is
LOCKED - the same order and the same meaning as %barrows bits 10-25, so one write sets a whole maze.
"""
import os, re, random, sys
from collections import deque

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LETTERS = 'abcdefghijklmnop'
# A shape-0 loc is a wall on ONE EDGE of its tile, and the rotation says which: the same
# 0=west 1=north 2=east 3=south that doors/scripts/door_procs.rs2 switches on.
EDGE = {0: (-1, 0), 1: (0, 1), 2: (1, 0), 3: (0, -1)}


def _read(p):
    return open(os.path.join(C, p), newline='', errors='replace').read().replace('\r\n', '\n')


def tunnel():
    """(walk, doors, ladders, chest) measured off the map.

    walk    - the set of level-0 tiles a player can stand on
    doors   - {letter: {(x, z, rot)}}, every door placement of that gate
    ladders - {letter: (x, z)} for the four chamber ladders
    chest   - (x, z) of the reward chest's south-west tile
    """
    locname = {}
    for line in _read('pack/loc.pack').split('\n'):
        if '=' in line:
            i, n = line.strip().split('=', 1)
            locname[int(i)] = n
    size = {}
    for root, _, fs in os.walk(os.path.join(C, 'scripts')):
        for f in sorted(fs):
            if not f.endswith('.loc'):
                continue
            for b in re.split(r'(?m)^(?=\[)',
                              _read(os.path.relpath(os.path.join(root, f), C))):
                m = re.match(r'\[(\w+)\]', b)
                if not m:
                    continue
                w = re.search(r'(?m)^width=(\d+)', b)
                l = re.search(r'(?m)^length=(\d+)', b)
                size[m.group(1)] = (int(w.group(1)) if w else 1, int(l.group(1)) if l else 1)

    txt = _read('maps/m55_151.jm2')
    # TILE FLAG BIT 0 IS THE BLOCKED FLAG, and it is set on 2,613 of the tunnel's 4,096 tiles -
    # including the four ladders' own tiles, which is why reachability is measured to the tiles
    # BESIDE a ladder rather than to the ladder.
    walk = set()
    for line in txt.split('==== MAP ====')[1].split('==== ')[0].split('\n'):
        m = re.match(r'^(\d+) (\d+) (\d+):(.*)$', line.strip())
        if not m or int(m.group(1)) != 0:
            continue
        f = re.search(r'\bf(\d+)', m.group(4))
        if (int(f.group(1)) if f else 0) & 1 == 0:
            walk.add((int(m.group(2)), int(m.group(3))))

    doors, ladders, chest, solid = {}, {}, None, set()
    for line in txt.split('==== LOC ====')[1].split('==== ')[0].split('\n'):
        m = re.match(r'^(\d+) (\d+) (\d+): (\d+) (\d+)(?: (\d+))?\s*$', line.strip())
        if not m:
            continue
        lv, x, z, i, shape, rot = (int(m.group(k) or 0) for k in range(1, 7))
        if lv != 0:
            continue
        n = locname.get(i, '')
        if shape == 0 and n.startswith('barrows_door_'):
            doors.setdefault(n[len('barrows_door_')], set()).add((x, z, rot))
        elif shape in (9, 10, 11):
            if n.startswith('barrows_ladder_'):
                ladders[n[len('barrows_ladder_')]] = (x, z)
                continue
            if n == 'barrows_stone_chest':
                chest = (x, z)
                continue
            w, l = size.get(n, (1, 1))
            if rot % 2 == 1:
                w, l = l, w
            for dx in range(w):
                for dz in range(l):
                    solid.add((x + dx, z + dz))
    return walk - solid, doors, ladders, chest


def _cuts(mask, doors):
    out = set()
    for i, L in enumerate(LETTERS):
        if not (mask >> i) & 1:
            continue
        for (x, z, rot) in doors.get(L, ()):
            dx, dz = EDGE[rot]
            out.add(((x, z), (x + dx, z + dz)))
            out.add(((x + dx, z + dz), (x, z)))
    return out


def reachable(start, walk, cuts):
    seen = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cur[0] + dx, cur[1] + dz)
            if n in walk and n not in seen and (cur, n) not in cuts:
                seen.add(n)
                q.append(n)
    return seen


def _beside(tile, walk):
    return [(tile[0] + dx, tile[1] + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))
            if (tile[0] + dx, tile[1] + dz) in walk]


def solves(mask, cache={}):
    """True when every chamber ladder can still reach the chest with this maze locked."""
    if 't' not in cache:
        cache['t'] = tunnel()
    walk, doors, ladders, chest = cache['t']
    cuts = _cuts(mask, doors)
    # The chest is a 2x2 loc with forceapproach=south, so its own tiles are not standable; the
    # target is the floor beside it.
    goal = set()
    for dx in range(2):
        for dz in range(2):
            goal |= set(_beside((chest[0] + dx, chest[1] + dz), walk))
    for L, tile in sorted(ladders.items()):
        start = _beside(tile, walk)
        if not start:
            return False
        if not (reachable(start[0], walk, cuts) & goal):
            return False
    return True


def generate(count, lo, hi, seed=377):
    """`count` distinct solvable masks locking between `lo` and `hi` of the sixteen gates."""
    rng = random.Random(seed)
    out = []
    while len(out) < count:
        k = lo + (len(out) * (hi - lo + 1) // count) % (hi - lo + 1)
        bits = rng.sample(range(16), k)
        mask = 0
        for b in bits:
            mask |= 1 << b
        if mask in out or not solves(mask):
            continue
        out.append(mask)
    return out


def names(mask):
    return ''.join(L for i, L in enumerate(LETTERS) if (mask >> i) & 1)


if __name__ == '__main__':
    walk, doors, ladders, chest = tunnel()
    print('walkable tiles: %d   gates: %s   ladders: %s   chest: %s'
          % (len(walk), ''.join(sorted(doors)), sorted(ladders), chest))
    print('every gate shut is solvable:', solves(0xFFFF))
    print('every gate open is solvable:', solves(0))
    ms = generate(int(sys.argv[1]) if len(sys.argv) > 1 else 24, 5, 10)
    for m in ms:
        print('  0x%04X  %2d locked  %s' % (m, bin(m).count('1'), names(m)))
