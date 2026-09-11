#!/usr/bin/env python3
"""Generate the two Construction windows: poh_roommenu.if and poh_furnmenu.if,
their interface.pack / interface.order entries, and the rs2 that drives them.

WHY GENERATED. Six rows of four components and eight slots of five, each with its own
x/y, is two hundred lines of arithmetic that has to agree with a second two hundred lines
of if_settext calls. Writing both from one table is the only way they stay in step.

THE THREE THINGS THE 377 CLIENT MAKES YOU DO

1. hide ONLY WORKS ON LAYERS. Client.drawInterface tests hide on the layer it is drawing
   and never on a child, so if_sethide on a text or model component does nothing at all -
   the first build panel hid empty slots that way and they stayed on screen. Every row and
   slot here is therefore its own type=layer, and hiding one hides its whole contents.

2. ZOOM IS INVERSE, AND LOC MODELS HANG UPWARD. See tools/ifmodels.py. The per-item zooms
   in poh_room_model / poh_furn_zoom are solved from each model's own geometry; the model
   components are twice the height of the icon and top-aligned so the box's centre line
   lands on the icon's bottom edge.

3. A WHOLE ROW CAN BE THE BUTTON. handleInterfaceInput hit-tests buttonType 1 without
   caring what the component's type is, so the row's outline rect is the click target and
   covers the whole row, the way OSRS's does. The text and model on top are not buttons.

The window frame is the smithing interface's, component for component - it is a real 377
window, so borrowing it beats inventing one.
"""

import os, re, json, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMITH = os.path.join(ROOT, 'scripts/skill_smithing/interfaces/smithing.if')

# --------------------------------------------------------------------------- frame

def parse_if(path):
    order, coms, cur = [], {}, None
    for raw in open(path, 'rb').read().decode('utf-8').replace('\r\n', '\n').split('\n'):
        line = raw.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('['):
            cur = line[1:line.index(']')]
            coms[cur] = {}
            order.append(cur)
        elif '=' in line and cur:
            k, v = line.split('=', 1)
            coms[cur][k] = v
    return order, coms

def frame():
    """Every background and border graphic of the smithing window, in its own order."""
    order, coms = parse_if(SMITH)
    out = []
    for n in order:
        c = coms[n]
        if c.get('type') != 'graphic':
            continue
        out.append(dict(type='graphic', x=c['x'], y=c['y'], width=c['width'],
                        height=c['height'], graphic=c['graphic']))
    return out

# --------------------------------------------------------------------------- emit

