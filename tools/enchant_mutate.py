#!/usr/bin/env python3
"""Mutation test for tools/enchant_battery.py. Same runner as compost_mutate.py.

Every entry breaks Lvl-6 Enchant, or the rule that found it, in one specific way, and expects the
battery to go red with the check that is named. A GREEN line is a hole in the battery.

Anchors are chosen to be unique to the lvl-6 row - twice now a mutation in this repo has edited
the wrong thing because replace(..., 1) takes the FIRST match and an identical line sat higher in
the file. Every pattern below was counted before it was used.

    python3 tools/enchant_mutate.py
    python3 tools/enchant_mutate.py "spec"     # just the ones whose name contains that
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'enchant_mutate_work')

DBROW = 'scripts/skill_magic/configs/magic_spells.dbrow'
CONST = 'scripts/skill_combat/configs/magic/spells.constant'
TRIG = 'scripts/skill_magic/scripts/spells/enchant.rs2'
MAGICIF = 'scripts/skill_magic/interfaces/magic.if'
IFPACK = 'pack/interface.pack'
OBJPACK = 'pack/obj.pack'
ALLOBJ = 'scripts/_unpack/377/all.obj'
RS2 = 'tools/rs2check.py'
SPEC = 'tools/unwiredspells.json'

MUTS = [
 # ---- 1, the numbers, and the cache's own button as the second opinion
 (DBROW, 'data=levelrequired,87', 'data=levelrequired,88',
  '1 the row asks for level 87'),
 (MAGICIF, 'script4=gt,86\ngraphic=magicoff2,34', 'script4=gt,87\ngraphic=magicoff2,34',
  '1 ...and the button the client draws lights up above 86, which is 87'),
 (DBROW, 'data=runesrequired,firerune,20,earthrune,20,cosmicrune,1',
         'data=runesrequired,firerune,15,earthrune,15,cosmicrune,1',
  '1 the row costs 20 fire, 20 earth and 1 cosmic'),
 (MAGICIF, 'script2=gt,19', 'script2=gt,14',
  '1 ...and the button counts fire runes and wants more than 19 of them'),
 (MAGICIF, 'script3=gt,19', 'script3=gt,14', '1 ...earth the same'),
 (MAGICIF, 'script1op1=inv_count,inventory:inv,cosmicrune\n'
           'script1op2=inv_count,rune_pouch_mirror:runes,cosmicrune\n'
           'script2op1=inv_count,inventory:inv,firerune',
           'script1op1=inv_count,inventory:inv,naturerune\n'
           'script1op2=inv_count,rune_pouch_mirror:runes,naturerune\n'
           'script2op1=inv_count,inventory:inv,firerune',
  '1 ...and one cosmic'),
 (DBROW, 'data=experience,970', 'data=experience,780', '1 it gives 970 xp'),
 (DBROW, 'data=members,true\ndata=levelrequired,87', 'data=members,false\ndata=levelrequired,87',
  '1 and it is members, like every onyx item'),

 # ---- 2, what turns into what
 (DBROW, 'data=convertobj,onyx_ring,enchanted_onyx_ring,', 'data=convertobj,onyx_ring,ring_of_wealth,',
  '2 onyx ring becomes the enchanted ring'),
 (ALLOBJ, 'name=Ring of stone', 'name=Ring of pebbles',
  '2 ...which the cache calls Ring of stone, so it is the right obj'),
 (DBROW, 'data=convertobj,strung_onyx_amulet,enchanted_onyx_amulet,', '',
  '2 the STRUNG onyx amulet becomes the enchanted amulet'),
 (ALLOBJ, 'name=Amulet of fury', 'name=Amulet of mild irritation',
  '2 ...which the cache calls Amulet of fury'),
 (DBROW, 'data=specificobj_reqmessage,unstrung_onyx_amulet,', 'data=ignored_reqmessage,unstrung_onyx_amulet,',
  '2 an unstrung one is told to get a string on it first'),
 (DBROW, 'data=convertobj,strung_onyx_amulet,enchanted_onyx_amulet,',
         'data=convertobj,unstrung_onyx_amulet,enchanted_onyx_amulet,',
  '2 ...and cannot be enchanted while unstrung'),
 (OBJPACK, '6585=enchanted_onyx_amulet', '6585=berserker_necklace',
  '2 there is still no berserker necklace obj in this cache'),
 (DBROW, 'data=additional_reqmessage,This spell can only be cast on onyx rings and amulets.',
         'data=convertobj,onyx_necklace,onyx_necklace,human_cast_enchantring,enchant_ring,enchant_onyx_ring',
  '2 ...so the onyx necklace has no row, rather than one pointing at nothing'),

 # ---- 3, the effects
 (DBROW, 'human_enchantamuletlvl3,enchant_amulet2_lvl6', 'human_enchantamuletlvl9,enchant_amulet2_lvl6',
  '3 seq human_enchantamuletlvl3 is in seq.pack and the row uses it'),
 (DBROW, 'enchant_amulet2_lvl6,enchant_onyx_amulet', 'enchant_amulet2_lvl7,enchant_onyx_amulet',
  '3 spotanim enchant_amulet2_lvl6 is in spotanim.pack and the row uses it'),
 (DBROW, 'enchant_ring,enchant_onyx_ring', 'enchant_ring,enchant_onyx_band',
  '3 synth enchant_onyx_ring is in synth.pack and the row uses it'),

 # ---- 4, the wiring
 (CONST, '^enchant_lvl6 = 228', '^enchant_lvl6 = 229', '4 ^enchant_lvl6 is 228'),
 (CONST, '^ape_atoll_teleport = 227', '^ape_atoll_teleport = 228',
  '4 ...and nothing else in spells.constant is 228'),
 (TRIG, '[opheldt,magic:enchant_lvl6]@magic_spell_enchant(^enchant_lvl6, last_slot);', '',
  '4 and an opheldt trigger casts it through the same label as the other five'),
 (MAGICIF, '[enchant_lvl6]', '[com_549]', '4 the component no longer carries its unpacked name'),
 (IFPACK, '6003=magic:enchant_lvl6', '6003=magic:com_549',
  '4 ...and interface.pack renames it in place, at the id the cache gave it'),
 (MAGICIF, 'actiontarget=heldobj\naction=Enchant Lvl-6 Jewelry',
           'actiontarget=npc\naction=Enchant Lvl-6 Jewelry',
  '4 the button targets a held item, which is what opheldt answers'),

 # ---- 5, the rule and its excuses. The rule is only coverage if it can go red, and the spec is
 # only honest if it cannot quietly grow to cover the next thing that breaks.
 (RS2, 'def check_castable_buttons():', 'def check_castable_buttons_disabled():',
  '5 rs2check has the uncastable-button rule'),
 (RS2, '    23:   ("probe_spellbook.if", 3),\n', '',
  '5 ...and the selftest proves it can go red, which an inert rule cannot'),
 (RS2, '        check_interfaces()\n        check_castable_buttons()\n\n    errors',
       '        check_interfaces()\n\n    errors',
  '5 ...and main() actually runs it'),
 (SPEC, '"Teleother Lumbridge, level 74. Needs the teleother accept/decline dialogue and '
         'target consent - none of that exists yet."', '""',
  '5 magic:com_511 carries a reason'),
 (SPEC, '"magic:com_521"', '"magic:com_5210"', '5 every key names a component that exists'),
 (SPEC, '"magic:com_531"', '"magic:enchant_lvl6"',
  '5 nothing in the spec is excusing a button that is wired'),
 (SPEC, 'ancient_magic.if is a hand-built reconstruction with an invented layout, made when '
         'this file could not be found', 'the server uses something else',
  '5 and the real ancient spellbook is named in it rather than quietly skipped'),
 (SPEC, '  "magic:com_541": ', '  "magic:com_542": "spare",\n  "magic:com_541": ',
  '5 the spec excuses five things and no more'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    muts = [m for m in MUTS if not only or only in m[3]]
    fails = loose = 0
    for path, find, repl, why in muts:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-34s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        if raw.count(f) != 1:
            print('  SKIP (pattern is not unique - %d hits) %-20s %s'
                  % (raw.count(f), os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'enchant_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:52] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-64s %s' % (state, why, note))
    print()
    if fails:
        print('%d MUTATIONS SURVIVED' % fails)
    elif loose:
        print('every mutation was caught, but %d by a check other than its own' % loose)
    else:
        print('every mutation was caught, each by its own check')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
