"""Symbol and signature battery for the two new .rs2 files, from claude/rs2-compile-traps.md."""
import re, sys, os
C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['scripts/skill_construction/scripts/poh.rs2', 'scripts/skill_construction/scripts/poh_test.rs2']
fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

src = {f: read(f) for f in FILES}
def strip(t):
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    out = []
    for line in t.split('\n'):
        line = re.sub(r'"[^"]*"', '""', line)
        out.append(line.split('//')[0])
    return '\n'.join(out)
clean = {f: strip(t) for f, t in src.items()}
alltext = '\n'.join(clean.values())

print('1. balance')
for f, t in clean.items():
    check(t.count('(') == t.count(')'), '%s parens %d/%d' % (os.path.basename(f), t.count('('), t.count(')')))
    check(t.count('{') == t.count('}'), '%s braces %d/%d' % (os.path.basename(f), t.count('{'), t.count('}')))

print('2. no @label jump inside a proc (trap 5b)')
bad = []
for f, t in clean.items():
    cur = None
    for ln in t.split('\n'):
        m = re.match(r'^\[(\w+),', ln)
        if m: cur = m.group(1)
        if re.search(r'@\w+[;(]', ln) and cur == 'proc': bad.append((f, ln.strip()))
check(not bad, 'none, got %s' % bad)

print('3. declared scripts are unique, and nothing is declared twice')
decl = re.findall(r'^\[(\w+),(\w+)\]', alltext, re.M)
check(len(decl) == len(set(decl)), 'no duplicate [kind,name] in the new files')
names = {n for k, n in decl}
print('   declares: ' + ', '.join('%s %s' % (k, n) for k, n in decl))

print('4. every ~proc call resolves')
called = set(re.findall(r'~(\w+)', alltext))
unknown = sorted(called - names)
check(not unknown, 'unresolved: %s' % unknown)

print('5. every %varp resolves against pack/varp.pack')
varps = {l.split('=', 1)[1] for l in open(C + '/pack/varp.pack').read().split('\n') if '=' in l}
used = set(re.findall(r'%(\w+)', alltext))
check(not (used - varps), 'unresolved: %s' % sorted(used - varps))
print('   uses: ' + ', '.join(sorted(used)))

print('6. every ^constant resolves')
consts = set()
for p in ['scripts/skill_construction/configs/construction.constant', 'scripts/engine.constant']:
    if os.path.exists(os.path.join(C, p)):
        consts |= set(re.findall(r'^\^(\w+)\s*=', read(p), re.M))
usedc = set(re.findall(r'\^(\w+)', alltext))
check(not (usedc - consts), 'unresolved: %s' % sorted(usedc - consts))

print('7. every enum name resolves against pack/enum.pack')
enums = {l.split('=', 1)[1] for l in open(C + '/pack/enum.pack').read().split('\n') if '=' in l}
usede = set(re.findall(r'enum\(\s*\w+\s*,\s*\w+\s*,\s*(\w+)\s*,', alltext))
check(not (usede - enums), 'unresolved: %s (used %s)' % (sorted(usede - enums), sorted(usede)))

print('8. the poh_hotspot category is really defined')
# pack/category.pack is GENERATED and gitignored - categories come from category= lines in the
# configs, so the pack in a working copy can be older than the content and proves nothing.
locs = read('scripts/skill_construction/configs/poh_templates.loc')
check(locs.count('category=poh_hotspot') > 0,
      '%d locs carry category=poh_hotspot' % locs.count('category=poh_hotspot'))

print('9. every command call matches its engine.rs2 signature')
sig = {}
for m in re.finditer(r'^\[command,(\w+)\]\s*(\(([^)]*)\))?\s*(\(([^)]*)\))?', read('scripts/engine.rs2'), re.M):
    name, args, rets = m.group(1), m.group(3), m.group(5)
    if args is None:
        sig[name] = (None, None)
    else:
        n = 0 if args.strip() == '' else len([a for a in args.split(',') if a.strip()])
        sig[name] = (n, (rets or '').strip())
def top_args(s):
    """split a call's argument text on top-level commas"""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(': depth += 1
        elif ch == ')': depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    if cur.strip(): out.append(cur)
    return out
bad = []
for f, t in clean.items():
    body = '\n'.join(l for l in t.split('\n') if not l.startswith('[command,'))
    for m in re.finditer(r'(?<![~$%^\w])(\w+)\(', body):
        name = m.group(1)
        if name not in sig: continue
        want = sig[name][0]
        if want is None: continue
        # find the matching close paren
        i = m.end(); depth = 1
        while i < len(body) and depth:
            if body[i] == '(': depth += 1
            elif body[i] == ')': depth -= 1
            i += 1
        got = len(top_args(body[m.end():i - 1]))
        if got != want:
            bad.append('%s: %s takes %d, given %d' % (os.path.basename(f), name, want, got))
check(not bad, 'arity mismatches: %s' % bad)
used_cmds = sorted({m.group(1) for f, t in clean.items() for m in re.finditer(r'(?<![~$%^\w])(\w+)\(', t) if m.group(1) in sig})
print('   commands used: ' + ', '.join(used_cmds))

print('10. no bare call to a command that returns something (trap 2)')
bad = []
for f, t in clean.items():
    for ln in t.split('\n'):
        s2 = ln.strip()
        m = re.match(r'^(\w+)\(.*\);$', s2)
        if m and m.group(1) in sig and sig[m.group(1)][1]:
            bad.append('%s: %s' % (os.path.basename(f), s2))
check(not bad, 'discarded returns: %s' % bad)

print('11. line endings')
for f in FILES + ['scripts/skill_construction/configs/poh_rooms.enum',
                  'scripts/skill_construction/configs/construction.varp',
                  'scripts/skill_construction/configs/construction.constant']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r\r' not in b and b.count(b'\n') == b.count(b'\r\n'), '%s is clean CRLF' % os.path.basename(f))
for f in ['pack/varp.pack', 'pack/enum.pack']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r' not in b and b.endswith(b'\n'), '%s is LF and ends with a newline' % os.path.basename(f))

print('12. pack ids are unique, and the new ones sit above what was there')
# Not contiguity: varp.pack is missing id 746 upstream and has always built fine. What matters is
# that nothing is claimed twice and that the ids added here were free.
NEW = {'pack/varp.pack': list(range(876, 894)), 'pack/enum.pack': [128, 129, 130]}
for f in ['pack/varp.pack', 'pack/enum.pack']:
    ids = [int(l.split('=', 1)[0]) for l in open(os.path.join(C, f)).read().split('\n') if '=' in l]
    check(len(set(ids)) == len(ids), '%s has no duplicate id' % os.path.basename(f))
    check(all(ids.count(i) == 1 for i in NEW[f]), '%s: every id added here appears exactly once' % os.path.basename(f))
    check(max(ids) == max(NEW[f]), '%s: the new block is the top of the file' % os.path.basename(f))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
