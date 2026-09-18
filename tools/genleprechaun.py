#!/usr/bin/env python3
"""Generate the tool leprechaun's storage window, and register it in the interface packs.

WHY A WINDOW. He used to hand tools back through a chatbox menu three items deep, and the store
behind it was three bits per tool - so seven rakes was the ceiling and there was no way to see what
he had without asking him about each one in turn. OSRS shows the store as a grid you can read at a
glance, and a grid is what an inv component already draws for free.

WHY PLACEHOLDERS. Every slot he is holding nothing in still shows a faded icon of the thing that
goes there, because the slot holds that obj with a count of ZERO - the bank's placeholder trick.
The client draws a count-0 slot at alpha 70 with the number suppressed, and it does that for ANY
inv component, not just the bank grid (the placeholder branch in drawInterface is not gated on
clientCode 206). So the window says what he will take before you have given him anything, and a
stacking deposit always lands in its own slot because Inventory.add finds the matching id first.

WHY A GENERATOR. Not the twelve slots - the panel: sixty-odd backing tiles and border pieces, and
pack/interface.pack and pack/interface.order having to agree exactly on every one. The framing and
the repack are tools/genbarrowschest.py's, which took them from tools/genriftpicker.py, where the
rules for both are written down.

    python3 genleprechaun.py
    python3 ifrender.py ../scripts/skill_farming/interfaces/leprechaun_store.if /tmp/lep.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# The interface, NOT the inv - those are two different names on purpose. inv_transmit takes an inv
# and if_openmain takes an interface, and giving both the same debugname leaves the reader (and the
# compiler's overload resolution) to work out which one each call site meant.
IFACE = 'leprechaun_window'
IF = os.path.join(ROOT, 'scripts/skill_farming/interfaces/%s.if' % IFACE)
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
INV = os.path.join(ROOT, 'scripts/skill_farming/configs/leprechaun.inv')
CONST = os.path.join(ROOT, 'scripts/skill_farming/configs/leprechaun.constant')

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 240
TILE_W, TILE_H = 88, 60
# Six across puts all twelve in two rows. ICON is an inventory icon and GAP is what margin means -
# the space BETWEEN icons - so the pitch is the sum of the two.
COLS = 6
ICON = 32
GAP = 40
STEP = ICON + GAP
GRID_Y = 72


def read(p):
    return open(p, newline='').read().replace('\r\n', '\n')


def inv_size():
    """The slot count, followed from leprechaun.inv through to the constant it names, so the window
    and the store cannot disagree about how many squares there are."""
    body = read(INV).split('[leprechaun_store]', 1)[1].split('\n[', 1)[0]
    size = re.search(r'(?m)^size=(.+)$', body).group(1).strip()
    if size.startswith('^'):
        m = re.search(r'(?m)^%s = (\d+)$' % re.escape(size), read(CONST))
        if not m:
            raise SystemExit('leprechaun.inv says size=%s and leprechaun.constant does not define it' % size)
        return int(m.group(1))
    return int(size)


def main():
    slots = inv_size()
    rows = (slots + COLS - 1) // COLS
    grid_w = COLS * STEP - GAP
    grid_x = PANEL_X + (PANEL_W - grid_w) // 2

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
    # the four 25x30 corners sit INSIDE the panel's corners, so the right-hand pair starts 25
    # short of its right edge. Every offset in this block is genbarrowschest.py's, turned back into
    # the relation it always was so that changing PANEL_H does not silently unstitch the frame.
    for i, (x, y) in enumerate(((PANEL_X, PANEL_Y), (PANEL_X + PANEL_W - 25, PANEL_Y),
                                (PANEL_X, PANEL_Y + PANEL_H - 30),
                                (PANEL_X + PANEL_W - 25, PANEL_Y + PANEL_H - 30))):
        com('corner%d' % i, type='graphic', x=x, y=y, width=25, height=30,
            graphic='steelborder,%d' % i)
    for i, x in enumerate(range(PANEL_X + 25, PANEL_X + PANEL_W - 24, 36)):
        com('top%d' % i, type='graphic', x=x, y=PANEL_Y - 15, width=36, height=36,
            graphic='steelborder2,0')
        com('bottom%d' % i, type='graphic', x=x, y=PANEL_Y + PANEL_H - 21, width=36, height=36,
            graphic='miscgraphics,3')
    for i, y in enumerate(range(PANEL_Y + 29, PANEL_Y + PANEL_H - 30, 36)):
        com('left%d' % i, type='graphic', x=PANEL_X - 15, y=y, width=36, height=36,
            graphic='miscgraphics,2')
        com('right%d' % i, type='graphic', x=PANEL_X + PANEL_W - 21, y=y, width=36, height=36,
            graphic='steelborder2,1')

    com('title', type='text', x=PANEL_X, y=PANEL_Y + 10, width=PANEL_W, height=14, center='yes',
        font='b12_full', shadowed='yes', text='Tool Leprechaun', colour='0xFFFF00')
    com('subtitle', type='text', x=PANEL_X, y=PANEL_Y + 28, width=PANEL_W, height=14, center='yes',
        font='p12_full', shadowed='yes',
        text="A hundred of each tool, a thousand of each bucket.", colour='0xFF981F')
    com('close', type='text', x=PANEL_X + 412, y=PANEL_Y + 8, buttontype='close', width=68,
        height=11, font='p11_full', shadowed='yes', text='Close Window', colour='0xC00000',
        overcolour='0xFFFFFF')
    # THE STORE ITSELF. An inv component is transmitted once and the client draws the icons, the
    # stack counts, the faded placeholders and the hover text for nothing; its five options come
    # back as [inv_button1..5] with last_slot already filled in.
    com('store', type='inv', x=grid_x, y=GRID_Y, width=COLS, height=rows,
        interactable='yes', margin='%d,%d' % (GAP, GAP),
        option1='Withdraw-1', option2='Withdraw-5', option3='Withdraw-10',
        option4='Withdraw-all', option5='Withdraw-as-note')
    com('depositall', type='text', x=PANEL_X, y=GRID_Y + rows * STEP - GAP + 14, width=PANEL_W,
        height=14, buttontype='normal', center='yes', font='p12_full', shadowed='yes',
        text='Deposit everything', colour='0xFF981F', overcolour='0xFFFFFF',
        option='Deposit everything')
    com('hint', type='text', x=PANEL_X, y=GRID_Y + rows * STEP - GAP + 36, width=PANEL_W,
        height=26, center='yes', font='p11_full', shadowed='yes',
        text='He keeps these for you anywhere in the world.', colour='0xC8C8C8')

    body = '\n'.join(out)
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genleprechaun.py - do not hand edit.\n'
        '// Scripts: skill_farming/scripts/leprechaun.rs2. The grid IS leprechaun_store.\n'
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
    print('%s: %d slots in %d rows, %d components, ids %d..%d'
          % (IFACE, slots, rows, len(names), min(mine), max(mine)))


main()
