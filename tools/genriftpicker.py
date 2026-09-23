#!/usr/bin/env python3
"""Generate the rift guardian's colour picker, and register it in the interface packs.

WHY A WINDOW. Old School's Metamorphosis on the rift guardian opens an interface of the colours you
have unlocked; this fork shipped it CYCLING one colour per right-click, which with fifteen colours
is up to fourteen clicks to get back to the one you wanted. The window is both what Old School does
and the only way fifteen colours are legible.

WHY A GENERATOR. Fifteen cells of four components each, plus the panel, plus pack/interface.pack and
pack/interface.order having to agree exactly - the same shape as tools/genprobita.py, and it follows
the same rules (see that file's header, and genmenus.repack's, for why).

WHAT IT READS RATHER THAN REPEATS. The cells come out of the tree itself: the ring order from
npc/configs/pet_forms.npc, the model of each form from its own record, and the altar each colour
belongs to from npc/configs/pet_variants.enum. So a colour added, moved or repainted cannot leave
the window behind - and tools/follower_battery.py checks the window against those same two files.

  python3 genriftpicker.py
  python3 ifrender.py ../scripts/npc/interfaces/rift_metamorph.if /tmp/rift.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFACE = 'rift_metamorph'
IF = os.path.join(ROOT, 'scripts/npc/interfaces/%s.if' % IFACE)
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
FORMS = os.path.join(ROOT, 'scripts/npc/configs/pet_forms.npc')
SKILLPETS = os.path.join(ROOT, 'scripts/npc/configs/skill_pets.npc')
VARENUM = os.path.join(ROOT, 'scripts/npc/configs/pet_variants.enum')

BASE = 'skillpet_rift_guardian'
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 300
TILE_W, TILE_H = 88, 60
# Only the colours an altar in THIS build can unlock get a cell. The ring is still fifteen long -
# two of its colours belong to the soul and wrath altars, which are not here - and a cell for a
# colour nothing can ever unlock is a dead square. Thirteen cells: the plain guardian and the twelve
# altars, the Astral altar on Lunar Isle (2026-09-23) the twelfth - which is why the grid is five
# across and 92 wide rather than the four by 116 that held twelve: a fourth row would run off the
# panel, and five 92s sit inside its 488 with the widest label ("Cosmic") to spare.
COLS, ROWS = 5, 3
CELL_W, CELL_H = 92, 78
GRID_X = PANEL_X + (PANEL_W - COLS * CELL_W) // 2
GRID_Y = 56
# The model box inside a cell, and the camera for it. 32204 is a small mesh and these are the
# numbers that framed it when the window was rendered - see the module docstring.
MODEL_W, MODEL_H, ZOOM, XAN, YAN = 44, 50, 1900, 160, 40
# The guardian does NOT fill that box. Rendered with tools/ifrender.py at this camera it comes out
# 26 wide and 28 tall at offset (9, 0) inside the 44x50 box: a model component puts the mesh's own
# origin at the box's centre, and this mesh hangs above and left of its origin. So centring the
# BOX is not centring the guardian - it left it high in its cell, which is what this corrects. The
# layout below positions the DRAWN rectangle and then backs the box out of it by that offset.
# Re-measure all four numbers if the camera, the cell or the mesh changes.
DRAWN_W, DRAWN_H, DRAWN_OX, DRAWN_OY = 26, 28, 9, 0
# The label is centred on its INK, not on its 13-tall component: p11_full puts the cap height in
# the top 9 rows and none of the twelve labels has a descender, so balancing the box would sit the
# whole cell two rows high. NAME_INK is that measured ink.
NAME_H, NAME_INK, NAME_GAP = 13, 9, 8
DRAWN_X = (CELL_W - DRAWN_W) // 2
DRAWN_Y = (CELL_H - (DRAWN_H + NAME_GAP + NAME_INK)) // 2
NAME_Y = DRAWN_Y + DRAWN_H + NAME_GAP


def read(p):
    return open(p, newline='').read().replace('\r\n', '\n')


def records():
    """Every pet record in the tree, as {name: body-without-comments}."""
    out = {}
    for src in (read(FORMS), read(SKILLPETS)):
        for b in re.split(r'(?m)^(?=\[)', src):
            m = re.match(r'\[(\w+)\]', b)
            if m:
                out[m.group(1)] = '\n'.join(l.split('//')[0] for l in b.split('\n'))
    return out


def ring(recs):
    """The guardian's ring, in its own order, starting at the base."""
    def nxt(n):
        m = re.search(r'param=metamorph_next,(\w+)', recs[n])
        return m.group(1) if m else None
    out, at = [BASE], nxt(BASE)
    while at and at != BASE:
        out.append(at)
        at = nxt(at)
    return out


def altars():
    """rune -> form, out of the enum the game itself reads."""
    b = re.search(r'(?m)^\[rift_rune_form\]\n(.*?)(?=^\[|\Z)', read(VARENUM), re.S)
    return dict(re.findall(r'(?m)^val=(\w+),(\w+)$', b.group(1)))


