#!/usr/bin/env python3
"""Re-implement the tool leprechaun's store from leprechaun.rs2 and beat on it.

WHY. The store is an inv with a fixed slot per item and a PLACEHOLDER in every empty slot, and the
reason that works at all is a detail of the engine's Inventory.add: it looks for a slot already
holding the same obj id BEFORE it looks for an empty one, so a deposit lands in its own square. If
that ever stopped being true the window would quietly fill up in the wrong order, and nothing in
the build would say so.

Worse, the op the deposit goes through is inv_moveitem_uncert, which deletes from the source first
and (until this round) threw away anything the destination could not fit. So the cap arithmetic is
load-bearing in the strongest sense: an off-by-one there was an item-destroying off-by-one. The
invariant the whole file exists to assert is CONSERVATION - the number of each thing the player has,
counting the store and counting notes as the thing they are notes for, never changes.

Both halves are transcribed here: the engine's Inventory (add/remove/placeholder/moveitem*, from
src/engine/Inventory.ts and src/engine/script/handlers/InvOps.ts) and the rs2 procs
(skill_farming/scripts/leprechaun.rs2). If either changes, change this.

The slots, caps and variants are READ from the configs rather than written down again, so a sim
that still passes cannot be a sim that is checking last week's numbers.
"""
import os, random, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONST = os.path.join(ROOT, 'scripts/skill_farming/configs/leprechaun.constant')
ENUM = os.path.join(ROOT, 'scripts/skill_farming/configs/leprechaun.enum')
RS2 = os.path.join(ROOT, 'scripts/skill_farming/scripts/leprechaun.rs2')


def read(p):
    return open(p, encoding='utf-8', newline='').read().replace('\r\n', '\n')


def const(name):
    m = re.search(r'(?m)^\^%s = (\d+)$' % re.escape(name), read(CONST))
    if not m:
        sys.exit('leprechaun.constant does not define ^%s' % name)
    return int(m.group(1))


SLOTS = const('leprechaun_slots')
CAP_TOOL = const('leprechaun_cap_tool')
CAP_SUPPLY = const('leprechaun_cap_supply')
CAP_SINGLE = const('leprechaun_cap_single')
DOSES = const('leprechaun_can_doses')

# slot number -> the obj name the enum puts there (also the placeholder art)
PLACEHOLDER = {int(k): v for k, v in re.findall(r'(?m)^val=(\d+),(\S+)$', read(ENUM))}
assert len(PLACEHOLDER) == SLOTS, 'leprechaun.enum has %d rows for %d slots' % (len(PLACEHOLDER), SLOTS)

# ~leprechaun_slot, transcribed from the switch in leprechaun.rs2 - but read out of it, so the sim
# cannot be testing a different set of items from the one the server accepts.
def rs2_slot_map():
    body = read(RS2).split('[proc,leprechaun_slot]', 1)[1].split('\n[', 1)[0]
    # join continuation lines: a case list can wrap
    body = re.sub(r',\s*\n\s*', ', ', body)
    out = {}
    for objs, slot in re.findall(r'(?m)^\s*case ([^:]+?)\s*:\s*return\(\^leprechaun_slot_(\w+)\);', body):
        for o in objs.split(','):
            out[o.strip()] = slot
    return out


SLOT_OF_NAME = {}
for name, tag in rs2_slot_map().items():
    SLOT_OF_NAME[name] = const('leprechaun_slot_' + tag)
assert len(set(SLOT_OF_NAME.values())) == SLOTS, \
    'the switch reaches %d of %d slots' % (len(set(SLOT_OF_NAME.values())), SLOTS)

# ~leprechaun_cap, the same way
def rs2_caps():
    body = read(RS2).split('[proc,leprechaun_cap]', 1)[1].split('\n[', 1)[0]
    body = re.sub(r',\s*\n\s*', ', ', body)
    caps = {}
    for names, cap in re.findall(r'(?m)^\s*case ([^:]+?)\s*:\s*return\(\^leprechaun_cap_(\w+)\);', body):
        if names.strip() == 'default':
            continue
        for n in names.split(','):
            caps[const(n.strip().lstrip('^'))] = const('leprechaun_cap_' + cap)
    dflt = re.search(r'case default : return\(\^leprechaun_cap_(\w+)\);', body).group(1)
    return caps, const('leprechaun_cap_' + dflt)


