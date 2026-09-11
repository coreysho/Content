#!/usr/bin/env python3
"""Mutation test for the build-window checks in poh_battery.py and the two sims.

A check that cannot fail is worse than no check: it reads as coverage and is not. Each entry
below breaks one thing the checkers claim to catch - in a throwaway copy of the tree, never in
place - and the named checker has to go red. Every mistake here is one that was actually made,
or one the 377 client fails silently on.

Naming the checker is half the point: a mutation caught by the wrong script means a check is
testing something other than what it says.

    python3 tools/poh_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'poh_mutate_work')

MUTS = [
 # (file, find, replace, which check group must go red)
 ('scripts/skill_construction/interfaces/poh_roommenu.if',
  '[row0]\ntype=layer', '[row0]\ntype=overlay', '31 hide-needs-a-layer'),
 ('scripts/skill_construction/interfaces/poh_roommenu.if',
  '[r0box]\nlayer=row0\ntype=rect\nx=0\ny=0\nbuttontype=normal',
  '[r0box]\nlayer=row0\ntype=rect\nx=0\ny=0', '31 resume button must be a button'),
 ('scripts/skill_construction/interfaces/poh_roommenu.if',
  '[cancel]\ntype=text\nx=272\ny=301', '[cancel]\ntype=text\nx=272\ny=321', '32 inside the window'),
 ('scripts/skill_construction/interfaces/poh_furnmenu.if',
  '[s0name]\nlayer=slot0\ntype=text\nx=96', '[s0name]\nlayer=slot0\ntype=text\nx=206',
  '32 inside the window'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '[proc,poh_room_zoom](int $type)(int)\nswitch_int ($type) {\n    case 1 : return(5096);',
  '[proc,poh_room_zoom](int $type)(int)\nswitch_int ($type) {\n    case 1 : return(900);',
  '33 the icon must fit its row'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'case 5 : return(12550);   // poh_bed1_8', 'case 5 : return(12551);   // poh_bed1_8',
  '33 a moved model id'),
 ('scripts/skill_construction/configs/poh_rooms.enum',
  'val=9,150,000', 'val=9,15,000', '34 the two price tables agree'),
 ('scripts/skill_construction/configs/poh_furniture.enum',
  'val=12,Clock', 'val=13,Clock', '34 poh_fam_name covers 12 families'),
 ('pack/interface.order', '19242\n', '', '30 pack and order hold the same ids'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if_sethide(poh_roommenu:row0, true);', 'if_sethide(poh_roommenu:r0name, true);',
  '31 hide-needs-a-layer'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if_settext(poh_roommenu:r0cost,', 'if_settext(poh_roommenu:row0,',
  '31 settext needs a text component'),
 ('scripts/skill_construction/configs/poh_menus.enum',
  'val=2,@bla@', 'val=2,@gry@', '37 an unknown colour tag'),
 ('scripts/skill_construction/configs/poh_menus.enum',
  'val=0,@gre@\nval=1,@red@\nval=2,@bla@', 'val=0,@gre@\nval=1,@red@', '37 a tint table missing a state'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if (stat(construction) >= enum(int, int, poh_room_level, $pick)) {',
  'if (true) {', '6 the level gate at the click (build sim)'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  '    if (enum(int, int, poh_furn_fam, $item) = $fam) {',
  '    if (enum(int, int, poh_furn_fam, $item) = $fam & enum(int, int, poh_furn_level, $item) <= 1) {',
  '6 the family is listed whole (furn sim)'),
 ('scripts/skill_construction/scripts/poh_build.rs2',
  'if (~poh_room_rot_for($rx, $rz, $type, $side) < 0) {',
  'if (stat(construction) < enum(int, int, poh_room_level, $type)) {', '6 rooms listed whole (build sim)'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  'case 87 : loc_add($spot, poh_pet_1, $angle, grounddecor,',
  'case 87 : loc_add($spot, poh_pet_1, $angle, centrepiece_straight,',
  '28 a family placed with the wrong shape'),
 ('scripts/skill_construction/scripts/poh_furniture.rs2',
  'case 238 : loc_add($spot, poh_treasure_magic_chest, $angle, centrepiece_straight, ^poh_loc_duration);\n',
  '', '28 an item that nothing places'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_furn_slots = 256', '^poh_furn_slots = 257', '28 a slot with no varp'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '[proc,poh_furn_xan](int $fam)(int)\nswitch_int ($fam) {\n    case 32 : return(120);',
  '[proc,poh_furn_xan](int $fam)(int)\nswitch_int ($fam) {\n    case 32 : return(150);',
  '33 a camera the zoom was not solved for'),
 ('scripts/skill_construction/configs/construction.constant',
  '^poh_furn_bit_lit = 22', '^poh_furn_bit_lit = 13', '1 the lit bit must sit above the old fields (furn sim)'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '[oploc1,poh_torch_1]', '[oploc2,poh_torch_1]', '39 a trigger on an op the loc does not have'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '[oplocu,poh_altar_saradomin_1]', '[oplocu,poh_lectern_1]', '39 the offer trigger on the wrong loc'),
 ('scripts/skill_construction/configs/poh.loc',
  '[loc_13610]\nname=Clay fireplace\ndesc=A fire burns cosily in the grate.\nmodel=loc_13609\nmodel2=loc_13610\nlength=2\nanim=fireplace\nanim=fire_effect\nforceapproach=east\nop5=Remove',
  '[loc_13610]\nname=Clay fireplace\ndesc=A fire burns cosily in the grate.\nmodel=loc_13609\nmodel2=loc_13610\nlength=2\nanim=fireplace\nanim=fire_effect\nforceapproach=east',
  '28 a lit twin you could never take out'),
 ('scripts/skill_construction/configs/poh_tablets.enum',
  'val=6,25', 'val=6,26', '40 poh_tab_level drifting from the spell row'),
 ('scripts/skill_construction/configs/poh_tablets.enum',
  'val=6,1 fire, 3 air, 1 law, 1 soft clay', 'val=6,1 fire, 2 air, 1 law, 1 soft clay',
  '40 poh_tab_need drifting from the spell row'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'return(db_getfield($d, magic_spell_table:runesrequired, 0));',
  'return(~staff_runes($d));',
  '40 a staff paying for a tablet'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'if (~wilderness_level(coord) > 20) {\n    mes("A mysterious force blocks your teleport!");\n    mes("You can\'t use this teleport after level 20 wilderness.");\n    return;\n}\nif (~pre_tele_checks(coord) = false) {\n    return;\n}\nif (inv_total(inv, $tab) < 1) {\n    return;\n}\ninv_del(inv, $tab, 1);\nmes("You break the tablet.");\ndef_dbrow $d',
  'if (~pre_tele_checks(coord) = false) {\n    return;\n}\nif (inv_total(inv, $tab) < 1) {\n    return;\n}\ninv_del(inv, $tab, 1);\nmes("You break the tablet.");\ndef_dbrow $d',
  '40 a tablet escaping deep wilderness'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'model=obj_tab_varrock\n2dzoom=465', 'model=obj_tab_lumbridge\n2dzoom=465',
  '41 two tablets sharing one model'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'model=obj_tab_varrock\n2dzoom=465', 'model=obj_tab_norrock\n2dzoom=465',
  '41 a tablet naming a model that is not there'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'members=yes\nstackable=yes\nweight=1g\ncost=56', 'members=yes\nweight=1g\ncost=56',
  '41 a tablet that does not stack'),
 ('scripts/skill_construction/configs/poh_tablets.obj',
  'model=obj_tab_varrock\n2dzoom=465\n2dxan=373', 'model=obj_tab_varrock\n2dzoom=1370\n2dxan=373',
  '41 an icon camera that is not the cache\'s'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  '[opheld1,poh_tab_varrock]', '[opheld2,poh_tab_varrock]',
  '41 a trigger on an op the obj does not have'),
 ('scripts/skill_construction/scripts/poh_furn_ops.rs2',
  '[oploc1,poh_lectern_7]\n~poh_tab_pick(7);', '[oploc1,poh_lectern_7]\n~poh_tab_pick(6);',
  '42 a lectern opening the wrong tablet list'),
 ('scripts/skill_construction/interfaces/poh_tabletmenu.if',
  '[t0model]\nlayer=row0\ntype=model\nx=4\ny=0\nwidth=34\nheight=28',
  '[t0model]\nlayer=row0\ntype=model\nx=4\ny=0\nwidth=34\nheight=44',
  '42 an icon box that drops the icon out of its row'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if_setobject(poh_tabletmenu:t0model, enum(int, namedobj, poh_tab_obj, $tab), 90);',
  'if_setobject(poh_tabletmenu:t0model, enum(int, namedobj, poh_tab_obj, $tab), 220);',
  '42 an icon scaled past its row'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'enum(int, namedobj, poh_tab_obj, $tab), 1);', 'enum(int, obj, poh_tab_obj, $tab), 1);',
  '15 an enum of the wrong type for the parameter (rs2check)'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'anim(poh_tab_break, 0);', 'anim(human_castteleport, 0);',
  '44 the cast animation creeping back into a break'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'sound_synth(teleport_all, 1, 0);\n~poh_tab_breakanim;\np_delay(2);\n~p_telejump_safe($dest);',
  'sound_synth(teleport_all, 1, 0);\np_delay(2);\n~p_telejump_safe($dest);',
  '44 a break with no animation at all'),
 ('scripts/skill_construction/configs/poh_tab_break.seq',
  'frame1=anim_osrs_10883_1', 'frame1=anim_osrs_10883_9',
  '44 a break frame that is not in anim.pack'),
 ('scripts/skill_construction/configs/poh_tab_break.spotanim',
  'model=spot_poh_tab_break_gfx', 'model=spot_poh_tab_break_ghost',
  '44 a break graphic whose model is not there'),
 ('scripts/skill_construction/interfaces/poh_tabletmenu.if',
  '[qty5]\ntype=text\nx=382\ny=46\nbuttontype=normal',
  '[qty5]\ntype=text\nx=382\ny=46',
  '45 a quantity button that is not a button'),
 ('scripts/skill_construction/interfaces/poh_tabletmenu.if',
  '[qty10]\ntype=text\nx=420\ny=46', '[qty10]\ntype=text\nx=420\ny=66',
  '45 a quantity button sitting on top of the first row'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '    if_addresumebutton(poh_tabletmenu:qty10);\n', '',
  '45 a quantity button nothing can click'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  'if (%poh_tab_qty > ^poh_tab_qty_max) {', 'if (%poh_tab_qty > 100000) {',
  '45 Make X with no cap'),
 ('scripts/skill_construction/scripts/poh_menus.rs2',
  '        if_close;\n        ~poh_tab_make_n($pick, %poh_tab_qty);',
  '        ~poh_tab_make_n($pick, %poh_tab_qty);\n        if_close;',
  '45 making tablets behind the window'),
 ('scripts/skill_construction/scripts/poh_tablets.rs2',
  'while ($i < $count & $i < ^poh_tab_qty_max) {', 'while ($i < $count) {',
  '45 an unbounded make loop'),
 ('scripts/skill_construction/configs/construction.varp',
  '[poh_tab_qty]', '[poh_tab_qty]\nscope=perm',
  '45 the quantity saved as if it were part of the house'),
]

def checker_for(why):
    if why.endswith('(rs2check)'):
        return 'tools/rs2check.py'
    if why.endswith('(build sim)'):
        return 'tools/poh_build_sim.py'
    if why.endswith('(furn sim)'):
        return 'tools/poh_furn_sim.py'
    return 'tools/poh_battery.py'

def main():
    # one copy of the tree, not one per mutation: the repo has 24k files in it and copying it
    # fifteen times turns a two-second test into a four-minute one
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
        checker = checker_for(why)
        if f not in raw:
            print('  SKIP (pattern not found) %-44s %s' % (path, why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        # rs2check takes the current directory as the script root, and refuses to run anywhere
        # else - see the note beside engine.rs2 in it.
        cwd = os.path.join(W, 'scripts') if checker.endswith('rs2check.py') else W
        r = subprocess.run([sys.executable, os.path.join(W, checker)], capture_output=True,
                           text=True, cwd=cwd)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        print('  %-5s %-46s %-20s %s' % ('red' if ok else 'GREEN', why,
              os.path.basename(checker), 'caught' if ok else 'NOT CAUGHT'))
        if not ok:
            fails += 1
    print('\n%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0

if __name__ == '__main__':
    sys.exit(main())
