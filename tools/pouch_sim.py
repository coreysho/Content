"""Simulation of the rune pouch: filling it, and spending runes across it and the inventory.

The battery proves the SHAPE of the two procs - that the pack is drained first, that the pouch
covers the shortfall, that Fill compares kinds against what the pouch can reach. This runs the
arithmetic those shapes describe over every case that matters, and checks the invariants that must
hold whatever the numbers are:

    nothing is created, nothing vanishes, the pouch is never overdrawn, and a cast that the check
    allows is a cast the spend can pay for.

Constants come out of the config, so the sim cannot drift from the game by holding its own copy.

    python3 tools/pouch_sim.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

CONST = read('scripts/storage_items/configs/rune_pouch.constant')
OBJ = read('scripts/storage_items/configs/rune_pouch.obj')
def const(n):
    return int(re.search(r'\^' + n + r'\s*=\s*(\d+)', CONST).group(1))
MAX = const('rune_pouch_max_per_rune')
def slots_of(item):
    b = OBJ.split('[' + item + ']', 1)[1].split('\n[', 1)[0]
    return int(re.search(r'param=pouch_slots,(\d+)', b).group(1))
PLAIN, DIVINE = slots_of('rune_pouch'), slots_of('divine_rune_pouch')
STORE_SLOTS = int(re.search(r'\[rune_pouch_store\][^\[]*?size=(\d+)',
                            read('scripts/storage_items/configs/storage_items.inv'), re.S).group(1))

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

# ---------------------------------------------------------------- the two procs, as written
def rune_total(pack, pouch, rune, carried_slots):
    """~rune_total: the pack alone with no pouch, otherwise both."""
    if rune is None:
        return 0
    if carried_slots == 0:
        return pack.get(rune, 0)
    return pack.get(rune, 0) + pouch.get(rune, 0)

def rune_del(pack, pouch, rune, count):
    """~rune_del: the pack first, then exactly the shortfall out of the pouch."""
    if rune is None or count < 1:
        return
    loose = min(pack.get(rune, 0), count)
    if loose:
        pack[rune] = pack[rune] - loose
        if pack[rune] == 0: del pack[rune]
    rest = count - loose
    if rest:
        pouch[rune] = pouch[rune] - rest
        if pouch[rune] == 0: del pouch[rune]

def rune_pouch_fill(pack, pouch, allowed, carried_slots):
    """~rune_pouch_fill, kind by kind in enum order."""
    moved = 0
    for rune in allowed:
        have = pack.get(rune, 0)
        if have <= 0:
            continue
        inside = pouch.get(rune, 0)
        if inside > 0 or len(pouch) < carried_slots:
            n = min(have, MAX - inside)
            if n > 0:
                pouch[rune] = inside + n
                pack[rune] = have - n
                if pack[rune] == 0: del pack[rune]
                moved += n
    return moved

RUNES = ['airrune', 'waterrune', 'earthrune', 'firerune', 'lawrune', 'deathrune']

# ============================================================================ 1
print('1. the store is big enough for the biggest pouch, and no bigger than it needs to be')
check(STORE_SLOTS == DIVINE, 'the store has as many slots as the divine pouch reaches (%d)' % DIVINE)
check(PLAIN < DIVINE, 'and the plain pouch reaches fewer (%d)' % PLAIN)

# ============================================================================ 2
print('2. Fill respects the kinds the pouch can reach, and the cap per kind')
pack = {r: 100 for r in RUNES}
pouch = {}
rune_pouch_fill(pack, pouch, RUNES, PLAIN)
check(len(pouch) == PLAIN, 'a plain pouch filled from six kinds takes %d: %d' % (PLAIN, len(pouch)))
check(sorted(pouch) == sorted(RUNES[:PLAIN]), '...the first %d in enum order' % PLAIN)
check(sum(pack.values()) == 100 * (len(RUNES) - PLAIN), 'and the rest stay in the pack')
pack2, pouch2 = {r: 100 for r in RUNES}, {}
rune_pouch_fill(pack2, pouch2, RUNES, DIVINE)
check(len(pouch2) == DIVINE, 'a divine pouch takes %d' % DIVINE)
# a kind already inside tops up without needing a slot
pack3, pouch3 = {'airrune': 50}, {r: 1 for r in RUNES[:PLAIN]}
rune_pouch_fill(pack3, pouch3, RUNES, PLAIN)
check(pouch3['airrune'] == 51 and not pack3,
      'a rune already inside tops up even with every slot used')
# the cap
pack4, pouch4 = {'airrune': 500}, {'airrune': MAX - 200}
moved = rune_pouch_fill(pack4, pouch4, RUNES, PLAIN)
check(pouch4['airrune'] == MAX and pack4['airrune'] == 300 and moved == 200,
      'filling stops at %s and leaves the remainder in the pack' % format(MAX, ','))
pack5, pouch5 = {'airrune': 5}, {'airrune': MAX}
check(rune_pouch_fill(pack5, pouch5, RUNES, PLAIN) == 0 and pack5['airrune'] == 5,
      'a full kind moves nothing')

# ============================================================================ 3
print('3. spending drains the pack first and never overdraws the pouch')
cases = [(0, 0, 1), (5, 0, 5), (0, 5, 5), (3, 7, 10), (10, 0, 4), (0, 10, 4),
         (1, 1, 2), (2, 3, 5), (MAX, MAX, 1000)]
for have_pack, have_pouch, cost in cases:
    pack = {'airrune': have_pack} if have_pack else {}
    pouch = {'airrune': have_pouch} if have_pouch else {}
    before = have_pack + have_pouch
    slots = PLAIN if have_pouch else PLAIN
    if rune_total(pack, pouch, 'airrune', slots) < cost:
        continue
    rune_del(pack, pouch, 'airrune', cost)
    after = pack.get('airrune', 0) + pouch.get('airrune', 0)
    check(after == before - cost,
          'pack %s + pouch %s, cost %s -> %s left' % (have_pack, have_pouch, cost, after))
    check(pouch.get('airrune', 0) >= 0, '...and the pouch is never negative')
    if cost <= have_pack:
        check(pouch.get('airrune', 0) == have_pouch, '...the pouch is untouched when the pack covers it')

# ============================================================================ 4
print('4. a cast the check allows is a cast the spend can pay for')
bad = []
for have_pack in range(0, 6):
    for have_pouch in range(0, 6):
        for cost in range(1, 6):
            pack = {'airrune': have_pack} if have_pack else {}
            pouch = {'airrune': have_pouch} if have_pouch else {}
            if rune_total(pack, pouch, 'airrune', PLAIN if have_pouch else 0) < cost:
                continue
            rune_del(pack, pouch, 'airrune', cost)
            if pack.get('airrune', 0) < 0 or pouch.get('airrune', 0) < 0:
                bad.append((have_pack, have_pouch, cost))
check(not bad, 'over all 180 pack/pouch/cost combinations, none goes negative: %s'
      % (bad[:3] or 'none'))

# ============================================================================ 5
print('5. with no pouch carried, nothing changes from what the game did before')
diff = []
for have_pack in range(0, 6):
    for cost in range(1, 6):
        pack = {'airrune': have_pack} if have_pack else {}
        pouch = {'airrune': 99}          # runes sitting in a pouch left in the bank
        if rune_total(pack, pouch, 'airrune', 0) != have_pack:
            diff.append(('total', have_pack, cost))
check(not diff, 'the count is the pack alone, whatever is in the store: %s' % (diff[:3] or 'all 30'))

# ============================================================================ 6
print('6. a null rune and a zero cost do nothing')
pack, pouch = {'airrune': 5}, {'airrune': 5}
check(rune_total(pack, pouch, None, PLAIN) == 0, 'a null rune counts 0')
rune_del(pack, pouch, None, 3)
rune_del(pack, pouch, 'airrune', 0)
check(pack['airrune'] == 5 and pouch['airrune'] == 5, 'and neither spends anything')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