CAPS, CAP_DEFAULT = rs2_caps()
def cap(slot):
    return CAPS.get(slot, CAP_DEFAULT)

# which objs have a note form, from the cache configs
CERT = {}
for name in SLOT_OF_NAME:
    CERT[name] = None
objs = ''
for f in ('scripts/_unpack/377/all.obj', 'scripts/skill_farming/configs/compost_bucket.obj',
          'scripts/general/configs/osrs_items.obj'):
    objs += read(os.path.join(ROOT, f))
declared = set(re.findall(r'(?m)^\[(\w+)\]$', objs))
for name in SLOT_OF_NAME:
    if 'cert_' + name in declared:
        CERT[name] = 'cert_' + name
NOTES = {v: k for k, v in CERT.items() if v}

STACKABLE = set(NOTES) | {'plant_cure'}     # notes stack; nothing else in the store does
# plant_cure is not actually stackable in the cache either - see the battery, which checks the
# real configs. The sim only needs "does add() stack it", and the STORE is stackall, so the only
# place this matters is the player's inventory.


# ============================================================ the engine's Inventory, transcribed
class Inv:
    def __init__(s, size, stackall=False):
        s.size = size
        s.stackall = stackall
        s.items = [None] * size          # each entry (name, count) or None

    def get(s, slot):
        return s.items[slot]

    def num(s, slot):
        it = s.items[slot]
        return it[1] if it else 0

    def obj(s, slot):
        it = s.items[slot]
        return it[0] if it else None

    def index_of(s, name):
        for i, it in enumerate(s.items):
            if it and it[0] == name:
                return i
        return -1

    def next_free(s):
        for i, it in enumerate(s.items):
            if it is None:
                return i
        return -1

    def freespace(s):
        return sum(1 for it in s.items if it is None)

    def total(s, name):
        return sum(it[1] for it in s.items if it and it[0] == name)

    def add(s, name, count):
        """Inventory.add. Returns how many went in."""
        stack = s.stackall or name in STACKABLE
        done = 0
        if not stack:
            for i in range(s.size):
                if s.items[i] is not None:
                    continue
                s.items[i] = (name, 1)
                done += 1
                if done >= count:
                    break
        else:
            at = s.index_of(name)
            if at == -1:
                at = s.next_free()
                if at == -1:
                    return 0
            have = s.num(at)
            s.items[at] = (name, have + count)
            done = count
        return done

    def remove(s, name, count):
        done = 0
        for i in range(s.size):
            it = s.items[i]
            if not it or it[0] != name:
                continue
            take = min(it[1], count - done)
            if it[1] - take <= 0:
                s.items[i] = None
            else:
                s.items[i] = (name, it[1] - take)
            done += take
            if done >= count:
                break
        return done

    def placeholder(s, slot, name):
        s.items[slot] = None if name is None else (name, 0)

    def itemspace_overflow(s, name, count):
        """inv_itemspace2: how many of count would NOT fit."""
        probe = Inv(s.size, s.stackall)
        probe.items = list(s.items)
        return count - probe.add(name, count)


GROUND = {}                              # what the overflow drops at the player's feet


def drop(name, n):
    if n > 0:
        GROUND[name] = GROUND.get(name, 0) + n


def moveitem(src, dst, name, count):
    done = src.remove(name, count)
    if done == 0:
        return
    drop(name, count - dst.add(name, done))


def moveitem_cert(src, dst, name, count):
    done = src.remove(name, count)
    if done == 0:
        return
    final = CERT.get(name) or name
    drop(final, count - dst.add(final, done))


