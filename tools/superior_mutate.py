#!/usr/bin/env python3
"""Mutation test for tools/superior_battery.py. Same runner as pet_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed.

    python3 tools/superior_mutate.py [filter]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'superior_mutate_work')

NPC = 'scripts/skill_slayer/configs/superiors.npc'
ENUM = 'scripts/skill_slayer/configs/superiors.enum'
RS2 = 'scripts/skill_slayer/scripts/superiors.rs2'
HORROR = 'scripts/areas/area_mos_le_harmless/scripts/cave_horror.rs2'
REQ = 'scripts/skill_slayer/configs/slayer_req.enum'
SPEC = 'tools/superiorspec.json'
NPCPACK = 'pack/npc.pack'

MUTS = [
 # 1 - art that is not the art the spec measured
 (NPC, 'model1=npc_superior_cave_abomination_1', 'model1=npc_cave_horror_1',
  '1 superior_cave_abomination names exactly the spec\'s models'),
 (SPEC, '"npc_superior_cave_abomination_1": {"verts": 1060, "faces": 2116}',
        '"npc_superior_cave_abomination_1": {"verts": 1059, "faces": 2116}',
  '1 ...and is the mesh the spec measured'),
 (NPCPACK, '3939=superior_cave_abomination\n', '',
  '1 ...and is registered in npc.pack'),
 # 2 - combat numbers drifting off the cache
 (NPC, 'vislevel=206\nattack=230', 'vislevel=205\nattack=230',
  '2 superior_cave_abomination is level 206'),
 (NPC, 'hitpoints=130', 'hitpoints=150',
  '2 ...with the cache\'s stats'),
 (NPC, '[superior_king_kurask]\nname=King kurask\n', '[superior_king_kurask]\nname=King kurask\nsize=4\n',
  '2 ...and is 5 tiles'),
 # 3 - the table, the configs and the requirements disagreeing
 (SPEC, '"osrs": 7401, "task": "^slayer_cavehorror"', '"osrs": 7401, "task": "^slayer_dustdevil"',
  '3 ...and the spec keys superior_cave_abomination on it'),
 (NPC, 'param=death_drop,null\nparam=slayer_category,^slayer_cavehorror',
       'param=death_drop,null\nparam=slayer_category,^slayer_turoth',
  '3 ...and superior_cave_abomination credits kills to it'),
 (ENUM, 'val=^slayer_cavehorror,superior_cave_abomination\nval=^slayer_aberrantspecter,superior_abhorrent_spectre',
        'val=^slayer_aberrantspecter,superior_abhorrent_spectre\nval=^slayer_cavehorror,superior_cave_abomination',
  '3 the table is in ascending slayer-requirement order'),
 (ENUM, 'val=^slayer_cavehorror,superior_cave_abomination\n', '',
  '3 every spec\'d superior has exactly one enum row'),
 # a death spawn quietly given a category, which would make it rollable as a superior
 (NPC, '[superior_chaotic_spawn_melee]', '[superior_chaotic_spawn_melee]\nparam=slayer_category,^slayer_cavehorror',
  '3 superior_chaotic_spawn_melee is not a superior and carries no slayer_category'),
 # 4 - dying, and what dying drops
 (RS2, '[ai_queue3,superior_cave_abomination] @superior_death;\n', '',
  '4 superior_cave_abomination reaches @superior_death when it dies'),
 (RS2, 'case superior_king_kurask : ~slayer_kursk_1_drop_table_loot;',
       'case superior_king_kurask : ~slayer_kursk_1_drop_table_loott;',
  '4 ...and the proc it names exists'),
 (RS2, '~superior_loot($type);\n~superior_loot($type);\n~superior_loot($type);',
       '~superior_loot($type);\n~superior_loot($type);',
  '4 the table is rolled three times per kill, as OSRS rolls it'),
 (RS2, '    case superior_cave_abomination : ~cave_horror_drop_table_loot;',
       '    case superior_cave_abomination : ~cave_horror_drop_table_loot;\n    case superior_chaotic_spawn_melee : ~cave_horror_drop_table_loot;',
  '4 ~superior_loot has exactly as many cases as there are superiors'),
 # 5 - a borrowed animation that is not there to borrow
 (NPC, 'param=death_anim,kursk_death\n', '',
  '5 superior_king_kurask names five animations'),
 (NPC, 'walkanim=gargoyle_fly', 'walkanim=gargoyle_flyy',
  '5 ...and every one is a [seq] block in the tree'),
 # 6 - the cave abomination, and the rig it borrows
 (NPC, 'readyanim=cave_horror_ready\nwalkanim=cave_horror_walk\nvislevel=206',
       'readyanim=banshee_ready\nwalkanim=cave_horror_walk\nvislevel=206',
  '6 its readyanim is the cave horror\'s own'),
 (NPC, 'param=slayer_category,^slayer_cavehorror\n\n[superior_abhorrent_spectre]',
       'param=slayer_category,^slayer_cavehorror\nparam=strengthbonus,50\n\n[superior_abhorrent_spectre]',
  '6 strengthbonus is left unset, as it is on the other fifteen'),
 (SPEC, '"fingerprint": {"9": 2, "20": 2, "28": 3, "29": 3}',
        '"fingerprint": {"9": 3, "20": 2, "28": 3, "29": 3}',
  '6 ...group 9 is the same size in both meshes'),
 (SPEC, '"unlabelled": 255, "unlabelled_verts": 69', '"unlabelled": 255, "unlabelled_verts": 60',
  '6 ...and its unlabelled vertices are the flat ground plate, which no frame moves'),
 (SPEC, '"shared_groups": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]',
        '"shared_groups": [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29]',
  '6 the abomination is rigged on exactly the groups the spec recorded'),
 # the screech: the whole point of the monster, and three ways to lose it
 (RS2, '''[ai_applayer2,superior_cave_abomination]
if (inv_total(worn, witchwood_icon) < 1) {
    ~cave_horror_screech;
    return;
}''', '''[ai_applayer2,superior_cave_abomination]
if (inv_total(worn, witchwood_icon) < 1) {
    npc_setmode(opplayer2);
    return;
}''',
  '6 with no witchwood icon worn it screeches instead of attacking'),
 (RS2, '''[ai_opplayer2,superior_cave_abomination]
if (inv_total(worn, witchwood_icon) < 1) {
    npc_setmode(applayer2);
    return;
}''', '''[ai_opplayer2,superior_cave_abomination]
if (inv_total(worn, witchwood_icon) < 1) {
    return;
}''',
  '6 and taking the icon off mid-fight sends it back to screeching'),
 # the banshee's protection quietly granted here, where it does nothing in OSRS
 (RS2, '''[ai_applayer2,superior_cave_abomination]
if (inv_total(worn, witchwood_icon) < 1) {''', '''[ai_applayer2,superior_cave_abomination]
if (inv_total(worn, witchwood_icon) < 1 & inv_total(worn, slayer_earmuffs) < 1) {''',
  '6 no slayer_earmuffs: earmuffs, the helm and the shield do nothing down there'),
 (RS2, 'case superior_cave_abomination : ~cave_horror_drop_table_loot;',
       'case superior_cave_abomination : ~slayer_jelly_loot;',
  '6 it rolls the cave horror\'s own table, the proc that was split out for it'),
 (REQ, 'val=^slayer_cavehorror,58', 'val=^slayer_cavehorror,57',
  '6 and the unique roll reads its 58 Slayer out of slayer_req.enum'),
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
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'superior_battery.py')],
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
            note = 'caught by its own check' + ('' if len(fired) == 1 else ' (and %d others)' % (len(fired) - 1))
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:56] if fired else 'a non-zero exit with no check named, which is a crash and not a catch')
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
