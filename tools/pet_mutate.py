#!/usr/bin/env python3
"""Mutation test for tools/pet_battery.py. Same runner as poh_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed.

    python3 tools/pet_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'pet_mutate_work')

ROLL = 'scripts/npc/scripts/skill_pets.rs2'
BRS2 = 'scripts/npc/scripts/boss_pets.rs2'
CONST = 'scripts/npc/configs/skill_pets.constant'
BCONST = 'scripts/npc/configs/boss_pets.constant'
MINE = 'scripts/skill_mining/configs/mine.dbrow'
TREES = 'scripts/skill_woodcutting/configs/trees.dbrow'
GWD = 'scripts/bosses/godwars/scripts/gwd_drops.rs2'
SPEC = 'tools/petspec.json'
MINERS2 = 'scripts/skill_mining/scripts/mining.rs2'
RC = 'scripts/skill_runecraft/scripts/runecraft.rs2'
GNOME = 'scripts/skill_agility/scripts/gnome_course.rs2'

MUTS = [
 # 1 - the formula itself
 (ROLL, 'calc($base - (stat_base($stat) * ^skillpet_level_step))',
        'calc($base - (stat_base($stat) * 25))',
  '1 the chance is base - (level * step)'),
 (ROLL, 'stat_base($stat)', 'stat($stat)',
  '1 and it is the UNBOOSTED level'),
 (CONST, '^skillpet_no_roll = 0', '^skillpet_no_roll = -1',
  '1 and that sentinel is 0'),
 (ROLL, 'if ($chance < 1) {', 'if ($chance < -1) {',
  '1 the chance is floored at 1'),
 (ROLL, 'if (~obj_gettotal($pet) > 0) {\n    return;\n}\n', '',
  '1 owning one already - pack, bank or worn - blocks a second'),
 # the inv sweep moved in front of the roll - correct, but one sweep per ACTION rather than per pet
 # the guards moved in front of the roll: correct behaviour, but one inventory sweep per ACTION
 # rather than one per pet earned - a skilling hook runs on every log and every ore.
 (ROLL, '''if (random($chance) ! 0) {
    return;
}
// Owning one anywhere - pack, bank, worn - or having it out already, stops a second.
if (~obj_gettotal($pet) > 0) {
    return;
}''', '''if (~obj_gettotal($pet) > 0) {
    return;
}
if (random($chance) ! 0) {
    return;
}''',
  '1 those two run only after the roll succeeds'),
 (ROLL, 'obj_add(coord, $pet, 1, ^lootdrop_duration);', 'mes("It escapes.");',
  '1 a full pack puts it on the floor rather than losing it'),
 # 2 - the boss rates
 (BRS2, '[proc,bosspet_roll](namedobj $pet, int $rate)', '[proc,bosspet_roll](namedobj $pet)',
  '2 the rate is an argument'),
 (BCONST, '^bosspet_gwd_droprate = 5000', '^bosspet_gwd_droprate = 3000',
  '2 ^bosspet_gwd_droprate is 5,000'),
 (GWD, '~bosspet_roll(bosspet_kril_item, ^bosspet_gwd_droprate);',
       '~bosspet_roll(bosspet_kril_item, ^bosspet_droprate);',
  '2 ...at ^bosspet_gwd_droprate, which is 1 in 5000'),
 (GWD, '~bosspet_roll(bosspet_zilyana_item, ^bosspet_gwd_droprate);\n', '',
  '2 bosspet_zilyana_item is rolled in exactly one place'),
 # a pet rolled twice - once in its own table and once in someone else's
 (GWD, '~bosspet_roll(bosspet_kree_item, ^bosspet_gwd_droprate);',
       '~bosspet_roll(bosspet_kree_item, ^bosspet_gwd_droprate);\n~bosspet_roll(bosspet_graardor_item, ^bosspet_gwd_droprate);',
  '2 bosspet_graardor_item is rolled in exactly one place'),
 # 3 - a base that drifts from the wiki
 (MINE, 'data=pet_base,42377', 'data=pet_base,42000',
  '3 skillpet_rock_golem: runite_rock_table is 42377'),
 (TREES, 'data=pet_base,72321', 'data=pet_base,145013',
  '3 skillpet_beaver: magic_tree_table is 72321'),
 (CONST, '^skillpet_rift_guardian_base = 1795758', '^skillpet_rift_guardian_base = 1795000',
  '3 skillpet_rift_guardian: ^skillpet_rift_guardian_base is 1795758'),
 (CONST, '^skillpet_squirrel_barbarian = 44376', '^skillpet_squirrel_barbarian = 35609',
  '3 skillpet_squirrel: ^skillpet_squirrel_barbarian is 44376'),
 # a row that grows a base the spec has never heard of
 (MINE, '[blurite_rock]\ntable=mining_table', '[blurite_rock2]\ntable=mining_table',
  '3 ...and no row carries a base the spec does not know'),
 # 4 - a base so small the formula runs out at 99
 (CONST, '^skillpet_squirrel_wilderness = 34666', '^skillpet_squirrel_wilderness = 2400',
  '4 skillpet_squirrel: its smallest base'),
 # 5 - a hook that stops rolling, or rolls the wrong skill
 (MINERS2, '~skillpet_roll(skillpet_rock_golem_item, mining, db_getfield($data, mining_table:pet_base, 0));',
           '~skillpet_roll(skillpet_rock_golem_item, fishing, db_getfield($data, mining_table:pet_base, 0));',
  '5 ...against mining'),
 (RC, '~skillpet_roll_each(skillpet_rift_guardian_item, runecraft, ^skillpet_rift_guardian_base, $total_ess);',
      '~skillpet_roll(skillpet_rift_guardian_item, runecraft, ^skillpet_rift_guardian_base);',
  '5 ...and the Rift guardian rolls once per essence, not once per click'),
 (GNOME, '    ~skillpet_roll(skillpet_squirrel_item, agility, ^skillpet_squirrel_gnome);\n', '',
  '5 skillpet_squirrel_item rolls in gnome_course.rs2'),
 # 6 - a pending pet quietly wired, which would put it in the game at a rate nobody checked
 ('scripts/skill_fishing/scripts/fishing.rs2', '~fishing_xp(struct_param($struct1, productexp));',
  '~fishing_xp(struct_param($struct1, productexp));\n        ~skillpet_roll(skillpet_heron_item, fishing, 116129);',
  '6 skillpet_heron is rolled nowhere'),
 # 7 - the two halves of a pet losing track of each other
 ('scripts/npc/configs/skill_pets.obj', 'param=follower_id,skillpet_beaver',
  'param=follower_id,skillpet_heron', '7 ...and the item names the npc'),
 ('scripts/npc/configs/skill_pets.npc', 'category=bosspet\nparam=pet_item_id,skillpet_rocky_item',
  'param=pet_item_id,skillpet_rocky_item',
  '7 ...both on the category the four follower triggers hang off'),
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
            print('  SKIP (pattern not found) %-40s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'pet_battery.py')],
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
            state, note = 'red', 'caught, but by: %s' % (fired[0][:56] if fired else 'a non-zero exit')
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
