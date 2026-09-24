#!/usr/bin/env python3
"""The monster drop table browser: every monster with a drop table, A to Z, one click from its table.

    python3 tools/gennpcbrowser.py            # write the window and its triggers, take pack ids
    python3 tools/gennpcbrowser.py --check    # exit 1 if anything would change

It is opened from the quest tab (Server Statistics, Quick actions). Examining a monster opens the
same drop table window (drop_tables/scripts/npc_drops.rs2); this is the way in for a monster that
is not in front of you.

WHAT IS LISTED is read from tools/gennpcdrops.py's output, configs/npc_drops.dbrow - one row per
distinct table, keyed by every npc that shares it - so the list can never offer a monster the
viewer has no table for. Run this after gennpcdrops.py (which runs it itself).

ONE ROW PER NAME AND COMBAT LEVEL, "Goblin" at level 2 and at level 5 being two rows, as a player
tells them apart. Where two npcs share both but not a table (a quest variant of a Cow, say) the
table most npcs of that name and level use is the one shown.

THE WINDOW is the smithing frame (genmenus.window) with two boxes set into it, as the quest tab
draws its boxes: on the left a button per letter, on the right one scrolling list of every monster
under letter headings. A 377 scroll layer cannot change length at runtime and a component cannot be
hidden unless it is a layer, so the list is not filtered - it is all there, and a letter scrolls to
its heading (if_setscrollpos). Every row is a static component written here, with its own
[if_button] in npc_browser_ui.rs2 naming its npc.

    scripts/drop_tables/interfaces/npc_browser.if
    scripts/drop_tables/scripts/npc_browser_ui.rs2
"""
import os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import genmenus as G
import ifids
import ifrender as R

C = os.path.dirname(HERE)
S = os.path.join(C, 'scripts')
DBROW = os.path.join(S, 'drop_tables', 'configs', 'npc_drops.dbrow')
OUT_IF = os.path.join(S, 'drop_tables', 'interfaces', 'npc_browser.if')
OUT_RS2 = os.path.join(S, 'drop_tables', 'scripts', 'npc_browser_ui.rs2')
IFACE = 'npc_browser'

# ------------------------------------------------------------------------------------ geometry
# The smithing frame spans 12..500 x 20..320; the title bar is at the top, the subtitle under it.
BODY_Y, BODY_H = 66, 240
LET_X, LET_W = 24, 124            # the letters' box
LIST_X, LIST_W = 156, 332         # the list's box
CELL_W, CELL_H, CELL_GAP, CELL_COLS = 26, 23, 3, 4
LETTERS = [chr(c) for c in range(ord('A'), ord('Z') + 1)] + ['#']
# The scroll layer sits 2px inside the list's box; the client draws its scrollbar just outside the
# layer's right edge, 16px wide, so the layer stops 16px short of the box's inner edge.
SCROLL_X, SCROLL_Y = LIST_X + 2, BODY_Y + 2
SCROLL_W, SCROLL_H = LIST_W - 4 - 16, BODY_H - 4
HEAD_H, ROW_H = 22, 15
NAME_X, LEVEL_R = 12, SCROLL_W - 8      # the level's right edge

ORANGE, WHITE, YELLOW, GREY = '0xFF981F', '0xFFFFFF', '0xFFFF00', '0x6F6250'
LEVEL = '0xC8C8C8'
EDGE, RIM, RULE = '0x2E2B23', '0x726451', '0x4A4033'


def read(p):
    with open(p, encoding='utf-8', errors='replace', newline='') as f:
        return f.read().replace('\r\n', '\n')


# ------------------------------------------------------------------------------------ data
def npc_configs():
    out = {}
    for base, dirs, files in os.walk(S):
        dirs.sort()
        for f in sorted(files):
            if not f.endswith('.npc'):
                continue
            cur = None
            for line in read(os.path.join(base, f)).split('\n'):
                line = line.split('//')[0].strip()
                m = re.match(r'^\[(\w+)\]$', line)
                if m:
                    cur = out.setdefault(m.group(1), {})
                elif cur is not None and '=' in line:
                    k, v = line.split('=', 1)
                    cur.setdefault(k, v)
    return out


def tables():
    """[(row, [npc...])] from npc_drops.dbrow, in file order."""
    out, cur = [], None
    for line in read(DBROW).split('\n'):
        m = re.match(r'^\[(\w+)\]$', line)
        if m:
            cur = (m.group(1), [])
            out.append(cur)
        m = re.match(r'^data=npc,(\w+)$', line)
        if m and cur:
            cur[1].append(m.group(1))
    return out


def level_of(cfg):
    v = cfg.get('vislevel', cfg.get('level'))
    if v is None or v == 'hide':
        return None
    try:
        return int(v)
    except ValueError:
        return None


