"""Battery for where the pets come from: the boss rates, and the skilling pets' per-action rolls.

tools/bossart_battery.py covers the ART. This covers the NUMBERS, against tools/petspec.json,
which records every rate and base chance and cites the wiki they came from. Nothing in the game is
allowed to hold a number the spec does not, and no base the spec holds is allowed to be missing
from the game - a pet that rolls at the wrong rate is otherwise invisible until someone does the
maths over ten thousand kills.

    python3 tools/pet_battery.py
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt):
    """The source with its comments gone. A rate in a comment is not a rate in the game."""
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

SPEC = json.loads(read('tools/petspec.json'))
ROLL = read('scripts/npc/scripts/skill_pets.rs2')
BOSSRS2 = read('scripts/npc/scripts/boss_pets.rs2')
CONST = read('scripts/npc/configs/skill_pets.constant')
BCONST = read('scripts/npc/configs/boss_pets.constant')
PETNPC = read('scripts/npc/configs/boss_pets.npc') + '\n' + read('scripts/npc/configs/skill_pets.npc')
PETOBJ = read('scripts/npc/configs/boss_pets.obj') + '\n' + read('scripts/npc/configs/skill_pets.obj')

def const(txt, n):
    m = re.search(r'\^' + n + r'\s*=\s*(\d+)', txt)
    return int(m.group(1)) if m else None

def rows(path):
    """dbrow blocks -> {block: {field: value}}"""
    out = {}
    for b in re.split(r'(?m)^(?=\[)', read(path)):
        m = re.match(r'\[(\w+)\]', b)
        if not m: continue
        d = {}
        for l in b.split('\n')[1:]:
            l = l.split('//')[0].strip()
            if l.startswith('data='):
                k, _, v = l[5:].partition(',')
                d.setdefault(k, []).append(v)
        out[m.group(1)] = d
    return out

# ============================================================================ 1
print('1. the roll is OSRS\'s formula, and it reads the level OSRS reads')
step = const(CONST, 'skillpet_level_step')
check(step == SPEC['level_step'], 'the level step is the spec\'s %d' % SPEC['level_step'])
body = code(ROLL).split('[proc,skillpet_roll]', 1)[1].split('\n[', 1)[0]
check('calc($base - (stat_base($stat) * ^skillpet_level_step))' in body,
      'the chance is base - (level * step), which is 1 in (B - level*25)')
check('stat_base(' in body and 'stat(' not in body.replace('stat_base(', ''),
      'and it is the UNBOOSTED level - a dwarven stout must not improve the odds')
check('random($chance)' in body, 'the roll is random(chance)')
check('^skillpet_no_roll' in body and body.index('^skillpet_no_roll') < body.index('random($chance)'),
      'an action with no base is refused before the roll, not after')
check(const(CONST, 'skillpet_no_roll') == 0,
      'and that sentinel is 0, so a missing table entry reads as "no pet" rather than "always"')
check('$chance < 1' in body, 'the chance is floored at 1, so a base added carelessly cannot divide by nothing')
check('~obj_gettotal($pet) > 0' in body, 'owning one already - pack, bank or worn - blocks a second')
check('%follower_obj = $pet' in body, 'and so does having it out')
check(body.index('~obj_gettotal') > body.index('random($chance)'),
      'those two run only after the roll succeeds, which is one inv sweep per pet rather than per action')
check('inv_freespace(inv) > 0' in body and 'obj_add(coord' in body,
      'a full pack puts it on the floor rather than losing it')

# ============================================================================ 2
print('2. the boss pets roll at their own rate, named at the call site')
check('[proc,bosspet_roll](namedobj $pet, int $rate)' in BOSSRS2,
      'the rate is an argument, so a family cannot inherit another family\'s number')
check('random($rate)' in code(BOSSRS2), 'and it is what the roll uses')
check(const(BCONST, 'bosspet_droprate') == 3000, '^bosspet_droprate is 3,000')
check(const(BCONST, 'bosspet_gwd_droprate') == 5000, '^bosspet_gwd_droprate is 5,000')
RATE_CONST = {3000: '^bosspet_droprate', 5000: '^bosspet_gwd_droprate'}
for pet, d in sorted(SPEC['boss'].items()):
    item = pet + '_item'
    hits = []
    for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
        for fn in files:
            if not fn.endswith('.rs2'): continue
            rel = os.path.join(dirpath, fn)[len(C) + 1:]
            for m in re.finditer(r'~bosspet_roll\(([^)]*)\)', code(read(rel))):
                if m.group(1).split(',')[0].strip() == item:
                    hits.append((os.path.basename(rel), m.group(1)))
    check(len(hits) == 1, '%s is rolled in exactly one place: %s'
          % (item, [h[0] for h in hits] or 'NOWHERE'))
    if len(hits) != 1: continue
    where, args = hits[0]
    check(where == d['table'], '...and it is %s' % d['table'])
    want = RATE_CONST[d['rate']]
    check(args.split(',')[1].strip() == want,
          '...at %s, which is 1 in %d' % (want, d['rate']))
check(len(SPEC['boss']) == 10, 'all ten boss pets are accounted for')

# ============================================================================ 3
print('3. every base chance in the game is the spec\'s, and the spec cites the wiki')
check('oldschool.runescape.wiki' in SPEC['wiki'], 'the spec says where its numbers came from')
wired = {k: v for k, v in SPEC['skill'].items() if v['wired']}
check(len(wired) == 4, 'four of the eight skilling pets are wired: %s' % sorted(wired))
for pet, d in sorted(wired.items()):
    if 'bases' in d:
        tbl = rows(d['held_in'])
        col = d['column'].split(':')[1]
        for blk, want in sorted(d['bases'].items()):
            got = tbl.get(blk, {}).get(col, [None])[0]
            check(got == str(want), '%s: %s is %s' % (pet, blk, want))
        extra = [b for b in tbl if col in tbl[b] and b not in d['bases']]
        check(not extra, '...and no row carries a base the spec does not know: %s'
              % (extra or 'none of %d' % len(tbl)))
    for cn, want in sorted(d.get('constants', {}).items()):
        check(const(CONST, cn) == want, '%s: ^%s is %s' % (pet, cn, want))

# ============================================================================ 4
print('4. no base can outrun the formula at 99')
# Read from the GAME, not from the spec: this is a claim about what ships. Group 3 is what holds
# the two equal, so a number lowered in one place is caught there and here.
for pet, d in sorted(wired.items()):
    vals = []
    if 'bases' in d:
        tbl = rows(d['held_in']); col = d['column'].split(':')[1]
        vals += [int(v[0]) for b, f in tbl.items() if (v := f.get(col)) and int(v[0]) > 0]
    vals += [c for cn in d.get('constants', {}) if (c := const(CONST, cn))]
    worst = min(vals) if vals else None
    check(worst is None or worst - 99 * SPEC['level_step'] >= 1,
          '%s: its smallest base (%s) still leaves a chance at 99: 1 in %s'
          % (pet, worst, worst - 99 * SPEC['level_step'] if worst else 'n/a'))

# ============================================================================ 5
print('5. every hook the spec names really rolls for that pet, with that skill')
for pet, d in sorted(wired.items()):
    item = pet + '_item'
    for f in d['hooks']:
        t = code(read(f))
        m = [x for x in re.findall(r'~skillpet_roll(?:_each)?\(([^)]*)\)', t)
             if x.split(',')[0].strip() == item]
        check(bool(m), '%s rolls in %s' % (item, os.path.basename(f)))
        if not m: continue
        stats = {x.split(',')[1].strip() for x in m}
        check(stats == {d['stat']}, '...against %s' % d['stat'])
    if d.get('per') == 'essence':
        t = code(read(d['hooks'][0]))
        check('~skillpet_roll_each(' in t and '$total_ess' in t,
              '...and the Rift guardian rolls once per essence, not once per click')
    if d.get('per') == 'lap':
        for f in d['hooks']:
            t = code(read(f))
            check('_course_progress = 0;' in t and '~skillpet_roll(' in t,
                  '...and %s rolls on completing a lap' % os.path.basename(f))

# ============================================================================ 6
print('6. the four that are not wired cannot be rolled, and say so')
pending = {k: v for k, v in SPEC['skill'].items() if not v['wired']}
check(len(pending) == 4, 'four are pending: %s' % sorted(pending))
allrs2 = ''
for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
    for fn in files:
        if fn.endswith('.rs2'):
            allrs2 += code(read(os.path.join(dirpath, fn)[len(C) + 1:]))
for pet, d in sorted(pending.items()):
    check('%s_item' % pet not in allrs2.replace('%s_item' % pet + '_', ''),
          '%s is rolled nowhere' % pet)
    check('why' in d, '...and the spec says why not: %s' % d['why'][:64])
check('hunter' == SPEC['skill']['skillpet_chinchompa']['stat'],
      'the chinchompa waits on Hunter, which this server does not have at all')
check(not re.search(r'stat_advance\(hunter', allrs2), '...and nothing advances Hunter, which is what makes that true')

# ============================================================================ 7
print('7. each pet names its item and each item names its pet back')
def blocks(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', b)
        if m: out[m.group(1)] = b
    return out
NB, OB = blocks(PETNPC), blocks(PETOBJ)
allpets = sorted(list(SPEC['boss']) + list(SPEC['skill']))
check(len(allpets) == 18, 'eighteen pets in the spec')
for pet in allpets:
    item = pet + '_item'
    check(pet in NB, '%s has an npc config' % pet)
    check(item in OB, '...and an item config')
    if pet not in NB or item not in OB: continue
    check('param=pet_item_id,%s' % item in NB[pet], '...the npc names the item')
    check('param=follower_id,%s' % pet in OB[item], '...and the item names the npc')
    check('category=bosspet' in NB[pet] and 'category=bosspet' in OB[item],
          '...both on the category the four follower triggers hang off')
    check('tradeable=no' in OB[item], '...and the item is untradeable')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
