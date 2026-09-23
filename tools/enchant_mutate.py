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
 (MAGICIF, 'script4=gt,86\ngraphic=i474_403,0', 'script4=gt,87\ngraphic=i474_403,0',
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
 (OBJPACK, '=berserker_necklace\n', '=berserker_necklace_gone\n',
  '2 the berserker necklace is an obj in this build'),
 (DBROW, 'data=convertobj,onyx_necklace,berserker_necklace,', 'data=convertobj,onyx_necklace,onyx_necklace,',
  '2 ...and Lvl-6 Enchant turns an onyx necklace into it'),

 # ---- 3, the effects
 # BOTH onyx lines at once - the amulet's and the necklace's share this seq and spotanim, so either
 # alone still leaves the row using it and the check green.
 (DBROW, 'enchanted_onyx_amulet,human_enchantamuletlvl3,enchant_amulet2_lvl6,enchant_onyx_amulet\ndata=convertobj,onyx_necklace,berserker_necklace,human_enchantamuletlvl3,enchant_amulet2_lvl6,', 'enchanted_onyx_amulet,human_enchantamuletlvl9,enchant_amulet2_lvl6,enchant_onyx_amulet\ndata=convertobj,onyx_necklace,berserker_necklace,human_enchantamuletlvl9,enchant_amulet2_lvl6,',
  '3 seq human_enchantamuletlvl3 is in seq.pack and the row uses it'),
 (DBROW, 'enchanted_onyx_amulet,human_enchantamuletlvl3,enchant_amulet2_lvl6,enchant_onyx_amulet\ndata=convertobj,onyx_necklace,berserker_necklace,human_enchantamuletlvl3,enchant_amulet2_lvl6,', 'enchanted_onyx_amulet,human_enchantamuletlvl3,enchant_amulet2_lvl7,enchant_onyx_amulet\ndata=convertobj,onyx_necklace,berserker_necklace,human_enchantamuletlvl3,enchant_amulet2_lvl7,',
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
 (RS2, '        check_castable_buttons()\n        check_varp_booleans(T)\n\n    errors',
       '        check_varp_booleans(T)\n\n    errors',
  '5 ...and main() actually runs it'),
 # RETARGETED 2026-09-21: the three Teleother keys these used to point at are gone, because the
 # Teleother round built the spells. Tele Block is the entry that remains, and its note is the
 # accurate kind - it needs a mechanism, not a panel.
 (SPEC, '"magic:com_531": "Tele Block, level 85. Needs a teleport-blocked timer on the target and the wilderness teleport paths to honour it. The three Teleother buttons used to sit beside this one saying the accept/decline dialogue did not exist; it did, as inter_251.if, and all three are built (2026-09-21). This one\'s note is the accurate kind: what it needs is a mechanism, not a panel."', '"magic:com_531": ""',
  '5 magic:com_531 carries a reason'),
 (SPEC, '"magic:com_531"', '"magic:com_5310"', '5 every key names a component that exists'),
 (SPEC, '"magic:com_531"', '"magic:enchant_lvl6"',
  '5 nothing in the spec is excusing a button that is wired'),
 (SPEC, 'ancient_magic.if is a hand-built reconstruction with an invented layout, made when '
         'this file could not be found', 'the server uses something else',
  '5 and the real ancient spellbook is named in it rather than quietly skipped'),
 (SPEC, '  "inter_267:*": ', '  "magic:com_542": "spare",\n  "inter_267:*": ',
  '5 the spec excuses exactly the entries it is pinned to, and no more'),
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
