"""Battery for the Ancient Magicks spellbook, swapped from the cache's own panel.

WHAT IS ACTUALLY AT RISK. Not the layout - a wrong coordinate is visible the moment anybody opens
the tab. It is the JOIN. Twenty-four buttons were renamed by matching a sprite index, and a wrong
match puts the right icon under the wrong trigger: you click Ice Barrage and cast Shadow Rush, with
a tooltip that still says Ice Barrage because the tooltip travelled with the panel. Nothing about
that is visible, and nothing about it fails to compile.

So the join is checked three ways from three sources that were not written together: the cache's
own `action=` text on the button, the level in the cache's own tooltip beside it, and this fork's
`levelrequired` in magic_spell_table. Jagex wrote two of those and this project wrote the third.

    python3 tools/ancientbook_battery.py
"""
import os, re, sys, glob

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFACE = 'ancient_magic'
SRC = 'scripts/interfaces/inter_267.if'
DST = 'scripts/skill_magic/interfaces/%s.if' % IFACE

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1

def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

def blocks(text):
    out = []
    # split on the HEADERS, not on '\n[' - the cache file starts with [com_0] and has no comment
    # above it, so a '\n[' split silently drops its first component and every count is one short
    for b in re.split(r'(?m)^\[', text)[1:]:
        n = b.split(']')[0]
        d = {}
        for l in b.split('\n')[1:]:
            if '=' in l and not l.lstrip().startswith('//'):
                k, v = l.split('=', 1)
                d.setdefault(k.strip(), v.strip())
        out.append((n, d, b))
    return out

DSTT, SRCT = read(DST), read(SRC)
NEW, OLD = blocks(DSTT), blocks(SRCT)
BY = {n: d for n, d, _ in NEW}
RAW = {n: b for n, _, b in NEW}

def sprite(d):
    m = re.match(r'^magicoff2,(\d+)$', d.get('graphic', ''))
    return int(m.group(1)) if m else None

# ============================================================================ 1
print('1. the join: which icon is which spell')
newbtn = {sprite(d): n for n, d, _ in NEW if 'buttontype' in d and sprite(d) is not None}
oldbtn = {sprite(d): (n, d) for n, d, _ in OLD if 'buttontype' in d and sprite(d) is not None}
check(len(newbtn) == 24, 'the book has 24 buttons: %d' % len(newbtn))
check(sorted(newbtn) == list(range(6, 30)),
      'on magicoff2 frames 6..29 with none missing or doubled: %s' % sorted(newbtn))
check(set(newbtn) == set(oldbtn),
      'the same 24 frames the cache panel carries')
# the cache's own words for the sixteen it names
named = [(i, d.get('action')) for i, (n, d) in sorted(oldbtn.items()) if d.get('action')]
check(len(named) == 16, 'the cache names 16 of them in plain English: %d' % len(named))
wrong = [(i, act, newbtn[i]) for i, act in named
         if act.lower().replace(' ', '_') != newbtn[i]]
check(not wrong, "and every one is under that spell's symbol: %s" % (wrong[:3] or 'all 16'))

# the tooltip beside each button, and this fork's own row for that spell
ROWS = {}
for p in glob.glob(os.path.join(C, 'scripts/**/*.dbrow'), recursive=True):
    for b in open(p, newline='').read().replace('\r\n', '\n').split('\n[')[1:]:
        s = re.search(r'data=spell,\^(\w+)', b)
        l = re.search(r'data=levelrequired,(\d+)', b)
        if s and l:
            ROWS.setdefault(s.group(1), int(l.group(1)))
# Jagex spells it Carrallangar; this fork's constant is carrallanger. One letter, written down
# rather than silently normalised everywhere.
SPELLING = {'carrallangar': 'carrallanger'}
def symbol(title):
    k = title.lower().replace(' ', '_')
    for a, b in SPELLING.items():
        k = k.replace(a, b)
    return k

