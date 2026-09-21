"""Battery for Lvl-6 Enchant, and for the rule that found it.

The spell was never written: the 377 interface draws the button, with its real level check and
its real rune checks, and the server had no trigger for it. So the interesting checks here are
the ones that hold the hand-written dbrow against the CACHE's own button - the level, the three
rune counts - because those two came from different places and neither was copied from the other.
The wiki supplies the xp, on the scale the five rows above it already use.

The second half checks the linter rule and its exception spec, which is the part that generalises:
the spec must not excuse a button that is wired, or name one that does not exist.

    python3 tools/enchant_battery.py
"""
import json
import os
import re

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')


fails = 0


def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1


DBROW = read('scripts/skill_magic/configs/magic_spells.dbrow')
CONST = read('scripts/skill_combat/configs/magic/spells.constant')
TRIG = read('scripts/skill_magic/scripts/spells/enchant.rs2')
MAGICIF = read('scripts/skill_magic/interfaces/magic.if')
IFPACK = read('pack/interface.pack')
OBJPACK = read('pack/obj.pack')
ALLOBJ = read('scripts/_unpack/377/all.obj')
RS2CHECK = read('tools/rs2check.py')
SPEC = json.loads(read('tools/unwiredspells.json'))


def block(txt, name):
    """The [name] block of a config, without the next block's header."""
    key = '[' + name + ']'
    if key not in txt:
        return ''
    return txt.split(key, 1)[1].split('\n[', 1)[0]


def objname(name):
    m = re.search(r'^name=(.+)$', block(ALLOBJ, name), re.M)
    return m.group(1).strip() if m else None


ROW = block(DBROW, 'magic_spell_enchant_level6')
BUTTON = block(MAGICIF, 'enchant_lvl6')

# ============================================================================ 1
print('1. the row and the cache\'s own button agree, and they came from different places')
check(ROW != '', 'magic_spell_table has a Lvl-6 Enchant row at all')
check('data=levelrequired,87' in ROW, 'the row asks for level 87')
check('script4=gt,86' in BUTTON, "...and the button the client draws lights up above 86, which is 87")
check('data=runesrequired,firerune,20,earthrune,20,cosmicrune,1' in ROW,
      'the row costs 20 fire, 20 earth and 1 cosmic')
check(re.search(r'script2op1=inv_count,inventory:inv,firerune\b', BUTTON) is not None
      and 'script2=gt,19' in BUTTON,
      '...and the button counts fire runes and wants more than 19 of them')
check(re.search(r'script3op1=inv_count,inventory:inv,earthrune\b', BUTTON) is not None
      and 'script3=gt,19' in BUTTON, '...earth the same')
check(re.search(r'script1op1=inv_count,inventory:inv,cosmicrune\b', BUTTON) is not None
      and 'script1=gt,0' in BUTTON, '...and one cosmic')
check('data=experience,970' in ROW, 'it gives 970 xp')
# The five rows above are 175, 370, 590, 670, 780 and the wiki's figures for those spells are
# 17.5, 37, 59, 67 and 78. The scale is the table's, so 97 -> 970 is arithmetic, not a choice.
check(re.findall(r'data=experience,(\d+)', DBROW)[:6] ==
      ['175', '370', '590', '670', '780', '970'],
      '...which is the wiki figure on the same times-ten scale as the five rows above it')
check('data=members,true' in ROW, 'and it is members, like every onyx item')

# ============================================================================ 2
print('2. the two conversions, and the third that does not exist')
check('data=convertobj,onyx_ring,enchanted_onyx_ring,' in ROW, 'onyx ring becomes the enchanted ring')
check(objname('enchanted_onyx_ring') == 'Ring of stone',
      "...which the cache calls Ring of stone, so it is the right obj")
check('data=convertobj,strung_onyx_amulet,enchanted_onyx_amulet,' in ROW,
      'the STRUNG onyx amulet becomes the enchanted amulet')
check(objname('enchanted_onyx_amulet') == 'Amulet of fury', '...which the cache calls Amulet of fury')
check('data=specificobj_reqmessage,unstrung_onyx_amulet,' in ROW,
      'an unstrung one is told to get a string on it first')
check('convertobj,unstrung_onyx_amulet' not in ROW, '...and cannot be enchanted while unstrung')
# The one Corey asked for and the one this cache cannot have. If a berserker necklace is ever
# imported, this check goes red and the row below it should be written.
check(not re.search(r'^\d+=berserker_necklace$', OBJPACK, re.M),
      'there is still no berserker necklace obj in this cache')
