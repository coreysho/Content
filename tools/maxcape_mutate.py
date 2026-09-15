#!/usr/bin/env python3
"""Mutation test for tools/maxcape_battery.py.

A check that cannot fail is worse than no check: it reads as coverage and is not. Each entry below
breaks one thing the battery claims to catch - in a throwaway copy of the tree, never in place - and
the battery has to go red. Every mistake here is one that was actually made while building the round,
or one the 377 client or compiler fails quietly on.

The runner is the same one poh_mutate.py uses, copied rather than shared: one tree copy, one mutation
at a time, restore, and the checker named in the entry must exit non-zero. If a third of these
appears the runner is worth lifting into a module of its own.

    python3 tools/maxcape_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'maxcape_mutate_work')

MUTS = [
 # (file, find, replace, which check group must go red)
 ('scripts/skillcapes/configs/max_cape.obj',
  'param=prayerbonus,4', 'param=prayerbonus,3',
  '2 a Max cape that is not a trimmed cape'),
 ('scripts/skillcapes/configs/max_cape.obj',
  'param=magicdefence,9', 'param=magicdefence,8',
  '2 one defence bonus drifting from the Attack cape'),
 ('scripts/skillcapes/configs/max_cape.obj',
  'iop4=Features', 'iop4=Features\niop5=Destroy',
  '2 an op that takes Drop away from an untradeable cape'),
 ('scripts/skillcapes/configs/max_cape.obj',
  '[max_hood]\nname=Max hood', '[max_hood]\nname=Max hood\nparam=prayerbonus,4',
  '2 a hood that quietly carries bonuses'),
 ('scripts/skillcapes/scripts/skillcape_equip.rs2',
  'if (~skillcape_count_99s < enum_getoutputcount(stats)) {',
  'if (~skillcape_count_99s < 21) {',
  '3 a requirement written down instead of counted'),
 ('scripts/skillcapes/scripts/skillcape_shop.rs2',
  'return(calc(^skillcape_price * enum_getoutputcount(stats)));',
  'return(2178000);',
  '3 a price written down instead of counted'),
 ('scripts/player/configs/stat.enum',
  'val=22,construction\n', '',
  '3 Construction dropped out of the skills the cape counts'),
 ('scripts/skillcapes/scripts/skillcape_shop.rs2',
  'if (inv_freespace(inv) < $missing) {', 'if (inv_freespace(inv) < 0) {',
  '3 a replacement handed out with nowhere to put it'),
 ('scripts/skillcapes/configs/skillcape.enum',
  'val=construction,construction_cape\n', '',
  '4 a skill with no cape, which the random emote could land on'),
 ('scripts/skillcapes/configs/skillcape.enum',
  'val=construction_cape,skillcape_construction\n', '',
  '4 a cape with an emote but no graphic'),
 ('scripts/skillcapes/scripts/skillcape_shop.rs2',
  'if ($cape = max_cape) {', 'if ($cape = max_hood) {',
  '4 the emote button forgetting the Max cape'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'if ($back = max_cape) {\n    return(true);\n}\n',
  '',
  '5 a Max cape with none of the passives'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'case 2 : @skillcape_agility_boost;', 'case 2 : mes("Nothing happens.");',
  '5 a feature that no longer reaches the cape that owns it'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'case 3 : @skillcape_teleport(0_40_53_50_3);', 'case 3 : @skillcape_teleport(0_40_53_50_9);',
  '5 a menu teleport to somewhere no cape goes'),
 ('scripts/skillcapes/scripts/skillcape_perks.rs2',
  'if (~wilderness_level(coord) > 20) {\n    mes("A mysterious force blocks your teleport.");\n    mes("You can\'t use this teleport after level 20 wilderness.");\n    return;\n}\nif (~pre_tele_checks(coord) = false) {\n    return;\n}\nif_close;\np_stopaction;',
  'if_close;\np_stopaction;',
  '5 a house teleport with no wilderness guard'),
 ('scripts/skillcapes/scripts/skillcape_equip.rs2',
  '[opheld2,construction_cape] @skillcape_require(stat_base(construction), "Construction", last_slot);',
  '[opheld2,construction_cape] @skillcape_unavailable("Construction");',
  '6 the Construction cape refused for a skill that exists'),
 ('scripts/skill_construction/scripts/poh_portal.rs2',
  'if (~skillcape_offer(construction) = true) {\n    return;\n}\n', '',
  '6 nobody selling the Construction cape'),
 # the Crafting emote holds the same prop, and comes first in the file - so this has to name the
 # construction block's own first frame to hit the right one of the two.
 ('scripts/skillcapes/configs/skillcape_emotes.seq',
  'replaceheldright=skillcape_prop_crafting_r\nframe1=anim_osrs_11524_1',
  'replaceheldright=skillcape_prop_cooking\nframe1=anim_osrs_11524_1',
  '7 the Construction emote holding the wrong prop'),
 ('scripts/skillcapes/configs/skillcape_emotes.seq',
  '[skillcape_construction_emote]\n// OSRS seq 4953', '[skillcape_construction_emote]\n// OSRS seq 4951',
  '7 an emote claiming an id another one already has'),
 ('scripts/skillcapes/configs/skillcape_emotes.spotanim',
  '[skillcape_construction]\n// OSRS spotanim 820\nmodel=spot_skillcape_construction',
  '[skillcape_construction]\n// OSRS spotanim 820\nmodel=spot_skillcape_constructionx',
  '7 a graphic whose model is not in the cache'),
 ('scripts/skillcapes/configs/skillcape_npcs.npc',
  '[skillcape_mac]\n// OSRS npc 1053\nname=Mac\ndesc=A master of all things.',
  '[skillcape_mac]\n// OSRS npc 1053\nname=Mac\ndesc=A master of all things.\nop2=Attack',
  '8 a shopkeeper you can attack'),
 ('maps/m44_55.jm2',
  '0 15 22: 3925', '0 25 22: 3925',
  '8 Mac standing inside the guild wall'),
 ('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc',
  'hitpoints=150', 'hitpoints=15',
  '9 a druid with the wrong hitpoints'),
 ('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc',
  'param=attackrate,4', 'param=attackrate,6',
  '9 an attack speed that is not OSRS\'s'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.constant',
  '^elder_chaos_maxhit = 17', '^elder_chaos_maxhit = 7',
  '9 a maximum hit that is not OSRS\'s'),
 ('scripts/areas/area_wilderness/scripts/elder_chaos_druid.rs2',
  '~elder_chaos_blast;\n\n[ai_opplayer2,elder_chaos_druid]\nif (~npc_combat_spell_checks = false) {\n    return;\n}\n~elder_chaos_blast;',
  '~elder_chaos_blast;\n\n[ai_opplayer2,elder_chaos_druid]\nif (~npc_check_notcombat = false) {\n    return;\n}\n~npc_default_attack;',
  '9 a caster that punches you when you stand next to it'),
 ('scripts/drop_tables/scripts/elder_chaos_druid.rs2',
  '} else if ($slot < 9) {', '} else if ($slot < 8) {',
  '10 a robe table slot that hands out two pieces'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.constant',
  '^elder_chaos_slots = 11', '^elder_chaos_slots = 12',
  '10 a robe rate that is no longer 1 in 1,419'),
 ('scripts/drop_tables/scripts/elder_chaos_druid.rs2',
  'obj_add(npc_coord, snape_grass, 1, ^lootdrop_duration);',
  'obj_add(npc_coord, snape_grass_x, 1, ^lootdrop_duration);',
  '10 a drop table naming an item that does not exist'),
 ('scripts/drop_tables/scripts/elder_chaos_druid.rs2',
  '} else if ($random < 121) {', '} else if ($random < 91) {',
  '10 an if-chain whose thresholds go backwards'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.obj',
  'param=magicattack,10', 'param=magicattack,12',
  '11 a robe bonus that is not the wiki\'s'),
 ('scripts/areas/area_wilderness/configs/elder_chaos.obj',
  'param=levelrequire,40\n\n[elder_chaos_robe]', 'param=levelrequire,30\n\n[elder_chaos_robe]',
  '11 a requirement in the config that the gate does not match'),
 ('scripts/levelrequire/scripts/tier40.rs2',
  '[opheld2,elder_chaos_top] @levelrequire_magic(40, last_slot);',
  '[opheld2,elder_chaos_top] @levelrequire_magic_and_defence(40, 40, last_slot);',
  '11 a Defence requirement on armour whose whole point is having none'),
 ('maps/m50_56.jm2',
  '0 41 24: 3926', '0 39 24: 3926',
  '12 a druid standing inside the altar'),
 ('maps/m50_56.jm2',
  '0 35 25: 3926\n', '',
  '12 a spawn quietly going missing'),
]

def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    fails = 0
    for path, find, repl, why in MUTS:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-44s %s' % (path, why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'maxcape_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        print('  %-5s %s' % ('red' if ok else 'GREEN', why) + ('' if ok else '   NOT CAUGHT'))
        if not ok:
            fails += 1
    print('\n%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
