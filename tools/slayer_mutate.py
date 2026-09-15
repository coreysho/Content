#!/usr/bin/env python3
"""Mutation test for tools/slayer_battery.py.

Each entry breaks one thing the battery claims to catch - in a throwaway copy, never in place - and
the battery has to go red. Same runner as poh_mutate.py and maxcape_mutate.py, copied a third time;
that is now three, so the next one should lift it into a module instead.

    python3 tools/slayer_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'slayer_mutate_work')

MUTS = [
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  '[tab4]\ntype=text', '[tab4]\ntype=rect',
  '2 a tab that is not a label any more'),
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  'text=Cosmetics', 'text=Cosmetic',
  '2 a tab whose name drifts from OSRS\'s'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_tab_buy = 2', '^slayer_tab_buy = 5',
  '2 a tab constant that is not the column it is drawn in'),
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  '[row10]\ntype=layer', '[row10]\ntype=rect',
  '3 a row that cannot be hidden because it is not a layer'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_task_rows = 6', '^slayer_task_rows = 12',
  '3 a tab that needs more rows than the window has'),
 ('scripts/skill_slayer/interfaces/slayer_rewards.if',
  '[r5name]\nlayer=row5\ntype=text\nx=6\ny=1\nwidth=328',
  '[r5name]\nlayer=row5\ntype=text\nx=6\ny=1\nwidth=328\noption=Select',
  '3 a second option string on a row'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,On task, a monster with a superior form has a 1 in 200 chance',
  'val=0,On task, a monster with a superior form has a 1 in 200 chance of summoning it when it dies, which is a long way of saying it is worth having.',
  '4 a description line too long for the panel'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1,of summoning it when it dies.\nval=3,',
  'val=1,of summoning it when it dies.\nval=2,and that is a third line.\nval=3,',
  '4 a description with more lines than the panel shows'),
 # the two recolour unlocks upstream added, which the Cosmetics tab now holds
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,Unholy Helmet', 'val=0,Unholy Helm',
  '4 a cosmetic unlock whose name drifts from the one the recolour asks for'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  '[slayer_cosmetic_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,5',
  '[slayer_cosmetic_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,7',
  '4 a cosmetic bought on a bit the recolour does not read'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,1000\nval=1,1000', 'val=0,500\nval=1,1000',
  "4 a recolour price that is not OSRS's 1,000"),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_buy_imbue = 3', '^slayer_buy_imbue = 2',
  '9 an imbue row that collides with a thing you buy'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=3,1250', 'val=3,1000',
  '9 an imbue price the enum and the constant disagree about'),
 ('scripts/skill_slayer/scripts/slayer_rewards.rs2',
  'if ($i = ^slayer_buy_imbue) {\n    return(~slayer_do_imbue);',
  'if ($i = ^slayer_buy_imbue) {\n    return(false);',
  '9 a Buy row that charges for the imbue and does not imbue'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_ui_row_off = 0x4A3F31', '^slayer_ui_row_off = 0x4A3F32',
  '5 a brown the script and the interface disagree about'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_ui_row_on = 0x8C7F63', '^slayer_ui_row_on = 0x4A3F31',
  '5 a selected row that looks like an unselected one'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_ui_clicks = 128', '^slayer_ui_clicks = 400',
  '6 a click bound that can run the script out of instructions'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'while ($clicks < ^slayer_ui_clicks) {', 'while ($clicks < 400) {',
  '6 a bound written down instead of taken from the constant'),
 ('scripts/skill_slayer/scripts/slayer_master.rs2',
  '~slayer_rewards_window;', '~slayer_taskname;',
  '7 a master that no longer opens the window'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'mes("Select something first.");', '~chatnpc("Select something first.");',
  '7 the window talking as the npc over the top of itself'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'if (%slayer_points < $cost) {', 'if (%slayer_points < 0) {',
  '8 a Confirm that does not check the points'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'if (~slayer_ui_owned($tab, $sel) = true) {\n    mes("You already have that.");',
  'if (~slayer_ui_owned($tab, $sel) = false) {\n    mes("You already have that.");',
  '8 a Confirm that sells you what you own'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  '[slayer_unlock_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,4',
  '[slayer_unlock_bit]\ninputtype=int\noutputtype=int\ndefault=-1\nval=0,0',
  '8 two unlocks sharing a bit'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1,120', 'val=1,100',
  '9 an unlock price that is not the wiki\'s'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=0,slayer_ring_8', 'val=0,slayer_ring_9',
  '9 a thing to buy that is not a real obj'),
 ('scripts/skill_slayer/configs/slayer.constant',
  '^slayer_cancel_cost = 30', '^slayer_cancel_cost = 45',
  '9 a task price the window changed by accident'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=1000,1,000', 'val=1000,1000',
  '9 a price the window spells without its thousands separator'),
 ('scripts/skill_slayer/configs/slayer_rewards.enum',
  'val=750,750\n', '',
  '9 a price with no row in the spelling table at all'),
 ('scripts/skill_slayer/scripts/slayer_window.rs2',
  'return("<enum(int, string, slayer_cost_text, $cost)> points");',
  'return("<tostring($cost)> points");',
  '9 a cost drawn with tostring, which cannot group digits'),
 ('tools/genslayerui.py',
  "    for c in ('slayer_cancel_cost', 'slayer_block_cost', 'slayer_imbue_cost'):",
  "    for c in ('slayer_block_cost', 'slayer_imbue_cost'):",
  '9 a spelling table that forgets the prices held in constants'),
 ('tools/genslayerui.py',
  "ROWS, ROW_Y, ROW_STEP, ROW_H = 11, 90, 15, 14",
  "ROWS, ROW_Y, ROW_STEP, ROW_H = 10, 90, 15, 14",
  '10 a generator whose output no longer matches what is checked in'),
 ('tools/genslayerui.py',
  "body = nl.join(src).replace('\\r\\n', '\\n').rstrip('\\n')",
  "body = nl.join(src).rstrip('\\r\\n')",
  '10 a generated file with two kinds of line ending'),
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
            print('  SKIP (pattern not found) %-40s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'slayer_battery.py')],
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