# the tooltip is a TEXT component INSIDE the hover panel, so its parent layer is what names it
tip = {}
for n, d, b in NEW:
    m = re.search(r'(?m)^text=Level (\d+) : (.+)$', b)
    if m:
        tip[d.get('layer')] = (int(m.group(1)), m.group(2).strip())
check(len(tip) == 24, 'each of the 24 has a level tooltip: %d' % len(tip))
orphan = [n for n in tip if not (n or '').startswith('info_')]
check(not orphan, 'each tooltip lives in an info_<spell> panel: %s' % (orphan[:3] or 'all 24'))
wrong = [(n, t[1]) for n, t in sorted(tip.items()) if symbol(t[1]) != (n or '')[5:]]
check(not wrong, "and the panel's own name is the spell the tooltip names: %s"
      % (wrong[:3] or 'all 24'))
missing = [(n, t) for n, t in sorted(tip.items()) if symbol(t[1]) not in ROWS]
check(not missing, 'every spell named has a row in a magic spell table: %s'
      % (missing[:3] or 'all 24'))
wrong = [(t[1], t[0], ROWS[symbol(t[1])]) for n, t in sorted(tip.items())
         if symbol(t[1]) in ROWS and ROWS[symbol(t[1])] != t[0]]
check(not wrong, "and the CACHE's level for it is this fork's levelrequired: %s"
      % (wrong[:3] or 'all 24 agree'))
# the button and its panel are wired to each other
crossed = [n for n in newbtn.values() if BY[n].get('overlayer') != 'info_%s' % n]
check(not crossed, 'every button opens its own panel on hover: %s' % (crossed[:3] or 'all 24'))

# ============================================================================ 2
print('2. it is the cache panel, not something that looks like one')
check(len(NEW) == len(OLD), 'component for component with inter_267: %d vs %d' % (len(NEW), len(OLD)))
def count(t, pat):
    return len(re.findall(pat, t))
for label, pat in (('script operands', r'(?m)^script\d+op\d+='),
                   ('staff checks', r'inv_contains,wornitems:worn,'),
                   ('rune-pouch reads', r'rune_pouch_mirror'),
                   ('rune models', r'(?m)^type=model$'),
                   ('lit-icon graphics', r'(?m)^activegraphic=magicon2,')):
    a, b = count(SRCT, pat), count(DSTT, pat)
    # ONE wording, pass or fail. A message that only exists once something is broken cannot be a
    # mutation label, and tools/mutate_labels.py reads a CLEAN run - see the handoff.
    check(a == b, '%s carried over from the cache panel unchanged: %d there, %d here'
          % (label, a, b))
rects = [n for n, d, _ in NEW if d.get('type') == 'rect']
check(len(rects) == 4, 'the bordered description frame is here - four nested rects: %d' % len(rects))
# geometry is the cache's, which is the whole point of the swap
moved = []
for i, n in sorted(newbtn.items()):
    o = oldbtn[i][1]
    if (BY[n].get('x'), BY[n].get('y')) != (o.get('x'), o.get('y')):
        moved.append((n, BY[n].get('x'), BY[n].get('y'), o.get('x'), o.get('y')))
check(not moved, "every button sits where Jagex put it: %s" % (moved[:3] or 'all 24'))

# ============================================================================ 3
print('3. the triggers, which are what a wrong join would betray')
TRIG = {}
for p in glob.glob(os.path.join(C, 'scripts/**/*.rs2'), recursive=True):
    t = open(p, newline='').read().replace('\r\n', '\n')
    for k, n in re.findall(r'(?m)^\[(\w+),%s:(\w+)\]' % IFACE, t):
        TRIG.setdefault(n, set()).add(k)
check(set(TRIG) == set(newbtn.values()),
      'every component a trigger names exists, and every button has one: %s'
      % (sorted(set(TRIG) ^ set(newbtn.values()))[:3] or '24 of each'))