def main():
    recs = records()
    order = ring(recs)
    by_form = {f: r for r, f in altars().items()}
    out = []

    def com(name, **kv):
        out.append('[%s]' % name)
        for k, v in kv.items():
            out.append('%s=%s' % (k.rstrip('_'), v))
        out.append('')

    n = 0
    for y in range(PANEL_Y, PANEL_Y + PANEL_H, TILE_H):
        for x in range(PANEL_X, PANEL_X + PANEL_W, TILE_W):
            com('frame%d' % n, type='graphic', x=x, y=y,
                width=min(TILE_W, PANEL_X + PANEL_W - x), height=TILE_H,
                graphic='tradebacking,0')
            n += 1
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
        shadowed='yes', text='Rift guardian', colour='0xFFFF00')
    com('close', type='text', x=424, y=28, buttontype='close', width=68, height=11,
        font='p11_full', shadowed='yes', text='Close Window', colour='0xC00000',
        overcolour='0xFFFFFF')
    # A cell is named for its RING INDEX, not for where it sits: the script's handlers pass an
    # index into the ring, and skipping three colours must not renumber the other twelve.
    cells = [(i, f) for i, f in enumerate(order) if i == 0 or f in by_form]
    for pos, (i, form) in enumerate(cells):
        cx = GRID_X + (pos % COLS) * CELL_W
        cy = GRID_Y + (pos // COLS) * CELL_H
        model = re.search(r'model1=(\S+)', recs[form]).group(1)
        com('cell%d' % i, type='layer', x=cx, y=cy, width=CELL_W, height=CELL_H, scroll=0)
        # The hit box carries the option, so the whole cell is clickable rather than the icon only.
        com('hit%d' % i, layer='cell%d' % i, type='rect', x=0, y=0, width=CELL_W, height=CELL_H,
            buttontype='normal', fill='no', colour='0x6F6250', overcolour='0xFFFFFF',
            option='Choose')
        # ...and the icon gets a LAYER of its own, because if_sethide only works on layers and a
        # colour you have not unlocked has to be able to hide its guardian.
        com('icon%d' % i, layer='cell%d' % i, type='layer',
            x=DRAWN_X - DRAWN_OX, y=DRAWN_Y - DRAWN_OY,
            width=MODEL_W, height=MODEL_H, scroll=0)
        com('model%d' % i, layer='icon%d' % i, type='model', x=0, y=0, width=MODEL_W,
            height=MODEL_H, model=model, zoom=ZOOM, xan=XAN, yan=YAN)
        # The name is STATIC: which altar paints a colour never changes at runtime, so the script
        # has no name table to keep in step and the locked state is shown by hiding the guardian
        # rather than by rewriting text. A cell with a name and no guardian in it reads as "not
        # yours yet", and the line under the grid says how to change that. NOTHING in this window
        # is set by the script except those hides: a count of what you have unlocked is the grid
        # itself, so the window has no text the script has to keep current.
        rune = by_form.get(form)
        label = 'Plain' if i == 0 else rune[:-4].capitalize()
        com('name%d' % i, layer='cell%d' % i, type='text', x=0, y=NAME_Y, width=CELL_W,
            height=13, center='yes', font='p11_full', shadowed='yes', text=label,
            colour='0xFF981F')

    com('hint', type='text', x=12, y=GRID_Y + ROWS * CELL_H + 4, width=488, height=26,
        center='yes', font='p11_full', shadowed='yes',
        text='Craft at an altar with your guardian out to unlock its colour.', colour='0xFF981F')

    body = '\n'.join(out)
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genriftpicker.py - do not hand edit.\n'
        '// Scripts: npc/scripts/pet_variants.rs2. Cells are the guardian\'s own ring order.\n'
        + body)
    names = re.findall(r'^\[([A-Za-z0-9_]+)\]$', body, re.M)

    pack = [l for l in read(PACK).split('\n') if l]
    order_raw = open(ORDER, encoding='utf-8', newline='').read()
    order_crlf = '\r\n' in order_raw
    ids_order = [l for l in order_raw.replace('\r\n', '\n').split('\n') if l.strip()]

    existing, keep, dropped = {}, [], set()
    for l in pack:
        i, nm = l.split('=', 1)
        if nm == IFACE or nm.startswith(IFACE + ':'):
            existing[nm] = i
            dropped.add(i)
            continue
        keep.append(l)
    ids_order = [l for l in ids_order if l not in dropped]
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
        ids_order.append(i)
        return int(i)

    mine = [take(IFACE)] + [take('%s:%s' % (IFACE, n)) for n in names]
    keep.sort(key=lambda l: int(l.split('=', 1)[0]))
    ids_order.sort(key=int)
    ids = [l.split('=', 1)[0] for l in keep]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    nm = [l.split('=', 1)[1] for l in keep]
    assert len(nm) == len(set(nm)), 'duplicate interface name'
    assert set(ids_order) == set(ids), 'interface.order and interface.pack disagree'
    open(PACK, 'w', encoding='utf-8', newline='').write('\n'.join(keep) + '\n')
    open(ORDER, 'w', encoding='utf-8', newline='').write(
        ('\r\n' if order_crlf else '\n').join(ids_order) + ('\r\n' if order_crlf else '\n'))
    print('%s: %d cells of %d ring colours, %d components, ids %d..%d'
          % (IFACE, len(cells), len(order), len(names), min(mine), max(mine)))
    print('cells: ' + ', '.join('ring %d = %s' % (i, by_form.get(f, 'plain')) for i, f in cells))
    print('no cell: ' + ', '.join('ring %d (%s)' % (i, f) for i, f in enumerate(order)
                                  if i and f not in by_form))

main()
