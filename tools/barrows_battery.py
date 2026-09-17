"""Battery for the Barrows: the dig in, the climb out, the sarcophagi and the six brothers.

Everything about the Barrows except the scripts was already in the cache and on the maps, and
nothing about it was clickable. That shape is what this battery is built around: the risk here is
not logic, it is ADDRESSING. Six mounds, six crypts, six staircases, six sarcophagi, six brothers
and six bits, all named alike and all easy to cross-wire in a way that compiles, runs, and quietly
sends the player who dug into Torag's mound out of Karil's staircase.

So none of the geometry is trusted from the constants. The mounds are RE-MEASURED off
maps/m55_51.jm2 every run - they are terrain, not locs, because Old School digs into them - and the
crypt tiles are re-measured off maps/m55_151.jm2 against the map's own loc occupancy. The brothers'
numbers are compared against tools/barrowsspec.json, which records Old School's monster infoboxes,
rather than against themselves.

    python3 tools/barrows_battery.py
"""
import json, os, re, sys
from collections import deque

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='', errors='replace').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

BROS = ('ahrim', 'dharok', 'guthan', 'karil', 'torag', 'verac')
SPEC = json.load(open(os.path.join(C, 'tools/barrowsspec.json')))

CONST = read('scripts/areas/area_barrows/configs/barrows.constant')
VARP  = read('scripts/areas/area_barrows/configs/barrows.varp')
RS2   = read('scripts/areas/area_barrows/scripts/barrows.rs2')
STAIRS = read('scripts/ladders+stairs/scripts/stairs.rs2')
SPADE  = read('scripts/general_use/scripts/spade.rs2')
NPCCFG = read('scripts/_unpack/377/all.npc')

def consts(txt):
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r'(?m)^\^(\w+)\s*=\s*(.+?)\s*$', txt)}
K = consts(CONST)

def coord(lit):
    """level_mapx_mapz_localx_localz -> (level, mapx, mapz, x, z)"""
    p = lit.split('_')
    return tuple(int(v) for v in p) if len(p) == 5 else None

def nocomment(txt):
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

