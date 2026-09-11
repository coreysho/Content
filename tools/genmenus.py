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

# --------------------------------------------------------------------------- the lectern window

TAB_ROWS = 8
TAB_Y, TAB_STEP, TAB_H = 62, 30, 28
TAB_X, TAB_W = 26, 448
TAB_ICON, TAB_BOX = 34, 28
TAB_SCALE = 90         # if_setobject's scale: zoom = the obj's 2dzoom x 100 / scale. The OSRS tablets
                       # carry 2dzoom 465, so 90 gives an effective 516 and draws one 24x23 - the
                       # biggest that fits a 28px row. Solved with tools/ifmodels.extent and checked
                       # by battery 42; the recoloured slab it replaced needed a 44-tall box because
                       # its own 2dzoom was 1370.
TAB_QTY_Y, TAB_QTY_W, TAB_QTY_H = 46, 34, 16
TAB_QTY_X = [344, 382, 420, 458]

def tabletmenu(spec):
    """One column of eight, not the furniture window's 2x4 grid: a tablet's shopping list is up
    to '15 earth, 15 water, 1 cosmic, 1 soft clay' and there is nowhere to put that in a 224px
    slot. Eight is also the most tablets any OSRS lectern lists, so nothing pages."""
    coms = window('Magic tablets')
    # The subtitle stops being centred so the quantity buttons can share its line: it is 129px of
    # text in a 250px box on the left, and Make 1 / 5 / 10 / X sit at the right. The row strip below
    # starts at y 62 and the bottom strip is already More and Cancel, so this line is the only place
    # in the frame with room for four more buttons.
    coms = [(n, c) for n, c in coms if n != 'subtitle']
    coms.append(('subtitle', dict(type='text', x=26, y=48, width=250, height=13,
                                  font='p12_full', shadowed='yes', text='', colour='0xFFFFFF')))
    coms.append(('qtylabel', dict(type='text', x=300, y=48, width=40, height=13,
                                  font='p12_full', shadowed='yes', text='Make:', colour='0xFFFF00')))
    for n, (nm, lab) in enumerate(zip(['qty1', 'qty5', 'qty10', 'qtyx'], ['1', '5', '10', 'X'])):
        coms.append((nm, dict(type='text', x=TAB_QTY_X[n], y=TAB_QTY_Y, buttontype='normal',
                              width=TAB_QTY_W, height=TAB_QTY_H, option='Make %s' % lab,
                              text=lab, **BTN)))
    for i in range(TAB_ROWS):
        L = 'row%d' % i
        coms.append((L, dict(type='layer', x=TAB_X, y=TAB_Y + i * TAB_STEP,
                             width=TAB_W, height=TAB_H, scroll=0)))
        p = 't%d' % i
        coms.append((p + 'box', dict(layer=L, type='rect', x=0, y=0, buttontype='normal',
                                     width=TAB_W, height=TAB_H, fill='no',
                                     colour='0x6F6250', overcolour='0xFFFFFF', option='Make')))
        # if_setobject overwrites model/xan/yan/zoom from the ObjType itself, so these four are
        # only what the packer preloads and what the previewer draws - they are the first tablet's.
        # The box is the row's own 28 and sits at its top: an OSRS tablet icon is drawn around the
        # centre of its component rather than hanging up from the floor the way a loc model does, so
        # a taller box would push it below the row instead of filling it. The centre line is 14 down
        # and the icon reaches 13 up and 11 down from there - inside the row, by battery 42.
        coms.append((p + 'model', dict(layer=L, type='model', x=4, y=0, width=TAB_ICON, height=TAB_BOX,
                                       model=spec['tablets'][0]['model'],
                                       zoom=spec['tablets'][0]['icon']['2dzoom'],
                                       xan=spec['tablets'][0]['icon'].get('2dxan', 0),
                                       yan=spec['tablets'][0]['icon'].get('2dyan', 0))))
        coms.append((p + 'name', dict(layer=L, type='text', x=42, y=7, width=126, height=14,
                                      font='p12_full', shadowed='yes', text='', colour='0xFFFFFF')))
        coms.append((p + 'need', dict(layer=L, type='text', x=172, y=8, width=200, height=13,
                                      font='p11_full', shadowed='yes', text='', colour='0xFFFF00')))
        coms.append((p + 'lvl', dict(layer=L, type='text', x=376, y=7, width=68, height=14,
                                     center='yes', font='p12_full', shadowed='yes',
                                     text='', colour='0xFFFFFF')))
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
// WHY THE TINTS ARE THREE ENUMS AND NOT A PROC. Colour comes from @xxx@ tags inside the text -
// PixFont.drawStringTag reads them mid-string, so one if_settext controls the colour of every run
// in a row without extra components. The tag itself has to come from somewhere, and a proc that
// returns a string has no precedent in this repo (claude/rs2-compile-traps.md), so each row works
// out an int state and looks the tag up: <enum(int, string, poh_tint_name, $state)>, which is the
// idiom poh_test.rs2 already compiles. State 0 is buildable, 1 is buildable but you cannot pay for
// it, 2 is above your Construction level.
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
        o.append('def_int $state = ^poh_state_ready;')
        o.append('if (inv_total(inv, coins) < enum(int, int, poh_room_cost, $type)) {')
        o.append('    $state = ^poh_state_poor;')
        o.append('}')
        o.append('if (stat(construction) < enum(int, int, poh_room_level, $type)) {')
        o.append('    $state = ^poh_state_locked;')
        o.append('}')
        o.append('if_setmodel(poh_roommenu:r%dmodel, ~poh_room_model($type));' % i)
        o.append('if_setangle(poh_roommenu:r%dmodel, ^poh_menu_xan, ^poh_menu_yan, ~poh_room_zoom($type));' % i)
        o.append('if_settext(poh_roommenu:r%dname, "<enum(int, string, poh_tint_name, $state)><enum(int, string, poh_room_name, $type)>: <enum(int, string, poh_tint_level, $state)>Lvl <tostring(enum(int, int, poh_room_level, $type))>");' % i)
        o.append('if_settext(poh_roommenu:r%dcost, "<enum(int, string, poh_tint_need, $state)><enum(int, string, poh_room_cost_text, $type)> coins");' % i)
        o.append('')
    o.append('// Six rooms a page, three pages, which is every room type twice over. The page loop is')
    o.append('// bounded rather than while(true): a menu that cannot end would hang the player script.')
    o.append('//')
    o.append('// A click on a room you have the level for returns it and the caller does the paying. A click')
    o.append('// on one you do not says so and leaves the window open - money is a thing you go and fix, a')
    o.append('// level is a thing you go on browsing past.')
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
    o.append('    def_int $pick = 0;')
    o.append('    switch_component (last_com) {')
    for i in range(ROOM_ROWS):
        o.append('        case poh_roommenu:r%dbox : $pick = $%s;' % (i, lets[i]))
    o.append('        case poh_roommenu:morebtn : $page = calc($page + 1);')
    o.append('        case default : if_close; return(0);')
    o.append('    }')
    o.append('    if ($pick > 0) {')
    o.append('        if (stat(construction) >= enum(int, int, poh_room_level, $pick)) {')
    o.append('            if_close;')
    o.append('            return($pick);')
    o.append('        }')
    o.append('        mes("You need a Construction level of <tostring(enum(int, int, poh_room_level, $pick))> to build a <enum(int, string, poh_room_name, $pick)>.");')
    o.append('    }')
    o.append('}')
    o.append('if_close;')
    o.append('return(0);')
    o.append('')
    return o

