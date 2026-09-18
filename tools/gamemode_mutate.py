#!/usr/bin/env python3
"""Mutation test for tools/gamemode_battery.py. Same runner as tools/leprechaun_mutate.py,
including its trick of copying the ENGINE files the battery reads into the work tree - half of
what this battery checks lives in the other repo, and a mutation to the engine's multiplier has to
be catchable or the check is decoration.

Every entry breaks one thing and expects the battery to go red with the check that is named. A
GREEN line is a hole in the battery.

    python3 tools/gamemode_mutate.py                [all of them]
    python3 tools/gamemode_mutate.py "the lock"     [just those]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(C), 'engine')
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'gamemode_mutate_work')

FOREIGN = {
    'engine:src/engine/entity/Player.ts': ENGINE,
    'engine:src/network/game/client/handler/ClientCheatHandler.ts': ENGINE,
}

CONST = 'scripts/gamemodes/configs/gamemode.constant'
VARP = 'scripts/gamemodes/configs/gamemode.varp'
RS2 = 'scripts/gamemodes/scripts/xprate.rs2'
IF = 'scripts/gamemodes/interfaces/xprate_choose.if'
GEN = 'tools/genxpratechooser.py'
GUIDE = 'scripts/tutorial/scripts/guides/runescape_guide.rs2'
VARPPACK = 'pack/varp.pack'
IPACK = 'pack/interface.pack'
PLAYER = 'engine:src/engine/entity/Player.ts'
CHEAT = 'engine:src/network/game/client/handler/ClientCheatHandler.ts'
FLETCH = 'scripts/skill_fletching/scripts/arrows.rs2'

MUTS = [
 # ---- 1 the rates
 (CONST, '^xprate_unset = 0', '^xprate_unset = 2',
  '"never chosen" is 0, which is what a varp reads as before anybody touches it'),
 (CONST, '^xprate_realism = 1', '^xprate_realism = 2',
  'realism is 1x - the authentic rate'),
 (CONST, '^xprate_5x = 5', '^xprate_5x = 6', '5x is 5 and 10x is 10'),
 (CONST, '^xprate_10x = 10', '^xprate_10x = 5',
  'and no two modes share a rate, or one of them would be unreachable'),
 (CONST, '^xprate_modes = 3', '^xprate_modes = 4', 'there are three modes'),

 # ---- 2 where it lives
 (VARP, '[xp_rate]\nscope=perm', '[xp_rate]\nscope=temp',
  "the rate is perm - it is the account's for good"),
 (VARP, '[xp_rate]\nscope=perm', '[xp_rate]\nscope=perm\ntransmit=yes',
  '...and NOT transmitted'),
 (VARPPACK, '1176=xp_rate\n', '', '...and registered in pack/varp.pack'),

 # ---- 3 the multiplier
 (PLAYER, 'const multi = allowMulti ? Environment.NODE_XPRATE * this.xpRate() : 1;',
          'const multi = allowMulti ? Environment.NODE_XPRATE : 1;',
  "addXp multiplies by the player's own rate as well as the world's"),
 (PLAYER, "        if (Player.xpRateVarp === -2) {\n            Player.xpRateVarp = VarPlayerType.getId('xp_rate');\n        }",
          '        Player.xpRateVarp = 1176;',
  '...and finds the varp by NAME, so content owns which varp it is'),
 (PLAYER, 'private static xpRateVarp: number = -2;', 'private static xpRateVarp: number = -1;',
  '...looked up lazily behind a -2 sentinel'),
 (PLAYER, '        if (Player.xpRateVarp < 0) {\n            return 1;\n        }',
          '        if (Player.xpRateVarp < 0) {\n            return 0;\n        }',
  '...and a MISSING varp reads as 1x, not as zero experience for everybody'),
 (PLAYER, '        if (!rate || rate < 1) {\n            return 1;\n        }',
          '        if (!rate || rate < 1) {\n            return 0;\n        }',
  '...and so does 0, which is every character that existed before this'),
 (PLAYER, 'return Math.min(rate, 100);', 'return rate;',
  '...with an upper rail, because a perm varp written wrong would otherwise be unbounded'),
 (CHEAT, 'player.addXp(stat, getExpByLevel(parseInt(args[1])), false);',
         'player.addXp(stat, getExpByLevel(parseInt(args[1])));',
  'setting a level still passes allowMulti=false'),
 (PLAYER, 'allowMulti: boolean = true', 'allowMulti: boolean = false',
  '...and everything else gets the multiplier by default'),
 (FLETCH, 'stat_advance(fletching, multiply($arrow_count, 10));',
          'stat_advance(fletching, multiply($arrow_count, %xp_rate));',
  'and %xp_rate is read nowhere else in the content tree'),

 # ---- 4 the lock
 (RS2, 'if (%xp_rate ! ^xprate_unset) {\n    return;\n}\n', '',
  'a rate already chosen is not asked for again'),
 (RS2, 'if (%tutorial >= ^tutorial_complete) {\n    return;\n}\n', '',
  '...and a finished tutorial is never asked at all'),
 # the lock AFTER the window opens is the version that looks right and does nothing
 (RS2, 'if (%tutorial >= ^tutorial_complete) {\n    return;\n}\np_arrivedelay;\nif_openmain(xprate_choose);',
       'p_arrivedelay;\nif_openmain(xprate_choose);\nif (%tutorial >= ^tutorial_complete) {\n    return;\n}',
  '...and BOTH of those come before the window opens, or the lock is decoration'),
 (RS2, 'if_addresumebutton(xprate_choose:pick1);\n', '',
  '...and box 1 is a resume button, or clicking it does nothing'),
 (RS2, 'p_pausebutton;', 'p_delay(1);',
  '...and p_pausebutton waits for the click inside the npc script'),
 (RS2, '    case xprate_choose:pick2 : ~xprate_set(^xprate_10x);\n', '',
  'all three boxes are handled'),
 (RS2, 'case xprate_choose:pick1 : ~xprate_set(^xprate_5x);',
       'case xprate_choose:pick1 : ~xprate_set(^xprate_realism);',
  '...and between them they set the three rates'),
 (RS2, '[proc,xprate_set](int $rate)\n%xp_rate = $rate;',
       '[proc,xprate_set](int $rate)\nmes("chosen");',
  'choosing writes the rate'),
 (RS2, 'This cannot be changed later.', 'Enjoy.',
  '...and says so, because a permanent choice made silently is a complaint later'),

 # ---- 5 when it is asked
 (GUIDE, '~xprate_choose;\n\nswitch_int(%tutorial) {', 'switch_int(%tutorial) {',
  'the RuneScape Guide asks'),
 (GUIDE, '~xprate_choose;\n\nswitch_int(%tutorial) {',
         'switch_int(%tutorial) {\n~xprate_choose;',
  '...before the switch on %tutorial'),
 (GUIDE, '[label,newbie_basics_instructor_welcome]',
         '[label,newbie_basics_instructor_welcome]\n~xprate_choose;',
  '...once, not once per branch'),
 (GUIDE, '~chatnpc("<p,neutral>Greetings!',
         'stat_advance(attack, 100);\n~chatnpc("<p,neutral>Greetings!',
  '...and his own script awards no experience'),

 # ---- 6 the window
 (IF, '[pick1]\ntype=rect\nx=186\ny=86\nbuttontype=normal',
      '[pick1]\ntype=rect\nx=186\ny=86\nbuttontype=select',
  'nothing in the window is a select button'),
 (IF, 'option=Choose 5x', 'text=Choose 5x', '...with a Choose option'),
 # the buttontype, not the component type: the check asks whether the thing CLOSES, and an
 # earlier version of this mutation only changed type=text to type=graphic, which it rightly
 # did not care about
 (IF, 'buttontype=close', 'buttontype=normal', 'there IS a close button'),
 (IF, 'text=Realism', 'text=Authentic', 'box 0 is labelled Realism'),
 (IF, '[rate0]', '[rate1]', 'only the Realism box carries a separate rate line'),
 (IPACK, '=xprate_choose:pick0\n', '=xprate_choose:pick0_gone\n',
  'every component is in pack/interface.pack'),
 (GEN, "raise SystemExit('two modes share a rate: %s' % rates)", 'pass',
  'the generator refuses to emit two modes at one rate'),

 # ---- 7 the test hook
 (RS2, 'queue(xprate_debug_set, 0, $rate);', '%xp_rate = $rate;',
  'the debugproc QUEUES its write'),
 (RS2, '[queue,xprate_debug_set](int $rate)\n%xp_rate = $rate;',
       '[queue,xprate_debug_set](int $rate)\nmes("set");',
  '...and the queue is what writes it'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    os.makedirs(W)
    shutil.copytree(C, os.path.join(W, 'content'),
                    ignore=shutil.ignore_patterns('.git', '__pycache__'))
    for tagged, root in FOREIGN.items():
        tag, rel = tagged.split(':', 1)
        dst = os.path.join(W, tag, rel)
        src = os.path.join(root, rel)
        if not os.path.exists(src):
            sys.exit('cannot find %s - pass the engine path as argv[2]' % src)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)

    only = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('/') else None
    muts = [m for m in MUTS if not only or only in m[3]]
    fails = loose = 0
    for path, find, repl, why in muts:
        if ':' in path:
            tag, rel = path.split(':', 1)
            p = os.path.join(W, tag, rel)
        else:
            p = os.path.join(W, 'content', path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-28s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        if raw.count(f) > 1:
            print('  SKIP (pattern not unique, %d hits) %-18s %s' % (raw.count(f), os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'content', 'tools', 'gamemode_battery.py'),
                            os.path.join(W, 'engine')],
                           capture_output=True, text=True, cwd=os.path.join(W, 'content'))
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(why in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            extra = len(fired) - 1
            state, note = 'red', 'caught by its own check' + (' (and %d others)' % extra if extra else '')
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:52] if fired else 'a crash, which is not a catch')
            loose += 1
        print('  %-5s %-62s %s' % (state, why[:62], note))
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
