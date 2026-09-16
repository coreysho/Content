"""Battery for the rune pouch.

The feature is not "an item that holds runes" - it is "every spell in the game now looks in two
places". So most of what is checked here is the NEGATIVE: that no rune read and no rune spend
anywhere in the magic path still looks only in the inventory. One missed site is a spell that says
you have no runes while the pouch is full.

    python3 tools/pouch_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt):
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

MAGIC = read('scripts/skill_magic/scripts/magic.rs2')
POUCH = read('scripts/storage_items/scripts/rune_pouch.rs2')
STORAGE = read('scripts/storage_items/scripts/storage_items.rs2')
OBJ = read('scripts/storage_items/configs/rune_pouch.obj')
INV = read('scripts/storage_items/configs/storage_items.inv')
CONST = read('scripts/storage_items/configs/rune_pouch.constant')
ENUM = read('scripts/storage_items/configs/rune_pouch.enum')
ALCH = read('scripts/skill_magic/scripts/spells/alchemy.rs2')
LEATHER = read('scripts/skill_crafting/scripts/leather/leather.rs2')
DEATH = read('scripts/player/scripts/death.rs2')

def const(n):
    m = re.search(r'\^' + n + r'\s*=\s*(\d+)', CONST)
    return int(m.group(1)) if m else None

def block(txt, name):
    return txt.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in txt else ''

def objblock(name):
    b = block(OBJ, name)
    return dict(l.split('=', 1) for l in b.split('\n') if '=' in l and not l.startswith('//'))

# ============================================================================ 1
print('1. one store, and the item in your hand decides how much of it you can reach')
iv = block(INV, 'rune_pouch_store')
check('size=4' in iv, 'the store has four slots')
check('scope=perm' in iv, 'and survives a logout')
check('stackall=yes' in iv, 'and stacks, so 16,000 of a rune is one slot')
plain, divine = objblock('rune_pouch'), objblock('divine_rune_pouch')
check(plain.get('param') == 'pouch_slots,3', 'the rune pouch reaches three of them')
check(divine.get('param') == 'pouch_slots,4', 'the divine one reaches four')
check('[proc,rune_pouch_slots]' in POUCH and 'oc_param($pouch, pouch_slots)' in POUCH,
      'and one proc reads that number rather than each caller knowing it')
slots = block(POUCH, 'proc,rune_pouch_slots')
check('return(0);' in slots, 'carrying no pouch answers 0')
kinds = code(block(POUCH, 'proc,rune_pouch_kinds_used'))
check('inv_size(rune_pouch_store)' in kinds, 'kinds-used walks the whole store...')
fill = code(block(POUCH, 'proc,rune_pouch_fill'))
check('~rune_pouch_kinds_used < $slots' in fill,
      '...and Fill compares it against what the pouch can reach, which is what stops the plain '
      'pouch touching the fourth slot')
check('$inside > 0 |' in fill, 'a rune already inside tops up without needing a slot')
check('^rune_pouch_max_per_rune - $inside' in fill, 'and the cap is per kind, not per pouch')
check(const('rune_pouch_max_per_rune') == 16000, 'that cap is OSRS\'s 16,000')

# ============================================================================ 2
print('2. NOTHING in the magic path still looks only in the inventory')
mc = code(MAGIC)
# the only inv_total/inv_del of a rune allowed in magic.rs2 are the ones INSIDE the two new procs
for proc in ('proc,rune_total', 'proc,rune_del'):
    check('[' + proc + ']' in MAGIC, '~%s exists' % proc.split(',')[1])
inside = code(block(MAGIC, 'proc,rune_total')) + code(block(MAGIC, 'proc,rune_del'))
outside = mc
for b in ('proc,rune_total', 'proc,rune_del'):
    outside = outside.replace(code(block(MAGIC, b)), '')
stray = re.findall(r'inv_(?:total|del)\(inv, \$rune\w*', outside)
check(not stray, 'no rune is read or spent straight from the inventory outside those two: %s'
      % (stray or 'none'))
check(len(re.findall(r'~rune_total\(\$rune', mc)) == 4,
      'all four rune checks go through ~rune_total')
check(len(re.findall(r'~rune_del\(\$rune', mc)) == 4,
      'and all four spends through ~rune_del')
# and the same for the one place outside magic.rs2 that counted runes for a spell
check('~rune_total(naturerune)' in code(ALCH) and '~rune_total(firerune)' in code(ALCH),
      'alching a rune counts the same way the cast does')
check(not re.findall(r'inv_total\(inv, (nature|fire)rune\)', code(ALCH)),
      '...and no longer counts the pack alone')

# ============================================================================ 3
print('3. with no pouch, the two procs are exactly what the file did before')
rt = code(block(MAGIC, 'proc,rune_total'))
check('if (~rune_pouch_slots = 0) {' in rt and 'return(inv_total(inv, $rune));' in rt,
      '~rune_total short-circuits to the old expression when no pouch is carried')
check('$rune = null' in rt, 'and a null rune is 0 rather than a lookup')
rd = code(block(MAGIC, 'proc,rune_del'))
check('min(inv_total(inv, $rune), $count)' in rd, '~rune_del takes what it can from the pack...')
check(rd.index('inv_del(inv, $rune, $loose)') < rd.index('inv_del(rune_pouch_store, $rune, $rest)'),
      '...before it touches the pouch, which is the conservative order')
check('$count - $loose' in rd, 'and the pouch covers exactly the shortfall')
check('$rune = null | $count < 1' in rd, 'nothing is spent for a null rune or a zero cost')

# ============================================================================ 4
print('4. the pouch holds every rune a spell in this repo can ask for')
allowed = re.findall(r'^val=\d+,(\w+)$', block(ENUM, 'rune_pouch_runes'), re.M)
check(len(allowed) == const('rune_pouch_kinds'),
      'the enum has as many kinds as the constant claims: %d and %d'
      % (len(allowed), const('rune_pouch_kinds')))
check(len(set(allowed)) == len(allowed), 'and no rune twice')
needed = set()
for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
    for fn in files:
        if not fn.endswith('.dbrow'): continue
        t = read(os.path.join(dirpath, fn)[len(C) + 1:])
        if 'magic_spell_table' not in t and 'magic_combat' not in t: continue
        for m in re.findall(r'data=(?:runesrequired|rune4),([\w,]+)', t):
            needed |= {x for x in m.split(',') if not x.isdigit() and x != 'null'}
missing = sorted(needed - set(allowed))
check(not missing, 'every rune a spell needs is one the pouch holds: %s'
      % (missing or '%d runes over %d spells' % (len(needed), len(allowed))))
objp = {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/obj.pack').split('\n') if '=' in l)}
bad = [r for r in allowed if r not in objp]
check(not bad, 'and each is a real obj: %s' % (bad or 'all %d' % len(allowed)))
check('blankrune' not in allowed, 'rune essence is not a rune and does not go in, as in OSRS')

# ============================================================================ 5
print('5. Fill, Empty, Check and Destroy, on the helpers the other three storage items use')
for op, what in (('opheld1', 'Fill'), ('opheld2', 'Empty'), ('opheld3', 'Check'),
                 ('opheld5', 'Destroy')):
    for item in ('rune_pouch', 'divine_rune_pouch'):
        check('[%s,%s]' % (op, item) in POUCH, '%s has %s' % (item, what))
        check(objblock(item).get(op.replace('opheld', 'iop')) == what,
              '...and the obj advertises it')
for helper, what in (('~storage_empty_to_inv(rune_pouch_store', 'Empty'),
                     ('~storage_check(rune_pouch_store', 'Check'),
                     ('@storage_destroy(', 'Destroy')):
    check(POUCH.count(helper) == 2,
          '%s reuses the shared helper, for both pouches' % what)
for h in ('proc,storage_empty_to_inv', 'proc,storage_check', 'label,storage_destroy'):
    check('[' + h + ']' in STORAGE, '...which still exists: %s' % h.split(',')[1])

# ============================================================================ 6
print('6. the upgrade is OSRS\'s recipe with the one unobtainable ingredient swapped')
up = code(block(POUCH, 'label,rune_pouch_upgrade'))
check('stat_base(crafting) < ^rune_pouch_craft_level' in up, 'it wants the level, unboosted')
check(const('rune_pouch_craft_level') == 75, 'which is OSRS\'s 75 Crafting')
check('inv_del(inv, thread, 1);' in up, 'it spends a thread')
check('inv_del(inv, rune_pouch, 1);' in up and 'inv_add(inv, divine_rune_pouch, 1);' in up,
      'and swaps the pouch for the divine one')
check('stat_advance' not in up, 'and gives no experience, as OSRS gives none')
check('case rune_pouch : @rune_pouch_upgrade;' in LEATHER,
      'it hangs off the needle\'s own [opheldu,needle] switch')
check(LEATHER.count('[opheldu,needle]') == 1,
      '...which is still declared once - a second would not compile')
check('[opheldu,rune_pouch]' in POUCH and 'last_useitem = needle' in POUCH,
      'and the pouch answers the other direction too')
rev = code(block(POUCH, 'opheld4,divine_rune_pouch'))
check('~rune_pouch_kinds_used > oc_param(rune_pouch, pouch_slots)' in rev,
      'Revert refuses while a fourth kind is inside rather than dropping it')
check('inv_add(inv, thread, 1);' in rev, 'and hands the thread back')
check(objblock('divine_rune_pouch').get('iop4') == 'Revert', 'the divine pouch advertises Revert')
check('iop4' not in objblock('rune_pouch'), 'and the plain one has nothing to revert')

# ============================================================================ 7
print('7. what happens to the runes when you die is a decision, not an oversight')
check('inv_dropall(looting_bag_store' in DEATH,
      'the looting bag still drops its contents, as OSRS does')
check('rune_pouch_store' not in DEATH,
      'and the pouch keeps its runes, as the herb sack and seed box keep theirs - the one place '
      'this differs from OSRS PvP, deliberately')
check(objblock('rune_pouch').get('tradeable') == 'no'
      and objblock('divine_rune_pouch').get('tradeable') == 'no',
      'both pouches are untradeable, as in OSRS')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
