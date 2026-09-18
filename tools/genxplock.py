#!/usr/bin/env python3
"""Generate the per-skill XP lock: the stats tab's second right-click option, the hover panel's
LOCKED marker, and the script behind both.

WHY GENERATED. Twenty-two skills times four places each - a button in stats.if, a marker in that
skill's hover layer, an [if_button] block, and a bit constant - is eighty-eight entries that all
have to name the same skill. One pass over stats.if writes every one.

WHERE THE SKILL LIST COMES FROM. Not a list in this file: stats.if itself. Each skill box is a
buttontype=normal text with an `overlayer`, and that layer's second-row number carries
`script1op1=stat_xp_remaining,<skill>` - the client script that reads that skill's experience. So
the skill symbol is read out of the interface that will show it, and a box this generator cannot
identify is an error rather than a skipped skill. The four combat boxes all SAY "Combat" in their
guide option, so the option text is no use for this and the client script is.

THE NEW BUTTON GOES BEFORE THE GUIDE BUTTON, and that is not cosmetic. Client.java's comment at
the top of the menu-swap code says it plainly: the left-click action is menuOption[menuSize - 1],
the LAST option appended, which drawMenu renders as the top row. Components are walked in child
order, so a lock button emitted AFTER the guide button would become the left-click action and
locking a skill would be one stray click away. Emitted first, it sits below the guide entry in the
menu and left-click still opens the guide.

THE MARKER IS THE HOVER PANEL'S SECOND LABEL, not a new component. Three versions were measured
and thrown away first. A new text to the right of the panel does not fit: the rect is 174 wide,
the second row's number starts at x=84 and a six-figure xp-to-next-level is 63px, leaving 31px for
a word that needs 37. Blanking the NUMBER while locked would free the room, but restoring it needs
`%1` inside an rs2 string literal - the client substitutes it at draw time from the component's own
script - and `%` is the varp sigil in rs2 with no precedent anywhere in this repo. Growing the
panel means moving all 22 layers up and making them taller for everyone, locked or not.

So the label is what changes: "Next Level At:" becomes "@red@XP locked". 53px against the 79px it
replaces, so it crowds the number LESS than what was there. The restore string is read out of the
.if rather than written here, so it cannot drift from what the interface actually says.

    python3 tools/genxplock.py
    python3 tools/ifrender.py scripts/interfaces/stats.if /tmp/stats.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS = os.path.join(ROOT, 'scripts/interfaces/stats.if')
RS2 = os.path.join(ROOT, 'scripts/gamemodes/scripts/xplock.rs2')
CONST = os.path.join(ROOT, 'scripts/gamemodes/configs/gamemode.constant')
VARP = os.path.join(ROOT, 'scripts/gamemodes/configs/gamemode.varp')
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
IFACE = 'stats'
PREFIX = 'xplock_'

# The bit each skill's lock lives at in %xp_locked, which is ITS OWN INDEX IN THE ENGINE'S STAT
# ORDER - PlayerStat.ts, and the identical list in tools/pack/config/ParamConfig.ts that the packer
# resolves a `stat` symbol through. The engine tests bit `stat` directly and needs no table; this
# list is the content side's copy of the same order, and gamemode_battery.py group "xplock bits"
# reads the engine's own file and fails if the two ever disagree. NEVER REORDER.
STAT_ORDER = [
    'attack', 'defence', 'strength', 'hitpoints', 'ranged', 'prayer', 'magic', 'cooking',
    'woodcutting', 'fletching', 'fishing', 'firemaking', 'crafting', 'smithing', 'mining',
    'herblore', 'agility', 'thieving', 'slayer', 'farming', 'runecraft', 'construction',
]

MARKER_TEXT = '@red@XP locked'


def read(p):
    return open(p, newline='').read()


def nl_of(text):
    return '\r\n' if text.count('\r\n') > text.count('\n') / 2 else '\n'


def parse(text):
    """-> [(name, {k: v}, raw_block)], in file order. Blocks are separated by a [name] line."""
    lines = text.replace('\r\n', '\n').split('\n')
    out, cur, kv, buf = [], None, None, []
    for ln in lines:
        m = re.match(r'^\[([A-Za-z0-9_]+)\]\s*$', ln)
        if m:
            if cur is not None:
                out.append((cur, kv, buf))
            cur, kv, buf = m.group(1), {}, [ln]
            continue
        if cur is None:
            out.append((None, {}, [ln]))       # the type=overlay header, comments, blank lines
            continue
        buf.append(ln)
        if '=' in ln:
            k, v = ln.split('=', 1)
            kv.setdefault(k.strip(), v.strip())
    if cur is not None:
        out.append((cur, kv, buf))
    return out


def skills(blocks):
    """Every skill box in stats.if, with the pieces this round needs, in file order."""
    by = {n: kv for n, kv, _ in blocks if n}
    kids = {}
    for n, kv, _ in blocks:
        if n and 'layer' in kv:
            kids.setdefault(kv['layer'], []).append(n)
    out = []
    for n, kv, _ in blocks:
        # skip OUR OWN buttons: they carry buttontype=normal and an overlayer too, so a second run
        # would find 44 skill boxes and refuse. Caught by gamemode_battery group 12 on day one.
        if not n or n.startswith(PREFIX) or kv.get('buttontype') != 'normal' or 'overlayer' not in kv:
            continue
        ov = kv['overlayer']
        rem = [k for k in kids.get(ov, [])
               if by[k].get('script1op1', '').startswith('stat_xp_remaining,')]
        if len(rem) != 1:
            raise SystemExit('%s: overlayer %s has %d stat_xp_remaining children, expected 1'
                             % (n, ov, len(rem)))
        skill = by[rem[0]]['script1op1'].split(',', 1)[1]
        if skill not in STAT_ORDER:
            raise SystemExit('%s reads stat_xp_remaining,%s which is not a stat this engine has'
                             % (n, skill))
        row = by[rem[0]]['y']
        lab = [k for k in kids.get(ov, [])
               if by[k].get('type') == 'text' and by[k].get('y') == row
               and 'script1op1' not in by[k] and by[k].get('text')]
        if len(lab) != 1:
            raise SystemExit('%s: overlayer %s has %d plain labels on row y=%s, expected 1'
                             % (n, ov, len(lab), row))
        out.append(dict(button=n, skill=skill, overlayer=ov, number=rem[0],
                        label=lab[0], label_text=by[lab[0]]['text'],
                        x=kv['x'], y=kv['y'], width=kv['width'], height=kv['height']))
    return out


def com(name, **kv):
    out = ['[%s]' % name]
    for k, v in kv.items():
        out.append('%s=%s' % (k.rstrip('_'), v))
    out.append('')
    return out


def title(skill):
    return 'Runecrafting' if skill == 'runecraft' else skill.capitalize()


def rewrite_stats(blocks, sk):
    """Drop any xplock_* components, then put a button before the FIRST skill box and a marker
    at the end of each hover layer."""
    kept = [(n, kv, buf) for n, kv, buf in blocks if not (n or '').startswith(PREFIX)]
    first = next(i for i, (n, _, _) in enumerate(kept) if n == sk[0]['button'])
    buttons = []
    for s in sk:
        buttons += com(PREFIX + s['skill'], type='text', x=s['x'], y=s['y'],
                       buttontype='normal', width=s['width'], height=s['height'],
                       overlayer=s['overlayer'],
                       option='Toggle @or1@%s @whi@XP-lock' % title(s['skill']))
    out = []
    for i, (n, kv, buf) in enumerate(kept):
        if i == first:
            out += buttons
        out += buf
    return out


def repack(names):
    """Give every new stats:<name> an id, reusing the one it already had. Same shape as
    tools/genxpratechooser.py's, except this interface is not ours to own - only our components
    are dropped and re-taken."""
    pack = [l for l in read(PACK).replace('\r\n', '\n').split('\n') if l]
    order_raw = read(ORDER)
    order_nl = nl_of(order_raw)
    ids_order = [l for l in order_raw.replace('\r\n', '\n').split('\n') if l.strip()]
    existing, keep, dropped = {}, [], set()
    for l in pack:
        i, nm = l.split('=', 1)
        if nm.startswith('%s:%s' % (IFACE, PREFIX)):
            existing[nm] = i
            dropped.add(i)
            continue
        keep.append(l)
    ids_order = [l for l in ids_order if l not in dropped]
    used = {int(l.split('=', 1)[0]) for l in keep}
    nxt = max(used) + 1
    mine = []
    for n in names:
        nm = '%s:%s' % (IFACE, n)
        i = existing.get(nm)
        if i is None or int(i) in used:
            while nxt in used:
                nxt += 1
            i = str(nxt); nxt += 1
        used.add(int(i))
        keep.append('%s=%s' % (i, nm))
        ids_order.append(i)
        mine.append(int(i))
    keep.sort(key=lambda l: int(l.split('=', 1)[0]))
    ids_order.sort(key=int)
    ids = [l.split('=', 1)[0] for l in keep]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    nms = [l.split('=', 1)[1] for l in keep]
    assert len(nms) == len(set(nms)), 'duplicate interface name'
    assert set(ids_order) == set(ids), 'interface.order and interface.pack disagree'
    open(PACK, 'w', encoding='utf-8', newline='').write('\n'.join(keep) + '\n')
    open(ORDER, 'w', encoding='utf-8', newline='').write(order_nl.join(ids_order) + order_nl)
    return mine


RS2_HEAD = '''// The per-skill XP lock.
//
// GENERATED by tools/genxplock.py from scripts/interfaces/stats.if - which is where the skill
// list lives. Edit the generator.
//
// WHAT LOCKING DOES. Nothing here. %xp_locked is a bitmask the ENGINE reads in Player.addXp,
// which returns before the experience is added - so a locked skill refuses every source at once,
// including the 163 stat_advance calls inside quests, without one of them knowing this exists.
// The action still happens: you still get the log, the ore and the quest's items, and the quest
// still completes. Only the experience is refused, and the engine says so at most once a minute
// per skill so that a locked skill being trained is not a wall of text.
//
// WHAT IT DELIBERATELY DOES NOT DO. It does not waive a requirement. A quest that wants 50
// Attack still wants 50 Attack with Attack locked, because every requirement reads stat(...) and
// a lock never touches a level - which is the whole point of Corey's constraint: locking a skill
// must not be a way to be handed the dragon mace or the better gloves.
//
// WHAT AN [if_button] IS NOT HANDED. p_active_player. It gets active_player and nothing more, so
// every one of these bodies opens with p_finduid - see claude/rs2-player-pointer-contexts.md, which
// says so in a table this round did not read until the build refused twenty-two scripts.
//
// WHAT THE HOVER PANEL SHOWS. A locked skill's second row says "XP locked" where it said
// "Next Level At:". That is the whole display: blank is the cache state, so an account with
// nothing locked pushes nothing at login, and the restore string is the interface's own.
//
// WHY THE BUTTONS ARE WHERE THEY ARE. See tools/genxplock.py: a lock button emitted after the
// guide button would become the box's LEFT-CLICK action, because the last option appended is the
// one drawMenu puts on top and the client fires on a left click.
'''


def emit_rs2(sk):
    o = RS2_HEAD.split('\n')
    o += ['[proc,xplock_is](int $bit)(boolean)',
          'if (testbit(%xp_locked, $bit) = ^true) {',
          '    return(true);',
          '}',
          'return(false);',
          '',
          '// Called from [login,_]. The client loads the stats tab\'s text from the cache every',
          '// login, so a locked skill has to be re-marked - but the cache already says the right',
          '// thing for an unlocked one, so an account with nothing locked sends no packets at all.',
          '[proc,xplock_restore]',
          'if (%xp_locked = 0) {',
          '    return;',
          '}']
    for s in sk:
        o += ['if (~xplock_is(^xplock_%s) = true) {' % s['skill'],
              '    if_settext(stats:%s, "%s");' % (s['label'], MARKER_TEXT),
              '}']
    o.append('')
    for s in sk:
        name = title(s['skill'])
        mark = 'stats:%s' % s['label']
        o += ['[if_button,stats:%s%s]' % (PREFIX, s['skill']),
              '// p_finduid FIRST. An [if_button] is handed active_player and NOT p_active_player -',
              '// see claude/rs2-player-pointer-contexts.md - so both halves of this body need it:',
              '// ~p_choice2 reaches p_pausebutton, which is a build error without it, and writing a',
              '// protect=yes varp from an unprotected script compiles fine and DROPS THE CONNECTION',
              '// when it runs. Taking the pointer fixes both and keeps the varp protected. Same shape',
              '// as [label,magic_teleport], which the spellbook buttons reach.',
              'if (p_finduid(uid) = true) {',
              '    if (~xplock_is(^xplock_%s) = true) {' % s['skill'],
              '        if (~p_choice2("Unlock %s experience?", 1, "No, keep it locked.", 2) = 1) {' % name,
              '            %%xp_locked = clearbit(%%xp_locked, ^xplock_%s);' % s['skill'],
              '            if_settext(%s, "%s");' % (mark, s['label_text']),
              '            mes("Your %s experience is no longer locked.");' % name,
              '        }',
              '        return;',
              '    }',
              '    if (~p_choice2("Lock %s experience?", 1, "No, leave it.", 2) = 1) {' % name,
              '        %%xp_locked = setbit(%%xp_locked, ^xplock_%s);' % s['skill'],
              '        if_settext(%s, "%s");' % (mark, MARKER_TEXT),
              '        mes("Your %s experience is locked. You will gain no more of it.");' % name,
              '    }',
              '}',
              '']
    return o


def patch_block(path, mark, block):
    """Replace the run of lines from `mark` up to the next blank-line-then-comment header, or
    append it. Same shape as tools/gentablets.py's constant block."""
    raw = read(path)
    nl = nl_of(raw)
    src = raw.replace('\r\n', '\n').split('\n')
    if mark in src:
        i = src.index(mark)
        j = i + 1
        while j < len(src) and not src[j].startswith('// ---- '):
            j += 1
        src[i:j] = block
    else:
        while src and not src[-1].strip():
            src.pop()
        src += ['', ''] + block
    open(path, 'wb').write((nl.join(src).rstrip('\r\n') + nl).encode('utf-8'))


