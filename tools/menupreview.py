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

def room_fill(types, more):
    rm, rz = rs2table(MENUS, 'poh_room_model'), rs2table(MENUS, 'poh_room_zoom')
    name, lvl, cost = enumtable(R, 'poh_room_name'), enumtable(R, 'poh_room_level'), enumtable(R, 'poh_room_cost_text')
    fill = {'subtitle': {'text': 'Select a room to build'}, 'more': {'hide': 'no' if more else 'yes'}}
    for i in range(6):
        if i < len(types):
            t = types[i]
            fill['r%dmodel' % i] = {'model': rm[t], 'zoom': rz[t]}
            fill['r%dname' % i] = {'text': '%s: Lvl %s' % (name[t], lvl[t])}
            fill['r%dcost' % i] = {'text': '%s coins' % cost[t]}
        else:
            fill['row%d' % i] = {'hide': 'yes'}
    return fill

def furn_fill(fam, more):
    fm, fz = rs2table(FURN, 'poh_furn_model'), rs2table(MENUS, 'poh_furn_zoom')
    famof = enumtable(F, 'poh_furn_fam'); name = enumtable(F, 'poh_furn_name')
    lvl = enumtable(F, 'poh_furn_level'); planks = enumtable(F, 'poh_furn_planks')
    wood = enumtable(F, 'poh_wood_name'); famname = enumtable(F, 'poh_fam_name')
    items = [i for i in sorted(famof) if int(famof[i]) == fam]
    fill = {'title': {'text': famname[fam]},
            'subtitle': {'text': 'Select what you want to build'},
            'more': {'hide': 'no' if more else 'yes'}}
    for s in range(8):
        if s < len(items):
            it = items[s]
            fill['s%dmodel' % s] = {'model': fm[it], 'zoom': fz[it]}
            fill['s%dlvl' % s] = {'text': 'Level %s' % lvl[it]}
            fill['s%dname' % s] = {'text': name[it]}
            fill['s%dneed' % s] = {'text': '%s %s' % (planks[it], wood[it])}
        else:
            fill['slot%d' % s] = {'hide': 'yes'}
    return fill

STATES = [
    ('Room creation, a full page with more to come', 'poh_roommenu', room_fill([1, 2, 3, 4, 5, 6], True)),
    ('Room creation, the costliest rooms, short page', 'poh_roommenu', room_fill([9, 10, 15], False)),
    ('Furniture, the bed hotspot (7 tiers)', 'poh_furnmenu', furn_fill(10, False)),
    ('Furniture, the larder hotspot (3 tiers)', 'poh_furnmenu', furn_fill(3, False)),
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