def moveitem_uncert(src, dst, name, count):
    done = src.remove(name, count)
    if done == 0:
        return
    final = NOTES.get(name, name)
    drop(final, count - dst.add(final, done))


# ============================================================ the rs2 procs, transcribed
class Player:
    def __init__(s):
        s.inv = Inv(28)
        s.store = Inv(SLOTS, stackall=True)
        s.varp = 0

    # ---- ~leprechaun_slot / ~leprechaun_cap / ~leprechaun_held / ~leprechaun_room
    def slot_of(s, name):
        return SLOT_OF_NAME.get(name, -1)

    def held(s, slot):
        return s.store.num(slot)

    def room(s, slot):
        return cap(slot) - s.held(slot)

    # ---- ~leprechaun_placeholders
    def placeholders(s):
        for slot in range(s.store.size):
            if s.store.obj(slot) is None:
                s.store.placeholder(slot, PLACEHOLDER[slot])

    # ---- ~leprechaun_deposit
    def deposit(s, name, count):
        slot = s.slot_of(NOTES.get(name, name))
        if slot < 0 or count < 1:
            return 0
        n = min(count, s.room(slot))
        if n < 1:
            return 0
        if s.held(slot) == 0:
            s.store.placeholder(slot, None)
        moveitem_uncert(s.inv, s.store, name, n)
        s.placeholders()
        return n

    # ---- ~leprechaun_deposit_kind
    def deposit_kind(s, name):
        moved = s.deposit(name, s.inv.total(name))
        note = CERT.get(name)
        if note:
            moved += s.deposit(note, s.inv.total(note))
        return moved

    # ---- ~leprechaun_deposit_all
    def deposit_all(s):
        moved = 0
        for slot in range(s.store.size):
            moved += s.deposit_kind(PLACEHOLDER[slot])
        for extra in EXTRA_KINDS:
            moved += s.deposit_kind(extra)
        return moved

    # ---- ~leprechaun_withdraw
    def withdraw(s, slot, count, note=False):
        name = s.store.obj(slot)
        if name is None:
            return 'empty'
        if s.held(slot) < 1:
            return 'none held'
        want = min(count, s.held(slot))
        give = name
        if note:
            give = CERT.get(name)
            if give is None:
                return 'not noteable'
        if give not in STACKABLE and not s.inv.stackall:
            take = min(want, s.inv.freespace())
        else:
            take = want - s.inv.itemspace_overflow(give, want)
        if take < 1:
            return 'no room'
        if note:
            moveitem_cert(s.store, s.inv, name, take)
        else:
            moveitem(s.store, s.inv, name, take)
        s.placeholders()
        return take

    # ---- ~leprechaun_migrate
    def migrate(s):
        if s.varp == 0:
            return
        for tag, obj in (('rake', 'rake'), ('dibber', 'dibber'), ('spade', 'spade'),
                         ('trowel', 'gardening_trowel'), ('secateurs', 'secateurs')):
            lo, hi = const('leprechaun_old_%s_lo' % tag), const('leprechaun_old_%s_hi' % tag)
            s.migrate_tool(obj, lo, hi)
        lo, hi = const('leprechaun_old_can_lo'), const('leprechaun_old_can_hi')
        can = (s.varp >> lo) & ((1 << (hi - lo + 1)) - 1)
        if 0 < can <= DOSES:
            s.migrate_tool('watering_can_%d' % (can - 1), 0, 0)
        s.varp = 0

    def migrate_tool(s, name, lo, hi):
        count = 1
        if hi > lo:
            count = (s.varp >> lo) & ((1 << (hi - lo + 1)) - 1)
        if count < 1:
            return
        slot = s.slot_of(name)
        n = min(count, s.room(slot))
        if n < 1:
            return
        if s.held(slot) == 0:
            s.store.placeholder(slot, None)
        s.store.add(name, n)
        s.placeholders()