check('convertobj,onyx_necklace' not in ROW,
      '...so the onyx necklace has no row, rather than one pointing at nothing')

print('3. every effect the row names is really in the packs')
for kind, pack, names in (
        ('seq', read('pack/seq.pack'), ['human_cast_enchantring', 'human_enchantamuletlvl3']),
        ('spotanim', read('pack/spotanim.pack'), ['enchant_ring', 'enchant_amulet2_lvl6']),
        ('synth', read('pack/synth.pack'), ['enchant_onyx_ring', 'enchant_onyx_amulet'])):
    for n in names:
        check(re.search(r'^\d+=' + re.escape(n) + r'$', pack, re.M) is not None
              and n in ROW, '%s %s is in %s.pack and the row uses it' % (kind, n, kind))

# ============================================================================ 4
print('4. the wiring: an id, a trigger, and a component that can be named')
ids = dict(re.findall(r'\^(\w+)\s*=\s*(\d+)', CONST))
check(ids.get('enchant_lvl6') == '228', '^enchant_lvl6 is 228')
check(list(ids.values()).count('228') == 1, '...and nothing else in spells.constant is 228')
check('data=spell,^enchant_lvl6' in ROW, 'the row is keyed on that constant')
check('[opheldt,magic:enchant_lvl6]@magic_spell_enchant(^enchant_lvl6, last_slot);' in TRIG,
      'and an opheldt trigger casts it through the same label as the other five')
check('[com_549]' not in MAGICIF, 'the component no longer carries its unpacked name')
check('6003=magic:enchant_lvl6' in IFPACK,
      '...and interface.pack renames it in place, at the id the cache gave it')
check('actiontarget=heldobj' in BUTTON and 'buttontype=target' in BUTTON,
      'the button targets a held item, which is what opheldt answers')

# ============================================================================ 5
print('5. the rule that found it, and its list of excuses')
check('def check_castable_buttons()' in RS2CHECK, 'rs2check has the uncastable-button rule')
check('23:   ("probe_spellbook.if", 3),' in RS2CHECK,
      '...and the selftest proves it can go red, which an inert rule cannot')
check('check_castable_buttons()' in RS2CHECK.split('def main(')[1],
      '...and main() actually runs it')
buttons, cur, kv = {}, None, {}
for raw in MAGICIF.split('\n'):
    s = raw.split('//')[0].strip()
    if s.startswith('[') and s.endswith(']'):
        if cur and kv.get('graphic', '').startswith('magicoff'):
            buttons[cur] = kv
        cur, kv = s[1:-1], {}
    elif '=' in s and cur:
        k, v = s.split('=', 1)
        kv.setdefault(k.strip(), v.strip())
if cur and kv.get('graphic', '').startswith('magicoff'):
    buttons[cur] = kv
spec_keys = [k for k in SPEC if not k.startswith('_')]
check(len(spec_keys) == 5, 'the spec excuses five things and no more')
wired = set()
for dp, _d, fs in os.walk(os.path.join(C, 'scripts')):
    for fn in fs:
        if fn.endswith('.rs2'):
            body = open(os.path.join(dp, fn), newline='').read().replace('\r\n', '\n')
            wired |= set(re.findall(r'^\s*\[[a-z_]+\s*,\s*([a-z0-9_]+):([a-z0-9_]+)\s*\]',
                                    body, re.M))
# These two are aggregated rather than one check per key, so the wording a mutation has to be
# named after is a line this battery prints on a CLEAN tree - tools/mutate_labels.py reads the
# clean run, and a message that only exists once something is broken cannot be a label.
ghosts, stale = [], []
for k in spec_keys:
    iface, comp = k.split(':', 1)
    check(bool(SPEC[k].strip()), '%s carries a reason' % k)
    if comp == '*':
        continue
    if iface == 'magic' and comp not in buttons:
        ghosts.append(k)
    if (iface, comp) in wired:
        stale.append(k)
check(not ghosts, 'every key names a component that exists'
      + (' - these do not: %s' % ghosts if ghosts else ''))
check(not stale, 'nothing in the spec is excusing a button that is wired'
      + (' - but these are: %s' % stale if stale else ''))
# Not just "is it excused" - the excuse has to say WHAT the server is running instead and where
# the finding is written down, or the entry becomes the place the finding goes to die.
_anc = SPEC.get('inter_267:*', '')
check('ancient_magic.if' in _anc and 'claude/' in _anc,
      'and the real ancient spellbook is named in it rather than quietly skipped')

print()
print('enchant battery: %s' % ('%d FAILED' % fails if fails else 'all checks pass'))
raise SystemExit(1 if fails else 0)
