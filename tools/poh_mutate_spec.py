#!/usr/bin/env python3
"""Mutate a SPEC file, regenerate, then run the battery - which is what a real mistake looks like.

poh_mutate.py changes one file and runs a checker. That is the right shape for a mutation to a
shipped file, but it is the WRONG shape for a mutation to tools/furnspec.json or any other spec,
because the battery re-runs the generators in place and group 38's "the generator still produces
exactly what is checked in" goes red first, every time, whatever the mutation was. The mutation is
caught, but by a check that would catch any spec edit at all, so it proves nothing about the check
it was written for.

A person does not leave a spec and its output out of step. They edit the spec, run the generators,
and commit both - and then group 38 is green and only the check that matters can fire. This runs
that sequence:

    edit the spec -> genfurn, genmenus, genhedge -> poh_battery

    python3 tools/poh_mutate_spec.py 171          # by index into poh_mutate.MUTS
    python3 tools/poh_mutate_spec.py 171,140

It is slow - a full regenerate and a full battery per mutation - so it is for the handful of checks
that read the spec rather than the generated file. The one it was written for is group 63's "every
material is bought somewhere or made somewhere", which is the check that would have caught six
formal-garden flowerbeds costing a bagged flower that no shop in the game sold.
"""
import os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import poh_mutate as M

C = M.C
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'poh_mutate_spec_work')
GENERATORS = ('tools/genfurn.py', 'tools/genmenus.py', 'tools/genhedge.py',
              'tools/genstores.py', 'tools/genslayerhelm.py')


def fresh():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    fails = 0
    for i in sys.argv[1].split(','):
        path, find, repl, why = M.MUTS[int(i)]
        fresh()
        p = os.path.join(W, path)
        raw = open(p, 'rb').read().decode('utf-8')
        if find not in raw:
            print('  SKIP (pattern not found) %s' % why)
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(find, repl, 1))
        for gen in GENERATORS:
            subprocess.run([sys.executable, os.path.join(W, gen)], capture_output=True, cwd=W)
        r = subprocess.run([sys.executable, os.path.join(W, 'tools/poh_battery.py')],
                           capture_output=True, text=True, cwd=W)
        named = [l for l in r.stdout.split('\n') if l.startswith('  FAIL')]
        print('  %-5s %-58s %s' % ('red' if r.returncode else 'GREEN', why,
                                   named[0][7:80] if named else ''))
        if not r.returncode:
            fails += 1
    print('\n%s' % ('every mutation was caught' if not fails else '%d MUTATIONS SURVIVED' % fails))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
