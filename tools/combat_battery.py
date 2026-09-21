"""Battery for the three things play reported on 2026-09-21, and the two it turned up.

All five were the same shape: CONTENT THAT EXISTS AND CANNOT BE REACHED WITHOUT ENDING THE SESSION.
A weapon with no attack sound, and five finished spells with no row in the table. rs2check rules
19, 21 and 22 are where the general cases live and the selftest proves those go red; what is here
is the part a linter cannot know - the numbers, which came off the wiki on 2026-09-21, and the
autocast arming, which is a three-way agreement between a script, a varbit and an interface.

    python3 tools/combat_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

AUTO = read('scripts/skill_combat/scripts/player/auto_cast.rs2')
STYLES = read('scripts/skill_combat/scripts/player/player_attackstyles.rs2')
STAFFIF = read('scripts/skill_combat/interfaces/magic/combat_staff_2.if')
VARBIT = read('scripts/_unpack/377/all.varbit')
ROWS = read('scripts/skill_combat/configs/magic/magic_combat_spells.dbrow')
MAGIC = read('scripts/skill_combat/scripts/player/player_magic.rs2')
IBANPVM = read('scripts/skill_combat/scripts/player/spells/scripts/ibans_blast.rs2')
IBANPVP = read('scripts/skill_combat/scripts/pvp/spells/scripts/ibans_blast.rs2')
UPASS = read('scripts/quests/quest_upass/scripts/quest_upass.rs2')

def block(txt, name):
    return txt.split('[' + name + ']', 1)[1].split('\n[', 1)[0] if '[' + name + ']' in txt else ''

def row(name):
    out = {}
    for line in block(ROWS, name).split('\n'):
        t = line.split('//')[0].strip()
        if t.startswith('data='):
            k, v = t[5:].split(',', 1)
            out[k] = v.strip()
    return out


print('1. choosing an autocast spell arms it')

# THE BUG: @open_autocast_interface writes %autocast_set = 0 before the picker opens, and choosing
# a spell used to leave it there - so the spell name appeared, the toggle stayed grey, and the next
# click on an npc was a melee swing. Reported as "ibans staff autocasting fire wave" followed by a
# melee script error.
_set = block(AUTO, 'label,set_autocast_spell')
check('%autocast_spell = $spell;' in _set, 'the chosen spell is remembered')
check('%autocast_set = 1;' in _set, '...and autocast is turned ON by choosing, the way OSRS does it')
check(_set.index('%autocast_set = 1;') > _set.index('if (~check_spell_requirements($spell_data) = false) {'),
      '...after the requirement check, so a spell you cannot cast does not arm it')

# and the three places that bit lives all have to mean the same bit
_vb = block(VARBIT, 'autocast_set')
check('basevar=lastcastspell' in _vb and 'startbit=0' in _vb and 'endbit=0' in _vb,
      'autocast_set is one bit of lastcastspell')
check('script1op1=testbit,lastcastspell,0' in STAFFIF,
      '...which is the bit the toggle button reads, so the lamp matches the state')
check('%autocast_set = togglebit(%autocast_set, 0);' in STYLES,
      '...and the toggle still flips that same bit')
check('testbit(%autocast_set, 0) = ^true & %autocast_spell > 0' in AUTO,
      'and combat still needs BOTH the bit and a spell before it casts')

print()
print('2. the five spells that had no row')

# EVERY NUMBER HERE IS THE WIKI'S, read 2026-09-21. Experience is stored x100 as every other row in
# that file is. This is the check that cannot come from the code, because the code is what it is
# checking - so the figures are written out once, here, with what they mean.
WIKI = {
    # row name                       level xp/100 maxhit runes                              worn
    'magic_combat_iban_blast':       (50, 3000, 25, 'firerune,5,deathrune,1,null,null',     'ibanstaff'),
    'magic_combat_crumble_undead':   (39, 2450, 15, 'airrune,2,earthrune,2,chaosrune,1',    None),
    'magic_combat_saradomin_strike': (60, 3500, 20, 'airrune,4,firerune,2,bloodrune,2',     'saradomin_staff'),
    'magic_combat_claws_of_guthix':  (60, 3500, 20, 'airrune,4,firerune,1,bloodrune,2',     'guthix_staff'),
    'magic_combat_flames_of_zamorak':(60, 3500, 20, 'airrune,1,firerune,4,bloodrune,2',     'zamorak_staff'),
}
for name, (lvl, xp, maxhit, runes, worn) in sorted(WIKI.items()):
    d = row(name)
    short = name[len('magic_combat_'):]
    # BY THE SPELL ID, NOT THE BLOCK NAME. The block name is a label nothing reads; ~get_spell_data
    # finds a row by db_find(magic_spell_table:spell, ...), so a row whose spell field says
    # something else is exactly as absent as no row at all - and a mutation that renamed the id
    # walked straight past the first version of this check, which only asked whether the block
    # existed.
    check(d.get('spell') == '^' + short,
          '%s has a row under its own spell id - this is the whole bug' % short)
    check(d.get('levelrequired') == str(lvl) and d.get('experience') == str(xp)
          and d.get('maxhit') == str(maxhit),
          '...%s: level %d, %s xp, max %d' % (short, lvl, xp / 100.0, maxhit))
    check(d.get('runesrequired') == runes, '...and costs %s' % runes.replace(',null,null', ''))
    if worn:
        check(d.get('wornrequired') == worn and 'reqmessage' in ' '.join(d),
              '...and needs %s wielded, with a message saying so' % worn)
    else:
        check('wornrequired' not in d, '...and needs nothing wielded, which is right for it')

# the two fields player_magic.rs2 reads with no guard at all
for name in sorted(WIKI):
    d = row(name)
    check('anim' in d and 'spotanim_target' in d,
          '%s carries the two fields that are read unguarded' % name[len('magic_combat_'):])

# the god spells land rather than fly, and their charged max is the wiki's 30
GODS = ['magic_combat_saradomin_strike', 'magic_combat_claws_of_guthix',
        'magic_combat_flames_of_zamorak']
check(all('spotanim_proj' not in row(n) for n in GODS),
      'no god spell carries a projectile - in OSRS they land on the target')
check(all(row(n).get('continue_by_autocast') == 'no' for n in GODS),
      '...and none of them autocasts: the only god staves here are the plain ones, which cannot')
check(len({row(n)['spotanim_target'] for n in GODS}) == 3,
      '...and each has its own impact effect, not one shared between them')
_scaled = [int(row(n)['maxhit']) * 3 // 2 for n in GODS]
check(_scaled == [30, 30, 30],
      'the scale(3, 2, $maxhit) in their scripts turns 20 into the wiki\'s charged 30')
check(row('magic_combat_crumble_undead').get('continue_by_autocast') == 'yes',
      'crumble undead DOES continue an autocast, which player_magic.rs2 says is OSRS behaviour')

print()
print('3. Iban\'s staff charges')

check('%iban_staff_charges < 1' in IBANPVM and '%iban_staff_charges = sub(%iban_staff_charges, 1);' in IBANPVM,
      'a cast at an npc costs one charge and is refused at zero')
check('%iban_staff_charges < 2' in IBANPVP and '%iban_staff_charges = sub(%iban_staff_charges, 2);' in IBANPVP,
      'a cast at a player costs two, which is what OSRS charges')
check('%iban_staff_charges = 120;' in UPASS,
      'and Underground Pass is still what fills it, at 120')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