def entries():
    """[(name, level or None, npc)] sorted as the list shows them."""
    npcs = npc_configs()
    by = {}                       # (name, level) -> {row: [npc...]}
    for row, ns in tables():
        for n in ns:
            cfg = npcs.get(n, {})
            name = cfg.get('name')
            if not name or name == 'null':
                continue
            by.setdefault((name, level_of(cfg)), {}).setdefault(row, []).append(n)
    out = []
    for (name, level), rows in by.items():
        # the table most of them use; a tie goes to the first in the file, which is deterministic
        row = max(rows, key=lambda r: len(rows[r]))
        out.append((name, level, sorted(rows[row])[0]))
    # A to Z, then the odd one out ("'Cuffs'") under #, as the letter grid has them
    out.sort(key=lambda e: (letter_of(e[0]) == '#', e[0].lower(), -1 if e[1] is None else e[1], e[2]))
    return out


def letter_of(name):
    c = name[:1].upper()
    return c if 'A' <= c <= 'Z' else '#'


# ------------------------------------------------------------------------------------ components
class Coms:
    def __init__(self):
        self.coms = []

    def add(self, name, **kv):
        self.coms.append((name, kv))

    def box(self, name, x, y, w, h, dark=146):
        """genquesttab.Page.box: a translucent black face in a 1px rim, dark along the top and left
        and brown along the bottom and right, so it reads as set into the stone."""
        self.add(name, type='rect', x=x + 1, y=y + 1, width=w - 2, height=h - 2, fill='yes', colour='0x000000',
                 trans=dark)
        self.add(name + '_rim', type='rect', x=x, y=y, width=w, height=h, colour=RIM)
        self.add(name + '_top', type='rect', x=x, y=y, width=w - 1, height=1, fill='yes', colour=EDGE)
        self.add(name + '_left', type='rect', x=x, y=y, width=1, height=h - 1, fill='yes', colour=EDGE)


