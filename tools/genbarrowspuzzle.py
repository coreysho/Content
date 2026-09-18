#!/usr/bin/env python3
"""Generate the Barrows door puzzle: its shape art, its interface, and its answer table.

WHAT IT IS. Old School guards the last door before the chest with a sequence puzzle: three symbols
and a question mark on top, three candidates below, click the one that finishes the sequence. Get
it wrong and the tunnels shift. This build had the same puzzle and the same consequence, but asked
it in WORDS, because the 377 cache has no shape art to draw a pattern out of.

It does now, and it is drawn here rather than imported. Two reasons: the shapes are geometric
primitives that PIL draws exactly, and drawing them means the puzzle SET is chosen here too - so
every sequence can be guaranteed to have exactly one right answer among its three candidates,
which is not something an imported sheet of pixels would tell us.

THE SPRITE RULES, from the packer (tools/pack/PixPack.generatePalette):
  - 0xFF00FF is palette index 0, i.e. TRANSPARENT. The sheet's background must be exactly that.
  - every other colour costs a palette slot, and over 255 the packer quantizes. So the shapes are
    drawn with hard edges and a handful of flat greys - no antialiasing, which would spend
    hundreds of slots on near-greys and muddy the edges in an indexed palette anyway.
  - a sheet is split by sprites/meta/<name>.opt, one "WxH" line, row-major.

WHY EIGHT LAYERS RATHER THAN ONE PANEL REDRAWN. There is no if_setgraphic in this engine - a
graphic component's sprite is fixed at pack time (if_setobject and if_setmodel exist; sprites have
no equivalent). So all eight puzzles are built into the interface, one layer each, and
~barrows_puzzle_show hides seven of them. if_sethide only works on layers, which is why each
puzzle's six shapes live inside one.

    python3 tools/genbarrowspuzzle.py
    python3 tools/ifrender.py ../scripts/areas/area_barrows/interfaces/barrows_puzzle.if /tmp/p.png
"""
import json, os, re
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFACE = 'barrows_puzzle'
IF = os.path.join(ROOT, 'scripts/areas/area_barrows/interfaces/%s.if' % IFACE)
SHEET = os.path.join(ROOT, 'sprites/%s.png' % IFACE)
OPT = os.path.join(ROOT, 'sprites/meta/%s.opt' % IFACE)
ENUM = os.path.join(ROOT, 'scripts/areas/area_barrows/configs/barrows_puzzle.enum')
SPEC = os.path.join(ROOT, 'tools/barrowspuzzlespec.json')
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
CONST = os.path.join(ROOT, 'scripts/areas/area_barrows/configs/barrows.constant')

MAGENTA = (255, 0, 255)
TILE = 32
COLS = 6                       # sheet columns; the split is row-major so this fixes every index
EDGE = (188, 180, 160)         # the outline: the same bone-grey the window chrome uses
FILL = (128, 120, 104)         # a filled area
DIM = (74, 69, 58)             # the box a candidate sits in

# ---------------------------------------------------------------- the tiles
# Five families, each a progression. Every tile is 32x32 with a 4px margin.
TILES = []                     # ordered; index in this list IS the sprite index


def tile(name):
    TILES.append(name)
    return name


SQ = [tile('sq%d' % n) for n in range(5)]        # a square, n of its four quadrants filled
POLY = [tile('p%d' % n) for n in range(3, 8)]    # regular polygons, 3..7 sides
EL = [tile('el%d' % n) for n in range(4)]        # an ellipse, widening
BA = [tile('ba%d' % n) for n in range(4)]        # a bar, growing
CI = [tile('ci%d' % n) for n in range(4)]        # a circle, shrinking


