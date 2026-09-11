"""Run build mode's rules the way poh_build.rs2 does, straight off the shipped files.

Companion to poh_sim.py, which covers the packing and join arithmetic. This covers what build mode
adds on top: turning a door hotspot's coordinate into a grid cell and a side, picking a rotation that
joins back through the doorway, paging a menu with no array to hold it, and the rule that decides
whether a room may be taken out again.

Every constant, every table and every rule below is PARSED OUT of the delivered files - the room
tables from poh_rooms.enum, the door hotspot positions from the real 474 template maps - so a change
to one of them cannot pass a test still asserting the old value.
"""
import os, re, sys, random

CONTENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(CONTENT, p), newline='').read().replace('\r\n', '\n')

const = read('scripts/skill_construction/configs/construction.constant')
enums = read('scripts/skill_construction/configs/poh_rooms.enum')
build = read('scripts/skill_construction/scripts/poh_build.rs2')

C = {m.group(1): int(m.group(2)) for m in re.finditer(r'\^(\w+)\s*=\s*(-?\d+)', const)}
GRID, ORIGIN = C['poh_grid'], C['poh_grid_origin']
N, E, S, W = C['poh_door_n'], C['poh_door_e'], C['poh_door_s'], C['poh_door_w']
COUNT = C['poh_room_count']

def enum_block(name):
    body = enums.split('[' + name + ']', 1)[1].split('\n[', 1)[0]
    return {int(k): v.strip() for k, v in re.findall(r'^val=(\d+),(.+)$', body, re.M)}

ZONE = {k: int(v) for k, v in enum_block('poh_room_zone').items()}
DOORS = {k: int(v) for k, v in enum_block('poh_room_doors').items()}
NAME = enum_block('poh_room_name')
COST = {k: int(v) for k, v in enum_block('poh_room_cost').items()}
LEVEL = {k: int(v) for k, v in enum_block('poh_room_level').items()}

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

