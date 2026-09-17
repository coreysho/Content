#!/usr/bin/env python3
"""Mutation test for tools/barrows_battery.py. Same runner as fightcave_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed, which is not the same as the check being aimed right.

Most of these are CROSS-WIRINGS rather than broken code - Torag's mound leading to Karil's crypt,
Guthan's sarcophagus handing over Verac, Karil's death setting Torag's bit. That is the whole risk
in the Barrows: six of everything, all named alike, and a swap that compiles and plays.

    python3 tools/barrows_mutate.py [filter]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'barrows_mutate_work')

CONST = 'scripts/areas/area_barrows/configs/barrows.constant'
VARBIT = 'scripts/areas/area_barrows/configs/barrows.varbit'
ENUM = 'scripts/areas/area_barrows/configs/barrows.enum'
TUN = 'scripts/areas/area_barrows/scripts/barrows_tunnels.rs2'
CHEST = 'scripts/areas/area_barrows/scripts/barrows_chest.rs2'
TELE = 'scripts/areas/area_barrows/scripts/barrows_teleport.rs2'
TOBJ = 'scripts/areas/area_barrows/configs/barrows.obj'
DEATH = 'scripts/skill_combat/scripts/npc/npc_death.rs2'
ALLVARP = 'scripts/_unpack/377/all.varp'
ALLVARBIT = 'scripts/_unpack/377/all.varbit'
CHESTSPEC = 'tools/barrowschestspec.json'
RS2 = 'scripts/areas/area_barrows/scripts/barrows.rs2'
STAIRS = 'scripts/ladders+stairs/scripts/stairs.rs2'
SPADE = 'scripts/general_use/scripts/spade.rs2'
ALLNPC = 'scripts/_unpack/377/all.npc'
SPEC = 'tools/barrowsspec.json'
SURFACE = 'maps/m55_51.jm2'
VARPPACK = 'pack/varp.pack'

MUTS = [
 # --- the mounds, which are terrain and so are re-measured off the map every run
 (CONST, '^barrows_mound_ahrim = 0_55_51_46_25', '^barrows_mound_ahrim = 0_55_51_44_25',
  "1 ahrim's mound coordinate"),
 (CONST, '^barrows_mound_dharok = 0_55_51_56_35', '^barrows_mound_dharok = 0_55_51_46_25',
  '1 the six coordinates are on six different hills'),
 (CONST, '^barrows_mound_torag = 0_55_51_34_20', '^barrows_mound_torag = 0_55_52_34_20',
  '1 all six sit on level 0 of m55_51'),
 (SPEC, '"dharok": "north-east"', '"dharok": "south-east"',
  "1 dharok's mound lies south-east"),
 (CONST, '^barrows_mound_radius = 2', '^barrows_mound_radius = 8',
  '1 no two mounds are within two radii'),
 # a seventh hill, raised on the map itself - the check counts them rather than trusting six
 (SURFACE, '0 0 0: h27 u50', '0 0 0: h80 u50',
  '1 m55_51 has exactly six hills above h70'),
 # ...and a hill taller than Ahrim's, which the wiki says is the tall one
 (SURFACE, '0 38 34: h79 u115', '0 38 34: h90 u115',
  "1 Ahrim's mound is also the tallest"),

 # --- the crypt tiles, re-measured against the map's own loc occupancy
 (CONST, '^barrows_crypt_ahrim = 3_55_151_37_39', '^barrows_crypt_ahrim = 3_55_151_35_34',
  "2 ahrim's drop tile (35,34) is free floor"),
 (CONST, '^barrows_crypt_ahrim = 3_55_151_37_39', '^barrows_crypt_ahrim = 3_55_151_36_39',
  "2 ahrim's drop tile is beside HIS OWN staircase"),
 (CONST, '^barrows_crypt_torag = 3_55_151_45_20', '^barrows_crypt_torag = 3_55_151_26_20',
  "2 torag's drop tile is nearest HIS OWN sarcophagus"),
 (CONST, '^barrows_crypt_verac = 3_55_151_57_39', '^barrows_crypt_verac = 0_55_151_57_39',
  '2 all six sit on level 3 of m55_151'),

 # --- digging in
 (RS2, '$crypt = ^barrows_crypt_guthan;', '$crypt = ^barrows_crypt_karil;',
  "3 guthan's mound leads to"),
 (RS2, 'if ($crypt = null) {\n    return(false);\n}', 'if ($crypt = null) {\n    return(true);\n}',
  '3 the dig reports false in exactly one place'),
 (RS2, 'distance(coord, ^barrows_mound_verac) <= ^barrows_mound_radius',
       'distance(coord, ^barrows_mound_verac) <= 2',
  '3 all six branches measure against ^barrows_mound_radius'),
 (SPADE, 'if (~barrows_mound_dig = true) {\n    return;\n}\n\n// Everything else\np_arrivedelay;',
         '// Everything else\np_arrivedelay;\nif (~barrows_mound_dig = true) {\n    return;\n}',
  '4 spade.rs2 asks the Barrows BEFORE its own dig'),

 # --- climbing out
 (STAIRS, '[oploc1,barrows_stairs_karil] @barrows_climb_out(^barrows_mound_karil);',
          '[oploc1,barrows_stairs_karil] @barrows_climb_out(^barrows_mound_torag);',
  "5 karil's staircase climbs out onto"),
 (STAIRS, '[oploc1,barrows_stairs_verac] @barrows_climb_out(^barrows_mound_verac);',
          '[oploc1,barrows_stairs_verac]\nswitch_coord (loc_coord) {\n'
          '    case default : @unhandled_stairs(loc_coord);\n}',
  '5 no Barrows staircase is left routed'),

 # --- the sarcophagi
 (RS2, '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_torag);',
       '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_verac, ^barrows_bit_torag);',
  '6 barrow_torag_sarcophagus hands over'),
 (RS2, '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_torag);',
       '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_verac);',
  '6 barrow_torag_sarcophagus hands over'),
 (RS2, '[oploc1,barrow_torag_sarcophagus] ~barrows_search(barrows_torag, ^barrows_bit_torag);\n',
       '',
  '6 every sarcophagus in the cache has a handler'),
 (RS2, 'if (testbit(%barrows_kills, $bit) = ^true) {',
       'npc_add(coord, $brother, ^barrows_brother_life);\n'
       'if (testbit(%barrows_kills, $bit) = ^true) {',
  '6 the sarcophagus reads the kill bit BEFORE it adds anybody'),
 (RS2, 'npc_add(coord, $brother, ^barrows_brother_life);',
       'npc_add(coord, $brother, ^max_32bit_int);',
  '6 a woken brother is added with ^barrows_brother_life, not forever'),
 (RS2, '%aggressive_npc = npc_uid;\n', '',
  '6 and he comes out fighting'),

 # --- the deaths, and the compile-time lesson about where the write has to live
 (RS2, '%barrows_killed_karil = ^true;', '%barrows_killed_torag = ^true;',
  "7 karil's death sets"),
 (RS2, '%barrows_killed_ahrim = ^true;',
       '~barrows_brother_killed(^barrows_bit_ahrim);\n\n'
       '[proc,barrows_brother_killed](int $bit)\n'
       '%barrows_kills = setbit(%barrows_kills, $bit);',
  '7 the bit is written only inside the death triggers'),
 (RS2, 'if (npc_findhero = ^false) {\n    return;\n}\n%barrows_killed_ahrim = ^true;',
       '%barrows_killed_ahrim = ^true;\nif (npc_findhero = ^false) {\n    return;\n}',
  '7 ahrim finds his killer before he writes to him'),
 (RS2, 'gosub(npc_death);\nif (npc_findhero = ^false) {\n    return;\n}\n'
       '%barrows_killed_dharok = ^true;',
       '%barrows_killed_dharok = ^true;',
  "7 dharok's death still dies properly"),

 # --- the var and the bits
 (CONST, '^barrows_bit_verac = 5', '^barrows_bit_verac = 4',
  '8 the six bits are 0-5 with no collision'),
 (CONST, '^barrows_brothers = 6', '^barrows_brothers = 5',
  '8 ^barrows_brothers counts the brothers there are'),

 # --- the brothers against Old School's own infoboxes
 (ALLNPC, 'param=strengthbonus,72\nparam=damagetype,^stab_style',
          'param=strengthbonus,72\nparam=damagetype,^crush_style',
  '9 verac attacks with stab'),
 (ALLNPC, 'param=attackrate,5\nparam=magicattack,-50', 'param=attackrate,4\nparam=magicattack,-50',
  '9 guthan attacks every 5 ticks'),
 (ALLNPC, 'param=attackrate,6\nparam=magicattack,73',
          'param=attackrate,6\nparam=slashattack,68\nparam=magicattack,73',
  '9 ahrim carries no invented per-style attack bonus'),
 (ALLNPC, 'param=stabdefence,252', 'param=stabdefence,253',
  "9 dharok's stab defence is"),
 (ALLNPC, 'param=rangeattack,134', 'param=rangeattack,140',
  "9 karil's ranged bonus is"),
 (ALLNPC, 'param=attack_anim,barrow_torag_crush',
          'param=attack_anim,barrow_torag_crushed',
  "9 torag's attack_anim is a real animation"),
 (ALLNPC, 'param=strengthbonus,105', 'param=strengthbonus,106',
  "9 dharok's strength bonus is"),
 (SPEC, '"combat": 98, "speed": 6', '"combat": 99, "speed": 6',
  '9 ahrim is combat 99 on the right-click'),
 # --- the run's storage, which is the cache's and not ours
 (VARBIT, '[barrows_entry_crypt]\nbasevar=barrows\nstartbit=0\nendbit=2',
          '[barrows_entry_crypt]\nbasevar=barrows\nstartbit=6\nendbit=8',
  '10 barrows_entry_crypt sits in %barrows bits 0-2'),
 (VARBIT, '[barrows_chest_paid]\nbasevar=barrows\nstartbit=3\nendbit=3',
          '[barrows_chest_paid]\nbasevar=barrows\nstartbit=9\nendbit=9',
  '10 barrows_chest_paid sits in %barrows bit 3'),
 ('pack/varbit.pack', '2114=barrows_entry_crypt\n', '',
  '10 barrows_entry_crypt is in pack/varbit.pack'),
 (ALLVARP, '[barrows_kills]\nprotect=no\ntransmit=yes', '[barrows_kills]\ntransmit=yes',
  '10 [barrows_kills] is protect=no'),
 (ALLVARBIT, '[barrows_killed_dharok]\nbasevar=barrows_kills\nstartbit=1\nendbit=1',
             '[barrows_killed_dharok]\nbasevar=barrows_kills\nstartbit=2\nendbit=2',
  '10 barrows_killed_dharok is bit 1 of %barrows_kills'),
 (ALLVARBIT, '[barrows_killed_monster]\nbasevar=barrows_kills\nstartbit=6\nendbit=15',
             '[barrows_killed_monster]\nbasevar=barrows_kills\nstartbit=6\nendbit=14',
  '10 barrows_killed_monster holds the reward potential and is wide enough'),
 (CHEST, 'mes("You close the chest.");', 'mes("You close the chest.");\n%barrows_killed = 0;',
  '10 nothing reads or writes a %barrows_killed varp any more'),

 # --- the maze
 (ENUM, 'val=7,34922', 'val=7,65535', '11 every maze still leaves all four ladders'),
 (ENUM, 'val=7,34922', 'val=7,2442', '11 and no row is a duplicate of another'),
 (ENUM, 'val=23,64868\n', '', '11 barrows_mazes holds ^barrows_mazes = 24 rows'),
 (ENUM, 'default=0', 'default=1', '11 a miss opens every door rather than shutting one'),
 (ENUM, 'val=3,33073', 'val=3,0', '11 every maze shuts something'),
 (CONST, '^barrows_mazes = 24', '^barrows_mazes = 23',
  '11 barrows_mazes holds ^barrows_mazes = 23 rows'),
 (CONST, '^barrows_door_first = 10', '^barrows_door_first = 11', '11 gate a is %barrows bit 11'),
 (CONST, '^barrows_door_last = 25', '^barrows_door_last = 24',
  '11 ^barrows_door_first..last is exactly sixteen bits wide'),

 # --- the equipment table
 (ENUM, 'val=2,barrows_ahrim_legs', 'val=2,barrows_dharok_legs',
  "12 piece 2 is one of ahrim's"),
 (ENUM, 'val=20,barrows_verac_head', 'val=20,barrows_verac_headd',
  "12 piece 20 is one of verac's"),
 (ENUM, 'val=1,barrows_ahrim_body', 'val=1,barrows_ahrim_head', '12 no piece is listed twice'),
 (ENUM, 'default=null', 'default=barrows_ahrim_head', '12 and says null out loud on a miss'),
 (CHEST, '~barrows_nth_killed(random($brothers))', '~barrows_nth_unkilled(random($brothers))',
  '12 and picks the brother from the ones that are DEAD'),
 (CHEST, 'if (testbit(%barrows_kills, $bit) = ^true) {\n        if ($n = 0) {',
         'if (testbit(%barrows_kills, $bit) = ^false) {\n        if ($n = 0) {',
  '12 ~barrows_nth_killed counts the killed bits'),
 (TUN, 'if (testbit(%barrows_kills, $bit) = ^false) {\n        if ($n = 0) {',
        'if (testbit(%barrows_kills, $bit) = ^true) {\n        if ($n = 0) {',
  '12 ...and its mirror, which a door uses, counts the live ones'),

 # --- the chest's own numbers
 (CONST, '^barrows_rolls_max = 7', '^barrows_rolls_max = 8', '13 one roll to start and seven at most'),
 (CONST, '^barrows_equip_step = 58', '^barrows_equip_step = 57', '13 which is 1/392 with 1 brother'),
 (CONST, '^barrows_potential_max = 1012', '^barrows_potential_max = 1014',
  '13 ...and that is arithmetic rather than three numbers'),
 (CONST, '^barrows_rp_mind = 381', '^barrows_rp_mind = 380', '13 mindrune needs 381 reward potential'),
 (CONST, '^barrows_rp_keyhalf = 1006', '^barrows_rp_keyhalf = 1000',
  '13 keyhalf needs 1006 reward potential'),
 (CONST, '^barrows_loot_coins_high = 774', '^barrows_loot_coins_high = 775',
  '13 coins comes 2-774 at a time'),
 (CHESTSPEC, '"rp": 881', '"rp": 880', '13 boltrack needs 880 reward potential'),
 (CHEST, '} else if ($roll >= ^barrows_rp_blood) {\n    ~obj_giveorbank(bloodrune,',
         '} else if ($roll >= ^barrows_rp_blood) {\n    ~obj_giveorbank(chaosrune,',
  '13 the blood band pays bloodrune'),
 (CHEST, 'if ($roll >= ^barrows_rp_dragonmed) {', 'if ($roll >= ^barrows_rp_mind) {',
  '13 the chest tests the bands from the top down'),
 (CHEST, 'add(random($potential), 1)', 'random($potential)',
  '13 the roll is a value in 1..potential'),

 # --- paying twice, and clearing the run
 (CHEST, '%barrows_chest_paid = ^true;\ndef_int $rolls',
         'def_int $rolls',
  '14 looting marks the chest paid'),
 (CHEST, '%barrows_entry_crypt = ^barrows_entry_none | %barrows_chest_paid = ^true',
         '%barrows_entry_crypt = ^barrows_entry_none',
  '14 and it refuses both a second search'),
 (CHEST, '~mesbox("You loot the chest,', '%barrows_kills = 0;\n~mesbox("You loot the chest,',
  '14 looting clears NOTHING'),
 (TUN, '%barrows_chest_paid = ^false;\n%barrows_chest_open = ^false;',
        '%barrows_chest_open = ^false;',
  '14 the next dig is what clears the last run'),
 (TUN, 'if (%barrows_entry_crypt ! ^barrows_entry_none & %barrows_chest_paid = ^false) {',
        'if (%barrows_entry_crypt ! ^barrows_entry_none) {',
  '14 ...and a run still owed its chest is never cleared'),

 # --- the doors
 (CONST, '^barrows_spawn_skeleton = 64', '^barrows_spawn_skeleton = 60', '15 a skeleton on 52'),
 (CONST, '^barrows_spawn_bloodworm = 96', '^barrows_spawn_bloodworm = 100', '15 a bloodworm on 32'),
 (CONST, '^barrows_spawn_crowd = 11', '^barrows_spawn_crowd = 12',
  '15 nothing comes through into a room already holding 11'),
 (TUN, 'if (%barrows_entry_crypt = ^barrows_entry_none) {\n    return;\n}\nif (~barrows_crowd',
        'if (~barrows_crowd',
  '15 a door with no run behind it lets nothing out'),
 (TUN, 'if (~barrows_crowd($where) >= ^barrows_spawn_crowd) {\n    return;\n}\n'
       'def_int $roll = random(^barrows_spawn_denom);',
       'def_int $roll = random(^barrows_spawn_denom);\n'
       'if (~barrows_crowd($where) >= ^barrows_spawn_crowd) {\n    return;\n}',
  '15 ...checked before the roll'),
 (TUN, 'if (%barrows_chest_paid = ^true) {\n    $roll = 0;\n}', '',
  '15 after the chest has paid, every door is a brother'),
 (TUN, '~barrows_nth_unkilled(random($left))', '~barrows_nth_killed(random($left))',
  "15 a door's brother is one the player has NOT killed"),
 (TUN, '[oploc1,barrows_door_unlocked_r] ~barrows_door_through;\n', '',
  '15 the r half of a doorway is handled'),

 # --- the passage and the ladder
 (CONST, '^barrows_chamber_tile_a = 0_55_151_15_48', '^barrows_chamber_tile_a = 0_55_151_14_48',
  "16 chamber a's drop tile is floor a player can stand on"),
 (CONST, '^barrows_chamber_tile_a = 0_55_151_15_48', '^barrows_chamber_tile_a = 0_55_151_47_48',
  "16 chamber a's drop tile is beside ITS OWN ladder"),
 (CONST, '^barrows_chamber_g = 2', '^barrows_chamber_g = 3',
  '16 the four chambers are numbered 0..3'),
 (TUN, 'case ^barrows_chamber_c : return(^barrows_chamber_tile_c);',
        'case ^barrows_chamber_c : return(^barrows_chamber_tile_g);',
  '16 chamber c answers with g\'s tile'),
 (TUN, 'case ^barrows_chamber_i : %barrows_chamber_i = ^true;',
        'case ^barrows_chamber_i : %barrows_chamber_a = ^true;',
  '16 and opening chamber i lights a\'s ladder'),
 (TUN, 'case ^barrows_bit_torag : return(^barrows_mound_torag);',
        'case ^barrows_bit_torag : return(^barrows_mound_karil);',
  "16 the ladder puts a player who came in by torag's crypt back on karil's mound"),
 (TUN, 'def_int $chamber = ~barrows_open_chamber;', 'def_int $chamber = -1;',
  '16 coming back down the same run reuses the chamber'),
 (RS2, 'if (%barrows_entry_crypt = add($bit, 1)) {', 'if (%barrows_entry_crypt = $bit) {',
  '16 the sarcophagus of the entry crypt gives the passage'),

 # --- reward potential
 (DEATH, '~barrows_potential;\n', '', '17 [proc,npc_death] pays reward potential'),
 (TUN, 'if (inzone(^barrows_tunnel_sw, ^barrows_tunnel_ne, npc_coord) = ^false) {\n    return;\n}',
        '',
  '17 and nothing outside the tunnels pays anything'),
 (TUN, 'if (~barrows_brother_bit(npc_type) >= 0) {\n    return;\n}', '',
  '17 a BROTHER pays nothing into the pool'),
 (TUN, 'min(add(%barrows_killed_monster, nc_vislevel(npc_type)), ^barrows_potential_cap)',
        'add(%barrows_killed_monster, nc_vislevel(npc_type))',
  "17 what it pays is the dead thing's own combat level, capped"),
 (CONST, '^barrows_potential_cap = 1000', '^barrows_potential_cap = 1001',
  '17 the pool caps at 1000'),
 (CHESTSPEC, '"barrows_bloodworm": 52', '"barrows_bloodworm": 53',
  '17 barrows_bloodworm is combat 53'),

 # --- the teleport
 (TOBJ, 'stackable=yes', 'stackable=no', '18 it stacks, which is the point of a tab'),
 (TOBJ, 'iop1=Break', 'iop2=Break', '18 and its one option is Break'),
 (TOBJ, '2dzoom=465', '2dzoom=400', "18 its 2dzoom is the lectern tablets' own"),
 (CONST, '^barrows_tele_dest = 0_55_51_45_48', '^barrows_tele_dest = 0_55_51_45_47',
  '18 it lands on 0_55_51_45_48, the tile Corey asked for'),
 (CONST, '^barrows_tele_rate = 10', '^barrows_tele_rate = 8', '18 the chest pays one at 1/10'),
 (CONST, '^barrows_tele_high = 6', '^barrows_tele_high = 8', '18 and pays 4 to 6 of them'),
 (CHEST, 'if (random(^barrows_tele_rate) = 0) {\n    ~obj_giveorbank(barrows_teleport,'
         ' ~barrows_between(^barrows_tele_low, ^barrows_tele_high));\n}', '',
  '18 the chest is the only thing in the game that hands one over'),
 (TELE, 'inv_del(inv, barrows_teleport, 1);', 'mes("");',
  '18 breaking one spends exactly one'),
 (TELE, 'if (~pre_tele_checks(coord) = false) {\n    return;\n}', '',
  '18 and it is not a way out of deep wilderness'),
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
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'barrows_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state = 'red'
            note = 'caught by its own check' + ('' if len(fired) == 1
                                                else ' (and %d others)' % (len(fired) - 1))
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:56] if fired else 'a non-zero exit with no check named, which is a crash '
                                            'and not a catch')
            loose += 1
        print('  %-5s %-70s %s' % (state, why, note))
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
