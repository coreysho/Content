#!/usr/bin/env python3
"""Generate Probita's pet-insurance window and register it in the interface packs.

WHY A GENERATOR. The panel is 88 background tiles and border pieces before a single component
of ours, and the .if, pack/interface.pack and pack/interface.order all have to agree exactly.
genmenus.py and genbanktabs.py exist for the same reason and this follows their rules:

  - PackShared walks interface.order and looks every id up in interface.pack, so the two files
    must agree EXACTLY. An id in the order with no pack entry packs a component with type -1 and
    the client throws on load.
  - Rewrite rather than append: the window's own entries are dropped from both files first, so
    running this twice reuses the same ids instead of abandoning a block on every run.
  - interface.pack is LF; interface.order follows the repo's other text files. Mixing them up is
    a whole-file diff.

THE PANEL is the 377 "stone panel in a steel frame" that the rune pouch window uses: tradebacking
tiled over the modal area, steelborder corners, steelborder2 along the top and right, miscgraphics
down the left and along the bottom. Written as loops here rather than copied tile by tile, and
checked by rendering - tools/ifrender.py draws the same file the packer reads.

  python3 genprobita.py            # writes the .if and repacks
  python3 ifrender.py ../scripts/npc/interfaces/probita_main.if /tmp/probita.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFACE = 'probita_main'
IF = os.path.join(ROOT, 'scripts/npc/interfaces/%s.if' % IFACE)
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')

# The modal main area the client gives a window: x 12..500, y 20..320.
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 300
TILE_W, TILE_H = 88, 60

# The grid. Six across, four down, is 24: the twenty pet items in the tree today and four spare,
# and lostpet_store is sized to exactly the same 24 - a store slot the grid cannot show would be a
# pet nobody could reclaim. tools/follower_battery.py holds the two in step, and a 21st pet will
# fail that check until both are widened, which is the point. A 32px icon plus margin 12,10 is a
# 44x42 cell, so the grid is 264x168.
COLS, ROWS = 6, 4
CELL_MX, CELL_MY = 12, 10
GRID_W = COLS * (32 + CELL_MX)
GRID_X = PANEL_X + (PANEL_W - GRID_W) // 2
GRID_Y = 106


def blocks():
    out = []
    def com(name, **kv):
        out.append('[%s]' % name)
        for k, v in kv.items():
            out.append('%s=%s' % (k, v))
        out.append('')

    n = 0
    for y in range(PANEL_Y, PANEL_Y + PANEL_H, TILE_H):
        for x in range(PANEL_X, PANEL_X + PANEL_W, TILE_W):
            w = min(TILE_W, PANEL_X + PANEL_W - x)
            com('frame%d' % n, type='graphic', x=x, y=y, width=w, height=TILE_H,
                graphic='tradebacking,0')
            n += 1
    # the steel frame: four corners, then the straight runs between them
    for i, (x, y) in enumerate(((12, 20), (475, 20), (12, 290), (475, 290))):
        com('corner%d' % i, type='graphic', x=x, y=y, width=25, height=30,
            graphic='steelborder,%d' % i)
    for i, x in enumerate(range(37, 476, 36)):
        com('top%d' % i, type='graphic', x=x, y=5, width=36, height=36, graphic='steelborder2,0')
        com('bottom%d' % i, type='graphic', x=x, y=299, width=36, height=36,
            graphic='miscgraphics,3')
    for i, y in enumerate(range(49, 290, 36)):
        com('left%d' % i, type='graphic', x=-3, y=y, width=36, height=36, graphic='miscgraphics,2')
        com('right%d' % i, type='graphic', x=479, y=y, width=36, height=36,
            graphic='steelborder2,1')

    com('title', type='text', x=12, y=30, width=488, height=14, center='yes', font='b12_full',
        shadowed='yes', text='Pet insurance', colour='0xFFFF00')
    com('close', type='text', x=424, y=28, buttontype='close', width=68, height=11,
        font='p11_full', shadowed='yes', text='Close Window', colour='0xC00000',
        overcolour='0xFFFFFF')
    # Set from the script: how many pets she is holding, or that she is holding none.
    com('subtitle', type='text', x=12, y=52, width=488, height=13, center='yes', font='p12_full',
        shadowed='yes', text='', colour='0xFFFFFF')
    com('help', type='text', x=12, y=80, width=488, height=13, center='yes', font='p12_full',
        shadowed='yes', text='Click a pet to take it back.', colour='0xFFFFFF')
    com('pets', type='inv', x=GRID_X, y=GRID_Y, width=COLS, height=ROWS, interactable='yes',
        margin='%d,%d' % (CELL_MX, CELL_MY), option1='Reclaim')
    com('hint', type='text', x=12, y=GRID_Y + ROWS * (32 + CELL_MY) + 8, width=488, height=26,
        center='yes', font='p11_full', shadowed='yes',
        text='Every pet is insured the moment you get it.\\nReclaiming one costs nothing.',
        colour='0xFF981F')
    return '\n'.join(out)


def main():
    body = blocks()
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genprobita.py - do not hand edit. Scripts: npc/scripts/probita.rs2\n'
        + body)
    names = re.findall(r'^\[([A-Za-z0-9_]+)\]$', body, re.M)

    pack = [l for l in open(PACK, encoding='utf-8', newline='').read()
            .replace('\r\n', '\n').split('\n') if l]
    order_raw = open(ORDER, encoding='utf-8', newline='').read()
    order_crlf = '\r\n' in order_raw
    order = [l for l in order_raw.replace('\r\n', '\n').split('\n') if l.strip()]

    existing, keep, dropped = {}, [], set()
    for l in pack:
        i, nm = l.split('=', 1)
        if nm == IFACE or nm.startswith(IFACE + ':'):
            existing[nm] = i
            dropped.add(i)
            continue
        keep.append(l)
    order = [l for l in order if l not in dropped]

    used = {int(l.split('=', 1)[0]) for l in keep}
    nxt = max(used) + 1
    def take(nm):
        nonlocal nxt
        i = existing.get(nm)
        if i is None or int(i) in used:
            while nxt in used:
                nxt += 1
            i = str(nxt); nxt += 1
        used.add(int(i))
        keep.append('%s=%s' % (i, nm))
        order.append(i)
        return int(i)

    mine = [take(IFACE)] + [take('%s:%s' % (IFACE, n)) for n in names]
    keep.sort(key=lambda l: int(l.split('=', 1)[0]))
    order.sort(key=int)

    ids = [l.split('=', 1)[0] for l in keep]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    nm = [l.split('=', 1)[1] for l in keep]
    assert len(nm) == len(set(nm)), 'duplicate interface name'
    assert set(order) == set(ids), 'interface.order and interface.pack disagree'

    open(PACK, 'w', encoding='utf-8', newline='').write('\n'.join(keep) + '\n')
    open(ORDER, 'w', encoding='utf-8', newline='').write(
        ('\r\n' if order_crlf else '\n').join(order) + ('\r\n' if order_crlf else '\n'))
    print('%s: %d components, ids %d..%d; grid %dx%d at %d,%d'
          % (IFACE, len(names), min(mine), max(mine), COLS, ROWS, GRID_X, GRID_Y))

main()