def blocks(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[([\w.]+)\]', b)
        if not m: continue
        d = {}
        for l in b.split('\n')[1:]:
            l = l.split('//')[0].strip()
            if '=' in l:
                k, v = l.split('=', 1)
                d.setdefault(k, []).append(v)
        out[m.group(1)] = d
    return out

def param(d, key):
    for pv in d.get('param', []):
        k, _, v = pv.partition(',')
        if k.strip() == key: return v.strip()
    return None

# --- the map, read rather than trusted --------------------------------------------------------
def heights(path, level=0):
    out = {}
    for line in read(path).split('==== MAP ====')[1].split('==== ')[0].split('\n'):
        m = re.match(r'^(\d+) (\d+) (\d+):(.*)$', line.strip())
        if not m: continue
        if int(m.group(1)) != level: continue
        h = re.search(r'\bh(-?\d+)', m.group(4))
        if h: out[(int(m.group(2)), int(m.group(3)))] = int(h.group(1))
    return out

def locrows(path):
    out = []
    for line in read(path).split('==== LOC ====')[1].split('==== ')[0].split('\n'):
        # "level x z: id shape [rot]" - THE ROTATION IS OMITTED WHEN IT IS ZERO, which is what
        # hid two of the six staircases from the first version of this parser.
        m = re.match(r'^(\d+) (\d+) (\d+): (\d+) (\d+)(?: (\d+))?\s*$', line.strip())
        if m: out.append(tuple(int(m.group(i) or 0) for i in range(1, 7)))
    return out

LOCNAME = {}
for line in read('pack/loc.pack').split('\n'):
    if '=' in line:
        i, n = line.strip().split('=', 1)
        LOCNAME[int(i)] = n
LOCID = {v: k for k, v in LOCNAME.items()}

LOCSIZE = {}
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if not f.endswith('.loc'): continue
        for b in re.split(r'(?m)^(?=\[)', read(os.path.relpath(os.path.join(root, f), C))):
            m = re.match(r'\[(\w+)\]', b)
            if not m: continue
            w = re.search(r'(?m)^width=(\d+)', b)
            l = re.search(r'(?m)^length=(\d+)', b)
            LOCSIZE[m.group(1)] = (int(w.group(1)) if w else 1, int(l.group(1)) if l else 1)

def footprint(x, z, locid, rot):
    w, l = LOCSIZE.get(LOCNAME.get(locid), (1, 1))
    if rot % 2 == 1: w, l = l, w
    return {(x + dx, z + dz) for dx in range(w) for dz in range(l)}

# =============================================================================================
print('--- the six mounds are the map\'s own six hills')
# =============================================================================================
MOUND = {b: coord(K.get('barrows_mound_' + b, '')) for b in BROS}
check(all(MOUND.values()), 'all six ^barrows_mound_* are coordinate literals: %s'
      % [b for b in BROS if not MOUND[b]])
check(sorted(set((c[0], c[1], c[2]) for c in MOUND.values())) == [(0, 55, 51)],
      'all six sit on level 0 of m55_51, the surface map: %s'
      % sorted(set((c[0], c[1], c[2]) for c in MOUND.values())))

H = heights('maps/m55_51.jm2', 0)
# A mound is a connected island of high ground, so the map is asked for its islands rather than
# for tiles that beat their neighbours: every one of the six peaks is a PLATEAU two to six tiles
# across, so a strict local-maximum test finds nothing at all - which is how this check started.
THRESH = 70
seen, comps = set(), []
for k in H:
    if H[k] < THRESH or k in seen: continue
    q, c = deque([k]), []
    seen.add(k)
    while q:
        cur = q.popleft(); c.append(cur)
        for dx in (-1, 0, 1):
            for dz in (-1, 0, 1):
                n = (cur[0] + dx, cur[1] + dz)
                if n not in seen and H.get(n, 0) >= THRESH:
                    seen.add(n); q.append(n)
    comps.append(c)
check(len(comps) == 6, 'm55_51 has exactly six hills above h%d - one per brother, no seventh to '
                       'confuse a pairing: %d' % (THRESH, len(comps)))

PEAKS = [{t for t in c if H[t] == max(H[x] for x in c)} for c in comps]
owner = {}
for b in BROS:
    _, _, _, x, z = MOUND[b]
    hit = [i for i, p in enumerate(PEAKS) if (x, z) in p]
    owner[b] = hit[0] if len(hit) == 1 else None
    check(len(hit) == 1, '%s\'s mound coordinate (%d,%d) is a PEAK tile of one hill, not its slope '
          '(h%s, hill peaks at h%s)'
          % (b, x, z, H.get((x, z)), max(H[t] for t in comps[hit[0]]) if hit else '?'))
check(len(set(owner.values())) == 6 and None not in owner.values(),
      'the six coordinates are on six different hills, so no two brothers share a mound')

CENTRE = (sum(MOUND[b][3] for b in BROS) / 6.0, sum(MOUND[b][4] for b in BROS) / 6.0)
def d2(b):
    return (MOUND[b][3] - CENTRE[0]) ** 2 + (MOUND[b][4] - CENTRE[1]) ** 2
check(min(BROS, key=d2) == 'ahrim',
      'Ahrim\'s mound is the most central of the six, which is the wiki\'s own description of it')
check(max(BROS, key=lambda b: H[(MOUND[b][3], MOUND[b][4])]) == 'ahrim',
      'Ahrim\'s mound is also the tallest (h%d), the other half of that description'
      % H[(MOUND['ahrim'][3], MOUND['ahrim'][4])])

# EAST is +x and NORTH is +z, and the wiki gives each brother's crypt a compass direction. With
# five outer hills against five directions the pairing is forced, not chosen - so it is checkable.
WANT = {'north': (0, +1), 'south': (0, -1), 'east': (+1, 0), 'west': (-1, 0),
        'north-east': (+1, +1), 'north-west': (-1, +1),
        'south-east': (+1, -1), 'south-west': (-1, -1)}
for b in BROS:
    face = SPEC['mound_compass'][b]
    if face == 'centre': continue
    wx, wz = WANT[face]
    dx, dz = MOUND[b][3] - CENTRE[0], MOUND[b][4] - CENTRE[1]
    ok = (wx == 0 or (dx > 0) == (wx > 0)) and (wz == 0 or (dz > 0) == (wz > 0))
    if wx == 0: ok = ok and abs(dx) < abs(dz)
    if wz == 0: ok = ok and abs(dz) < abs(dx)
    check(ok, '%s\'s mound lies %s of the middle, as the wiki places his crypt (dx%+.1f dz%+.1f)'
          % (b, face, dx, dz))

RADIUS = int(K['barrows_mound_radius'])
worst = min(((max(abs(MOUND[a][3] - MOUND[b][3]), abs(MOUND[a][4] - MOUND[b][4])), a, b)
             for i, a in enumerate(BROS) for b in BROS[i + 1:]))
check(worst[0] > 2 * RADIUS,
      'no two mounds are within two radii of each other, so the dig can never match two brothers '
      '(closest pair %s/%s at %d tiles, radius %d)' % (worst[1], worst[2], worst[0], RADIUS))

# =============================================================================================
print()
print('--- the six crypt tiles are real floor next to the right staircase')
# =============================================================================================
CRYPT = {b: coord(K.get('barrows_crypt_' + b, '')) for b in BROS}
check(all(CRYPT.values()), 'all six ^barrows_crypt_* are coordinate literals')
check(sorted(set((c[0], c[1], c[2]) for c in CRYPT.values())) == [(3, 55, 151)],
      'all six sit on level 3 of m55_151, where the crypts are built')
check(len(set((c[3], c[4]) for c in CRYPT.values())) == 6, 'the six crypt tiles are six tiles')

ROWS = locrows('maps/m55_151.jm2')
BLOCKED = set()
for lv, x, z, i, shape, rot in ROWS:
    if lv == 3 and shape in (9, 10, 11):
        BLOCKED |= footprint(x, z, i, rot)

PLACED = {}
for name in [f'barrow_{b}_sarcophagus' for b in BROS] + [f'barrows_stairs_{b}' for b in BROS]:
    i = LOCID.get(name)
    hits = [r for r in ROWS if r[3] == i and r[0] == 3]
    PLACED[name] = hits
    check(len(hits) == 1, '%s is on the map exactly once at level 3 (%d placements)'
          % (name, len(hits)))

for b in BROS:
    _, _, _, x, z = CRYPT[b]
    check((x, z) not in BLOCKED,
          '%s\'s drop tile (%d,%d) is free floor - nothing on the map stands on it' % (b, x, z))
    st = PLACED['barrows_stairs_' + b]
    if not st: continue
    foot = footprint(st[0][1], st[0][2], st[0][3], st[0][5])
    near = min(max(abs(x - fx), abs(z - fz)) for fx, fz in foot)
    check(near == 1, '%s\'s drop tile is beside HIS OWN staircase (%d tiles away)' % (b, near))

SARC = {}
for b in BROS:
    hits = PLACED['barrow_%s_sarcophagus' % b]
    if hits:
        SARC[b] = footprint(hits[0][1], hits[0][2], hits[0][3], hits[0][5])
for b in BROS:
    _, _, _, x, z = CRYPT[b]
    dist = {o: min(max(abs(x - fx), abs(z - fz)) for fx, fz in f) for o, f in SARC.items()}
    nearest = min(dist, key=lambda o: dist[o])
    check(nearest == b, '%s\'s drop tile is nearest HIS OWN sarcophagus, not a neighbour\'s '
          '(nearest: %s at %d)' % (b, nearest, dist[nearest]))

# =============================================================================================
print()
print('--- digging in, climbing out')
# =============================================================================================
DIG = nocomment(RS2.split('[proc,barrows_mound_dig]', 1)[1].split('\n[', 1)[0])
for b in BROS:
    # The branch that matches this mound must telejump to THIS crypt: the one cross-wiring that
    # would be invisible in play until somebody noticed the wrong sarcophagus in front of them.
    m = re.search(r'distance\(coord, \^barrows_mound_%s\)[^{]*\{\s*\$crypt = \^barrows_crypt_(\w+);'
                  % b, DIG)
    check(bool(m) and m.group(1) == b,
          '%s\'s mound leads to %s\'s crypt' % (b, m.group(1) if m else 'nothing'))
check(len(re.findall(r'\^barrows_mound_radius', DIG)) == 6,
      'all six branches measure against ^barrows_mound_radius, so one edit moves all six')
check(DIG.count('return(false)') == 1
      and re.search(r'if \(\$crypt = null\) \{\s*return\(false\);', DIG),
      'the dig reports false in exactly one place, and only when no mound matched - anything else '
      'would let a mound dig fall through to a clue')
check(DIG.strip().endswith('return(true);') and 'p_telejump($crypt);' in DIG,
      'and reports true after the telejump, which is what spends the dig')

SP = nocomment(SPADE)
check('~barrows_mound_dig' in SP, 'spade.rs2 asks the Barrows at all')
check(SP.index('~barrows_mound_dig') < SP.index('p_arrivedelay'),
      'spade.rs2 asks the Barrows BEFORE its own dig, so a mound dig is never also a clue dig')
check('~barrows_mound_dig' in re.split(r'(?m)^\[', SP)[
          [i for i, s in enumerate(re.split(r'(?m)^\[', SP)) if s.startswith('opheld1,spade')][0]],
      'and it asks inside [opheld1,spade] rather than in some other trigger')

for b in BROS:
    m = re.search(r'\[oploc1,barrows_stairs_%s\]\s*@barrows_climb_out\(\^barrows_mound_(\w+)\);' % b,
                  nocomment(STAIRS))
    check(bool(m) and m.group(1) == b,
          '%s\'s staircase climbs out onto %s\'s mound' % (b, m.group(1) if m else 'nothing'))
check(not re.search(r'\[oploc1,barrows_stairs_\w+\][^[]*unhandled_stairs', nocomment(STAIRS)),
      'no Barrows staircase is left routed to @unhandled_stairs')

# =============================================================================================
print()
print('--- the sarcophagi hand over one brother each')
# =============================================================================================
SEARCH = nocomment(RS2.split('[proc,barrows_search]', 1)[1].split('\n[', 1)[0])
check(SEARCH.index('testbit(%barrows_killed') < SEARCH.index('npc_add('),
      'the sarcophagus reads the kill bit BEFORE it adds anybody, so a dead brother cannot be '
      'searched out of his own box twice')
check('^barrows_brother_life' in SEARCH and '^max_32bit_int' not in SEARCH,
      'a woken brother is added with ^barrows_brother_life, not forever')
check('npc_setmode(opplayer2)' in SEARCH and '%aggressive_npc = npc_uid' in SEARCH,
      'and he comes out fighting, and interrupts what the player was doing')

# Every sarcophagus the CACHE has, not every one the script happens to mention.
for b in BROS:
    m = re.search(r'\[oploc1,barrow_%s_sarcophagus\] ~barrows_search\((\w+), \^barrows_bit_(\w+)\);'
                  % b, nocomment(RS2))
    check(bool(m) and m.group(1) == 'barrows_' + b and m.group(2) == b,
          'barrow_%s_sarcophagus hands over %s against bit %s'
          % (b, m.group(1) if m else 'nobody', m.group(2) if m else '-'))
cachesarcs = sorted(n for n in LOCID if re.fullmatch(r'barrow_\w+_sarcophagus', n))
handled = sorted(re.findall(r'\[oploc1,(barrow_\w+_sarcophagus)\]', nocomment(RS2)))
check(cachesarcs == handled,
      'every sarcophagus in the cache has a handler and none is invented: %s' % (
          sorted(set(cachesarcs) ^ set(handled)) or 'all six'))

# =============================================================================================
print()
print('--- a death sets his own bit, in his own trigger')
# =============================================================================================
for b in BROS:
    body = nocomment(RS2).split('[ai_queue3,barrows_%s]' % b, 1)
    check(len(body) == 2, 'barrows_%s has a death trigger' % b)
    if len(body) != 2: continue
    body = body[1].split('\n[', 1)[0]
    m = re.search(r'%barrows_killed = setbit\(%barrows_killed, \^barrows_bit_(\w+)\);', body)
    check(bool(m) and m.group(1) == b,
          '%s\'s death sets %s\'s bit' % (b, m.group(1) if m else 'nothing'))
    check('gosub(npc_death);' in body and 'npc_findhero = ^false' in body,
          '%s\'s death still dies properly and only credits a player it found' % b)
    check('npc_findhero' in body and 'setbit' in body
          and body.index('npc_findhero') < body.index('setbit'),
          '%s finds his killer before he writes to him' % b)
# THE COMPILE-TIME LESSON, pinned so a tidy-up cannot undo it: route this write through a label or
# a proc and the [ 'p_active_player' ] it needs lands on the CALL SITE, which is the trigger, where
# npc_findhero has not run yet - "Attempt to access uninitialized pointer", and no way round it
# except putting the write back where it is now.
holders = [seg for seg in re.split(r'(?m)^(?=\[)', nocomment(RS2))
           if 'setbit(%barrows_killed' in seg]
check(len(holders) == len(BROS)
      and all(h.startswith('[ai_queue3,barrows_') for h in holders),
      'the bit is written only inside the death triggers, never behind a label or a proc: %s'
      % [h.split(']', 1)[0] + ']' for h in holders])

check(re.search(r'(?m)^protect=no$', VARP) and re.search(r'(?m)^scope=perm$', VARP),
      '%barrows_killed is protect=no (an npc death can write it) and scope=perm (a run survives '
      'a logout)')
check('=barrows_killed' in read('pack/varp.pack'),
      'and barrows_killed is in pack/varp.pack, without which it will not resolve at all')
bits = {b: int(K['barrows_bit_' + b]) for b in BROS}
check(sorted(bits.values()) == [0, 1, 2, 3, 4, 5],
      'the six bits are 0-5 with no collision: %s' % bits)
check(int(K['barrows_brothers']) == len(BROS),
      '^barrows_brothers counts the brothers there are: %s' % K['barrows_brothers'])

# =============================================================================================
print()
print('--- the brothers themselves, against Old School\'s infoboxes')
# =============================================================================================
NPC = blocks(NPCCFG)
SEQS = set()
for line in read('pack/seq.pack').split('\n'):
    if '=' in line: SEQS.add(line.strip().split('=', 1)[1])
DEFBONUS = {'stab': 'stabdefence', 'slash': 'slashdefence', 'crush': 'crushdefence',
            'magic': 'magicdefence', 'ranged': 'rangedefence'}
for b in BROS:
    s = SPEC['brothers'][b]
    d = NPC.get('barrows_' + b, {})
    check(bool(d), 'barrows_%s exists as an npc' % b)
    if not d: continue
    got = {k: int(d[k][0]) for k in s['levels'] if k in d}
    check(got == s['levels'], '%s\'s levels are the infobox\'s: %s' % (b, got))
    check(d.get('vislevel', [None])[0] == str(s['combat']),
          '%s is combat %d on the right-click' % (b, s['combat']))
    check(param(d, 'attackrate') == str(s['speed']),
          '%s attacks every %d ticks' % (b, s['speed']))
    check(param(d, 'damagetype') == '^%s_style' % s['style'],
          '%s attacks with %s, which is the style his max hit is listed against (got %s)'
          % (b, s['style'], param(d, 'damagetype')))
    for k, pname in DEFBONUS.items():
        want = s['defensive'][k]
        got = int(param(d, pname) or 0)
        check(got == want, '%s\'s %s defence is %+d' % (b, k, want) if got == want
              else '%s\'s %s defence is %+d, infobox says %+d' % (b, k, got, want))
    check(int(param(d, 'strengthbonus') or 0) == s['aggressive']['strengthbonus'],
          '%s\'s strength bonus is %+d' % (b, s['aggressive']['strengthbonus']))
    check(int(param(d, 'magicattack') or 0) == s['aggressive']['magicbonus'],
          '%s\'s magic bonus is %+d' % (b, s['aggressive']['magicbonus']))
    check(int(param(d, 'rangeattack') or 0) == s['aggressive']['rangedbonus'],
          '%s\'s ranged bonus is %+d' % (b, s['aggressive']['rangedbonus']))
    # The infobox gives one melee Attack bonus and it is +0 for all six, so a per-style melee
    # attack bonus cannot be sourced from it - and two of them were sitting here, each a copy of
    # that brother's strength bonus.
    melee = {p: param(d, p) for p in ('stabattack', 'slashattack', 'crushattack')
             if param(d, p) is not None}
    check(s['aggressive']['attackbonus'] != 0 or not melee,
          '%s carries no invented per-style attack bonus (infobox gives +0): %s' % (b, melee or '-'))
    for p in ('attack_anim', 'defend_anim'):
        a = param(d, p)
        check(a is None or a in SEQS, '%s\'s %s is a real animation: %s' % (b, p, a))
    if s['aggressive']['rangedstrength']:
        check(param(d, 'rangedstrength') is None
              and 'rangedstrength' not in read('scripts/engine.rs2'),
              '%s\'s +%d ranged strength has nowhere to go in this engine, and is not faked'
              % (b, s['aggressive']['rangedstrength']))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