# the variants ~leprechaun_deposit_all names explicitly, read out of the proc so the sim sweeps
# exactly what the server sweeps
def extra_kinds():
    body = read(RS2).split('[proc,leprechaun_deposit_all]', 1)[1].split('\n[', 1)[0]
    named = re.findall(r'~leprechaun_deposit_kind\((\w+)\)', body)
    return [n for n in named if n]


EXTRA_KINDS = extra_kinds()

# ============================================================ the checks
bad = 0


def check(ok, what):
    global bad
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        bad += 1


print('%d slots; caps %s; %d kinds accepted; %d extra variants swept'
      % (SLOTS, sorted({cap(i) for i in range(SLOTS)}), len(SLOT_OF_NAME), len(EXTRA_KINDS)))

# every accepted obj is swept by Deposit-everything, either as an enum row or as a named extra
swept = set(PLACEHOLDER.values()) | set(EXTRA_KINDS)
check(swept == set(SLOT_OF_NAME),
      'Deposit-everything sweeps every obj the store accepts and nothing it does not: %s'
      % (sorted(set(SLOT_OF_NAME) ^ swept) or 'exact match'))

# the caps are OSRS's
check(cap(const('leprechaun_slot_can')) == 1 and cap(const('leprechaun_slot_bottomless')) == 1,
      'one watering can and one bottomless bucket')
check(all(cap(SLOT_OF_NAME[o]) == CAP_TOOL for o in
          ('rake', 'spade', 'dibber', 'secateurs', 'fairy_enchanted_secateurs', 'gardening_trowel')),
      'a hundred of each of the six tools')
check(all(cap(SLOT_OF_NAME[o]) == CAP_SUPPLY for o in
          ('plant_cure', 'bucket_empty', 'bucket_compost', 'bucket_supercompost')),
      'a thousand of each cure and bucket')
check(sum(1 for n in SLOT_OF_NAME if n.startswith('watering_can_')) == DOSES,
      'all %d watering can doses go to the one slot' % DOSES)


def wealth(p):
    """Everything the player has, counting the store and counting a note as the thing it notes."""
    w = {}
    for src in (p.inv, p.store):
        for it in src.items:
            if it and it[1] > 0:
                name = NOTES.get(it[0], it[0])
                w[name] = w.get(name, 0) + it[1]
    for name, n in GROUND.items():
        real = NOTES.get(name, name)
        w[real] = w.get(real, 0) + n
    return w


# ---- conservation and tidiness over random play
KINDS = sorted(SLOT_OF_NAME)
fails = {'conserve': 0, 'cap': 0, 'place': 0, 'canon': 0, 'ground': 0}
for seed in range(600):
    random.seed(seed)
    GROUND.clear()
    p = Player()
    p.placeholders()
    for _ in range(60):
        act = random.randrange(5)
        if act == 0:                      # pick something up
            name = random.choice(KINDS)
            p.inv.add(name, random.randrange(1, 30))  # return ignored; the replay below counts it
        elif act == 1:                    # pick up a noted stack of something noteable
            name = random.choice([n for n in KINDS if CERT.get(n)])
            p.inv.add(CERT[name], random.randrange(1, 900))
        elif act == 2:
            p.deposit_all()
        elif act == 3:
            p.withdraw(random.randrange(SLOTS), random.choice((1, 5, 10, 1 << 30)))
        else:
            p.withdraw(random.randrange(SLOTS), 1 << 30, note=True)

        # no cap is exceeded
        for slot in range(SLOTS):
            if p.held(slot) > cap(slot):
                fails['cap'] += 1
        # every empty slot shows its placeholder, and a placeholder is never stock
        for slot in range(SLOTS):
            o = p.store.obj(slot)
            if o is None:
                fails['place'] += 1
            elif p.held(slot) == 0 and o != PLACEHOLDER[slot]:
                fails['place'] += 1
        # everything is in its own slot
        for slot in range(SLOTS):
            o = p.store.obj(slot)
            if o is not None and SLOT_OF_NAME.get(o) != slot:
                fails['canon'] += 1

    # conservation, checked end to end: replay the same seed counting what was picked up
    random.seed(seed)
    GROUND.clear()
    q = Player()
    q.placeholders()
    got = {}
    for _ in range(60):
        act = random.randrange(5)
        if act == 0:
            name = random.choice(KINDS)
            # count what the inventory ACTUALLY took: a non-stacking item stops at 28 slots, and
            # crediting the asked-for number instead would make the sim's own books wrong
            n = q.inv.add(name, random.randrange(1, 30))
            got[name] = got.get(name, 0) + n
        elif act == 1:
            name = random.choice([n for n in KINDS if CERT.get(n)])
            n = q.inv.add(CERT[name], random.randrange(1, 900))
            got[name] = got.get(name, 0) + n
        elif act == 2:
            q.deposit_all()
        elif act == 3:
            q.withdraw(random.randrange(SLOTS), random.choice((1, 5, 10, 1 << 30)))
        else:
            q.withdraw(random.randrange(SLOTS), 1 << 30, note=True)
    # drop the zero entries on both sides: got accumulates a key the first time something is
    # picked up even when the inventory was full and took none of it, and wealth() never records
    # a zero at all, so the two agree on substance and disagree on which keys exist
    if {k: v for k, v in wealth(q).items() if v} != {k: v for k, v in got.items() if v}:
        fails['conserve'] += 1
    if GROUND:
        fails['ground'] += 1

