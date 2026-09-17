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
VARBIT = read('scripts/areas/area_barrows/configs/barrows.varbit')
ENUM  = read('scripts/areas/area_barrows/configs/barrows.enum')
RS2   = read('scripts/areas/area_barrows/scripts/barrows.rs2')
TUN   = read('scripts/areas/area_barrows/scripts/barrows_tunnels.rs2')
CHEST = read('scripts/areas/area_barrows/scripts/barrows_chest.rs2')
TELE  = read('scripts/areas/area_barrows/scripts/barrows_teleport.rs2')
COMBAT = read('scripts/areas/area_barrows/scripts/barrows_combat.rs2')
DEATH = read('scripts/skill_combat/scripts/npc/npc_death.rs2')
ALLVARP = read('scripts/_unpack/377/all.varp')
ALLVARBIT = read('scripts/_unpack/377/all.varbit')
ALLLOC = read('scripts/_unpack/377/all.loc')
CHESTSPEC = json.load(open(os.path.join(C, 'tools/barrowschestspec.json')))
sys.path.insert(0, os.path.join(C, 'tools'))
import barrowsmaze
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
check(SEARCH.index('testbit(%barrows_kills') < SEARCH.index('npc_add('),
      'the sarcophagus reads the kill bit BEFORE it adds anybody, so a dead brother cannot be '
      'searched out of his own box twice')
check('^barrows_brother_life' in SEARCH and '^max_32bit_int' not in SEARCH,
      'a woken brother is added with ^barrows_brother_life, not forever')
check('npc_setmode(opplayer2)' in SEARCH and '%aggressive_npc = npc_uid' in SEARCH,
      'and he comes out fighting, and interrupts what the player was doing')
# A BROTHER WHO IS ALREADY UP IS NOT IN HIS BOX. The kill bit only says he is dead; searching the
# sarcophagus of a brother who is out and still alive used to add a second copy of him, and two of
# him is two sets of armour for one fight.
check('~barrows_brother_here($brother) = ^true' in SEARCH
      and SEARCH.index('~barrows_brother_here') < SEARCH.index('npc_add('),
      'and a box whose brother is already out hands over nobody')
here = nocomment(CHEST.split('[proc,barrows_brother_here]', 1)[1].split('\n[', 1)[0])
# HuntVis: 0 is OFF, 1 is LINEOFSIGHT, 2 is LINEOFWALK. A presence test across a tunnel needs OFF,
# or a brother two rooms away answers "not here" and a second one is handed out.
check(re.search(r'npc_findall\(coord, \$brother, 64, 0\);', here),
      'and it looks for him without needing to see him, which is HuntVis 0')

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
    m = re.search(r'%barrows_killed_(\w+) = \^true;', body)
    check(bool(m) and m.group(1) == b,
          '%s\'s death sets %s\'s bit' % (b, m.group(1) if m else 'nothing'))
    check('gosub(npc_death);' in body and 'npc_findhero = ^false' in body,
          '%s\'s death still dies properly and only credits a player it found' % b)
    check(bool(m) and 'npc_findhero' in body and body.index('npc_findhero') < m.start(),
          '%s finds his killer before he writes to him' % b)
# THE COMPILE-TIME LESSON, pinned so a tidy-up cannot undo it: route this write through a label or
# a proc and the [ 'p_active_player' ] it needs lands on the CALL SITE, which is the trigger, where
# npc_findhero has not run yet - "Attempt to access uninitialized pointer", and no way round it
# except putting the write back where it is now.
holders = [seg for seg in re.split(r'(?m)^(?=\[)', nocomment(RS2))
           if re.search(r'%barrows_killed_\w+ = \^true', seg)]
check(len(holders) == len(BROS)
      and all(h.startswith('[ai_queue3,barrows_') for h in holders),
      'the bit is written only inside the death triggers, never behind a label or a proc: %s'
      % [h.split(']', 1)[0] + ']' for h in holders])

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