def rs2_furn(spec, cams, fams):
    o = ['// =========================================================================== furniture', '']
    o.append('// A framed picture has no depth: seen three-quarters on it is a one-pixel sliver, so the')
    o.append('// families that are pictures get turned face-on. Everything else keeps the shared camera.')
    o.append('// tools/furnspec.json holds the list and says why each one is on it.')
    for name, i in (('poh_furn_xan', 0), ('poh_furn_yan', 1)):
        o.append('[proc,%s](int $fam)(int)' % name)
        o.append('switch_int ($fam) {')
        for n, f in enumerate(fams, 1):
            if f['key'] in cams:
                o.append('    case %d : return(%d);   // %s' % (n, cams[f['key']][i], f['key']))
        o.append('    case default : return(^poh_menu_%s);' % ('xan' if i == 0 else 'yan'))
        o.append('}')
        o.append('')
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
        o.append('def_int $state = ^poh_state_ready;')
        o.append('if (~poh_furn_plank_total(enum(int, int, poh_furn_wood, $item)) < enum(int, int, poh_furn_planks, $item)) {')
        o.append('    $state = ^poh_state_poor;')
        o.append('}')
        o.append('if (stat(construction) < enum(int, int, poh_furn_level, $item)) {')
        o.append('    $state = ^poh_state_locked;')
        o.append('}')
        o.append('def_int $fam = enum(int, int, poh_furn_fam, $item);')
        o.append('if_setmodel(poh_furnmenu:s%dmodel, ~poh_furn_model($item));' % i)
        o.append('if_setangle(poh_furnmenu:s%dmodel, ~poh_furn_xan($fam), ~poh_furn_yan($fam), ~poh_furn_zoom($item));' % i)
        o.append('if_settext(poh_furnmenu:s%dlvl, "<enum(int, string, poh_tint_level, $state)>Level <tostring(enum(int, int, poh_furn_level, $item))>");' % i)
        o.append('if_settext(poh_furnmenu:s%dname, "<enum(int, string, poh_tint_name, $state)><enum(int, string, poh_furn_name, $item)>");' % i)
        o.append('if_settext(poh_furnmenu:s%dneed, "<enum(int, string, poh_tint_need, $state)><tostring(enum(int, int, poh_furn_planks, $item))> <enum(int, string, poh_wood_name, $item)>");' % i)
        o.append('')
    o.append('// Eight slots is one more than the largest family has tiers, so the More button is dead')
    o.append('// weight today and there anyway: the tables are data, and a family can grow.')
    o.append('//')
    o.append('// Level is not a filter - the whole family is listed and the tiers above you are dimmed, so')
    o.append('// the window is also where you find out what the next twenty levels are for.')
    o.append('[proc,poh_furn_pick](int $fam)(int)')
    o.append('def_int $page = 0;')
    o.append('while ($page < 3) {')
    lets = 'abcdefgh'
    for i in range(FURN_SLOTS):
        o.append('    def_int $%s = ~poh_furn_nth($fam, calc($page * ^poh_menu_slots + %d));' % (lets[i], i))
    o.append('    def_int $more = ~poh_furn_nth($fam, calc($page * ^poh_menu_slots + ^poh_menu_slots));')
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
    o.append('    def_int $pick = 0;')
    o.append('    switch_component (last_com) {')
    for i in range(FURN_SLOTS):
        o.append('        case poh_furnmenu:s%dbox : $pick = $%s;' % (i, lets[i]))
    o.append('        case poh_furnmenu:morebtn : $page = calc($page + 1);')
    o.append('        case default : if_close; return(0);')
    o.append('    }')
    o.append('    if ($pick > 0) {')
    o.append('        if (stat(construction) >= enum(int, int, poh_furn_level, $pick)) {')
    o.append('            if_close;')
    o.append('            return($pick);')
    o.append('        }')
    o.append('        mes("You need a Construction level of <tostring(enum(int, int, poh_furn_level, $pick))> to build that.");')
    o.append('    }')
    o.append('}')
    o.append('if_close;')
    o.append('return(0);')
    return o

