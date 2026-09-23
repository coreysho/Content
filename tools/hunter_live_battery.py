#!/usr/bin/env python3
"""Box trapping, live: runs tools/hunter_live.ts inside the engine against the built pack.

    python3 tools/hunter_live_battery.py <engine dir>

Build first (the test reads the packed scripts and maps). The TS file has to sit inside the engine
to resolve its '#/' imports, so it is copied into <engine>/tools for the run and removed after.
Four passes. Box traps at level 70 (four traps, everything must work) and 40 (below the grey
chinchompa's 53, so a trap in their clearing must stay empty - the level gate). Bird snares at 25,
among the tropical wagtails, and at 10, below the wagtail's 19 - the same gate for snares. And the
Hunter skillcape: refused at 50, worn at 99, and its emote and graphic play."""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(C, '..', 'engine'))
dst = os.path.join(E, 'tools', '_hunter_live.ts')
# Booting the world creates the trading post's sqlite under data/; leave the engine as it was found.
tp = os.path.join(E, 'data', 'tradingpost')
tp_existed = os.path.exists(tp)
shutil.copy(os.path.join(C, 'tools', 'hunter_live.ts'), dst)
failed = 0
try:
    for trap, level in (('box', '70'), ('box', '40'), ('snare', '25'), ('snare', '10'), ('cape', '50')):
        env = dict(os.environ, HTRAP=trap, HLEVEL=level, BUILD_SRC_DIR=C, NODE_PRODUCTION='true', NODE_MEMBERS='true')
        r = subprocess.run(['npx', 'tsx', 'tools/_hunter_live.ts'], cwd=E, env=env, capture_output=True, text=True, timeout=900)
        lines = [l for l in r.stdout.splitlines() if l.startswith('  ok') or l.startswith('  FAIL')]
        print(f'== {trap}, Hunter {level}')
        print('\n'.join(lines))
        bad = sum(1 for l in lines if l.startswith('  FAIL')) + (1 if r.returncode and not any('FAIL' in l for l in lines) else 0)
        if r.returncode and not bad:
            print(r.stdout[-2000:]); print(r.stderr[-2000:])
        failed += bad
finally:
    os.remove(dst)
    if not tp_existed and os.path.exists(tp):
        shutil.rmtree(tp)
print('\nALL PASS' if not failed else f'\n{failed} FAILED')
sys.exit(1 if failed else 0)
