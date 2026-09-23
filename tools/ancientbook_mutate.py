#!/usr/bin/env python3
"""Mutation test for tools/ancientbook_battery.py.

THE THING THIS IS FOR. The swap renamed 24 buttons by joining on a sprite index, and the 474 port
then moved each one to a slot named from a hand-written list. A wrong join is
invisible: the icon is right, the tooltip is right - it travelled with the panel - and the trigger
under it casts something else. So most of what is below breaks the join in a different place and
expects the check that would notice.

Every entry names the wording of a check the battery prints, and the runner asserts its anchor is
UNIQUE in the file before using it, because replace(find, repl, 1) takes the first match and two
rounds have been wasted on mutations that quietly edited a different block.

    python3 tools/ancientbook_mutate.py                 [all of them]
    python3 tools/ancientbook_mutate.py "the join"      [just those]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'ancientbook_mutate_work')

DBROW = 'scripts/skill_magic/configs/magic_spells.dbrow'
CONST = 'scripts/skill_combat/configs/magic/spells.constant'
TRIG = 'scripts/skill_magic/scripts/spells/enchant.rs2'
MAGICIF = 'scripts/skill_magic/interfaces/magic.if'
IFPACK = 'pack/interface.pack'
OBJPACK = 'pack/obj.pack'
ALLOBJ = 'scripts/_unpack/377/all.obj'
RS2 = 'tools/rs2check.py'
SPEC = 'tools/unwiredspells.json'


IF = 'scripts/skill_magic/interfaces/ancient_magic.if'
SRC = 'scripts/interfaces/inter_267.if'
PACK = 'pack/interface.pack'
GEN = 'tools/genancientbook.py'
PVP = 'scripts/skill_combat/scripts/pvp/pvp_magic.rs2'
ANCIENT = 'scripts/skill_magic/configs/ancient_spells.dbrow'

MUTS = [
 # ---- 1 the join
 (IF, '[ice_barrage]', '[ice_barrag3]',
  'every component a trigger names exists, and every button has one'),
 (IF, 'action=Ice Barrage', 'action=Shadow Rush',
  "and every one is under that spell's name"),
 (IF, 'graphic=i474_378,0', 'graphic=i474_377,0',
  "each spell's icon is the one 474's sprite order gives it"),
 (IF, 'activegraphic=i474_328,0', 'activegraphic=i474_327,0',
  '...and lights up as its own lit frame, 50 below it'),
 (IF, 'graphic=i474_356,0', 'graphic=i474_406,0',
  'Home Teleport needs no runes, so it is always its lit icon'),
 # ice_barrage into the empty slot beside Ghorrock: still in the tab, overlapping nothing, and
 # now read after a level 96 spell
 (IF, '[ice_barrage]\ntype=graphic\nx=151\ny=148', '[ice_barrage]\ntype=graphic\nx=64\ny=176',
  "and in 474's grid, read like a page, the levels only go up"),
 (IF, 'text=Level 94 : Ice Barrage', 'text=Level 93 : Ice Barrage',
  "and the CACHE's level for it is this fork's levelrequired"),
 (IF, 'text=Level 94 : Ice Barrage', 'text=Level 94 : Ice Barrag',
  'every spell named has a row in a magic spell table'),
 # the tooltip moved OUT of its panel, without orphaning a pack id - which is what the first
 # version of this entry did, so the pack check fired before the one under test
 (IF, 'layer=info_ice_barrage\ntype=text\nx=3\ny=5', 'layer=com_0\ntype=text\nx=3\ny=5',
  'each tooltip lives in an info_<spell> panel'),

 # ---- 2 it is the cache panel
 (IF, 'activegraphic=i474_328,0\nactionverb=Cast on',
      'actionverb=Cast on',
  'every lit icon the cache panel had is a lit 474 icon here'),
 (IF, 'script3op18=inv_contains,wornitems:worn,twinflame_staff\nscript4op1=stat_level,magic\nscript1=gt,3\nscript2=gt,1\nscript3=gt,5\nscript4=gt,93',
      'script4op1=stat_level,magic\nscript1=gt,3\nscript2=gt,1\nscript3=gt,5\nscript4=gt,93',
  'script operands carried over from the cache panel unchanged'),
 (IF, 'type=rect\nx=3\ny=9', 'type=graphic\nx=3\ny=9',
  "the 377 panel's own description box is still here, hidden"),
 (IF, '[ice_barrage]\ntype=graphic\nx=151\ny=148',
      '[ice_barrage]\ntype=graphic\nx=151\ny=250',
  'every icon is inside the tab'),
 (IF, '[ice_barrage]\ntype=graphic\nx=151\ny=148',
      '[ice_barrage]\ntype=graphic\nx=130\ny=148',
  'and no two overlap'),

 # ---- 3 the triggers
 (IF, 'buttontype=target\nwidth=24\nheight=24\noverlayer=info_ice_barrage',
      'buttontype=normal\nwidth=24\nheight=24\noverlayer=info_ice_barrage',
  '...and its button is buttontype=target aimed at npc,player'),
 (IF, 'overlayer=info_ice_barrage', 'overlayer=info_ice_rush',
  'every button opens its own panel on hover'),
 (IF, 'option=Cast @gre@Paddewwa Teleport', 'option=Cast @gre@Senntisten Teleport',
  '...naming its own destination'),
 (IF, 'option=Cast @gre@Ghorrock Teleport\n', '',
  '...with a right-click option, which the cache panel has none of'),
 (PVP, '[applayert,ancient_magic:ice_barrage] ~pvp_default_spell(^ice_barrage);\n', '',
  'each combat spell is castable on a player AND on an npc'),

 # ---- 4 the pack
 (PACK, '18956=ancient_magic\n', '20999=ancient_magic\n',
  'and it is still 18956, the id it was committed with'),
 (PACK, '=ancient_magic:ice_barrage\n', '=ancient_magic:ice_barrag3\n',
  'every component has one'),

 # ---- 5 reproducibility has no mutation here: it reruns LostCityServer's portmagic474.py, which
 # needs the orchestrator checkout around it, and this runs on a copy in TMPDIR, where it skips.
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
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'ancientbook_battery.py')],
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
