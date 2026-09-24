#!/usr/bin/env python3
"""The drop table viewer: the generated data, then examine against the real engine.

    python3 tools/npcdrops_battery.py <engine dir>

1. tools/gennpcdrops.py --check: the checked-in npc_drops.dbrow / .enum / .inv / .if are exactly what
   the drop scripts produce today, so a drop table edited without a re-run fails here.
2. tools/npcdrops_sim.ts inside the engine (build first - it reads the packed scripts): examining a
   goblin, a chicken, the King Black Dragon, General Graardor and a superior opens the window with
   every row the dbrow holds, in the right list tier, icons included, and nothing left over when a
   short table follows a long one; a spider (drops nothing) and a banker open nothing. The TS file
   has to sit inside the engine to resolve its '#/' imports, so it is copied into
   <engine>/tools/sim for the run and removed after."""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(C, '..', 'engine'))
failed = 0

print('== gennpcdrops --check')
r = subprocess.run([sys.executable, os.path.join(C, 'tools', 'gennpcdrops.py'), '--check'], cwd=C,
                   capture_output=True, text=True)
print(r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr[-2000:])
if r.returncode:
    failed += 1
    print('  FAIL the generated files are out of date: run tools/gennpcdrops.py')

dst = os.path.join(E, 'tools', 'sim', '_npcdrops_sim.ts')
# Booting the world creates the trading post's sqlite under data/; leave the engine as it was found.
tp = os.path.join(E, 'data', 'tradingpost')
tp_existed = os.path.exists(tp)
shutil.copy(os.path.join(C, 'tools', 'npcdrops_sim.ts'), dst)
try:
    env = dict(os.environ, BUILD_SRC_DIR=C, NODE_MEMBERS='true')
    r = subprocess.run(['npx', 'tsx', 'tools/sim/_npcdrops_sim.ts'], cwd=E, env=env, capture_output=True,
                       text=True, timeout=900, shell=(os.name == 'nt'))
    print('== examine, live')
    print('\n'.join(l for l in r.stdout.splitlines() if 'OnDemand' not in l))
    bad = sum(1 for l in r.stdout.splitlines() if l.startswith('  FAIL'))
    # The sim's own verdict is its last line. On Windows the process can then exit 3 (0x80000003)
    # while the engine's worker threads are torn down - after the checks, and not about them.
    finished = any(l.strip().endswith(' ok, 0 failed') for l in r.stdout.splitlines())
    if r.returncode and not bad and not finished:
        bad = 1
        print(f'  FAIL the run exited {r.returncode} with no failing check - its last output:')
        tail = [l for l in (r.stdout + r.stderr).splitlines() if 'ERR_INVALID_MODULE' not in l]
        print('\n'.join('       ' + l for l in tail[-25:]))
    failed += bad
finally:
    os.remove(dst)
    if not tp_existed and os.path.exists(tp):
        shutil.rmtree(tp)
print('\nALL PASS' if not failed else f'\n{failed} FAILED')
sys.exit(1 if failed else 0)