def rs2_tab(scale, steps):
    o = ['// =========================================================================== tablets', '']
    o.append('// The lectern window. Same three tints and the same whole-row button as the other two; the')
    o.append('// difference is the icon, which is an OBJ and not a loc model. if_setobject takes the obj and')
    o.append('// the client reads xan, yan and zoom off the ObjType itself - zoom = the obj\'s own 2dzoom x')
    o.append('// 100 / scale - so there is no zoom table here and nothing to solve. %d is the scale that puts' % scale)
    o.append('// a tablet in a 34px box; it was rendered and looked at, like the other two windows.')
    o.append('//')
    o.append('// State 1 here means "you have the level but not the runes", which is the same shape as not')
    o.append('// being able to afford a room - so the needs line goes red and the row stays clickable, and')
    o.append('// clicking it tells you exactly what is missing.')
    for i in range(TAB_ROWS):
        o.append('[proc,poh_tab_row%d](int $tab)' % i)
        o.append('if ($tab = 0) {')
        o.append('    if_sethide(poh_tabletmenu:row%d, true);' % i)
        o.append('    return;')
        o.append('}')
        o.append('if_sethide(poh_tabletmenu:row%d, false);' % i)
        o.append('def_int $state = ^poh_state_ready;')
        o.append('if (~poh_tab_have($tab) = false) {')
        o.append('    $state = ^poh_state_poor;')
        o.append('}')
        o.append('if (stat(magic) < enum(int, int, poh_tab_level, $tab)) {')
        o.append('    $state = ^poh_state_locked;')
        o.append('}')
        o.append('if_setobject(poh_tabletmenu:t%dmodel, enum(int, namedobj, poh_tab_obj, $tab), %d);' % (i, scale))
        o.append('if_settext(poh_tabletmenu:t%dname, "<enum(int, string, poh_tint_name, $state)><enum(int, string, poh_tab_name, $tab)>");' % i)
        o.append('if_settext(poh_tabletmenu:t%dneed, "<enum(int, string, poh_tint_need, $state)><enum(int, string, poh_tab_need, $tab)>");' % i)
        o.append('if_settext(poh_tabletmenu:t%dlvl, "<enum(int, string, poh_tint_level, $state)>Level <tostring(enum(int, int, poh_tab_level, $tab))>");' % i)
        o.append('')
    o.append('// Make 1 / 5 / 10 / X. The chosen one is green and the others white - the same @xxx@ tags the')
    o.append('// rows use, so no extra components and no second set of texts. The X button shows the number')
    o.append('// it was given rather than an X once it holds one, because "Make X" with X forgotten is the')
    o.append('// one thing about this control that can confuse.')
    o.append('[proc,poh_tab_qty_draw](int $qty)')
    for n in steps:
        o.append('if_settext(poh_tabletmenu:qty%d, "@whi@%d");' % (n, n))
    o.append('if_settext(poh_tabletmenu:qtyx, "@whi@X");')
    for n in steps:
        o.append('if ($qty = %d) {' % n)
        o.append('    if_settext(poh_tabletmenu:qty%d, "@gre@%d");' % (n, n))
        o.append('}')
    o.append('if (%s) {' % ' & '.join('$qty ! %d' % n for n in steps))
    o.append('    if_settext(poh_tabletmenu:qtyx, "@gre@<tostring($qty)>");')
    o.append('}')
    o.append('')
    o.append('// Make X. p_countdialog is the same "Enter amount" prompt Cook X uses; it can be opened over')
    o.append('// the main window because openMainModal only drops a suspended script when the script is')
    o.append('// waiting on a PAUSEBUTTON or a COUNTDIALOG, and this one is RUNNING. A cancelled prompt')
    o.append('// answers 0, which leaves the quantity alone.')
    o.append('[proc,poh_tab_qty_ask]')
    o.append('p_countdialog;')
    o.append('if (last_int < 1) {')
    o.append('    return;')
    o.append('}')
    o.append('%poh_tab_qty = last_int;')
    o.append('if (%poh_tab_qty > ^poh_tab_qty_max) {')
    o.append('    %poh_tab_qty = ^poh_tab_qty_max;')
    o.append('}')
    o.append('')
    o.append('// Study. The window stays up and redraws after every tablet, so one soft clay at a time turns')
    o.append('// into an inventory of tablets without walking away from the lectern; ^poh_tab_loops is an')
    o.append('// inventory\'s worth, and the bound is there because a loop that cannot end hangs the script.')
    o.append('//')
    o.append('// There is no second page: no lectern lists more than ^poh_tab_max tablets, which is exactly')
    o.append('// the number of rows, and ~poh_tab_nth has no index above that to give. The More button the')
    o.append('// shared frame provides is therefore hidden rather than wired up.')
    o.append('[proc,poh_tab_pick](int $lect)')
    o.append('def_int $n = 0;')
    o.append('while ($n < ^poh_tab_loops) {')
    o.append('    $n = calc($n + 1);')
    lets = 'abcdefgh'
    for i in range(TAB_ROWS):
        o.append('    def_int $%s = ~poh_tab_nth($lect, %d);' % (lets[i], i))
    o.append('    if ($a = 0) {')
    o.append('        if_close;')
    o.append('        return;')
    o.append('    }')
    o.append('    if_settext(poh_tabletmenu:title, "<enum(int, string, poh_lectern_name, $lect)>");')
    o.append('    if_settext(poh_tabletmenu:subtitle, "Select a tablet to make");')
    o.append('    if (%poh_tab_qty < 1) {')
    o.append('        %poh_tab_qty = 1;')
    o.append('    }')
    o.append('    ~poh_tab_qty_draw(%poh_tab_qty);')
    for i in range(TAB_ROWS):
        o.append('    ~poh_tab_row%d($%s);' % (i, lets[i]))
    o.append('    if_sethide(poh_tabletmenu:more, true);')
    o.append('    if_openmain(poh_tabletmenu);')
    for i in range(TAB_ROWS):
        o.append('    if ($%s ! 0) {' % lets[i])
        o.append('        if_addresumebutton(poh_tabletmenu:t%dbox);' % i)
        o.append('    }')
    for n in steps:
        o.append('    if_addresumebutton(poh_tabletmenu:qty%d);' % n)
    o.append('    if_addresumebutton(poh_tabletmenu:qtyx);')
    o.append('    if_addresumebutton(poh_tabletmenu:cancel);')
    o.append('    p_pausebutton;')
    o.append('    def_int $pick = 0;')
    o.append('    switch_component (last_com) {')
    for i in range(TAB_ROWS):
        o.append('        case poh_tabletmenu:t%dbox : $pick = $%s;' % (i, lets[i]))
    for n in steps:
        o.append('        case poh_tabletmenu:qty%d : %%poh_tab_qty = %d;' % (n, n))
    o.append('        case poh_tabletmenu:qtyx : ~poh_tab_qty_ask;')
    o.append('        case default : if_close; return;')
    o.append('    }')
    o.append('    if ($pick > 0) {')
    o.append('        // The window comes down while they are being made: the animation is the feedback, and')
    o.append('        // the loop above puts it back up with the new counts as soon as the batch is done.')
    o.append('        if_close;')
    o.append('        ~poh_tab_make_n($pick, %poh_tab_qty);')
    o.append('    }')
    o.append('}')
    o.append('if_close;')
    o.append('')
    return o