# =============================================================================================
print()
print('--- the run is stored in the cache\'s own varbits, not in a var of ours')
# =============================================================================================
def varbits(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', b)
        if not m:
            continue
        base = re.search(r'(?m)^basevar=(\w+)', b)
        lo = re.search(r'(?m)^startbit=(\d+)', b)
        hi = re.search(r'(?m)^endbit=(\d+)', b)
        if base and lo and hi:
            out[m.group(1)] = (base.group(1), int(lo.group(1)), int(hi.group(1)))
    return out

VB = varbits(ALLVARBIT)
VB.update(varbits(VARBIT))
VBPACK = [l.strip().split('=', 1)[1] for l in read('pack/varbit.pack').split('\n') if '=' in l]

# THE CHECK THAT MAKES testbit(%barrows_kills, $bit) LEGITIMATE. Every read of a brother's kill
# goes to the base var by bit number and every write goes through the named varbit, so the two
# only agree while the cache's bit order and ^barrows_bit_* stay the same six in the same order.
for b in BROS:
    name = 'barrows_killed_' + b
    check(VB.get(name) == ('barrows_kills', bits[b], bits[b]),
          '%s is bit %d of %%barrows_kills, which is where ^barrows_bit_%s points: %s'
          % (name, bits[b], b, VB.get(name)))
mon = VB.get('barrows_killed_monster')
check(mon and mon[0] == 'barrows_kills' and (1 << (mon[2] - mon[1] + 1)) > int(K['barrows_potential_cap']),
      'barrows_killed_monster holds the reward potential and is wide enough for %s of it: bits %s'
      % (K['barrows_potential_cap'], mon[1:] if mon else '-'))
check(VB.get('barrows_chest_open', ('', 0, 0))[0] == 'barrows_kills',
      'barrows_chest_open is the chest multiloc\'s own bit, on the same var')

# The two this round added, and the only two it needed.
check(VB.get('barrows_entry_crypt') == ('barrows', 0, 2),
      'barrows_entry_crypt sits in %%barrows bits 0-2, below everything the cache uses: %s'
      % (VB.get('barrows_entry_crypt'),))
check(VB.get('barrows_chest_paid') == ('barrows', 3, 3),
      'barrows_chest_paid sits in %%barrows bit 3: %s' % (VB.get('barrows_chest_paid'),))
ours = {'barrows_entry_crypt', 'barrows_chest_paid'}
theirs = [(n, v) for n, v in VB.items() if v[0] == 'barrows' and n not in ours]
clash = [n for n, v in theirs
         for o in ours if VB[o][1] <= v[2] and v[1] <= VB[o][2]]
check(not clash, 'and neither overlaps a varbit the cache already had: %s' % (clash or 'none'))
for n in sorted(ours):
    check(n in VBPACK, '%s is in pack/varbit.pack, without which it will not resolve' % n)

# THE INVENTED VAR IS GONE. %barrows_killed was a duplicate of barrows_killed_* written before
# anybody looked at the cache's varbits; this is the check that keeps it from coming back.
allrs2 = []
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if f.endswith('.rs2'):
            allrs2.append((os.path.relpath(os.path.join(root, f), C),
                           read(os.path.relpath(os.path.join(root, f), C))))
check(not [p for p, t in allrs2 if '%barrows_killed ' in t or '%barrows_killed=' in t],
      'nothing reads or writes a %barrows_killed varp any more')
check('barrows_killed\n' not in read('pack/varp.pack')
      and '=barrows_killed\n' not in read('pack/varp.pack'),
      'and it is out of pack/varp.pack too')
kills = ALLVARP.split('[barrows_kills]', 1)
check(len(kills) == 2 and re.match(r'\s*protect=no', kills[1]),
      '[barrows_kills] is protect=no, which is what lets a death write it at all')

# =============================================================================================
print()
print('--- the maze is chosen from rows that the map says can be finished')
# =============================================================================================
def enumblock(name):
    b = ENUM.split('[%s]' % name, 1)
    return b[1].split('\n[', 1)[0] if len(b) == 2 else ''

MZ = enumblock('barrows_mazes')
masks = [int(v) for _, v in re.findall(r'(?m)^val=(\d+),(\d+)$', MZ)]
ids = [int(k) for k, _ in re.findall(r'(?m)^val=(\d+),(\d+)$', MZ)]
check(len(masks) == int(K['barrows_mazes']),
      'barrows_mazes holds ^barrows_mazes = %s rows: %d' % (K['barrows_mazes'], len(masks)))
check(ids == list(range(len(ids))), 'keyed 0..%d with no gap, which is what random() indexes'
      % (len(ids) - 1))
check(len(set(masks)) == len(masks), 'and no row is a duplicate of another')
check(re.search(r'(?m)^default=0$', MZ),
      'a miss opens every door rather than shutting one, because obj 0 of a maze is a run nobody '
      'can finish')
# RE-MEASURED, not trusted: every row is flood-filled against maps/m55_151.jm2 on every run.
bad = [m for m in masks if not barrowsmaze.solves(m)]
check(not bad, 'every maze still leaves all four ladders able to walk to the chest: %s'
      % ['0x%04X' % m for m in bad])
check(all(0 < m < 0xFFFF for m in masks),
      'every maze shuts something and leaves something open')
check(not barrowsmaze.solves(0xFFFF),
      'and the map agrees that shutting all sixteen would NOT be finishable, so the check above '
      'can fail')
# The mask's bit order IS the varbits' bit order, which is the whole reason one write lays a maze.
for i, L in enumerate(barrowsmaze.LETTERS):
    want = int(K['barrows_door_first']) + i
    check(VB.get('barrows_door_' + L) == ('barrows', want, want),
          'gate %s is %%barrows bit %d, so bit %d of a mask is its lock: %s'
          % (L, want, i, VB.get('barrows_door_' + L)))
check(int(K['barrows_door_last']) - int(K['barrows_door_first']) + 1 == 16,
      '^barrows_door_first..last is exactly sixteen bits wide')

# =============================================================================================
print()
print('--- the twenty-four pieces, and only from a brother who was killed')
# =============================================================================================
EQ = enumblock('barrows_equipment')
eq = dict((int(k), v) for k, v in re.findall(r'(?m)^val=(\d+),(\w+)$', EQ))
check(len(eq) == len(BROS) * int(K['barrows_equip_pieces']),
      'barrows_equipment holds four pieces for each of the six brothers: %d' % len(eq))
check(re.search(r'(?m)^default=null$', EQ),
      'and says null out loud on a miss, because obj 0 is a real item')
objpack = set(l.strip().split('=', 1)[1] for l in read('pack/obj.pack').split('\n') if '=' in l)
for i in range(len(BROS) * 4):
    b = BROS[i // 4]
    name = eq.get(i, '')
    check(name.startswith('barrows_%s_' % b) and name in objpack,
          'piece %d is one of %s\'s and is a real obj: %s' % (i, b, name or '-'))
check(sorted(eq.values()) == sorted(set(eq.values())), 'no piece is listed twice')
# The address the chest builds, brother*4 + 0..3, is the address this table is keyed on.
check('multiply($bit, ^barrows_equip_pieces)' in CHEST
      and 'random(^barrows_equip_pieces)' in CHEST,
      'the chest addresses it as brother * four + a piece, the order it is written in')
check('~barrows_nth_killed(random($brothers))' in CHEST,
      'and picks the brother from the ones that are DEAD, evenly')
nk = [nocomment(x) for x in CHEST.split('[proc,barrows_nth_killed]', 1)]
check(len(nk) == 2 and 'testbit(%barrows_kills, $bit) = ^true' in nk[1],
      '~barrows_nth_killed counts the killed bits rather than all six')
nu = [nocomment(x) for x in TUN.split('[proc,barrows_nth_unkilled]', 1)]
check(len(nu) == 2 and 'testbit(%barrows_kills, $bit) = ^false' in nu[1],
      '...and its mirror, which a door uses, counts the live ones')

# =============================================================================================
print()
print('--- the chest pays what the wiki says it pays')
# =============================================================================================
CS = CHESTSPEC
check(int(K['barrows_rolls_base']) == CS['rolls']['base']
      and int(K['barrows_rolls_max']) == CS['rolls']['max'],
      'one roll to start and seven at most')
check('min(add(^barrows_rolls_base, $brothers), ^barrows_rolls_max)' in CHEST,
      'and a roll for every brother killed in between')
check(int(K['barrows_equip_base']) == CS['equipment']['base']
      and int(K['barrows_equip_step']) == CS['equipment']['step'],
      'the armour chance is 1/(%d - %d * brothers)' % (CS['equipment']['base'],
                                                       CS['equipment']['step']))
for n, odds in sorted(CS['equipment']['odds'].items(), key=lambda kv: int(kv[0])):
    got = int(K['barrows_equip_base']) - int(K['barrows_equip_step']) * int(n)
    check(got == odds, 'which is 1/%d with %s brother(s) down: 1/%d' % (odds, n, got))
check(int(K['barrows_potential_cap']) == CS['potential']['monster_cap']
      and int(K['barrows_potential_brother']) == CS['potential']['per_brother']
      and int(K['barrows_potential_max']) == CS['potential']['max'],
      'the pool caps at %d, a brother is worth %d, and the two make %d'
      % (CS['potential']['monster_cap'], CS['potential']['per_brother'], CS['potential']['max']))
check(int(K['barrows_potential_cap'])
      + len(BROS) * int(K['barrows_potential_brother']) == int(K['barrows_potential_max']),
      '...and that is arithmetic rather than three numbers that happen to be written down')

BANDS = [(r['item'], r['rp'], r['low'], r['high']) for r in CS['table']]
KCONST = {'mindrune': 'mind', 'chaosrune': 'chaos', 'deathrune': 'death', 'bloodrune': 'blood',
          'boltrack': 'boltrack', 'keyhalf': 'keyhalf', 'dragonmed': 'dragonmed'}
for item, rp, lo, hi in BANDS:
    if item == 'coins':
        continue
    c = K.get('barrows_rp_' + KCONST[item])
    check(c is not None and int(c) == rp,
          '%s needs %d reward potential before it can be rolled: %s' % (item, rp, c))
edges = [1] + [rp for item, rp, _, _ in BANDS if item != 'coins'] + [int(K['barrows_potential_max']) + 1]
widths = [edges[i + 1] - edges[i] for i in range(len(edges) - 1)]
check(sum(widths) == int(K['barrows_potential_max']),
      'the bands tile 1..%s with nothing left over: %s = %d'
      % (K['barrows_potential_max'], ' + '.join(str(w) for w in widths), sum(widths)))
check(widths == [380, 125, 125, 125, 125, 125, 6, 1],
      'and they are the wiki\'s own widths: %s' % widths)
for item, rp, lo, hi in BANDS:
    key = 'coins' if item == 'coins' else KCONST[item]
    if lo == hi == 1:
        continue
    check(int(K['barrows_loot_%s_low' % key]) == lo
          and int(K['barrows_loot_%s_high' % key]) == hi,
          '%s comes %d-%d at a time' % (item, lo, hi))
# THE ORDER OF THE IF-CHAIN IS THE WHOLE TABLE. Tested ascending it would pay coins for every
# roll, silently, and every band constant would still be right.
chain = re.findall(r'\$roll >= \^barrows_rp_(\w+)', CHEST)
check(chain == ['dragonmed', 'keyhalf', 'boltrack', 'blood', 'death', 'chaos', 'mind'],
      'the chest tests the bands from the top down, or it would pay coins for everything: %s'
      % chain)
PAYS = {'dragonmed': 'dragon_med_helm', 'boltrack': 'barrows_karil_ammo', 'blood': 'bloodrune',
        'death': 'deathrune', 'chaos': 'chaosrune', 'mind': 'mindrune'}
for band, obj in sorted(PAYS.items()):
    seg = CHEST.split('$roll >= ^barrows_rp_%s' % band, 1)
    check(len(seg) == 2 and obj in seg[1].split('} else')[0],
          'the %s band pays %s' % (band, obj))
# The key band holds an if/else of its own for the two halves, so its branch ends at the next
# BAND rather than at the next else - which is what the first version of this check cut on.
seg = CHEST.split('$roll >= ^barrows_rp_keyhalf', 1)
body = seg[1].split('} else if (', 1)[0] if len(seg) == 2 else ''
check('keyhalf1' in body and 'keyhalf2' in body,
      'the key band pays one half of the crystal key or the other')
check('~obj_giveorbank(coins,' in CHEST, 'and everything below the first band is coins')
check('add(random($potential), 1)' in CHEST,
      'the roll is a value in 1..potential, inclusive at both ends, as the wiki words it')
check('~barrows_between' in CHEST and 'add($low, random(add(sub($high, $low), 1)))' in CHEST,
      'and so is every quantity')
# Paying twice, and paying for nothing.
check('%barrows_chest_paid = ^true;' in CHEST, 'looting marks the chest paid')
check('[oploc1,barrows_stone_chest]' in CHEST and '[oploc2,barrows_stone_chest]' in CHEST
      and '~barrows_chest_search' in CHEST.split('[oploc1,barrows_stone_chest]', 1)[1],
      'one op1 handler opens the chest and searches it, branching on the bit the multiloc reads')
loot = nocomment(CHEST.split('[proc,barrows_chest_search]', 1)[1])
check('%barrows_chest_paid = ^true' in loot
      and loot.index('%barrows_chest_paid = ^true') < loot.index('~barrows_reward_roll'),
      '...before it rolls anything, so an interrupted payout cannot be taken twice')
check('%barrows_entry_crypt = ^barrows_entry_none | %barrows_chest_paid = ^true' in loot,
      'and it refuses both a second search and a search with no run behind it')
check('%barrows = 0' not in CHEST and '%barrows_kills = 0' not in CHEST,
      'looting clears NOTHING, because the run is what holds the ladder the player still has to '
      'climb and the brothers a door may still send')
begin = nocomment(TUN.split('[proc,barrows_begin_run]', 1)[1].split('\n[', 1)[0])
check(re.search(r'(?m)^%barrows_chest_paid = \^false;$', begin)
      and re.search(r'(?m)^%barrows_kills = 0;$', begin)
      and '~barrows_shut_ladders' in begin,
      'the next dig is what clears the last run - its bits, its chest and its ladder')
check('%barrows_entry_crypt ! ^barrows_entry_none & %barrows_chest_paid = ^false' in begin,
      '...and a run still owed its chest is never cleared out from under the player')

# =============================================================================================
print()
print('--- what comes through a door')
# =============================================================================================
D = CS['door_spawn']
check(int(K['barrows_spawn_denom']) == D['_denominator'], 'the door rolls out of 128')
check(int(K['barrows_spawn_brother']) == D['brother'],
      'a brother on %d of them' % D['brother'])
check(int(K['barrows_spawn_skeleton']) - int(K['barrows_spawn_brother']) == D['skeleton'],
      'a skeleton on %d' % D['skeleton'])
check(int(K['barrows_spawn_bloodworm']) - int(K['barrows_spawn_skeleton']) == D['bloodworm'],
      'a bloodworm on %d' % D['bloodworm'])
check(int(K['barrows_spawn_denom']) - int(K['barrows_spawn_bloodworm']) == D['crypt_rat'],
      'and a crypt rat on the remaining %d' % D['crypt_rat'])
check(int(K['barrows_spawn_crowd']) == D['crowd'],
      'nothing comes through into a room already holding %d' % D['crowd'])
spawn = nocomment(TUN.split('[proc,barrows_door_spawn]', 1)[1].split('\n[', 1)[0])
check('%barrows_entry_crypt = ^barrows_entry_none' in spawn,
      'a door with no run behind it lets nothing out')
check('~barrows_crowd($where) >= ^barrows_spawn_crowd' in spawn,
      'and neither does a crowded room')
check(spawn.index('^barrows_spawn_crowd') < spawn.index('random(^barrows_spawn_denom)'),
      '...checked before the roll, so a crowded room does not eat a brother')
check('%barrows_chest_paid = ^true' in spawn and '$roll = 0;' in spawn,
      'after the chest has paid, every door is a brother - the wiki\'s own guarantee')
NPCPACK = set(l.strip().split('=', 1)[1] for l in read('pack/npc.pack').split('\n') if '=' in l)
for n in ('barrows_skeleton_armed', 'barrows_skeleton_unarmed', 'barrows_bloodworm', 'barrows_rat'):
    check(n in spawn and n in NPCPACK, '%s is real and is what a door can send' % n)
sb = nocomment(TUN.split('[proc,barrows_spawn_brother]', 1)[1].split('\n[', 1)[0])
check('~barrows_nth_unkilled(random($left))' in sb,
      'a door\'s brother is one the player has NOT killed, picked evenly')
check('sub(^barrows_brothers, ~barrows_brothers_killed)' in sb
      and '$left <= 0' in sb,
      '...and with all six down it sends something else rather than nothing or a seventh brother')

# Every gate on the map has a lock bit, and the locked form is the one with no option on it -
# which is why a locked door needs no handler and no "it will not budge" message.
LOCB = blocks(ALLLOC)
check('op1' in LOCB.get('barrows_door_unlocked_l', {})
      and 'op1' in LOCB.get('barrows_door_unlocked_r', {}),
      'the unlocked door carries Open')
check(not [o for o in ('op1', 'op2', 'op3', 'op4', 'op5')
           if o in LOCB.get('barrows_door_locked_l', {})
           or o in LOCB.get('barrows_door_locked_r', {})],
      'and the locked one carries no option at all, which is 377\'s own "this one will not open"')
check('[oploc1,_barrows_door] ~barrows_door_through;' in TUN,
      'one handler serves every doorway, through the category the shells carry')
for L in barrowsmaze.LETTERS:
    for half in ('l', 'r'):
        d = LOCB.get('barrows_door_%s_%s' % (L, half), {})
        check(d.get('multivar', [None])[0] == 'barrows_door_' + L
              and 'multiloc' in d,
              'barrows_door_%s_%s reads gate %s\'s own bit' % (L, half, L))
check('~agility_exactmove(human_walk_style' in TUN and 'p_teleport($end)' in TUN,
      'a door is walked through rather than opened, because the cache has no open form of it')

# =============================================================================================
print()
print('--- the passage in and the ladder out')
# =============================================================================================
walk, doors, ladders, chesttile = barrowsmaze.tunnel()
for L in sorted(ladders):
    c = coord(K['barrows_chamber_tile_' + L])
    check(c and (c[0], c[1], c[2]) == (0, 55, 151),
          'chamber %s\'s drop tile is on the tunnel level: %s' % (L, K['barrows_chamber_tile_' + L]))
    check(c and (c[3], c[4]) in walk,
          'chamber %s\'s drop tile is floor a player can stand on' % L)
    lx, lz = ladders[L]
    check(c and max(abs(c[3] - lx), abs(c[4] - lz)) == 1,
          'chamber %s\'s drop tile is beside ITS OWN ladder' % L)
ct = {L: coord(K['barrows_chamber_tile_' + L]) for L in sorted(ladders)}
check(len(set((v[3], v[4]) for v in ct.values())) == len(ct), 'the four drop tiles are four tiles')
idx = {L: int(K['barrows_chamber_' + L]) for L in sorted(ladders)}
check(sorted(idx.values()) == list(range(int(K['barrows_chambers']))),
      'the four chambers are numbered 0..%d, which is what random() rolls: %s'
      % (int(K['barrows_chambers']) - 1, idx))
for L in sorted(ladders):
    m = re.search(r'case \^barrows_chamber_%s : return\(\^barrows_chamber_tile_(\w+)\);' % L,
                  nocomment(TUN))
    check(bool(m) and m.group(1) == L,
          'chamber %s answers with %s\'s tile' % (L, m.group(1) if m else 'nothing'))
    m = re.search(r'case \^barrows_chamber_%s : %%barrows_chamber_(\w+) = \^true;' % L,
                  nocomment(TUN))
    check(bool(m) and m.group(1) == L, 'and opening chamber %s lights %s\'s ladder'
          % (L, m.group(1) if m else 'nothing'))
check(LOCB.get('barrows_ladder_a', {}).get('multivar', [None])[0] == 'barrows_chamber_a',
      'a ladder is a multiloc on its chamber\'s bit, so it does not exist until the run opens it')
check('[oploc1,_barrows_ladder]' in TUN,
      'and all four are served by one handler, through their own category')
for b in BROS:
    m = re.search(r'case \^barrows_bit_%s : return\(\^barrows_mound_(\w+)\);' % b,
                  nocomment(TUN.split('[proc,barrows_entry_mound]', 1)[1]))
    check(bool(m) and m.group(1) == b,
          'the ladder puts a player who came in by %s\'s crypt back on %s\'s mound'
          % (b, m.group(1) if m else 'nothing'))
psg = nocomment(TUN.split('[proc,barrows_passage]', 1)[1].split('\n[', 1)[0])
check('~barrows_open_chamber' in psg and '$chamber < 0' in psg,
      'coming back down the same run reuses the chamber it opened rather than rolling a new one')
check('enum(int, int, barrows_mazes, random(^barrows_mazes))' in psg,
      'and the maze is laid once, on the way in')
check('~barrows_passage' in RS2 and '%barrows_entry_crypt = add($bit, 1)' in RS2,
      'the sarcophagus of the entry crypt gives the passage instead of its brother')
check('~barrows_begin_run' in RS2.split('[proc,barrows_mound_dig]', 1)[1].split('\n[', 1)[0],
      'and the run is drawn by the first dig, before any box is searched')

# =============================================================================================
print()
print('--- reward potential')
# =============================================================================================
check('~barrows_potential;' in nocomment(DEATH),
      '[proc,npc_death] pays reward potential, which is the one place every death passes through')
check(nocomment(DEATH).index('~barrows_potential') > nocomment(DEATH).index('npc_arrivedelay'),
      '...while the npc is still there to be asked what it was')
pot = nocomment(TUN.split('[proc,barrows_potential]', 1)[1].split('\n[', 1)[0])
check('inzone(^barrows_tunnel_sw, ^barrows_tunnel_ne, npc_coord)' in pot,
      'and nothing outside the tunnels pays anything')
check('~barrows_brother_bit(npc_type) >= 0' in pot,
      'a BROTHER pays nothing into the pool: his two points are added by the chest off his own '
      'bit, and the 1000 + 6*2 cap is what says he is worth two and not his combat level')
check('npc_findhero = ^false' in pot and '%barrows_entry_crypt = ^barrows_entry_none' in pot,
      'and a kill with no player or no run behind it pays nothing')
check('min(add(%barrows_killed_monster, nc_vislevel(npc_type)), ^barrows_potential_cap)' in pot,
      'what it pays is the dead thing\'s own combat level, capped at ^barrows_potential_cap')
check('multiply($brothers, ^barrows_potential_brother)' in CHEST,
      'and the chest is where the brothers\' two points each are added')
NPCS = blocks(NPCCFG)
for n, lvl in sorted(CS['tunnel_monsters'].items()):
    got = NPCS.get(n, {}).get('vislevel', [None])[0]
    check(got == str(lvl), '%s is combat %d, which is what it pays: %s' % (n, lvl, got))
check(int(K['barrows_spawn_range']) > 0 and 'npc_findallany($where, ^barrows_spawn_range, 1)' in TUN,
      'the crowd is counted with npc_findallany around the tile stepped onto')

# =============================================================================================
print()
print('--- the Barrows teleport')
# =============================================================================================
T = CS['teleport']
TOBJ = blocks(read('scripts/areas/area_barrows/configs/barrows.obj')).get('barrows_teleport', {})
check(bool(TOBJ), 'barrows_teleport exists as an obj')
check('barrows_teleport' in objpack, '...and is in pack/obj.pack')
check(TOBJ.get('stackable', [None])[0] == 'yes', 'it stacks, which is the point of a tab')
check(TOBJ.get('iop1', [None])[0] == 'Break', 'and its one option is Break')
# THE SAME ICON CAMERA AS THE FOURTEEN LECTERN TABLETS, which is what makes it read as a tablet
# in the pack rather than a thing of its own. Compared against a tablet, not against a number.
TAB = blocks(read('scripts/skill_construction/configs/poh_tablets.obj')).get('poh_tab_varrock', {})
for f in ('2dzoom', '2dxan', '2dyof'):
    check(TOBJ.get(f) == TAB.get(f) and TOBJ.get(f) is not None,
          'its %s is the lectern tablets\' own: %s' % (f, TOBJ.get(f, ['-'])[0]))
check(TOBJ.get('model', [None])[0] == 'obj_barrows_teleport'
      and 'obj_barrows_teleport' in set(l.strip().split('=', 1)[1]
                                        for l in read('pack/model.pack').split('\n') if '=' in l),
      'its model is imported, named and packed')
check(os.path.exists(os.path.join(C, 'models/obj/obj_barrows_teleport.ob2')),
      '...and the .ob2 is actually in the tree')
check(K['barrows_tele_dest'] == T['destination'],
      'it lands on %s, the tile Corey asked for: %s' % (T['destination'], K['barrows_tele_dest']))
check(int(K['barrows_tele_rate']) == T['rate'],
      'the chest pays one at 1/%d' % T['rate'])
check(int(K['barrows_tele_low']) == T['low'] and int(K['barrows_tele_high']) == T['high'],
      'and pays %d to %d of them' % (T['low'], T['high']))
check('random(^barrows_tele_rate) = 0' in CHEST
      and '~barrows_between(^barrows_tele_low, ^barrows_tele_high)' in CHEST,
      'which is what the chest actually rolls')
gives = sorted(p for p, t in allrs2
               if re.search(r'(?:inv_add|obj_add|~obj_giveorbank)\([^;]*\bbarrows_teleport\b',
                            nocomment(t)))
check(gives == ['scripts/areas/area_barrows/scripts/barrows_chest.rs2'],
      'the chest is the only thing in the game that hands one over: %s' % gives)
check('[opheld1,barrows_teleport]' in TELE and 'inv_del(inv, barrows_teleport, 1);' in TELE,
      'breaking one spends exactly one')
check('~pre_tele_checks(coord) = false' in TELE and '~wilderness_level(coord) > 20' in TELE,
      'and it is not a way out of deep wilderness, a duel or the trawler')

# =============================================================================================
print()
print('--- every handler is on a loc that is actually on the map')
# =============================================================================================
# THE FAULT THIS SECTION EXISTS FOR. A multiloc has a shell on the map and children it resolves
# to, and the ops the player sees come from the CHILD - so a trigger on the child looks right and
# reads right. It never fires. Player.getOpTrigger looks the script up on
# LocType.get(target.type), the type that is ON THE MAP, and does not resolve the multiloc,
# even though OpLocHandler resolved one moments earlier to decide whether the op exists at all.
# Three of this round's four handlers were written on children: both halves of every door, all
# four ladders and the chest, so the tunnels had no working doors and the chest could not be
# opened. Every check that existed asked whether the trigger was WRITTEN DOWN. This one asks
# whether it can run.
LOCCFG = {}
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if not f.endswith('.loc'):
            continue
        LOCCFG.update(blocks(read(os.path.relpath(os.path.join(root, f), C))))

PLACED = set()
for m in ('maps/m55_51.jm2', 'maps/m55_151.jm2'):
    for line in read(m).split('==== LOC ====')[1].split('==== ')[0].split('\n'):
        mm = re.match(r'^(\d+) (\d+) (\d+): (\d+) (\d+)(?: (\d+))?\s*$', line.strip())
        if mm:
            PLACED.add(LOCNAME.get(int(mm.group(4)), '?'))
PLACEDCAT = {}
for n in PLACED:
    c = LOCCFG.get(n, {}).get('category', [None])[0]
    if c:
        PLACEDCAT.setdefault(c, []).append(n)

def ops_of(name):
    """Every op number the player can ever see on this loc, its multiloc children included."""
    d = LOCCFG.get(name, {})
    out = set()
    for i in range(1, 6):
        if 'op%d' % i in d:
            out.add(i)
    for mv in d.get('multiloc', []):
        child = mv.split(',', 1)[1].strip() if ',' in mv else ''
        cd = LOCCFG.get(child, {})
        for i in range(1, 6):
            if 'op%d' % i in cd:
                out.add(i)
    return out

BARROWSRS2 = [('areas/area_barrows/scripts/barrows.rs2', RS2),
              ('areas/area_barrows/scripts/barrows_tunnels.rs2', TUN),
              ('areas/area_barrows/scripts/barrows_chest.rs2', CHEST),
              ('ladders+stairs/scripts/stairs.rs2', STAIRS)]
trigs = []
for where, txt in BARROWSRS2:
    for m in re.finditer(r'(?m)^\[oploc(\d),(\w+)\]', nocomment(txt)):
        if 'barrow' in m.group(2):
            trigs.append((where, int(m.group(1)), m.group(2)))
check(len(trigs) >= 10, 'the Barrows declares %d loc handlers to check' % len(trigs))
for where, op, name in trigs:
    if name.startswith('_'):
        cat = name[1:]
        holders = PLACEDCAT.get(cat, [])
        check(bool(holders),
              'op%d on category %s: %d locs on the Barrows maps carry it'
              % (op, cat, len(holders)))
        for h in holders:
            check(op in ops_of(h),
                  '...and %s really has an op%d for it to catch: %s'
                  % (h, op, sorted(ops_of(h)) or 'no ops at all'))
    else:
        check(name in PLACED,
              'op%d on %s: that loc is on one of the Barrows maps' % (op, name))
        check(op in ops_of(name),
              '...and it has an op%d, on itself or on a multiloc child: %s'
              % (op, sorted(ops_of(name)) or 'no ops at all'))
# The reverse, which is the dead-click question: every op a Barrows loc on the map can show has
# a handler somewhere in the tree.
ALLTRIG = set()
for p_, t in allrs2:
    for m in re.finditer(r'(?m)^\[oploc(\d),(\w+)\]', nocomment(t)):
        ALLTRIG.add((int(m.group(1)), m.group(2)))
dead = []
for n in sorted(PLACED):
    if not n.startswith('barrow'):
        continue
    cat = LOCCFG.get(n, {}).get('category', [None])[0]
    for op in sorted(ops_of(n)):
        if (op, n) in ALLTRIG or (cat and (op, '_' + cat) in ALLTRIG):
            continue
        dead.append('%s op%d "%s"' % (n, op, (LOCCFG.get(n, {}).get('op%d' % op, ['?'])[0])))
check(not dead, 'no Barrows loc on either map has an option nothing handles: %s' % (dead or 'none'))

# =============================================================================================
print()
print('--- the dig ends, and the tunnels pay nothing')
# =============================================================================================
dig = nocomment(RS2.split('[proc,barrows_mound_dig]', 1)[1].split('\n[', 1)[0])
# .rindex on a string that is not there RAISES, and a crash is not a catch - ninth time in this
# project, so the membership test comes first.
check('anim(human_dig_long, 0);' in dig and 'anim(null, 0);' in dig
      and dig.rindex('anim(null, 0);') > dig.index('p_telejump'),
      'the dig animation is stopped after the telejump - human_dig_long is loops=8 and outlives '
      'the script that started it, so without this the player keeps digging inside the crypt')
DIGSEQ = read('scripts/_unpack/377/all.seq').split('[human_dig_long]', 1)
check(len(DIGSEQ) == 2 and re.search(r'(?m)^loops=[2-9]', DIGSEQ[1].split('\n[', 1)[0]),
      '...which is worth checking because the seq really does loop: %s'
      % (re.search(r'(?m)^loops=(\d+)', DIGSEQ[1].split('\n[', 1)[0]).group(1)
         if len(DIGSEQ) == 2 and re.search(r'(?m)^loops=(\d+)', DIGSEQ[1].split('\n[', 1)[0])
         else 'no loops line'))

# NOTHING IN THE TUNNELS DROPS ANYTHING. The two skeletons were on the ordinary skeleton table -
# coins, arrows, runes, a herb and a shot at the ultra-rare - in a place whose entire reward is
# the chest. And death_drop DEFAULTS TO BONES, so a monster that says nothing still drops bones
# through [ai_queue3,_] -> ~npc_default_death: saying null out loud is the only way to drop
# nothing.
TUNNELMON = sorted(CS['tunnel_monsters'])
for n in TUNNELMON:
    d = NPCS.get(n, {})
    check(param(d, 'death_drop') == 'null',
          '%s drops nothing, said out loud because death_drop defaults to bones: %s'
          % (n, param(d, 'death_drop')))
    owners = sorted(p_ for p_, t in allrs2
                    if re.search(r'(?m)^\[ai_queue3,%s\]' % n, nocomment(t)))
    check(not owners, '...and has no death trigger of its own to put it back on a table: %s'
          % owners)
check(param(NPCS.get('death_drop_probe', {}), 'death_drop') is None
      and re.search(r'(?m)^default=bones$',
                    read('scripts/skill_combat/configs/npc_combat.param')
                    .split('[death_drop]', 1)[1].split('\n[', 1)[0]),
      'and death_drop really does default to bones, which is why the line above is needed')

# =============================================================================================
print()
print('--- the brothers fight the way Old School says, and hit as hard')
# =============================================================================================
# THE MAX HITS ARE RE-DERIVED, not stored. Every one of them comes out of the engine's own formula
# from the bonuses the infoboxes give, so this section is what says the stat blocks are right -
# and it is the check that would have caught Karil's missing ranged strength, because without it
# his max hit computes to 11 against the wiki's 20.
def eff_stat(level):
    # ~combat_effective_stat(level, 100) is scale(max(100,100), 100, level), which is level.
    return level + 9  # the 'style bonus' of 1 that every npc gets

def engine_maxhit(level, bonus):
    # ~combat_maxhit(~combat_stat(...)) = (effective * (bonus + 64) + 320) / 640
    return (eff_stat(level) * (bonus + 64) + 320) // 640

for b in BROS:
    sp = SPEC['brothers'][b]
    d = NPC.get('barrows_' + b, {})
    e = sp['effect']
    if e['style'] == 'ranged':
        got = engine_maxhit(sp['levels']['ranged'], int(param(d, 'rangebonus') or 0))
    elif e['style'] == 'magic':
        got = int(K['barrows_ahrim_maxhit'])
    else:
        got = engine_maxhit(sp['levels']['strength'], int(param(d, 'strengthbonus') or 0))
    # The expected number stays OUT of the leading text: a mutation to the spec would otherwise
    # rewrite the message this check is identified by.
    check(got == sp['maxhit'],
          "%s's max hit comes out of his own record through the engine's formula: %d, wiki %d"
          % (b, got, sp['maxhit']))
# Dharok at one hitpoint, which is the whole of Wretched Strength.
dh = SPEC['brothers']['dharok']
base = engine_maxhit(dh['levels']['strength'], 105)
check(base + (99 * base) // 100 == dh['maxhit_at_1'],
      "dharok at one hitpoint hits %d, which is his %d plus one per cent of it for each of the 99 "
      'he is missing: %d' % (dh['maxhit_at_1'], base, base + (99 * base) // 100))
check('scale(sub(npc_basestat(hitpoints), npc_stat(hitpoints)), 100, $maxhit)' in COMBAT,
      '...and that is the line that does it')
check(re.search(r'if \(npc_type ! barrows_dharok\) \{\s*return\(\$maxhit\);', COMBAT),
      'and nobody else gets it')

# THE AI. A bare damagetype does not stop the engine handing an npc the melee AI every npc gets:
# [ai_queue1,_] sets opplayer2 and [ai_opplayer2,_] swings. This is the check for the bug Corey
# found - Ahrim walking up and hitting people with his staff.
for b in BROS:
    st = SPEC['brothers'][b]['effect']['style']
    if st == 'melee':
        check('[ai_opplayer2,barrows_%s] ~barrows_melee;' % b in COMBAT,
              '%s swings, through his own handler' % b)
        check('[ai_queue1,barrows_%s]' % b not in COMBAT,
              '...and keeps the default melee retaliate, which is the right one for him')
    else:
        check('[ai_queue1,barrows_%s] ~npc_default_retaliate_ap;' % b in COMBAT,
              '%s retaliates AT RANGE, which is what sets applayer2' % b)
        check('[ai_applayer2,barrows_%s]' % b in COMBAT
              and '[ai_opplayer2,barrows_%s] npc_setmode(applayer2);' % b in COMBAT,
              '...and both being walked up to and standing off send him to the same %s attack' % st)
check('~npc_meleeattack' not in COMBAT,
      'no brother goes through the plain melee attack, because every one of them has something '
      'the plain one does not do')

# VERAC'S PIERCE skips the rolls rather than weighting them: "ignoring prayer and armour" means
# the attack roll that returns zero under Protect from Melee is never consulted, and neither is
# the player's defence.
pierce = nocomment(COMBAT.split('[proc,barrows_melee_damage]', 1)[1].split('\n[', 1)[0])
check(int(K['barrows_verac_pierce_pct']) == SPEC['brothers']['verac']['effect']['chance'],
      "verac's prayer pierce is %d%%" % SPEC['brothers']['verac']['effect']['chance'])
check('npc_type = barrows_verac & random(100) < ^barrows_verac_pierce_pct' in pierce
      and pierce.index('barrows_verac_pierce_pct') < pierce.index('~npc_melee_attack_roll'),
      '...and a pierced hit is decided BEFORE the rolls, so neither prayer nor armour is asked')
check('return(add(random($maxhit), 1));' in pierce,
      'and it lands for one to his max, never nothing')

# THE FOUR EFFECTS THAT NEED A PICTURE have one, and it is the cache's own - all four spotanims
# were sitting in 377 unused.
SPOT = set(l.strip().split('=', 1)[1] for l in read('pack/spotanim.pack').split('\n') if '=' in l)
efx = nocomment(COMBAT.split('[proc,barrows_effect]', 1)[1].split('\n[', 1)[0])
for b in BROS:
    e = SPEC['brothers'][b]['effect']
    got = int(K.get('barrows_%s_effect_pct' % b, -1)) if b != 'dharok' and b != 'verac' else e['chance']
    if b not in ('dharok', 'verac'):
        check(got == e['chance'], "%s's %s fires on %d%% of his landed hits: %s"
              % (b, e['name'], e['chance'], got))
    if e['spotanim']:
        check(e['spotanim'] in SPOT, "%s's %s has the cache's own graphic: %s"
              % (b, e['name'], e['spotanim']))
        # Slice HIS case out of the switch rather than regexing across it: a lazy match that
        # wandered into the next case would call any brother's graphic his.
        seg = efx.split('case barrows_%s :' % b, 1)
        seg = seg[1].split('\n    case ', 1)[0] if len(seg) == 2 else ''
        plays = re.findall(r'spotanim_npc\((\w+),', seg)
        check(plays == [e['spotanim']],
              '...and it is the one HIS case plays: %s' % (plays or 'none'))
    else:
        check('case barrows_%s :' % b not in efx,
              '%s has no case in the effect switch, because his effect is a number' % b)
check(int(K['barrows_ahrim_strength_drain']) == 5, "Ahrim's aura takes five levels of Strength")
check(int(K['barrows_karil_agility_pct']) == 20, "Karil's bolt takes a fifth of Agility")
check(int(K['barrows_torag_energy_pct']) == 20, "Torag's hammers take a fifth of the energy left")
check('npc_statheal(hitpoints, $damage, 0);' in efx,
      'Guthan heals for THE DAMAGE HE DEALT, which is why the effect takes it as an argument')
check('scale($percent, 100, runenergy)' in COMBAT,
      "and Torag's fifth is a fifth of what is LEFT, not a fifth of the bar")
# Every player-side write goes through a queue: an npc script has the player but not protected
# access to him, which is the same wall the kill bits ran into.
for q in ('barrows_ahrim_drain', 'barrows_karil_drain', 'barrows_torag_drain'):
    check('[queue,%s]' % q in COMBAT and 'queue(%s, 0,' % q in COMBAT,
          '%s reaches the player through his own queue' % q)
check('stat_sub(strength, $amount, 0);' in COMBAT and 'stat_sub(agility, 0, $percent);' in COMBAT,
      "and the two stat drains are flat for Ahrim's five levels and a percentage for Karil's fifth")

# AHRIM CASTS A REAL SPELL, so the freeze and debuff paths are the engine's.
check('~get_spell_data(^iban_blast)' in COMBAT
      and SPEC['ahrim_spell']['spell'] == 'iban_blast',
      "Ahrim's attack is Iban's Blast, the one dark burst in the spell table")
check('~npc_player_hit_roll(^magic_style)' in COMBAT,
      '...and his aura rolls on THE SAME hit roll the cast makes, not a second one')
check('~npc_cast_spell(~barrows_ahrim_debuff' in COMBAT
      and int(K['barrows_ahrim_debuff_odds']) == 4,
      'and one cast in four is Confuse, Weaken or Curse, which the wiki lists')
dbf = nocomment(COMBAT.split('[proc,barrows_ahrim_debuff]', 1)[1].split('\n[', 1)[0])
check(sorted(re.findall(r'\^(confuse|weaken|curse)', dbf)) == ['confuse', 'curse', 'weaken'],
      '...all three of them: %s' % sorted(re.findall(r'\^(\w+)\)', dbf)))
check('param=rangebonus,55' in NPCCFG.replace('\r\n', '\n'),
      "Karil's +55 ranged strength is on his record, which is the only reason his max hit is 20")
check(param(NPC.get('barrows_karil', {}), 'proj_travel') == 'crossbowbolt_travel',
      '...and he has a bolt to fire, which ~npc_rangeattack needs: %s'
      % param(NPC.get('barrows_karil', {}), 'proj_travel'))

# =============================================================================================
print()
print('--- the prayer drain')
# =============================================================================================
PD = SPEC['prayer_drain']
check(int(K['barrows_drain_interval']) == PD['interval_ticks'],
      'a face appears every %d ticks, which is the wiki\'s %d seconds'
      % (PD['interval_ticks'], PD['interval_seconds']))
check(int(K['barrows_drain_base']) == PD['base'],
      'and takes %d points before any brother is down' % PD['base'])
check(int(K['barrows_drain_base']) + len(BROS) * PD['per_brother'] == PD['max'],
      '...rising to %d with all six dead, which is arithmetic and not a third number' % PD['max'])
drain = nocomment(COMBAT.split('[timer,barrows_prayer_drain]', 1)[1].split('\n[', 1)[0])
check('add(^barrows_drain_base, ~barrows_brothers_killed)' in drain,
      'and the rise is one point per brother, counted off the kill bits')
check('inzone(^barrows_crypt_sw, ^barrows_crypt_ne, coord)' in drain
      and 'inzone(^barrows_tunnel_sw, ^barrows_tunnel_ne, coord)' in drain,
      'it drains in the crypts AND the tunnels, which are the same map square two levels apart')
check('cleartimer(barrows_prayer_drain);' in drain,
      '...and takes itself off the moment the player is anywhere else')
check('stat(prayer) = 0' in drain and drain.index('stat(prayer) = 0') < drain.index('stat_sub'),
      'and a player with no prayer left is not told about it every eighteen seconds')
check('~barrows_drain_start;' in nocomment(RS2) and '~barrows_drain_start;' in nocomment(TUN),
      'both ways underground start it - the dig and the passage')
check(coord(K['barrows_crypt_sw']) and coord(K['barrows_crypt_sw'])[0] == 3
      and coord(K['barrows_tunnel_sw'])[0] == 0
      and coord(K['barrows_crypt_sw'])[1:3] == coord(K['barrows_tunnel_sw'])[1:3],
      'and the two zones really are one square at two levels: %s and %s'
      % (K['barrows_crypt_sw'], K['barrows_tunnel_sw']))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