check(fails['conserve'] == 0,
      '600 random sessions: nothing is created or destroyed (%d bad)' % fails['conserve'])
check(fails['cap'] == 0, 'no slot ever goes over its cap (%d breaches)' % fails['cap'])
check(fails['place'] == 0,
      'every empty slot keeps its own placeholder, and a placeholder is never counted as stock (%d bad)'
      % fails['place'])
check(fails['canon'] == 0,
      'every item is always in its own slot, whatever order it arrived in (%d misplaced)'
      % fails['canon'])
check(fails['ground'] == 0,
      'the cap arithmetic never overflows the store, so nothing is ever dropped at your feet (%d sessions did)'
      % fails['ground'])

# ---- the single-item slots really are one ACROSS their variants
p = Player(); p.placeholders(); GROUND.clear()
p.inv.add('watering_can_3', 1)
p.inv.add('watering_can_8', 1)
p.deposit_all()
check(p.held(const('leprechaun_slot_can')) == 1 and p.inv.total('watering_can_3') + p.inv.total('watering_can_8') == 1,
      'he takes one watering can and leaves the other, whichever doses they are')

p = Player(); p.placeholders(); GROUND.clear()
p.inv.add('bottomless_bucket_filled', 1)
p.deposit_all()
check(p.store.obj(const('leprechaun_slot_bottomless')) == 'bottomless_bucket_filled'
      and p.held(const('leprechaun_slot_bottomless')) == 1,
      'a FILLED bottomless bucket stores in the bucket slot, over the empty one placeholding it')

# ---- deposit-everything is idempotent: a second click stores nothing and loses nothing
p = Player(); p.placeholders(); GROUND.clear()
for k in KINDS:
    p.inv.add(k, 3)
first = p.deposit_all()
snapshot = list(p.store.items), list(p.inv.items)
second = p.deposit_all()
check(second == 0 and (list(p.store.items), list(p.inv.items)) == snapshot,
      'a second Deposit-everything moves nothing and changes nothing (first took %d)' % first)

# ---- a full slot refuses rather than swallowing
p = Player(); p.placeholders(); GROUND.clear()
slot = SLOT_OF_NAME['bucket_compost']
p.store.placeholder(slot, None)
p.store.add('bucket_compost', cap(slot))
p.placeholders()
p.inv.add('cert_bucket_compost', 500)
took = p.deposit_kind('bucket_compost')
check(took == 0 and p.inv.total('cert_bucket_compost') == 500 and not GROUND,
      'a full slot takes nothing and the noted stack stays in your inventory')

