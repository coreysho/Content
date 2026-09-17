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
VARP = 'scripts/areas/area_barrows/configs/barrows.varp'
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
 (RS2, 'facesquare(loc_coord);\nif (testbit(',
       'facesquare(loc_coord);\nnpc_add(coord, $brother, ^barrows_brother_life);\nif (testbit(',
  '6 the sarcophagus reads the kill bit BEFORE it adds anybody'),
 (RS2, 'npc_add(coord, $brother, ^barrows_brother_life);',
       'npc_add(coord, $brother, ^max_32bit_int);',
  '6 a woken brother is added with ^barrows_brother_life, not forever'),
 (RS2, '%aggressive_npc = npc_uid;\n', '',
  '6 and he comes out fighting'),

 # --- the deaths, and the compile-time lesson about where the write has to live
 (RS2, '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_karil);',
       '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_torag);',
  "7 karil's death sets"),
 (RS2, '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_ahrim);',
       '~barrows_brother_killed(^barrows_bit_ahrim);\n\n'
       '[proc,barrows_brother_killed](int $bit)\n'
       '%barrows_killed = setbit(%barrows_killed, $bit);',
  '7 the bit is written only inside the death triggers'),
 (RS2, 'if (npc_findhero = ^false) {\n    return;\n}\n'
       '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_ahrim);',
       '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_ahrim);\n'
       'if (npc_findhero = ^false) {\n    return;\n}',
  '7 ahrim finds his killer before he writes to him'),
 (RS2, 'gosub(npc_death);\nif (npc_findhero = ^false) {\n    return;\n}\n'
       '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_dharok);',
       '%barrows_killed = setbit(%barrows_killed, ^barrows_bit_dharok);',
  "7 dharok's death still dies properly"),

 # --- the var and the bits
 (VARP, '[barrows_killed]\nprotect=no\nscope=perm', '[barrows_killed]\nscope=perm',
  '8 %barrows_killed is protect=no'),
 (VARP, '[barrows_killed]\nprotect=no\nscope=perm',
        '[barrows_killed]\nprotect=no\nscope=temp',
  '8 %barrows_killed is protect=no'),
 (VARPPACK, '1176=barrows_killed\n', '',
  '8 barrows_killed is in pack/varp.pack'),
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