def draw_tile(name):
    im = Image.new('RGB', (TILE, TILE), MAGENTA)
    d = ImageDraw.Draw(im)
    m = 4
    box = (m, m, TILE - 1 - m, TILE - 1 - m)
    if name.startswith('sq'):
        n = int(name[2:])
        x0, y0, x1, y1 = box
        cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
        quads = [(x0, y0, cx, cy), (cx, y0, x1, cy), (cx, cy, x1, y1), (x0, cy, cx, y1)]
        for q in quads[:n]:
            d.rectangle(q, fill=FILL)
        d.rectangle(box, outline=EDGE)
    elif name.startswith('p'):
        sides = int(name[1:])
        r = (TILE - 2 * m) / 2
        cx, cy = TILE / 2, TILE / 2
        # flat-bottomed, so a triangle reads as a triangle and a square as a square
        import math
        rot = math.pi / sides + math.pi / 2
        # rounded to whole pixels: PIL draws a polygon outline from float vertices with a
        # one-pixel spur where two edges meet off-grid, which on a 32px triangle is a visible nick
        pts = [(round(cx + r * math.cos(2 * math.pi * i / sides + rot)),
                round(cy + r * math.sin(2 * math.pi * i / sides + rot))) for i in range(sides)]
        d.polygon(pts, fill=FILL, outline=EDGE)
    elif name.startswith('el'):
        n = int(name[2:])
        w = 10 + n * 5
        d.ellipse((TILE // 2 - w // 2, m, TILE // 2 + w // 2, TILE - 1 - m), fill=FILL, outline=EDGE)
    elif name.startswith('ba'):
        n = int(name[2:])
        h = 8 + n * 5
        d.rectangle((m + 4, TILE - 1 - m - h, TILE - 1 - m - 4, TILE - 1 - m), fill=FILL, outline=EDGE)
    elif name.startswith('ci'):
        n = int(name[2:])
        r = 12 - n * 2 - (1 if n == 3 else 0)
        d.ellipse((TILE // 2 - r, TILE // 2 - r, TILE // 2 + r, TILE // 2 + r), fill=FILL, outline=EDGE)
    else:
        raise SystemExit('no drawing for tile %s' % name)
    return im


# ---------------------------------------------------------------- the eight puzzles
# (sequence of three, the answer, the two wrong candidates, which slot the answer sits in)
# WHICH SLOT IS DIFFERENT IN EVERY PUZZLE that shares a family, because eight puzzles whose answer
# is always the middle option is one puzzle. Across the eight, slot 0 comes up three times and
# slots 1 and 2 come up two and three times - checked below rather than eyeballed.
PUZZLES = [
    dict(why='a square filling up, one quarter at a time',
         seq=[SQ[1], SQ[2], SQ[3]], answer=SQ[4], wrong=[SQ[2], SQ[0]], slot=0),
    dict(why='polygons losing a side each step',
         seq=[POLY[4], POLY[3], POLY[2]], answer=POLY[1], wrong=[POLY[0], POLY[2]], slot=1),
    dict(why='an ellipse widening',
         seq=[EL[0], EL[1], EL[2]], answer=EL[3], wrong=[EL[0], EL[2]], slot=2),
    dict(why='a bar growing',
         seq=[BA[0], BA[1], BA[2]], answer=BA[3], wrong=[BA[1], BA[0]], slot=1),
    dict(why='polygons gaining a side each step',
         seq=[POLY[0], POLY[1], POLY[2]], answer=POLY[3], wrong=[POLY[0], POLY[1]], slot=0),
    dict(why='a square emptying, one quarter at a time',
         seq=[SQ[4], SQ[3], SQ[2]], answer=SQ[1], wrong=[SQ[0], SQ[2]], slot=2),
    dict(why='a circle shrinking',
         seq=[CI[0], CI[1], CI[2]], answer=CI[3], wrong=[CI[1], CI[0]], slot=0),
    dict(why='square, circle, square - so a circle',
         seq=[POLY[1], CI[1], POLY[1]], answer=CI[1], wrong=[POLY[0], POLY[1]], slot=1),
]

# ---------------------------------------------------------------- panel geometry
PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 240
TILE_W, TILE_H = 88, 60
SEQ_Y = 92                     # the row that poses the question
RULE_Y = 152                   # the line between the question and the answers
PICK_Y = 172                   # the row you click
STEP = 56                      # horizontal pitch between shapes
BOX = 40                       # the box a candidate sits in


def read(p):
    return open(p, newline='').read().replace('\r\n', '\n')


def const(name):
    m = re.search(r'(?m)^\^%s = (\d+)' % name, read(CONST))
    if not m:
        raise SystemExit('barrows.constant does not define ^%s' % name)
    return int(m.group(1))


def main():
    want = const('barrows_puzzles')
    if want != len(PUZZLES):
        raise SystemExit('^barrows_puzzles is %d and there are %d puzzles here' % (want, len(PUZZLES)))
    slots = [p['slot'] for p in PUZZLES]
    for s in (0, 1, 2):
        if slots.count(s) < 2:
            raise SystemExit('slot %d is the answer in only %d puzzle(s) - too guessable'
                             % (s, slots.count(s)))
    for i, p in enumerate(PUZZLES):
        if p['answer'] in p['wrong']:
            raise SystemExit('puzzle %d offers its answer twice' % i)
        if len(set([p['answer']] + p['wrong'])) != 3:
            raise SystemExit('puzzle %d has duplicate candidates' % i)

    # ---- the sheet
    rows = -(-len(TILES) // COLS)
    sheet = Image.new('RGB', (COLS * TILE, rows * TILE), MAGENTA)
    for i, name in enumerate(TILES):
        sheet.paste(draw_tile(name), ((i % COLS) * TILE, (i // COLS) * TILE))
    os.makedirs(os.path.dirname(SHEET), exist_ok=True)
    os.makedirs(os.path.dirname(OPT), exist_ok=True)
    sheet.save(SHEET)
    open(OPT, 'w', newline='').write('%dx%d\n' % (TILE, TILE))
    palette = {c for _, c in (sheet.getcolors(65536) or [])} - {MAGENTA}
    if len(palette) > 255:
        raise SystemExit('%d non-transparent colours - the packer would quantize' % len(palette))
    idx = {name: i for i, name in enumerate(TILES)}

    # ---- the interface
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
                width=min(TILE_W, PANEL_X + PANEL_W - x), height=TILE_H, graphic='tradebacking,0')
            n += 1
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
        font='b12_full', shadowed='yes', text='A pattern is carved into the door',
        colour='0xFFFF00')
    com('hint', type='text', x=PANEL_X, y=PANEL_Y + 28, width=PANEL_W, height=14, center='yes',
        font='p12_full', shadowed='yes', text='Choose the symbol that completes it.',
        colour='0xFF981F')
    com('close', type='text', x=PANEL_X + 412, y=PANEL_Y + 8, buttontype='close', width=68,
        height=11, font='p11_full', shadowed='yes', text='Close Window', colour='0xC00000',
        overcolour='0xFFFFFF')

    # the four slots the question sits in, and the three you click. Centred as a row of four /
    # three at STEP pitch, so the "?" lines up as the fourth member of the sequence.
    def row_x(count, i):
        width = (count - 1) * STEP
        return PANEL_X + PANEL_W // 2 - width // 2 + i * STEP - TILE // 2

    # the question mark is TEXT, not a tile: it is a glyph and the font already has one
    com('qmark', type='text', x=row_x(4, 3), y=SEQ_Y + 6, width=TILE, height=20, center='yes',
        font='b12_full', shadowed='yes', text='?', colour='0xFFFFFF')
    com('rule', type='rect', x=PANEL_X + 120, y=RULE_Y, width=PANEL_W - 240, height=1,
        fill='yes', colour='0x%06X' % (DIM[0] << 16 | DIM[1] << 8 | DIM[2]))
    # the boxes are drawn once, outside the layers: they do not change with the puzzle
    for i in range(3):
        com('box%d' % i, type='rect', x=row_x(3, i) - (BOX - TILE) // 2,
            y=PICK_Y - (BOX - TILE) // 2, width=BOX, height=BOX, fill='yes',
            colour='0x%06X' % (DIM[0] << 16 | DIM[1] << 8 | DIM[2]))

    # ---- one layer per puzzle, six shapes inside it
    for pi, p in enumerate(PUZZLES):
        com('set%d' % pi, type='layer', x=PANEL_X, y=0, width=PANEL_W, height=PANEL_Y + PANEL_H)
        for si, t in enumerate(p['seq']):
            com('set%dseq%d' % (pi, si), layer='set%d' % pi, type='graphic',
                x=row_x(4, si) - PANEL_X, y=SEQ_Y, width=TILE, height=TILE,
                graphic='%s,%d' % (IFACE, idx[t]))
        cands = list(p['wrong'])
        cands.insert(p['slot'], p['answer'])
        for ci_, t in enumerate(cands):
            com('set%dpick%d' % (pi, ci_), layer='set%d' % pi, type='graphic',
                x=row_x(3, ci_) - PANEL_X, y=PICK_Y, width=TILE, height=TILE,
                graphic='%s,%d' % (IFACE, idx[t]))

    # ---- the three buttons, on top of everything, one per slot and never moving
    for i in range(3):
        com('pick%d' % i, type='rect', x=row_x(3, i) - (BOX - TILE) // 2,
            y=PICK_Y - (BOX - TILE) // 2, buttontype='normal', width=BOX, height=BOX,
            fill='no', colour='0x6F6250', overcolour='0xFFFFFF', option='Choose')

    body = '\n'.join(out)
    os.makedirs(os.path.dirname(IF), exist_ok=True)
    open(IF, 'w', newline='').write(
        '// GENERATED by tools/genbarrowspuzzle.py - do not hand edit.\n'
        '// Scripts: areas/area_barrows/scripts/barrows_puzzle.rs2. Art: sprites/%s.png.\n'
        '// One layer per puzzle; ~barrows_puzzle_show hides the seven that are not being asked.\n'
        % IFACE + body)
    names = re.findall(r'^\[([A-Za-z0-9_]+)\]$', body, re.M)

    # ---- the answer table
    lines = ['// GENERATED by tools/genbarrowspuzzle.py - do not hand edit.',
             '// Which of the three candidate slots is the right answer, per puzzle. The shapes',
             '// themselves are in the interface; this is the only part the scripts need.', '',
             '[barrows_puzzle_answer]', 'inputtype=int', 'outputtype=int', 'default=-1']
    for i, p in enumerate(PUZZLES):
        lines.append('val=%d,%d' % (i, p['slot']))
    lines.append('')
    open(ENUM, 'w', newline='').write('\n'.join(lines))

    json.dump({
        '_source': 'tools/genbarrowspuzzle.py - the puzzle set is chosen here, not imported.',
        '_shape': ('Old School: three symbols and a question mark, three candidates, click the one '
                   'that completes the sequence; a wrong answer shifts the tunnels.'),
        'tile': TILE, 'cols': COLS, 'tiles': TILES,
        'puzzles': [dict(why=p['why'], seq=p['seq'], answer=p['answer'], wrong=p['wrong'],
                         slot=p['slot'],
                         candidates=[p['wrong'][0], p['wrong'][1]][:p['slot']] + [p['answer']]
                                    + [p['wrong'][0], p['wrong'][1]][p['slot']:])
                    for p in PUZZLES],
    }, open(SPEC, 'w', newline=''), indent=2)

    # ---- repack, the same rules as tools/genbarrowschest.py
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

    print('%s: %d tiles in a %dx%d sheet (%d colours), %d puzzles, answer slots %s'
          % (IFACE, len(TILES), sheet.width, sheet.height, len(palette), len(PUZZLES), slots))
    print('   %d components, ids %d..%d' % (len(names), min(mine), max(mine)))


main()
