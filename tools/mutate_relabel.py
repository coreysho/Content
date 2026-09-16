#!/usr/bin/env python3
"""Run each unmatchable mutation and record WHICH check it really trips.

A mutation's label has to name the check it is written for, and the only way to know which check
that is, without guessing, is to fire the mutation and look. This is the tool that does it -
tools/mutate_labels.py says WHICH labels are wrong, this says what they should be.

GUESSING DOES NOT WORK, and this was tried first: matching a label to the check whose wording it
most resembles put two slayer labels on "the interface has 150 components", a check with nothing to
do with either mutation. A label naming the wrong check is worse than one naming no check, because
it prints "caught by its own check" and means nothing by it.

RESUMABLE, because it is slow - one checker run per mutation, which for poh_battery is a minute and
a half each. Every result is written to the json as it is produced, so a container that recycles
costs one mutation rather than the run. That is also the fix for the sweep never having finished.

It refuses to start unless the checker is green on a clean tree: a checker that is already red
cannot tell you which check a mutation tripped.

    python3 tools/mutate_relabel.py slayer_mutate slayer_battery.py
"""
import importlib.util, json, os, re, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else os.getcwd()
C = os.getcwd()
TOOLS = os.path.join(C, 'tools')
OUT = os.environ.get('RELABEL_OUT', '/tmp/relabel_%s.json' % sys.argv[1])
W = '/tmp/relabel_work_%s' % sys.argv[1]

HARNESS = sys.argv[1]
CHECKER = sys.argv[2]

def muts(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(TOOLS, name + '.py'))
    m = importlib.util.module_from_spec(spec)
    argv, sys.argv2 = sys.argv, None
    sys.argv = [name]
    try:
        spec.loader.exec_module(m)
    finally:
        sys.argv = argv
    return m.MUTS

def messages(checker, cwd):
    ENGINE = os.path.join(C, '..', 'engine')
    r = subprocess.run([sys.executable, os.path.join(cwd, 'tools', checker)],
                       capture_output=True, text=True, cwd=cwd,
                       env=dict(os.environ, LOSTCITY_ENGINE=ENGINE))
    ok, fail = [], []
    for line in r.stdout.split('\n'):
        t = line.strip()
        if t.startswith('ok '):
            ok.append(re.sub(r'^ok\s+', '', t))
        elif t.startswith('FAIL '):
            fail.append(re.sub(r'^FAIL\s+', '', t))
    return ok, fail, r.returncode

db = json.load(open(OUT)) if os.path.exists(OUT) else {}

if os.path.exists(W):
    shutil.rmtree(W)
shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))

clean_ok, clean_fail, _ = messages(CHECKER, W)
assert not clean_fail, 'the checker is not green on a clean tree: %s' % clean_fail[:2]
HAY = clean_ok

M = muts(HARNESS)
todo = []
for i, (p, f, r, why) in enumerate(M):
    label = why.split(' ', 1)[1] if why[:1].isdigit() else why
    if label.endswith(('(rs2check)', '(build sim)', '(furn sim)')):
        continue
    if any(label in h for h in HAY):
        continue
    todo.append(i)
print('%s: %d mutations need a label, %d already recorded' %
      (HARNESS, len(todo), sum(1 for i in todo if '%s:%d' % (HARNESS, i) in db)))

for n, i in enumerate(todo):
    key = '%s:%d' % (HARNESS, i)
    if key in db:
        continue
    path, find, repl, why = M[i]
    p = os.path.join(W, path)
    original = open(p, 'rb').read()
    raw = original.decode('utf-8')
    nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
    f2, r2 = find.replace('\n', nl), repl.replace('\n', nl)
    if f2 not in raw:
        db[key] = {'why': why, 'fired': None, 'note': 'pattern not found'}
    else:
        open(p, 'w', newline='').write(raw.replace(f2, r2, 1))
        _o, fired, rc = messages(CHECKER, W)
        open(p, 'wb').write(original)
        db[key] = {'why': why, 'fired': fired, 'rc': rc}
    json.dump(db, open(OUT, 'w'), indent=1)
    got = db[key].get('fired')
    print('  [%3d/%3d] %-52s -> %s' % (n + 1, len(todo), why[:52],
          ('%d fired: %s' % (len(got), got[0][:60]) if got else db[key].get('note', 'NOTHING FIRED'))))
print('done')
