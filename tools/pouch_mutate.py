#!/usr/bin/env python3
"""Mutation test for tools/pouch_battery.py. Same runner as pet_mutate.py.

    python3 tools/pouch_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'pouch_mutate_work')

MAGIC = 'scripts/skill_magic/scripts/magic.rs2'
POUCH = 'scripts/storage_items/scripts/rune_pouch.rs2'
OBJ = 'scripts/storage_items/configs/rune_pouch.obj'
INV = 'scripts/storage_items/configs/storage_items.inv'
CONST = 'scripts/storage_items/configs/rune_pouch.constant'
ENUM = 'scripts/storage_items/configs/rune_pouch.enum'
ALCH = 'scripts/skill_magic/scripts/spells/alchemy.rs2'
LEATHER = 'scripts/skill_crafting/scripts/leather/leather.rs2'
DEATH = 'scripts/player/scripts/death.rs2'
UI = 'scripts/storage_items/scripts/rune_pouch_ui.rs2'
LOGIN = 'scripts/login_logout/scripts/login.rs2'
MAINIF = 'scripts/storage_items/interfaces/rune_pouch_main.if'
MIRRORIF = 'scripts/storage_items/interfaces/rune_pouch_mirror.if'
MAGICIF = 'scripts/skill_magic/interfaces/magic.if'
STAFFIF = 'scripts/skill_combat/interfaces/magic/staff_spells.if'
SPEC = 'tools/nosourcespec.json'

MUTS = [
 # ---- 6, the recipe's real second ingredient
 (POUCH, 'inv_del(inv, thread_of_elidinis, 1);', 'inv_del(inv, thread, 1);',
  '6 it spends a Thread of Elidinis'),
 (POUCH, 'if (inv_total(inv, thread_of_elidinis) < 1) {', 'if (inv_total(inv, thread) < 1) {',
  '6 ...and says so when you have none'),
 (POUCH, 'inv_add(inv, thread_of_elidinis, 1);', 'inv_add(inv, thread, 1);',
  '6 and hands the Thread of Elidinis back'),
 (SPEC, '"rune_pouch.rs2:opheld4,divine_rune_pouch"', '"rune_pouch.rs2"',
  '6 ...and only that one script is excused from the obtainability sweep'),

 # ---- 8, the window
 (UI, '[opheld3,rune_pouch] ~rune_pouch_open;\n', '',
  '8 Check opens the window, for both pouches'),
 (UI, 'if ($slots = 0) {', 'if ($slots < 0) {',
  '8 it does nothing when you are not carrying a pouch'),
 (UI, 'inv_transmit(inv, rune_pouch_side:inv);', 'inv_transmit(worn, rune_pouch_side:inv);',
  '8 it transmits the store and your pack'),
 (UI, 'inv_stoptransmit(rune_pouch_side:inv);', 'inv_stoptransmit(rune_pouch_mirror:runes);',
  '8 and stops both on close'),
 # The one that matters most: stopping the mirror on close would break every spell the moment the
 # player looked in the pouch once.
 (UI, '// The mirror is deliberately NOT stopped here. It is not part of this window.',
      'inv_stoptransmit(rune_pouch_mirror:runes);',
  '8 ...but NOT the mirror, which is not part of this window'),
 (UI, 'if ($slot >= ~rune_pouch_slots) {', 'if ($slot >= inv_size(rune_pouch_store)) {',
  '8 a slot the carried pouch cannot reach will not empty'),
 (UI, 'def_int $take = min($count, inv_total(rune_pouch_store, $rune));',
      'def_int $take = $count;',
  '8 ...and it never takes more than is there'),
 (UI, 'if_settext(rune_pouch_main:name2, ~rune_pouch_slotname(2));\n', '',
  '8 slot 2 gets its rune name written under it'),
 (UI, 'if_sethide(rune_pouch_main:locked, false);', 'if_sethide(rune_pouch_main:locked, true);',
  '8 the fourth slot is marked locked for the plain pouch'),
 (MAINIF, 'option4=Remove All', 'option4=Destroy', '8 the window slot advertises Remove All'),
 (POUCH, '[opheldu,divine_rune_pouch]\nif (~rune_pouch_put(last_useitem, ^max_32bit_int) = true) {\n    return;\n}\n~displaymessage(^dm_default);\n',
         '',
  '8 a rune used on either pouch goes in, which is how anyone tries it first'),
 (UI, '~rune_pouch_accepts($obj) = false', '$obj = null', '8 only a rune goes in'),
 (UI, '$inside = 0 & ~rune_pouch_kinds_used >= ~rune_pouch_slots',
      '~rune_pouch_kinds_used >= inv_size(rune_pouch_store)',
  '8 ...a new kind needs a slot the pouch can reach'),

 # ---- 9, the mirror
 (LOGIN, '~rune_pouch_mirror_start;\n', '',
  '9 ...and login starts it, so it runs for the whole session'),
 (MIRRORIF, 'type=inv', 'type=layer', '9 the mirror component is an inv'),
 (MIRRORIF, 'width=4', 'width=3', '9 ...and as many slots as the store has'),
 # A rune the spellbook can ask for that the client cannot see in the pouch: the spell stays grey
 # and the cast is refused before a packet is sent, which is the whole bug.
 (MAGICIF, 'script1op2=inv_count,rune_pouch_mirror:runes,airrune\n', '',
  '9 magic.if counts every pack rune in the pouch too'),
 (STAFFIF, 'script1op2=inv_count,rune_pouch_mirror:runes,airrune\n', '',
  '9 staff_spells.if counts every pack rune in the pouch too'),
 (MAGICIF, 'script1op1=inv_count,inventory:inv,airrune',
           'script1op1=inv_count,inventory:inv,banana\nscript1op30=inv_count,rune_pouch_mirror:runes,banana',
  '9 ...and banana is not, being no kind of rune'),
 # 1 - the store and the slot limits
 (OBJ, 'param=pouch_slots,3', 'param=pouch_slots,4',
  '1 the rune pouch reaches three of them'),
 (CONST, '^rune_pouch_max_per_rune = 16000', '^rune_pouch_max_per_rune = 1000',
  '1 that cap is OSRS\'s 16,000'),
 # Fill comparing against the STORE rather than against what the pouch can reach: the plain pouch
 # then quietly holds four kinds, which is the whole point of the param.
 (POUCH, '~rune_pouch_kinds_used < $slots', '~rune_pouch_kinds_used < inv_size(rune_pouch_store)',
  '1 ...and Fill compares it against what the pouch can reach'),
 (POUCH, '$inside > 0 |', '$inside > -1 |',
  '1 a rune already inside tops up without needing a slot'),
 # 2 - a rune read or spend left looking only in the pack. One of these is the whole feature
 # silently not working for that spell.
 (MAGIC, 'if (~rune_total($rune2) < $rune_count2 & $rune2 ! null) {',
         'if (inv_total(inv, $rune2) < $rune_count2 & $rune2 ! null) {',
  '2 all four rune checks go through ~rune_total'),
 (MAGIC, '~rune_del($rune3, $rune_count3);', 'inv_del(inv, $rune3, $rune_count3);',
  '2 and all four spends through ~rune_del'),
 (ALCH, '~rune_total(naturerune)', 'inv_total(inv, naturerune)',
  '2 alching a rune counts the same way the cast does'),
 # 3 - the order and the shortfall
 (MAGIC, 'def_int $loose = min(inv_total(inv, $rune), $count);', 'def_int $loose = 0;',
  '3 ~rune_del takes what it can from the pack...'),
 (MAGIC, 'if (~rune_pouch_slots = 0) {\n    return(inv_total(inv, $rune));\n}\n', '',
  '3 ~rune_total short-circuits to the old expression when no pouch is carried'),
 (MAGIC, 'def_int $rest = calc($count - $loose);', 'def_int $rest = $count;',
  '3 and the pouch covers exactly the shortfall'),
 (MAGIC, 'if ($rune = null | $count < 1) {', 'if ($count < 1) {',
  '3 nothing is spent for a null rune or a zero cost'),
 # 4 - the runes it holds
 (ENUM, 'val=9,lawrune\n', '',
  '4 every rune a spell needs is one the pouch holds'),
 (ENUM, 'val=0,airrune', 'val=0,blankrune',
  '4 rune essence is not a rune and does not go in, as in OSRS'),
 (CONST, '^rune_pouch_kinds = 19', '^rune_pouch_kinds = 18',
  '4 the enum has as many kinds as the constant claims'),
 # 5 - an op that the item does not advertise, which is a dead click
 (OBJ, 'iop3=Check\niop5=Destroy\nparam=pouch_slots,3', 'iop5=Destroy\nparam=pouch_slots,3',
  '5 ...and the obj advertises it'),
 (POUCH, '~storage_empty_to_inv(rune_pouch_store, "rune pouch");',
         'inv_moveitem(rune_pouch_store, inv, airrune, 1);',
  '5 Empty reuses the shared helper, for both pouches'),
 ('scripts/storage_items/scripts/rune_pouch_ui.rs2',
  '~storage_empty_to_inv(rune_pouch_store, "rune pouch");',
  'inv_moveitem(rune_pouch_store, inv, airrune, ^max_32bit_int);',
  '5 ...and the window\'s Empty button goes through the same helper as the item op'),
 # 6 - the upgrade
 (CONST, '^rune_pouch_craft_level = 75', '^rune_pouch_craft_level = 1',
  '6 which is OSRS\'s 75 Crafting'),
 (POUCH, 'if (stat_base(crafting) < ^rune_pouch_craft_level) {', 'if (stat(crafting) < ^rune_pouch_craft_level) {',
  '6 it wants the level, unboosted'),
 (POUCH, 'inv_add(inv, divine_rune_pouch, 1);\n// No experience, as OSRS gives none for it.',
         'inv_add(inv, divine_rune_pouch, 1);\nstat_advance(crafting, 100);',
  '6 and gives no experience, as OSRS gives none'),
 (LEATHER, '    case rune_pouch : @rune_pouch_upgrade;', '',
  '6 it hangs off the needle\'s own [opheldu,needle] switch'),
 (POUCH, '~rune_pouch_kinds_used > oc_param(rune_pouch, pouch_slots)', '$false = true',
  '6 Revert refuses while a fourth kind is inside rather than dropping it'),
 # 7 - death
 (DEATH, 'inv_dropall(looting_bag_store, coord, ^lootdrop_duration);',
         'inv_dropall(looting_bag_store, coord, ^lootdrop_duration);\ninv_dropall(rune_pouch_store, coord, ^lootdrop_duration);',
  '7 and the pouch keeps its runes'),
 (OBJ, 'tradeable=no\niop1=Fill', 'iop1=Fill',
  '7 both pouches are untradeable, as in OSRS'),
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
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'pouch_battery.py')],
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
        print('  %-5s %-62s %s' % (state, why, note))
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
