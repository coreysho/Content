"""Run the furniture packing and menu rules the way poh_furniture.rs2 does, off the shipped files.

The third simulator, after poh_sim.py (rooms) and poh_build_sim.py (build mode). Bit packing is the
part no compile check can see: a field one bit short silently truncates, two fields that overlap
silently corrupt each other, and neither shows up until a player's house comes back wrong.

Every constant and every table is PARSED OUT of the delivered files.
"""
import os, re, sys, random, itertools

CONTENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(CONTENT, p), newline='').read().replace('\r\n', '\n')

const = read('scripts/skill_construction/configs/construction.constant')
enums = read('scripts/skill_construction/configs/poh_furniture.enum')
rs2 = read('scripts/skill_construction/scripts/poh_furniture.rs2')
ops = read('scripts/skill_construction/scripts/poh_furn_ops.rs2')

C = {m.group(1): int(m.group(2)) for m in re.finditer(r'\^(\w+)\s*=\s*(-?\d+)', const)}
SLOTS, ITEMS = C['poh_furn_slots'], C['poh_furn_items']
BIT = {k[len('poh_furn_bit_'):]: v for k, v in C.items() if k.startswith('poh_furn_bit_')}
# Widths are derived from where the NEXT field starts, so adding a field to the record adds it here
# too and nothing has to be kept in step by hand. The top field's width is checked against the .rs2
# by check 1 below; `lit` is one bit and is never written by ~poh_furn_pack (~poh_furn_light flips
# it afterwards), so it gets its width from the constants like the rest.
_edges = sorted(BIT.values()) + [31]
WIDTH = {k: next(e for e in _edges if e > v) - v for k, v in BIT.items()}
WIDTH['lit'] = 1
# The TOP field cannot get its width from the next field's start - there is no next field - so it
# comes out of the .rs2's own range instead.
WIDTH['item_hi'] = int(re.search(r'\^poh_furn_bit_item_hi \+ (\d+)\)', rs2).group(1)) + 1

def table(name):
    body = enums.split('[' + name + ']', 1)[1].split('\n[', 1)[0]
    return {int(k): v.strip() for k, v in re.findall(r'^val=(\d+),(.+)$', body, re.M)}
FAM = {k: int(v) for k, v in table('poh_furn_fam').items()}
LEVEL = {k: int(v) for k, v in table('poh_furn_level').items()}
WOOD = {k: int(v) for k, v in table('poh_furn_wood').items()}
PLANKS = {k: int(v) for k, v in table('poh_furn_planks').items()}
NAME = table('poh_furn_name')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

# ---- the engine's own bit ops (NumberOps.ts), same as poh_sim.py -----------------------------
def setbit_range_toint(num, value, start, end):
    mask = (1 << (end - start + 1)) - 1
    return (num & ~(mask << start)) | (min(value, mask) << start)
def getbit_range(num, start, end):
    a = 31 - end
    return ((num << a) & 0xFFFFFFFF) >> (start + a)

# The item number is split across two ranges - the low byte at `item` and the high seven bits at
# `item_hi`, above `lit` - so that widening it from 8 bits could not move anything an existing save
# had already written. LO is read out of the .rs2's own modulo, not assumed.
LO = int(re.search(r'setbit_range_toint\(\$v, modulo\(\$item, (\d+)\)', rs2).group(1))

