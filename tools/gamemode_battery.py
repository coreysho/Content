"""Battery for the XP rate modes: realism, 5x and 10x.

WHAT IS ACTUALLY AT RISK HERE, and it is not the arithmetic. It is that the multiplier sits in ONE
place and that the choice cannot be remade. There are 288 stat_advance call sites across 122
content files and no wrapper they pass through, so the rate lives in Player.addXp - which means
half of what this checks is in the ENGINE repo, and a content battery can only read its source.
That is exactly the half most likely to be left behind, since it is a separate checkout.

The other half is the lock. A mode that can be changed later is a button that says "give me ten
times the experience", so the checks about ~xprate_choose refusing to ask are the ones that matter
most, and they are written from both sides: the early returns are there, and the interface opens
after them.

    python3 tools/gamemode_battery.py [path/to/Engine-TS]
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(C), 'engine')

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')
def readat(root, p):
    f = os.path.join(root, p)
    return open(f, newline='').read().replace('\r\n', '\n') if os.path.exists(f) else None

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt): return '\n'.join(l.split('//')[0] for l in txt.split('\n'))
def block(txt, n):
    return txt.split('[' + n + ']', 1)[1].split('\n[', 1)[0] if '[' + n + ']' in txt else ''

CONST = read('scripts/gamemodes/configs/gamemode.constant')
VARP = read('scripts/gamemodes/configs/gamemode.varp')
RS2 = read('scripts/gamemodes/scripts/xprate.rs2')
IF = read('scripts/gamemodes/interfaces/xprate_choose.if')
GEN = read('tools/genxpratechooser.py')
GUIDE = read('scripts/tutorial/scripts/guides/runescape_guide.rs2')
VARPPACK = read('pack/varp.pack')
IPACK = read('pack/interface.pack')
IORDER = read('pack/interface.order')
QUESTC = read('scripts/general/configs/quest.constant')

def const(txt, n):
    m = re.search(r'(?m)^\^' + n + r' = (\d+)\s*(?://.*)?$', txt)
    return int(m.group(1)) if m else None

def ifcoms(txt):
    out = {}
    for chunk in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', chunk)
        if m:
            out[m.group(1)] = dict(re.findall(r'(?m)^(\w+)=(.*)$', chunk))
    return out

IFC = ifcoms(IF)

# ============================================================================ 1
print('1. the rates, and the one that means "never chosen"')
RATES = {n: const(CONST, 'xprate_' + n) for n in ('unset', 'realism', '5x', '10x')}
check(RATES['unset'] == 0,
      '"never chosen" is 0, which is what a varp reads as before anybody touches it (%s)'
      % RATES['unset'])
check(RATES['realism'] == 1,
      'realism is 1x - the authentic rate, so it is what the server already did (%s)'
      % RATES['realism'])
check(RATES['5x'] == 5 and RATES['10x'] == 10, '5x is 5 and 10x is 10 (%s, %s)'
      % (RATES['5x'], RATES['10x']))
check(RATES['unset'] not in (RATES['realism'], RATES['5x'], RATES['10x']),
      'no mode uses the "never chosen" value, or choosing it would not stick')
check(len({RATES['realism'], RATES['5x'], RATES['10x']}) == 3,
      'and no two modes share a rate, or one of them would be unreachable')
check(const(CONST, 'xprate_modes') == 3, 'there are three modes')

# ============================================================================ 2
print('2. where the rate lives')
xp = block(VARP, 'xp_rate')
check('scope=perm' in xp, "the rate is perm - it is the account's for good")
check('transmit' not in xp,
      '...and NOT transmitted: the window is only ever open while the rate is unset, so the '
      'client has nothing to do with the number')
check('1176=xp_rate' in VARPPACK, '...and registered in pack/varp.pack, or the packer never sees it')
check('%xp_rate' in code(RS2), 'the scripts read it by name')

# ============================================================================ 3
print('3. the multiplier, which is in the engine because there is nowhere else for it')
PLAYER = readat(ENGINE, 'src/engine/entity/Player.ts')
if PLAYER is None:
    check(False, 'the engine repo is not beside content - pass its path as argv[1]')
else:
    check('const multi = allowMulti ? Environment.NODE_XPRATE * this.xpRate() : 1;' in PLAYER,
          "addXp multiplies by the player's own rate as well as the world's")
    check(len(re.findall(r'const multi = allowMulti', PLAYER)) == 1,
          '...in exactly one place, which is the whole point of putting it there')
    rate = PLAYER.split('xpRate(): number {', 1)[1].split('\n    }', 1)[0] if 'xpRate(): number {' in PLAYER else ''
    check(rate != '', 'Player.xpRate() exists')
    check("VarPlayerType.getId('xp_rate')" in rate,
          '...and finds the varp by NAME, so content owns which varp it is')
    check('Player.xpRateVarp === -2' in rate and 'private static xpRateVarp: number = -2;' in PLAYER,
          '...looked up lazily behind a -2 sentinel, because the configs are not loaded when the '
          'class is')
    check('if (Player.xpRateVarp < 0) {\n            return 1;' in rate,
          '...and a MISSING varp reads as 1x, not as zero experience for everybody')
    check('if (!rate || rate < 1) {\n            return 1;' in rate,
          '...and so does 0, which is every character that existed before this - they are untouched')
    check('Math.min(rate, 100)' in rate,
          '...with an upper rail, because a perm varp written wrong would otherwise be unbounded')
    # the one caller that must NOT be multiplied
    CHEAT = readat(ENGINE, 'src/network/game/client/handler/ClientCheatHandler.ts')
    check(CHEAT is not None and 'player.addXp(stat, getExpByLevel(parseInt(args[1])), false);' in CHEAT,
          'setting a level still passes allowMulti=false, so ::setlevel 50 is level 50 and not 500')
    check('allowMulti: boolean = true' in PLAYER,
          '...and everything else gets the multiplier by default')

# AND NOTHING IN THE CONTENT DOES IT A SECOND TIME. The strong version of this: %xp_rate appears
# in exactly one place in the whole content tree - the file that owns it - so no skill can be
# quietly multiplying on top of the engine. Two earlier drafts of this check were wrong: one
# flagged every multiply() inside a stat_advance (arrows.rs2 multiplies a COUNT by an xp value),
# and one flagged this file's own proc.
users = []
for dp, dn, fn in os.walk(os.path.join(C, 'scripts')):
    for f in fn:
        if not f.endswith(('.rs2', '.constant', '.varp')):
            continue
        full = os.path.join(dp, f)
        rel = full[len(C) + 1:].replace(os.sep, '/')
        if rel.startswith('scripts/gamemodes/'):
            continue
        if '%xp_rate' in code(open(full, newline='', errors='replace').read()):
            users.append(rel)
check(not users,
      'and %%xp_rate is read nowhere else in the content tree, so no skill multiplies on top of '
      'the engine: %s' % (users or 'only scripts/gamemodes/'))

# ============================================================================ 4
print('4. the lock, which is the only thing keeping this a choice')
ch = code(block(RS2, 'proc,xprate_choose'))
check('if (%xp_rate ! ^xprate_unset) {' in ch and 'return;' in ch,
      'a rate already chosen is not asked for again')
check('if (%tutorial >= ^tutorial_complete) {' in ch,
      '...and a finished tutorial is never asked at all, so a maxed account cannot walk back to '
      'the island and pick 10x')
check(const(QUESTC, 'tutorial_complete') is not None,
      '...against the tutorial\'s own constant (%s)' % const(QUESTC, 'tutorial_complete'))
check(0 <= ch.find('%tutorial >= ^tutorial_complete') < ch.find('if_openmain'),
      '...and BOTH of those come before the window opens, or the lock is decoration')
check('if_openmain(xprate_choose);' in ch, 'the chooser opens as a main modal')
for i in range(3):
    check('if_addresumebutton(xprate_choose:pick%d);' % i in ch,
          '...and box %d is a resume button, or clicking it does nothing' % i)
check('p_pausebutton;' in ch and 'switch_component (last_com)' in ch,
      '...and p_pausebutton waits for the click inside the npc script')
picks = re.findall(r'case xprate_choose:pick(\d) : ~xprate_set\(\^xprate_(\w+)\);', ch)
check([p[0] for p in picks] == ['0', '1', '2'],
      'all three boxes are handled: %s' % [p[0] for p in picks])
check(sorted(const(CONST, 'xprate_' + p[1]) for p in picks) == [1, 5, 10],
      '...and between them they set the three rates: %s'
      % sorted(const(CONST, 'xprate_' + p[1]) for p in picks))
st = code(block(RS2, 'proc,xprate_set'))
check('%xp_rate = $rate;' in st, 'choosing writes the rate')
check('cannot be changed later' in block(RS2, 'proc,xprate_set'),
      '...and says so, because a permanent choice made silently is a complaint later')

# ============================================================================ 5
print('5. asked before any experience can be earned')
g = code(GUIDE)
check('~xprate_choose;' in g, 'the RuneScape Guide asks')
check(0 <= g.find('~xprate_choose;') < g.find('switch_int(%tutorial)'),
      '...before the switch on %tutorial, so the welcome, the come-back label AND the '
      'skip-the-tutorial branch are all covered by one call')
check(g.count('~xprate_choose;') == 1,
      '...once, not once per branch')
check('newbie_basics_instructor' in GUIDE,
      'and he is the basics instructor, who stands in the first room')
check('stat_advance' not in code(GUIDE),
      '...and his own script awards no experience, so the asking happens before any is earned')
TUTC = read('scripts/tutorial/configs/tutorial.constant')
_last_basics = const(TUTC, 'newbie_basics_instructor_interacted_with_door')
_first_skill = const(TUTC, 'newbie_survival_instructor_cut_tree')
check(_last_basics is not None and _first_skill is not None and _last_basics < _first_skill,
      '...and every step of his comes before the first skilling step, by the tutorial\'s own '
      'progress numbers (%s < %s)' % (_last_basics, _first_skill))

# ============================================================================ 6
print('6. the window')
boxes = [n for n in IFC if re.fullmatch(r'pick\d', n)]
check(len(boxes) == 3, 'three boxes (%d)' % len(boxes))
for n in sorted(boxes):
    b = IFC[n]
    check(b.get('type') == 'rect' and b.get('buttontype') == 'normal',
          '%s is a normal button, not a select one' % n)
    check(b.get('option', '').startswith('Choose'), '...with a Choose option')
    check(b.get('overcolour'), '...and a hover colour, which a rect honours')
# THE TRAP THIS AVOIDS: a buttontype=select rect over the whole box takes the click and shows its
# own option, so it would swallow the one p_pausebutton is waiting for and suspend the script
# forever. The first draft did exactly that.
check('buttontype=select' not in IF,
      'nothing in the window is a select button - one covering a box would swallow the click '
      'p_pausebutton waits for')
check('pushvar,xp_rate' not in IF,
      '...and nothing highlights a chosen mode, because the window never opens with one chosen')
check(IFC.get('close', {}).get('buttontype') == 'close',
      'there IS a close button: closing leaves the rate at 0, which reads as 1x, and the guide '
      'asks again - a mandatory window with no way out can strand a player')
names = ['xprate_choose'] + ['xprate_choose:%s' % n for n in re.findall(r'(?m)^\[(\w+)\]$', IF)]
packed = dict(l.split('=', 1)[::-1] for l in IPACK.split('\n') if l)
missing = [n for n in names if n not in packed]
check(not missing, 'every component is in pack/interface.pack (%s)' % (missing[:3] or 'all %d' % len(names)))
order = {l.strip() for l in IORDER.split('\n') if l.strip()}
check(all(packed[n] in order for n in names if n in packed),
      '...and in pack/interface.order - an id in one and not the other packs type -1 and the '
      'client throws on load')
for i, label in enumerate(('Realism', '5x', '10x')):
    check(IFC.get('name%d' % i, {}).get('text') == label,
          'box %d is labelled %s' % (i, label))
check('rate0' in IFC and 'rate1' not in IFC and 'rate2' not in IFC,
      'only the Realism box carries a separate rate line - on the others the name already IS the '
      'multiplier, and a box saying "5x" over "5x" says one thing twice')
check(IFC.get('rate0', {}).get('text') == '%dx' % RATES['realism'],
      "...and it reads the constant's value (%s)" % IFC.get('rate0', {}).get('text'))
check('two modes share a rate' in GEN and 'never chosen' in GEN,
      'the generator refuses to emit two modes at one rate, or a mode at the unset value')

# ============================================================================ 7
print('7. the test hook')
dbg = code(block(RS2, 'debugproc,xprate'))
check('queue(xprate_debug_set, 0, $rate);' in dbg,
      'the debugproc QUEUES its write: ClientCheatHandler runs a debugproc with '
      'executeScript(script, false), so it has no protected access - the same rule that crashed '
      'the Barrows chest out of its [if_close]')
check('%xp_rate' not in dbg,
      '...and does not write the varp inline, which is a build error rather than a surprise')
q = code(block(RS2, 'queue,xprate_debug_set'))
check('%xp_rate = $rate;' in q, '...and the queue is what writes it')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
