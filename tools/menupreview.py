#!/usr/bin/env python3
"""Draw the two Construction windows as the client would, filled with real data.

The battery can prove a component is the right type and inside the window. It cannot say
whether the window LOOKS right - that is a question about pixels, and the only two rounds
this project lost were both lost to shipping a layout without looking at it. This renders
the states worth looking at: a full page, a short page, and the widest strings in the data.

    python3 tools/menupreview.py out.png
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import ifrender
from PIL import Image, ImageDraw

def enumtable(path, name):
    txt = open(os.path.join(ROOT, path), newline='').read().replace('\r\n', '\n')
    b = txt.split('[%s]' % name)[1].split('\n[')[0]
    return {int(m.group(1)): m.group(2) for m in re.finditer(r'^val=(\d+),(.*)$', b, re.M)}

def rs2table(path, proc):
    txt = open(os.path.join(ROOT, path), newline='').read().replace('\r\n', '\n')
    b = txt.split('[proc,%s]' % proc)[1].split('\n[')[0]
    return {int(a): int(c) for a, c in re.findall(r'case (\d+) : return\((\d+)\);', b)}

R = 'scripts/skill_construction/configs/poh_rooms.enum'
F = 'scripts/skill_construction/configs/poh_furniture.enum'
MENUS = 'scripts/skill_construction/scripts/poh_menus.rs2'
FURN = 'scripts/skill_construction/scripts/poh_furniture.rs2'

TINTS = 'scripts/skill_construction/configs/poh_menus.enum'

def tint(state):
    """The three @xxx@ tags a row of this state is drawn with, straight out of the enum."""
    return tuple(enumtable(TINTS, t)[state] for t in
                 ('poh_tint_name', 'poh_tint_level', 'poh_tint_need'))

def state(level, cost, have_level, have_cost):
    if have_level < level:
        return 2
    return 0 if have_cost >= cost else 1

def room_fill(types, more, level=99, coins=10 ** 9):
    rm, rz = rs2table(MENUS, 'poh_room_model'), rs2table(MENUS, 'poh_room_zoom')
    name, lvl = enumtable(R, 'poh_room_name'), enumtable(R, 'poh_room_level')
    cost, costn = enumtable(R, 'poh_room_cost_text'), enumtable(R, 'poh_room_cost')
    fill = {'subtitle': {'text': 'Select a room to build'}, 'more': {'hide': 'no' if more else 'yes'}}
    for i in range(6):
        if i < len(types):
            t = types[i]
            st = state(int(lvl[t]), int(costn[t]), level, coins)
            tn, tl, td = tint(st)
            fill['r%dmodel' % i] = {'model': rm[t], 'zoom': rz[t]}
            fill['r%dname' % i] = {'text': '%s%s: %sLvl %s' % (tn, name[t], tl, lvl[t])}
            fill['r%dcost' % i] = {'text': '%s%s coins' % (td, cost[t])}
        else:
            fill['row%d' % i] = {'hide': 'yes'}
    return fill

def furn_fill(fam, more, level=99, planks=10 ** 6):
    fm, fz = rs2table(FURN, 'poh_furn_model'), rs2table(MENUS, 'poh_furn_zoom')
    famof = enumtable(F, 'poh_furn_fam'); name = enumtable(F, 'poh_furn_name')
    lvl = enumtable(F, 'poh_furn_level'); plank = enumtable(F, 'poh_furn_planks')
    wood = enumtable(F, 'poh_wood_name'); famname = enumtable(F, 'poh_fam_name')
    items = [i for i in sorted(famof) if int(famof[i]) == fam]
    fill = {'title': {'text': famname[fam]},
            'subtitle': {'text': 'Select what you want to build'},
            'more': {'hide': 'no' if more else 'yes'}}
    for s in range(8):
        if s < len(items):
            it = items[s]
            st = state(int(lvl[it]), int(plank[it]), level, planks)
            tn, tl, td = tint(st)
            fill['s%dmodel' % s] = {'model': fm[it], 'zoom': fz[it]}
            fill['s%dlvl' % s] = {'text': '%sLevel %s' % (tl, lvl[it])}
            fill['s%dname' % s] = {'text': '%s%s' % (tn, name[it])}
            fill['s%dneed' % s] = {'text': '%s%s %s' % (td, plank[it], wood[it])}
        else:
            fill['slot%d' % s] = {'hide': 'yes'}
    return fill

STATES = [
    ('Room creation at level 12 with 3,000 coins: all three states at once',
     'poh_roommenu', room_fill([1, 2, 3, 4, 5, 6], True, level=12, coins=3000)),
    ('Room creation, the costly end of the ladder, all of it locked',
     'poh_roommenu', room_fill([9, 10, 15], False, level=22, coins=6000)),
    ('The bed hotspot at level 33 with 3 planks of everything',
     'poh_furnmenu', furn_fill(10, False, level=33, planks=3)),
    ('The bed hotspot at 99 with nothing in the bank',
     'poh_furnmenu', furn_fill(10, False, level=99, planks=0)),
    ('The larder hotspot, all three affordable', 'poh_furnmenu', furn_fill(3, False)),
]

if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else '/tmp/menus.png'
    tiles = []
    for label, win, fill in STATES:
        path = os.path.join(ROOT, 'scripts/skill_construction/interfaces/%s.if' % win)
        tmp = '/tmp/_%s.png' % win
        ifrender.render(path, tmp, fill=fill)
        tiles.append((label, Image.open(tmp).convert('RGB')))
    W, H = 512, 334
    sheet = Image.new('RGB', (W + 8, len(tiles) * (H + 22) + 8), (25, 25, 28))
    d = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate(tiles):
        y = 8 + i * (H + 22)
        sheet.paste(im, (4, y))
        d.text((6, y + H + 4), label, fill=(190, 190, 195))
    sheet.save(out)
    print(out)