def _crlf(path):
    """.gitattributes says `* text=auto`, so the repo stores LF and a Windows checkout has
    CRLF. New files must match whatever the working copy they are written into uses, or the
    diff is the whole file."""
    raw = open(path, 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2

def emit(coms):
    """coms: list of (name, dict). dict keys are written in a fixed, readable order."""
    KEY = ['layer', 'type', 'x', 'y', 'buttontype', 'width', 'height', 'scroll', 'hide',
           'center', 'font', 'shadowed', 'fill', 'graphic', 'model', 'zoom', 'xan', 'yan',
           'text', 'colour', 'activecolour', 'overcolour', 'option']
    out = []
    for name, c in coms:
        out.append('[%s]' % name)
        for k in KEY:
            if k in c:
                out.append('%s=%s' % (k, c[k]))
        for k in c:
            if k not in KEY:
                raise SystemExit('unknown interface key %r' % k)
        out.append('')
    return '\n'.join(out).rstrip('\n') + '\n'

BTN = dict(center='yes', font='b12_full', shadowed='yes',
           colour='0xFF9040', overcolour='0xFFFFFF')

def window(title):
    """The shared parts: frame, title bar, close button, subtitle."""
    coms = [('frame%d' % i, c) for i, c in enumerate(frame())]
    coms.append(('title', dict(type='text', x=12, y=30, width=488, height=14, center='yes',
                               font='b12_full', shadowed='yes', text=title, colour='0xFFFF00')))
    coms.append(('close', dict(type='text', x=424, y=28, buttontype='close', width=68,
                               height=11, font='p11_full', shadowed='yes', text='Close Window',
                               colour='0xC00000', overcolour='0xFFFFFF')))
    coms.append(('subtitle', dict(type='text', x=12, y=48, width=488, height=13, center='yes',
                                  font='p12_full', shadowed='yes', text='', colour='0xFFFFFF')))
    return coms

# --------------------------------------------------------------------------- the rooms window

ROOM_ROWS = 6
ROOM_Y, ROOM_STEP, ROOM_H = 66, 39, 36
ROOM_X, ROOM_W = 26, 448
ROOM_ICON, ROOM_BELOW = 34, 8

def roommenu():
    coms = window('Room creation menu')
    for i in range(ROOM_ROWS):
        coms.append(('row%d' % i, dict(type='layer', x=ROOM_X, y=ROOM_Y + i * ROOM_STEP,
                                       width=ROOM_W, height=ROOM_H, scroll=0)))
        p = 'r%d' % i
        coms.append((p + 'box', dict(layer='row%d' % i, type='rect', x=0, y=0,
                                     buttontype='normal', width=ROOM_W, height=ROOM_H,
                                     fill='no', colour='0x6F6250', overcolour='0xFFFFFF',
                                     option='Build')))
        coms.append((p + 'model', dict(layer='row%d' % i, type='model', x=10, y=1,
                                       width=ROOM_ICON, height=2 * (ROOM_ICON - ROOM_BELOW),
                                       model='poh_bed1_8', zoom=3000, xan=150, yan=40)))
        coms.append((p + 'name', dict(layer='row%d' % i, type='text', x=56, y=11, width=248,
                                      height=14, font='p12_full', shadowed='yes',
                                      text='', colour='0xFFFFFF')))
        coms.append((p + 'cost', dict(layer='row%d' % i, type='text', x=308, y=11, width=134,
                                      height=14, center='yes', font='p12_full', shadowed='yes',
                                      text='', colour='0xFFFF00')))
    coms += tail('More rooms')
    return coms

# --------------------------------------------------------------------------- the furniture window

FURN_SLOTS = 8
FURN_COLS, FURN_ROWS = 2, 4
FURN_X, FURN_XSTEP, FURN_W = 26, 230, 224
FURN_Y, FURN_YSTEP, FURN_H = 66, 58, 54
FURN_ICON, FURN_BELOW = 38, 9

def furnmenu():
    coms = window('Furniture creation menu')
    for i in range(FURN_SLOTS):
        col, row = i % FURN_COLS, i // FURN_COLS
        coms.append(('slot%d' % i, dict(type='layer', x=FURN_X + col * FURN_XSTEP,
                                        y=FURN_Y + row * FURN_YSTEP,
                                        width=FURN_W, height=FURN_H, scroll=0)))
        p = 's%d' % i
        L = 'slot%d' % i
        coms.append((p + 'box', dict(layer=L, type='rect', x=0, y=0, buttontype='normal',
                                     width=FURN_W, height=FURN_H, fill='no',
                                     colour='0x6F6250', overcolour='0xFFFFFF', option='Build')))
        coms.append((p + 'lvl', dict(layer=L, type='text', x=0, y=20, width=54, height=14,
                                     center='yes', font='p12_full', shadowed='yes',
                                     text='', colour='0xFFFFFF')))
        coms.append((p + 'model', dict(layer=L, type='model', x=56, y=5, width=FURN_ICON,
                                       height=2 * (FURN_ICON - FURN_BELOW),
                                       model='poh_bed1_8', zoom=3000, xan=150, yan=40)))
        coms.append((p + 'name', dict(layer=L, type='text', x=96, y=11, width=126, height=14,
                                      font='p12_full', shadowed='yes', text='', colour='0xFFFFFF')))
        coms.append((p + 'need', dict(layer=L, type='text', x=96, y=28, width=126, height=13,
                                      font='p11_full', shadowed='yes', text='', colour='0xFFFF00')))
    coms += tail('More')
    return coms

def tail(moretext):
    """More (in a layer so it can be hidden) and Cancel."""
    out = [('more', dict(type='layer', x=130, y=301, width=110, height=16, scroll=0))]
    out.append(('morebtn', dict(layer='more', type='text', x=0, y=0, buttontype='normal',
                                width=110, height=16, option='More', text=moretext, **BTN)))
    out.append(('cancel', dict(type='text', x=272, y=301, buttontype='normal', width=110,
                               height=16, option='Cancel', text='Cancel', **BTN)))
    return out

# --------------------------------------------------------------------------- the rs2

HEAD = '''// The two Construction windows, and the code that fills them.
//
// GENERATED by tools/genmenus.py from the same table that writes the .if files - the row
// blocks below are identical except for which component they name, and hand-keeping six of
// those in step with six more in the interface is how the first build panel went wrong.
// Edit the generator, not this file.
//
// WHY EVERY ROW IS A LAYER. Client.drawInterface tests a component's hide flag only when
// that component is the LAYER it is about to draw - a hidden text or model is drawn anyway.
// So an empty row is hidden by hiding its layer, and the row's contents come along.
//
// WHY THE ROW OUTLINE IS THE BUTTON. handleInterfaceInput hit-tests buttonType 1 without
// looking at the component type, so a type=rect can be the click target and cover the whole
// row, as OSRS's does. r0box..r5box and s0box..s7box are those rects.
//
// WHY if_openmain CAN SUSPEND. if_addresumebutton only pushes a component id onto the
// player's resumeButtons list, and IfButtonHandler resumes a PAUSEBUTTON script for any
// visible component on that list - isComponentVisible accepts modalMain exactly as it
// accepts modalChat. The chat menus are not a special case; they are just the only ones
// that had been written.
//
// WHY THE ZOOMS ARE A TABLE. The zoom is a DIVISOR - bigger means smaller - and a loc model
// hangs upward from the middle of its component because its origin is the floor. One shared
// value cannot frame 78 models of different sizes, so tools/ifmodels.py solves each one from
// its own geometry and writes the tables below.
//
// ON THE MODELS ARRIVING LATE. if_setmodel names a model the .if never mentions, so the packer
// does not flag it for the client's preload batch. Model.tryGet asks the on-demand stream for
// anything missing and returns null until it lands, so an icon can be blank for the first frame
// or two the very first time a window shows it. The furniture models are all flagged anyway -
// ~poh_furn_show spawns those same locs - and a room icon that blinks once per session is not
// worth a second table.
'''

def rs2_room(spec, costtext):
    o = [HEAD, '', '// =========================================================================== rooms', '']
    o.append('// The model each room is shown by, and the zoom that frames it. Raw model.pack ids:')
    o.append('// if_setmodel takes an id, not a symbol. Battery check 31 reads every one back out of')
    o.append('// model.pack and fails if a name ever moves under them.')
    o.append('[proc,poh_room_model](int $type)(int)')
    o.append('switch_int ($type) {')
    for r in spec:
        o.append('    case %d : return(%d);   // %s' % (r['type'], r['id'], r['model']))
    o.append('    case default : return(%d);' % spec[0]['id'])
    o.append('}')
    o.append('')
    o.append('[proc,poh_room_zoom](int $type)(int)')
    o.append('switch_int ($type) {')
    for r in spec:
        o.append('    case %d : return(%d);' % (r['type'], r['zoom']))
    o.append('    case default : return(%d);' % spec[0]['zoom'])
    o.append('}')
    o.append('')
    for i in range(ROOM_ROWS):
        o.append('[proc,poh_room_row%d](int $type)' % i)
        o.append('if ($type = 0) {')
        o.append('    if_sethide(poh_roommenu:row%d, true);' % i)
        o.append('    return;')
        o.append('}')
        o.append('if_sethide(poh_roommenu:row%d, false);' % i)
        o.append('if_setmodel(poh_roommenu:r%dmodel, ~poh_room_model($type));' % i)
        o.append('if_setangle(poh_roommenu:r%dmodel, ^poh_menu_xan, ^poh_menu_yan, ~poh_room_zoom($type));' % i)
        o.append('if_settext(poh_roommenu:r%dname, "<enum(int, string, poh_room_name, $type)>: Lvl <tostring(enum(int, int, poh_room_level, $type))>");' % i)
        o.append('if_settext(poh_roommenu:r%dcost, "<enum(int, string, poh_room_cost_text, $type)> coins");' % i)
        o.append('')
    o.append('// Six rooms a page, three pages, which is every room type twice over. The page loop is')
    o.append('// bounded rather than while(true): a menu that cannot end would hang the player script.')
    o.append('[proc,poh_pick_room](int $rx, int $rz, int $side)(int)')
    o.append('def_int $page = 0;')
    o.append('while ($page < 3) {')
    lets = 'abcdef'
    for i in range(ROOM_ROWS):
        o.append('    def_int $%s = ~poh_nth_room($rx, $rz, $side, calc($page * ^poh_menu_rows + %d));' % (lets[i], i))
    o.append('    def_int $more = ~poh_nth_room($rx, $rz, $side, calc($page * ^poh_menu_rows + ^poh_menu_rows));')
    o.append('    if ($a = 0) {')
    o.append('        return(0);')
    o.append('    }')
    o.append('    if_settext(poh_roommenu:subtitle, "Select a room to build");')
    for i in range(ROOM_ROWS):
        o.append('    ~poh_room_row%d($%s);' % (i, lets[i]))
    o.append('    if ($more = 0) {')
    o.append('        if_sethide(poh_roommenu:more, true);')
    o.append('    } else {')
    o.append('        if_sethide(poh_roommenu:more, false);')
    o.append('    }')
    o.append('    if_openmain(poh_roommenu);')
    for i in range(ROOM_ROWS):
        o.append('    if ($%s ! 0) {' % lets[i])
        o.append('        if_addresumebutton(poh_roommenu:r%dbox);' % i)
        o.append('    }')
    o.append('    if ($more ! 0) {')
    o.append('        if_addresumebutton(poh_roommenu:morebtn);')
    o.append('    }')
    o.append('    if_addresumebutton(poh_roommenu:cancel);')
    o.append('    p_pausebutton;')
    o.append('    switch_component (last_com) {')
    for i in range(ROOM_ROWS):
        o.append('        case poh_roommenu:r%dbox : if_close; return($%s);' % (i, lets[i]))
    o.append('        case poh_roommenu:morebtn : $page = calc($page + 1);')
    o.append('        case default : if_close; return(0);')
    o.append('    }')
    o.append('}')
    o.append('if_close;')
    o.append('return(0);')
    o.append('')
    return o

def rs2_furn(spec):
    o = ['// =========================================================================== furniture', '']
    o.append('[proc,poh_furn_zoom](int $item)(int)')
    o.append('switch_int ($item) {')
    for r in spec:
        o.append('    case %d : return(%d);   // %s' % (r['item'], r['zoom'], r['model']))
    o.append('    case default : return(%d);' % spec[0]['zoom'])
    o.append('}')
    o.append('')
    for i in range(FURN_SLOTS):
        o.append('[proc,poh_furn_slot%d](int $item)' % i)
        o.append('if ($item = 0) {')
        o.append('    if_sethide(poh_furnmenu:slot%d, true);' % i)
        o.append('    return;')
        o.append('}')
        o.append('if_sethide(poh_furnmenu:slot%d, false);' % i)
        o.append('if_setmodel(poh_furnmenu:s%dmodel, ~poh_furn_model($item));' % i)
        o.append('if_setangle(poh_furnmenu:s%dmodel, ^poh_menu_xan, ^poh_menu_yan, ~poh_furn_zoom($item));' % i)
        o.append('if_settext(poh_furnmenu:s%dlvl, "Level <tostring(enum(int, int, poh_furn_level, $item))>");' % i)
        o.append('if_settext(poh_furnmenu:s%dname, "<enum(int, string, poh_furn_name, $item)>");' % i)
        o.append('if_settext(poh_furnmenu:s%dneed, "<tostring(enum(int, int, poh_furn_planks, $item))> <enum(int, string, poh_wood_name, $item)>");' % i)
        o.append('')
    o.append('// Eight slots is one more than the largest family has tiers, so the More button is dead')
    o.append('// weight today and there anyway: the tables are data, and a family can grow.')
    o.append('[proc,poh_furn_pick](int $fam, int $level)(int)')
    o.append('def_int $page = 0;')
    o.append('while ($page < 3) {')
    lets = 'abcdefgh'
    for i in range(FURN_SLOTS):
        o.append('    def_int $%s = ~poh_furn_nth($fam, calc($page * ^poh_menu_slots + %d), $level);' % (lets[i], i))
    o.append('    def_int $more = ~poh_furn_nth($fam, calc($page * ^poh_menu_slots + ^poh_menu_slots), $level);')
    o.append('    if ($a = 0) {')
    o.append('        return(0);')
    o.append('    }')
    o.append('    if_settext(poh_furnmenu:title, "<enum(int, string, poh_fam_name, $fam)>");')
    o.append('    if_settext(poh_furnmenu:subtitle, "Select what you want to build");')
    for i in range(FURN_SLOTS):
        o.append('    ~poh_furn_slot%d($%s);' % (i, lets[i]))
    o.append('    if ($more = 0) {')
    o.append('        if_sethide(poh_furnmenu:more, true);')
    o.append('    } else {')
    o.append('        if_sethide(poh_furnmenu:more, false);')
    o.append('    }')
    o.append('    if_openmain(poh_furnmenu);')
    for i in range(FURN_SLOTS):
        o.append('    if ($%s ! 0) {' % lets[i])
        o.append('        if_addresumebutton(poh_furnmenu:s%dbox);' % i)
        o.append('    }')
    o.append('    if ($more ! 0) {')
    o.append('        if_addresumebutton(poh_furnmenu:morebtn);')
    o.append('    }')
    o.append('    if_addresumebutton(poh_furnmenu:cancel);')
    o.append('    p_pausebutton;')
    o.append('    switch_component (last_com) {')
    for i in range(FURN_SLOTS):
        o.append('        case poh_furnmenu:s%dbox : if_close; return($%s);' % (i, lets[i]))
    o.append('        case poh_furnmenu:morebtn : $page = calc($page + 1);')
    o.append('        case default : if_close; return(0);')
    o.append('    }')
    o.append('}')
    o.append('if_close;')
    o.append('return(0);')
    return o


# --------------------------------------------------------------------------- pack registration

def repack(names_by_iface, drop):
    """Rewrite pack/interface.pack and pack/interface.order.

    PackShared walks interface.order and looks every id up in interface.pack, so the two
    files have to agree exactly: an id in the order with no entry in the pack packs a
    component with type -1 and the client throws on load. Dropping poh_buildmenu means
    dropping it from BOTH, which is why this rewrites rather than appends - and why the
    windows being written are dropped first too, so running the generator twice reuses the
    same ids instead of abandoning a block of them on every run.

    interface.pack is LF; interface.order is CRLF. Mixing them up is a whole-file diff.
    """
    p = os.path.join(ROOT, 'pack/interface.pack')
    o = os.path.join(ROOT, 'pack/interface.order')
    pack = [l for l in open(p, 'rb').read().decode('utf-8').split('\n') if l]
    keep, ids = [], set()
    gone = list(drop) + list(names_by_iface)     # re-running must reuse the same ids, not append
    for l in pack:
        i, n = l.split('=', 1)
        if any(n == g or n.startswith(g + ':') for g in gone):
            continue
        keep.append((int(i), n))
        ids.add(int(i))
    nxt = max(ids) + 1
    order = [int(l) for l in open(o, 'rb').read().decode('utf-8').replace('\r\n', '\n').split('\n') if l.strip()]
    order = [i for i in order if i in ids]
    for iface, names in names_by_iface.items():
        base = nxt
        keep.append((base, iface))
        order.append(base)
        nxt += 1
        for n in names:
            keep.append((nxt, '%s:%s' % (iface, n)))
            order.append(nxt)
            nxt += 1
        print('%-14s ids %d..%d' % (iface, base, nxt - 1))
    keep.sort()
    open(p, 'wb').write(('\n'.join('%d=%s' % kv for kv in keep) + '\n').encode('utf-8'))
    nl = '\r\n' if _crlf(o) else '\n'
    open(o, 'wb').write((nl.join(str(i) for i in order) + nl).encode('utf-8'))

# --------------------------------------------------------------------------- enums

def group(n):
    """1000 -> 1,000. OSRS writes room prices this way and the 377 engine has no command
    that formats a number, so the text is a table checked against the number by the
    battery rather than built at runtime."""
    s = str(n)
    out = ''
    while len(s) > 3:
        out = ',' + s[-3:] + out
        s = s[:-3]
    return s + out

FAMS = ['Stove', 'Sink', 'Larder', 'Shelves', 'Kitchen table', 'Barrel', 'Dining table',
        'Bench', 'Bell-pull', 'Bed', 'Wardrobe', 'Clock']

def enum_block(name, rows, outtype='string', head=''):
    o = []
    if head:
        o += head.split('\n')
    o.append('[%s]' % name)
    o.append('inputtype=int')
    o.append('outputtype=%s' % outtype)
    for k, v in rows:
        o.append('val=%s,%s' % (k, v))
    return o

def add_enum(path, name, lines):
    """Write an enum table into a .enum file, replacing it if it is already there.

    Line-wise rather than by string offsets, because the table is introduced by its own
    comment block: replacing from the [name] header leaves the old comment behind, and
    running the generator twice then grows the file a paragraph at a time.
    """
    raw = open(path, 'rb').read().decode('utf-8')
    nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
    src = raw.split(nl)
    hdr = '[%s]' % name
    if hdr in src:
        i = src.index(hdr)
        j = i
        while j > 0 and src[j - 1].startswith('//'):
            j -= 1
        k = i + 1
        while k < len(src) and not src[k].startswith('['):
            k += 1
        while k - 1 > i and src[k - 1].strip() == '':
            k -= 1
        src[j:k] = lines
    else:
        while src and src[-1].strip() == '':
            src.pop()
        src += [''] + lines
    open(path, 'wb').write((nl.join(src).rstrip('\r\n') + nl).encode('utf-8'))

# --------------------------------------------------------------------------- main

def poh_locs():
    txt = open(os.path.join(ROOT, 'scripts/skill_construction/configs/poh.loc'),
               newline='').read().replace('\r\n', '\n')
    out = {}
    for b in re.split(r'\n(?=\[)', txt):
        m = re.match(r'\[(\w+)\]', b)
        if not m:
            continue
        d = {}
        for l in b.split('\n')[1:]:
            if '=' in l:
                k, v = l.split('=', 1)
                d.setdefault(k, v)
        out[m.group(1)] = d
    return out

def resolve(locname, locs, mp):
    """A loc names its model without the shape suffix the model.pack entry carries
    (poh_stove1 -> poh_stove1_8), so take the first entry that extends it."""
    base = locs[locname].get('model', '').split(',')[0]
    cands = sorted(n for n in mp if n == base or n.startswith(base + '_'))
    if not cands:
        raise SystemExit('no model in model.pack for loc %s (model=%s)' % (locname, base))
    return cands[0]

def read_costs():
    raw = open(os.path.join(ROOT, 'scripts/skill_construction/configs/poh_rooms.enum'),
               newline='').read().replace('\r\n', '\n')
    b = raw[raw.index('[poh_room_cost]'):]
    b = b[:b.index('\n[', 1)] if '\n[' in b[1:] else b
    return [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r'^val=(\d+),(\d+)$', b, re.M)]

