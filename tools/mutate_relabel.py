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

ABSORBING CHECKS. Some checks go red for any edit at all to the files they cover - group 38's
"re-running it changes nothing", which re-runs the generators and compares. A mutation to a
generated file trips that FIRST, before the check it was written for can fire, so the first FAIL
line is the wrong answer: it would relabel dozens of unrelated mutations to the same sentence. The
label is taken from the first fired check that is NOT one of those, and a mutation that trips
nothing else is REPORTED rather than relabelled - it is proving nothing about its own check and
belongs in tools/poh_mutate_spec.py, which regenerates before it checks.

    python3 tools/mutate_relabel.py slayer_mutate slayer_battery.py     # measure
    python3 tools/mutate_relabel.py slayer_mutate --apply               # write the labels
"""
import importlib.util, json, os, re, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) if '__file__' in dir() else os.getcwd()
C = os.getcwd()
TOOLS = os.path.join(C, 'tools')
OUT = os.environ.get('RELABEL_OUT', '/tmp/relabel_%s.json' % sys.argv[1])
W = '/tmp/relabel_work_%s' % sys.argv[1]

HARNESS = sys.argv[1]
CHECKER = sys.argv[2] if len(sys.argv) > 2 else None

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

def measure():
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



# ---------------------------------------------------------------------------- writing them back

# A check that goes red for ANY edit to the files it covers, so it tells you nothing about which
# check a mutation was written for. Matched on the opening of the message.
ABSORBING = ('re-running it changes nothing',)


def newlabel(why, fired):
    """Keep the group number; take the wording of the first non-absorbing check that fired, up to
    where its values start. A check puts its numbers after a colon by convention, and a label
    carrying a value goes stale the moment the value does - that fault has been found four times."""
    useful = [f for f in fired if not f.startswith(ABSORBING)]
    if not useful:
        return None
    grp = re.match(r'^(\d+[a-z]?)\s+', why)
    head = grp.group(1) + ' ' if grp else ''
    txt = re.sub(r'\s+', ' ', useful[0].split(':')[0].strip())
    if len(txt) > 78:
        txt = txt[:78].rsplit(' ', 1)[0]
    return head + txt


def apply(harness):
    db = json.load(open(os.environ.get('RELABEL_OUT', '/tmp/relabel_%s.json' % harness)))
    p = os.path.join(TOOLS, harness + '.py')
    raw = open(p, 'rb').read()
    nl = '\r\n' if b'\r\n' in raw else '\n'
    s = raw.decode('utf-8').replace('\r\n', '\n')
    done = absorbed = nothing = stuck = 0
    multi = []
    for key in sorted(db, key=lambda k: int(k.split(':')[1])):
        v = db[key]
        fired = v.get('fired')
        if not fired:
            print('  NOTHING FIRED  %s' % v['why'])
            nothing += 1
            continue
        new = newlabel(v['why'], fired)
        if new is None:
            print('  ONLY %r fired - so either this mutation is ABOUT the generator, in which '
                  'case that is its own check, or it edits a generated file and is absorbed '
                  'before its own check can fire, in which case it belongs in '
                  'poh_mutate_spec.py. Intent decides, so it is left alone: %s'
                  % (fired[0].split(':')[0], v['why']))
            absorbed += 1
            continue
        if new == v['why']:
            continue
        old = "'" + v['why'].replace("'", "\\'") + "'"
        if s.count(old) != 1:
            old = '"' + v['why'] + '"'
        if s.count(old) != 1:
            print('  COULD NOT PLACE %r' % v['why'])
            stuck += 1
            continue
        s = s.replace(old, old[0] + new.replace("'", "\\'") + old[0], 1)
        done += 1
        if len([f for f in fired if not f.startswith(ABSORBING)]) > 1:
            multi.append((new, len(fired)))
    open(p, 'wb').write(s.replace('\n', nl).encode('utf-8'))
    print()
    print('%s: %d relabelled, %d absorbed, %d fired nothing, %d unplaceable'
          % (harness, done, absorbed, nothing, stuck))
    print('%d of the relabelled trip more than one check of their own' % len(multi))
    if absorbed:
        print('the %d above need a person: see the note beside each' % absorbed)
    return 1 if (absorbed or nothing or stuck) else 0


if __name__ == '__main__':
    # Two modes, and the measuring one must not run for --apply: it copies a 24k-file tree and
    # runs the checker before it does anything else.
    if len(sys.argv) > 2 and sys.argv[2] == '--apply':
        sys.exit(apply(HARNESS))
    measure()
    sys.exit(0)