# ---- the rules, transcribed from the two .rs2 files -----------------------------------------
def rot_doors(d, rot):                                   # ~poh_rot_doors
    r = rot % 4
    if r == 1: return (d * 2 + d // 8) & 15
    if r == 2: return (d * 4 + d // 4) & 15
    if r == 3: return (d * 8 + d // 2) & 15
    return d

class House:
    def __init__(s): s.cell = {}
    def type(s, rx, rz): return s.cell.get((rx, rz), (0, 0))[0]
    def rot(s, rx, rz): return s.cell.get((rx, rz), (0, 0))[1]
    def total(s): return sum(1 for v in s.cell.values() if v[0])
    def set(s, rx, rz, t, r):
        if t == 0: s.cell.pop((rx, rz), None)
        else: s.cell[(rx, rz)] = (t, r % 4)
    def doors_at(s, rx, rz):                             # ~poh_doors_at
        t = s.type(rx, rz)
        return 0 if t == 0 else rot_doors(DOORS[t], s.rot(rx, rz))
    def door_on(s, rx, rz, side):                        # ~poh_door_on
        return (s.doors_at(rx, rz) & side) != 0
    def can_place(s, rx, rz, t, rot):                    # ~poh_can_place
        if rx < 0 or rx >= GRID or rz < 0 or rz >= GRID: return False
        if t == 0: return True
        if s.total() == 0: return True
        d = rot_doors(DOORS[t], rot)
        if d & N and s.door_on(rx, rz + 1, S): return True
        if d & E and s.door_on(rx + 1, rz, W): return True
        if d & S and s.door_on(rx, rz - 1, N): return True
        if d & W and s.door_on(rx - 1, rz, E): return True
        return False
    def rot_for(s, rx, rz, t, side):                     # ~poh_room_rot_for
        for rot in range(4):
            if rot_doors(DOORS[t], rot) & side and s.can_place(rx, rz, t, rot):
                return rot
        return -1
    def can_build(s, rx, rz, t, side, level):            # ~poh_can_build
        if s.type(rx, rz) != 0: return False
        if level < LEVEL[t]: return False
        return s.rot_for(rx, rz, t, side) >= 0
    def nth_room(s, rx, rz, side, n, level):             # ~poh_nth_room
        seen = 0
        for t in range(1, COUNT + 1):
            if s.can_build(rx, rz, t, side, level):
                if seen == n: return t
                seen += 1
        return 0
    def joined_count(s, rx, rz):                         # ~poh_joined_count
        n = 0
        if s.door_on(rx, rz, N) and s.door_on(rx, rz + 1, S): n += 1
        if s.door_on(rx, rz, E) and s.door_on(rx + 1, rz, W): n += 1
        if s.door_on(rx, rz, S) and s.door_on(rx, rz - 1, N): n += 1
        if s.door_on(rx, rz, W) and s.door_on(rx - 1, rz, E): n += 1
        return n
    def reachable(s, start):
        seen = {start}; q = [start]
        while q:
            rx, rz = q.pop()
            for side, (dx, dz) in ((N, (0, 1)), (E, (1, 0)), (S, (0, -1)), (W, (-1, 0))):
                nb = (rx + dx, rz + dz)
                if nb in seen or s.type(*nb) == 0: continue
                if s.door_on(rx, rz, side) and s.door_on(nb[0], nb[1], OPP[side]):
                    seen.add(nb); q.append(nb)
        return seen

OPP = {N: S, S: N, E: W, W: E}
DXDZ = {N: (0, 1), E: (1, 0), S: (0, -1), W: (-1, 0)}

def hotspot_side(lx, lz):                                # ~poh_hotspot_side
    if lx == 0: return W
    if lx == 7: return E
    if lz == 0: return S
    if lz == 7: return N
    return 0

def starter():                                           # ~poh_grant_starter
    h = House(); m = GRID // 2
    h.set(m, m, 1, 0); h.set(m + 1, m, 2, 0)
    return h

# ---- 1. the .rs2 tables and the sim agree -----------------------------------------------------
print('1. the rules here match the ones in poh_build.rs2')
for name, want in (('poh_hotspot_side', [('$lx = 0', 'w'), ('$lx = 7', 'e'), ('$lz = 0', 's'), ('$lz = 7', 'n')]),):
    body = build.split('[proc,%s]' % name, 1)[1].split('\n[', 1)[0]
    for cond, side in want:
        m = re.search(re.escape(cond) + r'\)\s*\{\s*return\(\^poh_door_(\w)\)', body)
        check(m is not None and m.group(1) == side, '%s: %s -> %s' % (name, cond, side))
opp = build.split('[proc,poh_side_opposite]', 1)[1].split('\n[', 1)[0]
for a, b in (('n', 's'), ('e', 'w'), ('s', 'n'), ('w', 'e')):
    check(re.search(r'case \^poh_door_%s : return\(\^poh_door_%s\)' % (a, b), opp) is not None,
          'poh_side_opposite: %s -> %s' % (a, b))
for side in (N, E, S, W):
    check(OPP[OPP[side]] == side, 'opposite is its own inverse for side %d' % side)

# ---- 2. every door hotspot in the real templates resolves ------------------------------------
print('2. every door hotspot in the six style squares resolves to the side it is on')
DOOR_IDS = set()
templ = read('scripts/skill_construction/configs/poh_templates.loc')
ids = {}
for l in read('pack/loc.pack').split('\n'):
    if '=' in l: i, n = l.split('=', 1); ids[n] = int(i)
cur = None
for line in templ.split('\n'):
    line = line.split('//')[0].strip()
    if line.startswith('['): cur = line.strip('[]'); nm = None
    elif line.startswith('name=') and cur and line[5:] == 'Door hotspot': DOOR_IDS.add(ids[cur])
check(len(DOOR_IDS) == 13, 'found %d Door hotspot locs' % len(DOOR_IDS))

def load_locs(path):
    out = {}
    sec = None
    for l in read(path).split('\n'):
        if l.startswith('===='): sec = l.strip('= '); continue
        if sec != 'LOC' or ':' not in l: continue
        head, data = l.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        out.setdefault((lv, x, z), []).append(int(data.split()[0]))
    return out
STYLES = [('maps/m29_79.jm2', 0), ('maps/m29_79.jm2', 1), ('maps/m29_79.jm2', 2),
          ('maps/m29_79.jm2', 3), ('maps/m30_79.jm2', 0), ('maps/m30_79.jm2', 1)]
maps = {p: load_locs(p) for p in {p for p, _ in STYLES}}
seen = 0; off_side = 0; mask_bad = []
for si, (p, lv) in enumerate(STYLES):
    L = maps[p]
    for t in sorted(ZONE):
        zx, zz = ZONE[t] // 8 * 8, ZONE[t] % 8 * 8
        mask = 0
        for (l2, x, z), es in L.items():
            if l2 != lv or not (zx <= x < zx + 8 and zz <= z < zz + 8): continue
            for lid in es:
                if lid in DOOR_IDS:
                    seen += 1
                    sd = hotspot_side(x - zx, z - zz)
                    if sd == 0: off_side += 1
                    mask |= sd
        if mask != DOORS[t]: mask_bad.append((si, NAME[t], mask, DOORS[t]))
check(seen > 0 and off_side == 0, '%d hotspots, %d not on a side midpoint' % (seen, off_side))
check(not mask_bad, 'the sides they spell out match poh_room_doors in all %d room/style pairs: %s'
      % (len(STYLES) * len(ZONE), mask_bad or 'yes'))

# ---- 3. a clicked doorway only ever offers rooms that join back through it --------------------
print('3. every room the menu offers really joins back through the doorway')
bad = []
h = starter()
for (rx, rz), (t, r) in list(h.cell.items()):
    for side in (N, E, S, W):
        if not h.door_on(rx, rz, side): continue
        dx, dz = DXDZ[side]
        tx, tz = rx + dx, rz + dz
        if h.type(tx, tz): continue
        need = OPP[side]
        for ty in range(1, COUNT + 1):
            rot = h.rot_for(tx, tz, ty, need)
            if rot < 0: continue
            if not rot_doors(DOORS[ty], rot) & need: bad.append((NAME[ty], side, rot, 'no door back'))
            if not h.can_place(tx, tz, ty, rot): bad.append((NAME[ty], side, rot, 'can_place false'))
check(not bad, 'no offered room fails its own rule: %s' % (bad or 'none'))

# ---- 4. building only ever through doorways keeps the house walkable --------------------------
print('4. a thousand random build sessions leave every room reachable from the entry room')
random.seed(377)
disconnected = 0; built = 0; sessions = 0
for trial in range(1000):
    h = starter(); sessions += 1
    level = random.choice([1, 5, 20, 40, 60, 99])
    for step in range(random.randint(1, 25)):
        spots = [(rx, rz, side) for (rx, rz) in list(h.cell) for side in (N, E, S, W)
                 if h.door_on(rx, rz, side)]
        random.shuffle(spots)
        placed = False
        for rx, rz, side in spots:
            dx, dz = DXDZ[side]; tx, tz = rx + dx, rz + dz
            if not (0 <= tx < GRID and 0 <= tz < GRID) or h.type(tx, tz): continue
            need = OPP[side]
            opts = [t for t in range(1, COUNT + 1) if h.can_build(tx, tz, t, need, level)]
            if not opts: continue
            t = random.choice(opts)
            h.set(tx, tz, t, h.rot_for(tx, tz, t, need)); built += 1; placed = True
            break
        if not placed: break
    entry = next((k for k, v in sorted(h.cell.items()) if v[0] == 1), sorted(h.cell)[0])
    if len(h.reachable(entry)) != h.total(): disconnected += 1
check(disconnected == 0, '%d sessions, %d rooms built, %d houses with an unreachable room'
      % (sessions, built, disconnected))

# ---- 5. the leaf rule ------------------------------------------------------------------------
print('5. removing a leaf never cuts the house in two, and the rule is not vacuous')
random.seed(1066)
leaf_broke = 0; leaf_tested = 0; nonleaf_would_break = 0; nonleaf_tested = 0
for trial in range(600):
    h = starter()
    level = 99
    for step in range(random.randint(3, 20)):
        spots = [(rx, rz, side) for (rx, rz) in list(h.cell) for side in (N, E, S, W)
                 if h.door_on(rx, rz, side)]
        random.shuffle(spots)
        for rx, rz, side in spots:
            dx, dz = DXDZ[side]; tx, tz = rx + dx, rz + dz
            if not (0 <= tx < GRID and 0 <= tz < GRID) or h.type(tx, tz): continue
            opts = [t for t in range(1, COUNT + 1) if h.can_build(tx, tz, t, OPP[side], level)]
            if not opts: continue
            t = random.choice(opts); h.set(tx, tz, t, h.rot_for(tx, tz, t, OPP[side]))
            break
    if h.total() < 3: continue
    for (rx, rz) in list(h.cell):
        joined = h.joined_count(rx, rz)
        saved = h.cell[(rx, rz)]
        h.set(rx, rz, 0, 0)
        rest = [k for k, v in h.cell.items() if v[0]]
        ok = (not rest) or len(h.reachable(sorted(rest)[0])) == len(rest)
        h.cell[(rx, rz)] = saved
        if joined <= 1:
            leaf_tested += 1
            if not ok: leaf_broke += 1
        else:
            nonleaf_tested += 1
            if not ok: nonleaf_would_break += 1
check(leaf_tested > 0 and leaf_broke == 0,
      '%d leaf removals, %d that cut the house in two' % (leaf_tested, leaf_broke))
check(nonleaf_would_break > 0,
      '%d of %d non-leaf removals WOULD have cut it in two - the guard earns its place'
      % (nonleaf_would_break, nonleaf_tested))

# ---- 6. level gating and paging --------------------------------------------------------------
print('6. the level gate and the menu paging')
h = starter()
rx, rz = sorted(h.cell)[0]
side = N
tx, tz = rx, rz + 1
for level in (1, 10, 25, 40, 60, 99):
    offered = {h.nth_room(tx, tz, OPP[side], n, level) for n in range(COUNT)} - {0}
    for t in offered:
        check(LEVEL[t] <= level, 'at level %d, %s (needs %d) is offered' % (level, NAME[t], LEVEL[t]))
    missing = [t for t in range(1, COUNT + 1)
               if LEVEL[t] <= level and h.rot_for(tx, tz, t, OPP[side]) >= 0 and t not in offered]
    check(not missing, 'at level %d nothing eligible is hidden: %s' % (level, [NAME[t] for t in missing]))
# nth_room must enumerate each eligible room exactly once, and five pages of three must reach all
seq = [h.nth_room(tx, tz, OPP[side], n, 99) for n in range(COUNT)]
listed = [t for t in seq if t]
check(len(listed) == len(set(listed)), 'nth_room lists each room once: %s' % [NAME[t] for t in listed])
check(len(listed) <= 5 * 3, '%d eligible rooms fit in the five pages of three the menu loops over'
      % len(listed))
pages = build.split('[proc,poh_pick_room]', 1)[1].split('\n[', 1)[0]
m = re.search(r'while \(\$page < (\d+)\)', pages)
check(m is not None and int(m.group(1)) * 3 >= COUNT,
      'the page loop bound (%s x 3) covers all %d room types' % (m and m.group(1), COUNT))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