def build(ents):
    f = R.font('p12_full')
    c = Coms()
    for nm, kv in G.window('Monster Drop Tables'):
        if nm == 'subtitle':
            kv = dict(kv, text='%d monsters. Pick one to see what it drops, and how often.' % len(ents),
                      colour=ORANGE)
        c.add(nm, **kv)

    # the list first, so the letters know where their headings are
    rows, heads, y = [], {}, 4
    for i, (name, level, npc) in enumerate(ents):
        L = letter_of(name)
        if L not in heads:
            if heads:
                y += 6
            heads[L] = y
            y += HEAD_H
        rows.append((i, name, level, npc, y))
        y += ROW_H
    scroll = max(y + 6, SCROLL_H + 1)

    # the letters
    c.box('letters', LET_X, BODY_Y, LET_W, BODY_H)
    c.add('letters_title', type='text', x=LET_X, y=BODY_Y + 5, width=LET_W, height=15, center='yes',
          font='b12_full', shadowed='yes', text='Jump to', colour=YELLOW)
    grid_w = CELL_COLS * CELL_W + (CELL_COLS - 1) * CELL_GAP
    gx = LET_X + (LET_W - grid_w) // 2
    gy = BODY_Y + 22
    lit = []
    for k, L in enumerate(LETTERS):
        x = gx + (k % CELL_COLS) * (CELL_W + CELL_GAP)
        y0 = gy + (k // CELL_COLS) * (CELL_H + CELL_GAP)
        n = 'letter_%s' % ('num' if L == '#' else L.lower())
        c.box(n + '_box', x, y0, CELL_W, CELL_H, dark=110)
        if L in heads:
            c.add(n, type='rect', x=x, y=y0, buttontype='normal', overlayer=n + '_hover', width=CELL_W,
                  height=CELL_H, fill='yes', colour='0x000000', trans=255, option='Jump to @lre@%s' % L)
            c.add(n + '_label', type='text', x=x, y=y0 + 6, width=CELL_W, height=15, center='yes',
                  font='b12_full', shadowed='yes', text=L, colour=ORANGE)
            lit.append((n, x, y0, L))
        else:
            c.add(n + '_label', type='text', x=x, y=y0 + 6, width=CELL_W, height=15, center='yes',
                  font='b12_full', shadowed='yes', text=L, colour=GREY)
    # the lit copies, drawn over the grid
    for n, x, y0, L in lit:
        c.add(n + '_hover', type='layer', x=x, y=y0, width=CELL_W, height=CELL_H, hide='yes')
        c.add(n + '_lit', layer=n + '_hover', type='rect', x=1, y=1, width=CELL_W - 2, height=CELL_H - 2,
              fill='yes', colour='0x8C7F63', trans=150)
        c.add(n + '_lit_label', layer=n + '_hover', type='text', x=0, y=6, width=CELL_W, height=15,
              center='yes', font='b12_full', shadowed='yes', text=L, colour=WHITE)
    hint_y = gy + 7 * (CELL_H + CELL_GAP) + 1
    c.add('hint', type='text', x=LET_X + 4, y=hint_y, width=LET_W - 8, height=26, center='yes',
          font='p11_full', shadowed='yes', text=r'Or examine any\nmonster you meet.', colour=LEVEL)

    # the list
    c.box('list_box', LIST_X, BODY_Y, LIST_W, BODY_H)
    c.add('list', type='layer', x=SCROLL_X, y=SCROLL_Y, width=SCROLL_W, height=SCROLL_H, scroll=scroll)
    for L, hy in heads.items():
        n = 'head_%s' % ('num' if L == '#' else L.lower())
        c.add(n, layer='list', type='text', x=8, y=hy + 2, width=SCROLL_W - 16, height=15, font='b12_full',
              shadowed='yes', text=L, colour=YELLOW)
        c.add(n + '_rule', layer='list', type='rect', x=6, y=hy + 18, width=SCROLL_W - 12, height=1, fill='yes',
              colour=RULE)
    for i, name, level, npc, ry in rows:
        c.add('m%d' % i, layer='list', type='text', x=NAME_X, y=ry, buttontype='normal', width=LEVEL_R - NAME_X,
              height=ROW_H, font='p12_full', shadowed='yes', text=name, colour=ORANGE, overcolour=WHITE,
              option='View drops @lre@%s' % name)
        if level is not None:
            s = 'Lvl %d' % level
            w = f.width(s)
            c.add('m%d_lvl' % i, layer='list', type='text', x=LEVEL_R - w, y=ry, width=w, height=ROW_H,
                  font='p12_full', shadowed='yes', text=s, colour=LEVEL)
    return c.coms, rows, heads


ORDER = ['layer', 'type', 'x', 'y', 'buttontype', 'overlayer', 'width', 'height', 'scroll', 'hide', 'center',
         'font', 'shadowed', 'fill', 'graphic', 'text', 'colour', 'overcolour', 'trans', 'option']


def emit(coms):
    out = ['// GENERATED by tools/gennpcbrowser.py - do not hand-edit. The monster drop table browser;',
           '// its triggers are drop_tables/scripts/npc_browser_ui.rs2, its code npc_browser.rs2.', '']
    for name, kv in coms:
        out.append('[%s]' % name)
        for k in ORDER:
            if k in kv:
                out.append('%s=%s' % (k, kv[k]))
        extra = [k for k in kv if k not in ORDER]
        if extra:
            raise SystemExit('gennpcbrowser: unknown interface key %s on %s' % (extra, name))
        out.append('')
    return '\n'.join(out).rstrip('\n') + '\n'


def build_rs2(rows, heads):
    o = ['// GENERATED by tools/gennpcbrowser.py - do not hand-edit. The monster drop table browser\'s',
         '// buttons: a letter scrolls the list to its heading, a monster opens its drop table',
         '// (~npc_browser_view, npc_browser.rs2) and passes where its row is, for the Back button.', '']
    for L, hy in heads.items():
        o.append('[if_button,%s:letter_%s] ~npc_browser_jump(%d);' % (IFACE, 'num' if L == '#' else L.lower(), hy))
    o.append('')
    for i, name, level, npc, ry in rows:
        o.append('[if_button,%s:m%d] ~npc_browser_view(%s, %d);' % (IFACE, i, npc, ry))
    return '\n'.join(o) + '\n'


def main():
    check = '--check' in sys.argv
    ents = entries()
    coms, rows, heads = build(ents)
    want = {OUT_IF: emit(coms), OUT_RS2: build_rs2(rows, heads)}
    bad = []
    for path, body in want.items():
        nl = '\r\n' if os.path.exists(path) and b'\r\n' in open(path, 'rb').read() else '\n'
        body = body.replace('\n', nl)
        have = open(path, encoding='utf-8', newline='').read() if os.path.exists(path) else None
        if have != body:
            bad.append(os.path.relpath(path, C))
            if not check:
                open(path, 'w', encoding='utf-8', newline='').write(body)
    if check:
        packed = set(re.findall(r'^\d+=(\S+?)\r?$', read(ifids.PACK), re.M))
        ids_ok = IFACE in packed and all('%s:%s' % (IFACE, n) in packed for n, _ in coms)
        if bad or not ids_ok:
            print('gennpcbrowser --check: would change %s' % ', '.join(bad + ([] if ids_ok else ['interface.pack'])))
            return 1
        print('gennpcbrowser --check: everything is already what this writes')
        return 0
    for line in ifids.sync([IFACE]):
        print(line)
    print('gennpcbrowser: %d monsters under %d letters, %d components, list %dpx; wrote %d files'
          % (len(ents), len(heads), len(coms), max(r[4] for r in rows) + ROW_H, len(bad)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
