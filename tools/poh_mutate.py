#!/usr/bin/env python3
"""Mutation test for the build-window checks in poh_battery.py.

A check that cannot fail is worse than no check: it reads as coverage and is not. Each entry
below breaks one thing the battery claims to catch - in a throwaway copy of the tree, never in
place - and the battery has to go red. Every mistake here is one that was actually made, or
one the 377 client fails silently on.

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
]

def run():
    r = subprocess.run([sys.executable, os.path.join(W, 'tools/poh_battery.py')],
                       capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr

fails = 0
for path, find, repl, why in MUTS:
    if os.path.exists(W): shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    p = os.path.join(W, path)
    raw = open(p, newline='').read()
    nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
    f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
    if f not in raw:
        print('  SKIP (pattern not found) %-44s %s' % (path, why)); fails += 1; continue
    open(p, 'w', newline='').write(raw.replace(f, r2, 1))
    code, out = run()
    ok = code != 0
    print('  %-4s %-46s -> %s' % ('red' if ok else 'GREEN', why, 'caught' if ok else 'NOT CAUGHT'))
    if not ok: fails += 1
print('\n%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
sys.exit(1 if fails else 0)