def pack(rx, rz, lx, lz, angle, item):                   # ~poh_furn_pack
    v = 0
    for k, val in (('rx', rx), ('rz', rz), ('lx', lx), ('lz', lz),
                   ('angle', angle % 4), ('item', item % LO), ('item_hi', item // LO)):
        v = setbit_range_toint(v, val, BIT[k], BIT[k] + WIDTH[k] - 1)
    return v
def field(v, k):                                         # ~poh_furn_field
    if k == 'item':                                      # ~poh_furn_item
        return (getbit_range(v, BIT['item'], BIT['item'] + WIDTH['item'] - 1)
                + getbit_range(v, BIT['item_hi'], BIT['item_hi'] + WIDTH['item_hi'] - 1) * LO)
    return getbit_range(v, BIT[k], BIT[k] + WIDTH[k] - 1)

print('1. the layout in the .rs2 is the layout here')
# the packed value may itself hold a comma (modulo($angle, 4)), so match up to the field constant
for k in WIDTH:
    if k == 'item_hi':
        m = re.search(r'setbit_range_toint\(\$v, divide\(\$item, %d\), \^poh_furn_bit_item_hi, calc\(\^poh_furn_bit_item_hi \+ (\d+)\)\)' % LO, rs2)
        check(m is not None and int(m.group(1)) + 1 == WIDTH[k],
              'the item high byte is %d bits wide in poh_furniture.rs2' % WIDTH[k])
        check(re.search(r'\[proc,poh_furn_item\]\(int \$v\)\(int\)\nreturn\(calc\(~poh_furn_field\(\$v, \^poh_furn_bit_item, %d\) \+ ~poh_furn_field\(\$v, \^poh_furn_bit_item_hi, %d\) \* %d\)\);'
                        % (WIDTH['item'], WIDTH['item_hi'], LO), rs2) is not None,
              '~poh_furn_item reassembles the two halves, and every reader goes through it')
        # Exactly four mentions of the two halves in the whole layer: the two writes in
        # ~poh_furn_pack and the two reads in ~poh_furn_item. Anything else is a reader that would
        # see only part of the number.
        both = rs2 + ops
        check(both.count('^poh_furn_bit_item,') == 2 and both.count('^poh_furn_bit_item_hi,') == 2,
              'only ~poh_furn_pack and ~poh_furn_item touch the halves (%d + %d mentions)'
              % (both.count('^poh_furn_bit_item,'), both.count('^poh_furn_bit_item_hi,')))
        check((1 << (WIDTH['item'] + WIDTH['item_hi'])) > ITEMS,
              '%d pieces fit the %d-bit item number (ceiling %d)'
              % (ITEMS, WIDTH['item'] + WIDTH['item_hi'], (1 << (WIDTH['item'] + WIDTH['item_hi'])) - 1))
        continue
    if k == 'lit':
        # not packed at build time - ~poh_furn_light sets it on a record that already exists
        m = re.search(r'setbit_range_toint\(\$v, 1, \^poh_furn_bit_lit, \^poh_furn_bit_lit\)', ops)
        check(m is not None, 'lit is set one bit at a time by ~poh_furn_light, not by ~poh_furn_pack')
        continue
    m = re.search(r'setbit_range_toint\(.*?\^poh_furn_bit_%s, calc\(\^poh_furn_bit_%s \+ (\d+)\)\)' % (k, k), rs2)
    check(m is not None and int(m.group(1)) + 1 == WIDTH[k],
          '%s is %d bits wide in poh_furniture.rs2' % (k, WIDTH[k]))
check(re.search(r'setbit_range_toint\(\$v, modulo\(\$angle, 4\), \^poh_furn_bit_angle', rs2) is not None,
      'the angle is taken modulo 4 before packing, so it cannot overflow its two bits')
edges = sorted((BIT[k], BIT[k] + WIDTH[k]) for k in WIDTH)
gapless = all(edges[i][1] == edges[i + 1][0] for i in range(len(edges) - 1)) and edges[0][0] == 0
check(gapless, 'the fields run from bit 0 with no gap and no overlap: %s' % edges)
check(edges[-1][1] <= 31, 'a piece fits an int (%d bits)' % edges[-1][1])
ITEM_BITS = WIDTH['item'] + WIDTH['item_hi']
check(ITEMS < (1 << ITEM_BITS), '%d items fit the %d bits of the item number (%d low, %d high)'
      % (ITEMS, ITEM_BITS, WIDTH['item'], WIDTH['item_hi']))
check(SLOTS <= 256, '%d slots' % SLOTS)

print('2. every value that can be packed comes back out unchanged')
bad = []
for rx in range(8):
    for rz in range(8):
        for lx in range(8):
            for lz in range(8):
                for angle in range(4):
                    for item in (1, 2, ITEMS // 2, ITEMS):
                        v = pack(rx, rz, lx, lz, angle, item)
                        got = (field(v, 'rx'), field(v, 'rz'), field(v, 'lx'),
                               field(v, 'lz'), field(v, 'angle'), field(v, 'item'))
                        if got != (rx, rz, lx, lz, angle, item):
                            bad.append((rx, rz, lx, lz, angle, item, got))
check(not bad, '%d combinations round-trip, %d wrong %s' % (8*8*8*8*4*4, len(bad), bad[:2]))
# and a packed piece is never 0, because 0 is what "empty slot" means
zeros = [(rx, rz, lx, lz, a, i) for rx in range(8) for rz in range(8) for lx in range(8)
         for lz in range(8) for a in range(4) for i in (1, ITEMS) if pack(rx, rz, lx, lz, a, i) == 0]
check(not zeros, 'no real piece packs to 0, which is the empty marker: %s' % zeros[:2])

# THE ONE THIS ROUND EARNED. `lit` was appended at the top of the record, above every field that
# already existed, because a save written before it existed has 0 in those bits. Decode a record
# packed WITHOUT it and every old field has to come back unchanged, with lit reading as 0 - unlit,
# which is what it was.
OLD = {k: (BIT[k], WIDTH[k]) for k in WIDTH if k not in ('lit', 'item_hi')}
oldtop = max(b + w for b, w in OLD.values())
check('lit' in WIDTH and BIT['lit'] >= oldtop,
      'lit sits at bit %s, above the %d bits that existed before it' % (BIT.get('lit'), oldtop))
check(BIT['item_hi'] > BIT['lit'],
      'the item high byte sits at bit %d, above lit as well' % BIT['item_hi'])
bad = []
for rx, rz, lx, lz, angle, item in [(0,0,0,0,0,1), (7,7,7,7,3,238), (3,5,2,6,1,63), (1,2,3,4,2,127),
                                    (2,2,5,5,3,255)]:
    v = 0
    for k, (b, w) in OLD.items():
        v |= (dict(rx=rx, rz=rz, lx=lx, lz=lz, angle=angle, item=item)[k] & ((1 << w) - 1)) << b
    got = tuple(field(v, k) for k in ('rx', 'rz', 'lx', 'lz', 'angle', 'item', 'lit'))
    if got != (rx, rz, lx, lz, angle, item, 0):
        bad.append((rx, rz, lx, lz, angle, item, got))
check(not bad, 'a record written before the lit bit and the item high byte existed still decodes: %s'
      % (bad[:2] or '5 shapes checked, including item 255, lit reads 0'))

print('3. the slot scan finds the right piece and nothing else')
random.seed(4525)
store = [0] * SLOTS
placed = {}
for _ in range(SLOTS):
    while True:
        key = (random.randrange(8), random.randrange(8), random.randrange(8), random.randrange(8))
        if key not in placed: break
    item = random.randint(1, ITEMS)
    slot = next(i for i, v in enumerate(store) if v == 0)
    store[slot] = pack(key[0], key[1], key[2], key[3], random.randrange(4), item)
    placed[key] = (slot, item)
def at(rx, rz, lx, lz):                                  # ~poh_furn_at
    for i, v in enumerate(store):
        if v and field(v, 'rx') == rx and field(v, 'rz') == rz \
           and field(v, 'lx') == lx and field(v, 'lz') == lz:
            return i
    return -1
wrong = [k for k, (slot, _) in placed.items() if at(*k) != slot]
check(not wrong, '%d pieces, every one found in its own slot (%d wrong)' % (len(placed), len(wrong)))
check(at(*next(k for k in itertools.product(range(8), repeat=4) if k not in placed)) == -1,
      'an empty tile reports no piece')
check(next((i for i, v in enumerate(store) if v == 0), -1) == -1,
      'with %d pieces stored there is no free slot, so the %dst is refused' % (SLOTS, SLOTS + 1))

print('4. a room takes its own furniture and nothing else')
target = (placed and sorted(placed)[0][0], sorted(placed)[0][1])
before = sum(1 for v in store if v)
doomed = [i for i, v in enumerate(store) if v and (field(v, 'rx'), field(v, 'rz')) == target]
for i in doomed: store[i] = 0                            # ~poh_furn_clear_cell
left = [(field(v, 'rx'), field(v, 'rz')) for v in store if v]
check(target not in left, 'the cleared room has nothing left in it')
check(before - len(doomed) == sum(1 for v in store if v), 'only its %d piece(s) went' % len(doomed))

print('5. the tables agree with each other and with the script')
byfam = {}
for i in range(1, ITEMS + 1):
    byfam.setdefault(FAM[i], []).append(i)
check(sum(len(v) for v in byfam.values()) == ITEMS, 'every item belongs to exactly one family')
for f, its in sorted(byfam.items()):
    labels = [NAME[i] for i in its]
    check(len(set(labels)) == len(labels), 'family %d: %d tiers, %d distinct labels' % (f, len(its), len(set(labels))))
    lv = [LEVEL[i] for i in its]
    check(lv == sorted(lv), 'family %d levels rise with the tier: %s' % (f, lv))
    wd = [WOOD[i] for i in its]
    check(wd == sorted(wd), 'family %d woods do not go backwards: %s' % (f, wd))
# MATERIALS. The plank switches are gone: every piece carries what it costs (poh_furn_mat1/mat2) and
# what it pays (poh_furn_xp), because the garden is built out of bagged plants and limestone rather
# than planks and a rule that only knew about wood could not say that.
MAT1, MAT1N = table('poh_furn_mat1'), {k: int(v) for k, v in table('poh_furn_mat1n').items()}
MAT2, MAT2N = table('poh_furn_mat2'), {k: int(v) for k, v in table('poh_furn_mat2n').items()}
XP = {k: int(v) for k, v in table('poh_furn_xp').items()}
NEED = table('poh_furn_need')
OBJS = {l.split('=', 1)[1] for l in read('pack/obj.pack').split('\n') if '=' in l}
check(sorted(MAT1) == list(range(1, ITEMS + 1)), 'every piece has a first material: %d rows' % len(MAT1))
check(sorted(MAT1N) == list(range(1, ITEMS + 1)), 'every piece says how much of it: %d rows' % len(MAT1N))
bad = [i for i in MAT1 if MAT1[i] not in OBJS] + [i for i in MAT2 if MAT2[i] not in OBJS]
check(not bad, 'every material is a real obj: %s' % (bad[:4] or 'all %d' % (len(MAT1) + len(MAT2))))
bad = [i for i in MAT1N if MAT1N[i] < 1] + [i for i in MAT2N if MAT2N[i] < 1]
check(not bad, 'nothing costs zero of a material: %s' % (bad[:4] or 'all positive'))
check(sorted(MAT2) == sorted(MAT2N),
      'the second material and its count go together: %d pieces need two' % len(MAT2))
bad = [i for i in XP if XP[i] < 0]
check(sorted(XP) == list(range(1, ITEMS + 1)) and not bad,
      'every piece pays experience: %d rows, %d..%d' % (len(XP), min(XP.values()), max(XP.values())))
# a plank family's row still IS the old rule - planks x the per-plank value - so the refactor did
# not quietly retune 238 pieces that were already shipped
PLANK_OBJ = {1: 'plank', 2: 'oak_plank', 3: 'teak_plank', 4: 'mahogany_plank'}
XP_WOOD = {1: C['poh_xp_plank'], 2: C['poh_xp_oak'], 3: C['poh_xp_teak'], 4: C['poh_xp_mahogany']}
bad = []
for i in MAT1:
    if not WOOD[i]:
        continue                                    # the garden: its own numbers, checked below
    if (MAT1[i], MAT1N[i], XP[i]) != (PLANK_OBJ[WOOD[i]], PLANKS[i], PLANKS[i] * XP_WOOD[WOOD[i]]):
        bad.append((i, MAT1[i], MAT1N[i], XP[i]))
check(not bad, 'every plank piece costs its own planks and pays planks x the per-plank value: %s'
      % (bad[:3] or '%d pieces' % sum(1 for i in MAT1 if WOOD[i])))
# and a garden piece's needs line names each of its materials with the right count
bad = []
for i in MAT1:
    if WOOD[i]:
        continue
    want = [str(MAT1N[i])] + ([str(MAT2N[i])] if i in MAT2N else [])
    if not all(w in NEED[i] for w in want):
        bad.append((i, NEED[i]))
check(not bad, 'every garden needs line names its counts: %s'
      % (bad[:3] or '%d pieces' % sum(1 for i in MAT1 if not WOOD[i])))
check(set(WOOD.values()) <= {0, 1, 2, 3, 4}, 'the wood column is a wood or 0 for the garden')

print('6. the window lists a whole family whatever the level, and gates on the way out')
# The level stopped being a filter when the window started dimming what you cannot reach: a tier you
# have not earned is shown in black with its level in red, which is the point of the thing.
def nth(fam, n):                                         # ~poh_furn_nth
    seen = 0
    for i in range(1, ITEMS + 1):
        if FAM[i] == fam:
            if seen == n: return i
            seen += 1
    return 0
nthbody = rs2.split('[proc,poh_furn_nth]', 1)[1].split('\n[', 1)[0]
check('poh_furn_level' not in nthbody,
      '~poh_furn_nth does not filter by level - the window dims instead of hiding')
check(nthbody.count('poh_furn_fam') == 1, 'it filters on the family and on nothing else')
for fam, its in sorted(byfam.items()):
    offered = {nth(fam, n) for n in range(ITEMS)} - {0}
    check(offered == set(its), 'family %d lists all %d of its tiers' % (fam, len(its)))
locked = [f for f, its in byfam.items() if any(LEVEL[i] > 1 for i in its)]
check(len(locked) == len(byfam), 'every family has a tier a level-1 player cannot build (%d of %d)'
      % (len(locked), len(byfam)))
menus = read('scripts/skill_construction/scripts/poh_menus.rs2')
pick = menus.split('[proc,poh_furn_pick]', 1)[1].split('\n[', 1)[0]
check('stat(construction) >= enum(int, int, poh_furn_level, $pick)' in pick,
      '~poh_furn_pick re-checks the level before it returns a piece')
check(pick.index('p_pausebutton') < pick.index('stat(construction) >='),
      'and it does so AFTER the click, not while building the page')
check('mes(' in pick.split('stat(construction) >=', 1)[1], 'a click it refuses says why')
# the three tint tables have to cover every state the row procs can produce
tints = read('scripts/skill_construction/configs/poh_menus.enum')
slot = menus.split('[proc,poh_furn_slot0]', 1)[1].split('\n[', 1)[0]
states = {v for k, v in C.items() if k.startswith('poh_state_')}
for t in ('poh_tint_name', 'poh_tint_level', 'poh_tint_need'):
    rows = {int(m.group(1)) for m in re.finditer(r'^val=(\d+),', tints.split('[%s]' % t)[1].split('\n[')[0], re.M)}
    check(states <= rows, '%s answers for every ^poh_state_* (%s)' % (t, sorted(rows)))
check('^poh_state_poor' in slot and '^poh_state_locked' in slot,
      'the slot proc really sets both states')
# ~poh_furn_pick moved to poh_menus.rs2 when the menu became a window, and a page is now as many
# slots as the window has - so read both numbers rather than keeping a literal that can go stale.
# NOT `SLOTS`: that one is ^poh_furn_slots, the 64 varp slots a house's furniture is saved in.
MENU_SLOTS = C['poh_menu_slots']
m = re.search(r'while \(\$page < (\d+)\)', pick)
bound = int(m.group(1)) if m else 0
biggest = max(len(v) for v in byfam.values())
check(bound * MENU_SLOTS >= biggest,
      'the page loop (%d x %d) reaches all %d tiers of the biggest family' % (bound, MENU_SLOTS, biggest))
check(pick.count('~poh_furn_slot') == MENU_SLOTS,
      'it fills exactly the %d slots the window has' % MENU_SLOTS)
pages = [(f, -(-len(v) // MENU_SLOTS)) for f, v in sorted(byfam.items()) if len(v) > MENU_SLOTS]
check(all(p <= bound for _, p in pages),
      '%d of %d families need a second page and all of them fit the loop: %s'
      % (len(pages), len(byfam), pages or 'none do'))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