CONST_MARK = '// ---- the XP lock (xplock.rs2) ----'
VARP_BLOCK = '[xp_locked]'


def main():
    raw = read(STATS)
    nl = nl_of(raw)
    blocks = parse(raw)
    sk = skills(blocks)
    if len(sk) != len(STAT_ORDER):
        raise SystemExit('stats.if has %d skill boxes and this engine has %d stats: %s'
                         % (len(sk), len(STAT_ORDER),
                            sorted(set(STAT_ORDER) - {s['skill'] for s in sk})))
    if len({s['skill'] for s in sk}) != len(sk):
        raise SystemExit('two skill boxes read the same stat')

    out = rewrite_stats(blocks, sk)
    open(STATS, 'wb').write(nl.join(out).encode('utf-8'))

    names = [PREFIX + s['skill'] for s in sk]
    ids = repack(names)

    body = emit_rs2(sk)
    os.makedirs(os.path.dirname(RS2), exist_ok=True)
    open(RS2, 'wb').write((nl_of(read(RS2)) if os.path.exists(RS2) else nl)
                          .join(body).rstrip('\r\n').encode('utf-8') + nl.encode('utf-8'))

    const = [CONST_MARK,
             '// GENERATED by tools/genxplock.py.',
             '//',
             '// The bit each skill owns in %xp_locked. It is the skill\'s index in the ENGINE\'s stat',
             '// order (PlayerStat.ts, and the identical list the packer resolves a `stat` symbol',
             '// through), because Player.addXp tests bit `stat` directly and keeps no table of its',
             '// own. gamemode_battery.py reads the engine\'s file and fails if these drift.',
             '^xplock_skills = %d' % len(STAT_ORDER)]
    for s in sk:
        const.append('^xplock_%s = %d' % (s['skill'], STAT_ORDER.index(s['skill'])))
    const.append('')
    patch_block(CONST, CONST_MARK, const)

    if VARP_BLOCK not in read(VARP):
        varp = read(VARP)
        nlv = nl_of(varp)
        add = ['',
               '// Which skills refuse experience, one bit each, at the skill\'s own index in the',
               '// engine\'s stat order - see ^xplock_* in gamemode.constant. Read by Player.addXp,',
               '// which returns before the experience is added.',
               '//',
               '// scope=perm because a lock is the account\'s until the player lifts it. NOT',
               '// transmitted: the client has no use for it, and the stats tab\'s LOCKED markers are',
               '// pushed as text by ~xplock_restore at login rather than driven from a varp.',
               '[xp_locked]',
               'scope=perm']
        open(VARP, 'wb').write((varp.rstrip('\r\n') + nlv + nlv.join(add) + nlv).encode('utf-8'))

    print('xplock: %d skills, %d components, ids %d..%d' % (len(sk), len(names), min(ids), max(ids)))
    print('  ' + ', '.join('%s=%d' % (s['skill'], STAT_ORDER.index(s['skill'])) for s in sk[:6]) + ', ...')


main()