combat = {n for n in TRIG if TRIG[n] & {'applayert', 'apnpct'}}
tele = {n for n in TRIG if 'if_button' in TRIG[n]}
check(len(combat) == 16 and len(tele) == 8,
      '16 combat spells and 8 teleports: %d and %d' % (len(combat), len(tele)))
bad = [n for n in combat if TRIG[n] != {'applayert', 'apnpct'}]
check(not bad, 'each combat spell is castable on a player AND on an npc: %s' % (bad[:3] or 'all 16'))
bad = [n for n in combat if BY[n].get('buttontype') != 'target'
       or BY[n].get('actiontarget') != 'npc,player']
check(not bad, '...and its button is buttontype=target aimed at npc,player: %s'
      % (bad[:3] or 'all 16'))
bad = [n for n in tele if BY[n].get('buttontype') != 'normal']
check(not bad, 'each teleport is a plain button: %s' % (bad[:3] or 'all 8'))
# the option the cache does not carry, and which the round puts back
bad = [n for n in tele if not BY[n].get('option')]
check(not bad, '...with a right-click option, which the cache panel has none of: %s'
      % (bad[:3] or 'all 8'))
bad = [(n, BY[n].get('option')) for n in sorted(tele)
       if n.replace('_teleport', '') not in (BY[n].get('option') or '').lower()]
check(not bad, '...naming its own destination: %s' % (bad[:3] or 'all 8'))

# ============================================================================ 4
print('4. the pack, and the id login.rs2 sends')
pack = {}
for l in read('pack/interface.pack').split('\n'):
    if '=' in l:
        i, nm = l.split('=', 1)
        pack[nm] = int(i)
order = {int(l) for l in read('pack/interface.order').split('\n') if l.strip()}
check(IFACE in pack, '%s has an id: %s' % (IFACE, pack.get(IFACE)))
# THE ONE ID THAT MAY NOT MOVE. if_settab sends the interface's id, and login.rs2 is what calls it.
# THE ONE ID THAT MAY NOT MOVE, and the number is the COMMITTED one rather than one written from
# memory - an earlier draft of this check asserted 5063, which is not and never was its id, and the
# check caught its own author. repack() keeps the interface's own line and re-takes only its
# components; this is what says so.
check(pack.get(IFACE) == 18956,
      'and it is still 18956, the id it was committed with, which is what '
      'if_settab(ancient_magic, ...) sends from login.rs2')
missing = [n for n, _, _ in NEW if '%s:%s' % (IFACE, n) not in pack]
check(not missing, 'every component has one: %s' % (missing[:3] or '%d of them' % len(NEW)))
missing = [n for n, _, _ in NEW if pack['%s:%s' % (IFACE, n)] not in order]
check(not missing, '...and is in interface.order: %s' % (missing[:3] or 'all of them'))
ids = [pack['%s:%s' % (IFACE, n)] for n, _, _ in NEW]
check(len(set(ids)) == len(ids), 'no id is used twice inside the book')
check('if_settab(%s, ^tab_magic);' % IFACE in read('scripts/login_logout/scripts/login.rs2'),
      'login.rs2 still puts it on the magic tab')

# ============================================================================ 5
print('5. the generator still produces exactly what is checked in')
import subprocess as _sp
kept = {f: open(os.path.join(C, f), 'rb').read() for f in
        [DST, 'pack/interface.pack', 'pack/interface.order']}
r = _sp.run([sys.executable, os.path.join(C, 'tools/genancientbook.py')],
            capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/genancientbook.py runs clean'
      + ('' if r.returncode == 0 else ': ' + (r.stderr or r.stdout)[-400:]))
moved = [f for f in kept if open(os.path.join(C, f), 'rb').read() != kept[f]]
for f in moved:
    open(os.path.join(C, f), 'wb').write(kept[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
check(os.path.exists(os.path.join(C, SRC)),
      'inter_267.if is still in the tree, because it is what this is generated from')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
