#!/usr/bin/env python3
"""Generate the Barrows chest's reward window, and register it in the interface packs.

WHY A WINDOW. The chest used to pay into the chatbox and the inventory, which loses the whole point
of a Barrows run: you cannot see what you got, a full inventory silently sent things to the bank,
and Old School has shown the loot in a window of its own for years. So the roll drops into a perm
inv and this is what shows it.

WHY A GENERATOR. Not for the eight slots - it is the panel: fifty-odd backing tiles and border
pieces, plus pack/interface.pack and pack/interface.order having to agree exactly on every
component. The framing code and the repack are tools/genriftpicker.py's, which is where the rules
for both live (see that file's header).

    python3 genbarrowschest.py
    python3 ifrender.py ../scripts/areas/area_barrows/interfaces/barrows_chest.if /tmp/chest.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFACE = 'barrows_chest'
IF = os.path.join(ROOT, 'scripts/areas/area_barrows/interfaces/%s.if' % IFACE)
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
INV = os.path.join(ROOT, 'scripts/areas/area_barrows/configs/barrows.inv')

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 300
TILE_W, TILE_H = 88, 60
# The grid. Eight slots is the ceiling on one chest: seven rolls at six brothers killed, plus the
# teleport tabs. SIZE is read out of the inv config rather than written here, so the window and the
# store cannot disagree about how many slots there are.
COLS = 4
ICON = 32
GAP = 40                      # extra pixels between icons, which is what margin means
STEP = ICON + GAP
GRID_Y = 100

SHOP = os.path.join(ROOT, 'scripts/shop/interfaces/shop_template.if')


def read(p):
    return open(p, newline='').read().replace('\r\n', '\n')


def shop_frame():
    """Every graphic in the shop window, as (name, {key: value}) in file order."""
    out, cur = [], None
    for line in read(SHOP).split('\n'):
        line = line.strip()
        if line.startswith('[') and line.endswith(']'):
            cur = (line[1:-1], {})
            out.append(cur)
        elif '=' in line and cur is not None:
            k, v = line.split('=', 1)
            cur[1][k] = v
    return [(n, kv) for n, kv in out if kv.get('type') == 'graphic']


def inv_size():
    body = read(INV).split('[barrows_reward_store]', 1)[1].split('\n[', 1)[0]
    return int(re.search(r'(?m)^size=(\d+)$', body).group(1))


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

    # THE SHOP'S FRAME, every graphic of shop_template.if borrowed whole - the backing, the steel
    # border round the viewport and the bar under the title - as tools/gentradingpost.py does. The
    # first version tiled its own backing and border, a few pixels off the shop's, and sat off-centre.
    for nm, kv in shop_frame():
        com('frame_' + nm.replace('com_', ''), **kv)

    com('title', type='text', x=12, y=29, width=488, height=14, center='yes', font='b12_full',
        shadowed='yes', text='Barrows chest', colour='0xFFFF00')
    # Set by the script: how many rolls the chest made and the reward potential they were made at,
    # which is the one thing about a Barrows reward a player cannot work out by looking.
    com('subtitle', type='text', x=12, y=60, width=488, height=14, center='yes', font='p12_full',
        shadowed='yes', text='', colour='0xFF981F')
    com('close', type='text', x=420, y=29, buttontype='close', width=68, height=11,
        font='p11_full', shadowed='yes', text='Close Window', colour='0x808080',
        overcolour='0xFFFFFF')
    # THE STORE ITSELF, not a row of model components: an inv component is transmitted and the
    # client draws the icons, the stack counts and the hover text for nothing, and its options come
    # back as [inv_button1..4] with last_slot already filled in.
    com('loot', type='inv', x=grid_x, y=GRID_Y, width=COLS, height=rows,
        interactable='yes', margin='%d,%d' % (GAP, GAP),
        option1='Take', option2='Take-all', option3='Bank')
    com('takeall', type='text', x=12, y=GRID_Y + rows * STEP + 10, width=488, height=14,
        buttontype='normal', center='yes', font='p12_full', shadowed='yes', text='Take everything',
        colour='0xFF981F', overcolour='0xFFFFFF', option='Take everything')
    com('hint', type='text', x=12, y=GRID_Y + rows * STEP + 34, width=488, height=26,
        center='yes', font='p11_full', shadowed='yes',
        text='Whatever you leave here goes to your bank.', colour='0xC8C8C8')

    body = '\n'.join(out)
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genbarrowschest.py - do not hand edit.\n'
        '// Scripts: areas/area_barrows/scripts/barrows_chest.rs2. The grid IS barrows_reward_store.\n'
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