def furn_models():
    """~poh_furn_model in poh_furniture.rs2 is already the table of which model each piece
    is shown by - generated by tools/genfurn.py from the locs. Read it rather than keep a
    second copy that can drift."""
    raw = open(os.path.join(ROOT, 'scripts/skill_construction/scripts/poh_furniture.rs2'),
               newline='').read().replace('\r\n', '\n')
    body = raw.split('[proc,poh_furn_model]')[1].split('\n[')[0]
    return [{'item': int(a), 'id': int(b), 'model': c}
            for a, b, c in re.findall(r'case (\d+) : return\((\d+)\);\s*//\s*(\S+)', body)]

if __name__ == '__main__':
    import ifmodels
    spec = json.load(open(sys.argv[1] if len(sys.argv) > 1
                          else os.path.join(ROOT, 'tools/menuspec.json')))
    mp = ifmodels.modelpack()
    byid = {v: k for k, v in mp.items()}
    locs = poh_locs()

    rooms = []
    for r in spec['rooms']:
        name = resolve(r['loc'], locs, mp)
        z, hw, rise, drop = ifmodels.fit(ifmodels.ob2path(name), ROOM_ICON, ROOM_ICON, ROOM_BELOW)
        rooms.append(dict(type=r['type'], loc=r['loc'], model=name, id=mp[name], zoom=z))
    furn = []
    for f in furn_models():
        if byid.get(f['id']) != f['model']:
            raise SystemExit('poh_furn_model item %d says %s but model.pack id %d is %s'
                             % (f['item'], f['model'], f['id'], byid.get(f['id'])))
        z, hw, rise, drop = ifmodels.fit(ifmodels.ob2path(f['model']), FURN_ICON, FURN_ICON, FURN_BELOW)
        furn.append(dict(f, zoom=z))

    names = {}
    for name, builder in [('poh_roommenu', roommenu), ('poh_furnmenu', furnmenu)]:
        coms = builder()
        path = os.path.join(ROOT, 'scripts/skill_construction/interfaces/%s.if' % name)
        text = emit(coms)
        if _crlf(os.path.join(ROOT, 'scripts/interfaces/skill_guide.if')):
            text = text.replace('\n', '\r\n')
        open(path, 'wb').write(text.encode('utf-8'))
        names[name] = [n for n, _ in coms]
        print('%-14s %3d components' % (name, len(coms)))

    old = os.path.join(ROOT, 'scripts/skill_construction/interfaces/poh_buildmenu.if')
    if os.path.exists(old):
        os.remove(old)
        print('removed poh_buildmenu.if')
    repack(names, ['poh_buildmenu'])

    costs = read_costs()
    add_enum(os.path.join(ROOT, 'scripts/skill_construction/configs/poh_rooms.enum'),
             'poh_room_cost_text',
             enum_block('poh_room_cost_text', [(k, group(v)) for k, v in costs], 'string',
                        '// The same numbers as poh_room_cost, written the way OSRS writes them. The 377 engine\n'
                        '// has no command that groups digits, and a menu that says 150000 coins reads as noise.\n'
                        '// Battery check 34 fails if the two tables ever disagree.'))
    add_enum(os.path.join(ROOT, 'scripts/skill_construction/configs/poh_furniture.enum'),
             'poh_fam_name',
             enum_block('poh_fam_name', list(enumerate(FAMS, 1)), 'string',
                        '// What the furniture window calls each hotspot family, for its title bar. Families are\n'
                        '// the ^poh_fam_* constants in construction.constant.'))
    print('enums: poh_room_cost_text, poh_fam_name')

    rs2 = rs2_room(rooms, None) + rs2_furn(furn)
    path = os.path.join(ROOT, 'scripts/skill_construction/scripts/poh_menus.rs2')
    nl = '\r\n' if _crlf(os.path.join(ROOT, 'scripts/skill_construction/scripts/poh_build.rs2')) else '\n'
    open(path, 'wb').write((nl.join(rs2).rstrip('\r\n') + nl).encode('utf-8'))
    print('poh_menus.rs2  %d lines' % len(rs2))