# --------------------------------------------------------------------------- the tint tables

TINTS = [
    ('poh_tint_name',  ['@whi@', '@whi@', '@bla@'],
     'What colour each part of a row is drawn in, by state: 0 you can build it, 1 you can build it but\n'
     'cannot pay for it, 2 your Construction level is too low. These are PixFont @xxx@ tags, read\n'
     'mid-string by drawStringTag, so one if_settext colours a whole row.\n'
     '\n'
     'The name of a locked row is BLACK rather than grey: PixFont.evaluateTag has no grey, and black on\n'
     'the stone panel recedes the way a disabled entry should. Checked by rendering it - see\n'
     'tools/menupreview.py.'),
    ('poh_tint_level', ['@whi@', '@whi@', '@red@'],
     'The level requirement, red when you have not got it. This is the one OSRS shows in red too.'),
    ('poh_tint_need',  ['@gre@', '@red@', '@bla@'],
     'What it costs: green when you have it, red when you have not, black when the level puts it out of\n'
     'reach anyway. Green-for-have and red-for-have-not is the smithing interface\'s own convention\n'
     '(its bar counts are colour=0xC00000 with activecolour=0x00C000).'),
]

# --------------------------------------------------------------------------- pack registration

def repack(names_by_iface, drop):
    """Rewrite pack/interface.pack and pack/interface.order.

    PackShared walks interface.order and looks every id up in interface.pack, so the two
    files have to agree exactly: an id in the order with no entry in the pack packs a
    component with type -1 and the client throws on load. Dropping poh_buildmenu means
    dropping it from BOTH, which is why this rewrites rather than appends - and why the
    windows being written are dropped first too, so running the generator twice reuses the
    same ids instead of abandoning a block of them on every run.

    interface.pack is LF; interface.order follows the repo's other text files. Mixing them
    up is a whole-file diff.
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

def enum_block(name, rows, outtype='string', head=''):
    o = []
    if head:
        o += [l.rstrip() for l in head.split('\n')]
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
    raw = open(path, 'rb').read().decode('utf-8') if os.path.exists(path) else ''
    nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
    if not raw:
        nl = '\r\n' if _crlf(os.path.join(ROOT, 'scripts/skill_construction/configs/poh_rooms.enum')) else '\n'
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
        src += ([''] if any(x.strip() for x in src) else []) + lines
    open(path, 'wb').write((nl.join(src).lstrip('\r\n').rstrip('\r\n') + nl).encode('utf-8'))

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

def default_camera():
    c = read_text('scripts/skill_construction/configs/construction.constant')
    return (int(re.search(r'\^poh_menu_xan\s*=\s*(\d+)', c).group(1)),
            int(re.search(r'\^poh_menu_yan\s*=\s*(\d+)', c).group(1)))

def read_text(p):
    return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')

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
    fspec = json.load(open(os.path.join(ROOT, 'tools/furnspec.json')))
    fams = fspec['families']
    cams = {k: v for k, v in fspec.get('cameras', {}).items() if k != '_'}
    famof = {}
    n = 0
    for f in fams:
        for _ in f['locs']:
            n += 1
            famof[n] = f['key']
    XAN, YAN = default_camera()
    furn = []
    for f in furn_models():
        if byid.get(f['id']) != f['model']:
            raise SystemExit('poh_furn_model item %d says %s but model.pack id %d is %s'
                             % (f['item'], f['model'], f['id'], byid.get(f['id'])))
        xan, yan = cams.get(famof[f['item']], (XAN, YAN))
        z, hw, rise, drop = ifmodels.fit(ifmodels.ob2path(f['model']), FURN_ICON, FURN_ICON,
                                         FURN_BELOW, xan=xan, yan=yan)
        furn.append(dict(f, zoom=z))

    tspec = json.load(open(os.path.join(ROOT, 'tools/tabletspec.json')))
    names = {}
    for name, builder in [('poh_roommenu', roommenu), ('poh_furnmenu', furnmenu),
                          ('poh_tabletmenu', lambda: tabletmenu(tspec))]:
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
    # poh_fam_name belongs to tools/genfurn.py, which owns poh_furniture.enum and the family list
    tints = os.path.join(ROOT, 'scripts/skill_construction/configs/poh_menus.enum')
    if not os.path.exists(tints):
        open(tints, 'wb').write(b'')
    for name, vals, why in TINTS:
        add_enum(tints, name, enum_block(name, list(enumerate(vals)), 'string',
                                         '\n'.join('// ' + l for l in why.split('\n'))))
    print('enums: poh_room_cost_text, poh_fam_name, ' + ', '.join(n for n, _, _ in TINTS))

    rs2 = rs2_room(rooms, None) + rs2_furn(furn, cams, fams) + [''] + rs2_tab(TAB_SCALE, tspec['quantities']['steps'])
    path = os.path.join(ROOT, 'scripts/skill_construction/scripts/poh_menus.rs2')
    nl = '\r\n' if _crlf(os.path.join(ROOT, 'scripts/skill_construction/scripts/poh_build.rs2')) else '\n'
    open(path, 'wb').write((nl.join(rs2).rstrip('\r\n') + nl).encode('utf-8'))
    print('poh_menus.rs2  %d lines' % len(rs2))