# ---- and a partly full one takes exactly the difference
p = Player(); p.placeholders(); GROUND.clear()
p.store.placeholder(slot, None)
p.store.add('bucket_compost', cap(slot) - 7)
p.placeholders()
p.inv.add('cert_bucket_compost', 500)
took = p.deposit_kind('bucket_compost')
check(took == 7 and p.inv.total('cert_bucket_compost') == 493 and p.held(slot) == cap(slot) and not GROUND,
      'a slot seven short of full takes seven out of a noted stack of 500 (took %d)' % took)

# ---- withdraw-as-note only works where a note exists
p = Player(); p.placeholders(); GROUND.clear()
p.store.placeholder(SLOT_OF_NAME['fairy_enchanted_secateurs'], None)
p.store.add('fairy_enchanted_secateurs', 4)
p.placeholders()
check(p.withdraw(SLOT_OF_NAME['fairy_enchanted_secateurs'], 1 << 30, note=True) == 'not noteable',
      'magic secateurs have no note form, so Withdraw-as-note says so instead of doing something else')
p.store.placeholder(SLOT_OF_NAME['rake'], None)
p.store.add('rake', 100)
p.placeholders()
took = p.withdraw(SLOT_OF_NAME['rake'], 1 << 30, note=True)
check(took == 100 and p.inv.total('cert_rake') == 100 and p.inv.freespace() == 27,
      'a hundred rakes come back as one noted stack in one slot (took %s)' % took)

# ---- an empty placeholder slot is not a withdrawal
p = Player(); p.placeholders(); GROUND.clear()
check(p.withdraw(SLOT_OF_NAME['spade'], 5) == 'none held',
      'clicking Withdraw on a faded placeholder takes nothing')

# ---- the withdrawal is capped by inventory room, not by what he holds
p = Player(); p.placeholders(); GROUND.clear()
p.store.placeholder(SLOT_OF_NAME['rake'], None)
p.store.add('rake', 100)
p.placeholders()
for i in range(20):
    p.inv.add('bucket_empty', 1)
took = p.withdraw(SLOT_OF_NAME['rake'], 1 << 30)
check(took == 8 and p.held(SLOT_OF_NAME['rake']) == 92 and not GROUND,
      'with 8 free inventory slots, Withdraw-all brings back 8 rakes and leaves 92 (took %s)' % took)

# ---- migration: every value the old varp could hold
worst = 0
for rake in range(8):
    for dib in range(8):
        for spade in range(8):
            for can in range(10):
                p = Player(); p.placeholders(); GROUND.clear()
                p.varp = (rake << const('leprechaun_old_rake_lo')) \
                    | (dib << const('leprechaun_old_dibber_lo')) \
                    | (spade << const('leprechaun_old_spade_lo')) \
                    | (can << const('leprechaun_old_can_lo'))
                p.migrate()
                ok = (p.held(SLOT_OF_NAME['rake']) == rake
                      and p.held(SLOT_OF_NAME['dibber']) == dib
                      and p.held(SLOT_OF_NAME['spade']) == spade
                      and p.varp == 0
                      and p.held(SLOT_OF_NAME['watering_can_0']) == (1 if 0 < can <= DOSES else 0))
                if can > 0 and can <= DOSES:
                    ok = ok and p.store.obj(SLOT_OF_NAME['watering_can_0']) == 'watering_can_%d' % (can - 1)
                if not ok:
                    worst += 1
check(worst == 0,
      'all %d combinations of the old varp migrate to the right counts and zero the varp (%d wrong)'
      % (8 * 8 * 8 * 10, worst))

# migrating twice must not double anything
p = Player(); p.placeholders(); GROUND.clear()
p.varp = (7 << const('leprechaun_old_rake_lo')) | (9 << const('leprechaun_old_can_lo'))
p.migrate()
p.migrate()
check(p.held(SLOT_OF_NAME['rake']) == 7 and p.held(SLOT_OF_NAME['watering_can_0']) == 1,
      'opening the window twice migrates once')

print()
print('ALL PASS' if bad == 0 else '%d FAILED' % bad)
sys.exit(0 if bad == 0 else 1)
