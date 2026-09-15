#!/usr/bin/env python3
"""Generate scripts/skill_construction/scripts/poh_rug.rs2 from the template squares.

A rug is one piece of furniture covering a whole rectangle of floor - 36 tiles in the Skill hall
and the Quest hall, 24 in the Bedroom, 16 in the Parlour, 10 in the Chapel. Like the combat ring,
that is not something ~poh_furn_show can express, so it goes through the "show" hand-off and the
piece is anchored at one tile of the room rather than at the tile that was clicked.

WHICH PIECE GOES ON WHICH TILE is the rectangle's own geometry - corners, edges, middle - and the
hotspot ghosts agree exactly. Every rug hotspot's model is one of three:

    4 vertices,  2 faces    a plain square          the middle
   54 vertices, 76 faces    a fringed straight edge the side
   45 vertices, 63 faces    a fringed L             the corner

and the FIRST TIER'S THREE PIECES ARE THOSE SAME THREE MODELS, vertex for vertex. That is the
cross-check this refuses to write without: geometry and the cache have to say the same thing.

The Quest hall is the odd one - its four corner hotspots are zero-length models, so they render
nothing and cannot be clicked. They are placement targets, exactly like the balance beam's tiles
in the combat room; the rug still has corners there, you just start it from a side tile.

    python3 tools/genrugs.py
"""
import os, re, sys, struct, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = 'scripts/skill_construction/scripts/poh_rug.rs2'
SQUARES = [('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))]

# tier -> (corner, side, middle). Read out of poh.loc in file order and then CHECKED against the
# hotspot geometry below, which is what says the order is corner/side/middle rather than assumed.
TIERS = [('brown', ['loc_13588', 'loc_13589', 'loc_13590']),
         ('plain', ['loc_13591', 'loc_13592', 'loc_13593']),
         ('opulent', ['loc_13594', 'loc_13595', 'loc_13596'])]
KINDS = ['corner', 'side', 'middle']


def read(p):
    return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')


def crlf(p):
    raw = open(os.path.join(ROOT, p), 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2


def write(p, lines):
    path = os.path.join(ROOT, p)
    nl = '\r\n' if (os.path.exists(path) and crlf(p)) else '\n'
    open(path, 'wb').write((nl.join(lines).rstrip('\r\n') + nl).encode('utf-8'))


def cfg(path):
    out, cur = {}, None
    for l in read(path).split('\n'):
        l = l.strip()
        m = re.match(r'^\[(\w+)\]$', l)
        if m:
            cur = m.group(1); out[cur] = {}
        elif cur and '=' in l and not l.startswith('//'):
            k, v = l.split('=', 1)
            out[cur].setdefault(k, v)
    return out


def geometry(model):
    """(vertices, faces) of a loc model, from the 377 .ob2 footer."""
    if not model:
        return None
    d = os.path.join(ROOT, 'models/loc')
    fs = [f for f in os.listdir(d) if f.startswith(model + '_') and f.endswith('.ob2')]
    if not fs:
        return None
    b = open(os.path.join(d, sorted(fs)[0]), 'rb').read()
    if len(b) < 18:
        return None
    v, f, _ = struct.unpack_from('>HHB', b, len(b) - 18)
    return (v, f)


def main():
    P = cfg('scripts/skill_construction/configs/poh.loc')
    T = cfg('scripts/skill_construction/configs/poh_templates.loc')
    packname = {}
    for l in read('pack/loc.pack').split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            packname[int(i)] = n
    packid = {v: k for k, v in packname.items()}
    zone2room, roomname = {}, {}
    sec = None
    for l in read('scripts/skill_construction/configs/poh_rooms.enum').split('\n'):
        l = l.strip()
        if l.startswith('['):
            sec = l[1:-1]; continue
        if l.startswith('val='):
            a, b = l[4:].split(',', 1)
            if sec == 'poh_room_zone':
                zone2room[int(b)] = int(a)
            if sec == 'poh_room_name':
                roomname[int(a)] = b

    err = []
    # the three hotspot geometries, and which kind each is
    hotgeo = {}
    for n, d in T.items():
        if d.get('name') == 'Rug space':
            hotgeo[n] = geometry((d.get('model') or '').split(',')[0])
    shapes = {g for g in hotgeo.values() if g and g != (0, 0)}
    if len(shapes) != 3:
        err.append('expected three rug hotspot geometries, found %s' % sorted(shapes))
    # tier 1's pieces ARE the ghosts - that is what names the kinds
    t1 = [geometry((P[l].get('model') or '').split(',')[0]) for l in TIERS[0][1]]
    if sorted(x for x in t1 if x) != sorted(shapes):
        err.append('tier 1 is %s but the hotspots are %s - the kind order is not confirmed'
                   % (t1, sorted(shapes)))
    KINDGEO = dict(zip(KINDS, t1))

    # every rug tile, per room, from every style square
    per = collections.defaultdict(dict)
    for sq, levels in SQUARES:
        sec = None
        for l in read('maps/%s.jm2' % sq).split('\n'):
            if l.startswith('===='):
                sec = l.strip('= '); continue
            if sec != 'LOC' or ':' not in l:
                continue
            head, rest = l.split(':', 1)
            lv, x, z = (int(v) for v in head.split())
            p = rest.split()
            n = packname.get(int(p[0]))
            room = roomname.get(zone2room.get((x // 8) * 8 + (z // 8)))
            if lv in levels and room and T.get(n, {}).get('name') == 'Rug space':
                angle = int(p[2]) if len(p) > 2 else 0
                key = (sq, lv, room)
                per[key][(x % 8, z % 8)] = (n, angle)
    byroom = collections.defaultdict(list)
    for (sq, lv, room), tiles in per.items():
        byroom[room].append(((sq, lv), tiles))
    rooms = {}
    for room, entries in byroom.items():
        sigs = {k: sorted((t, v[1]) for t, v in tiles.items()) for k, tiles in entries}
        first = sorted(sigs)[0]
        for k, v in sigs.items():
            if v != sigs[first]:
                err.append('%s lays its rug differently in %s and %s' % (room, first, k))
        rooms[room] = dict(entries[0][1])

    # the rectangle, and the kind of every tile in it
    laid = {}
    for room, tiles in sorted(rooms.items()):
        xs = [t[0] for t in tiles]; zs = [t[1] for t in tiles]
        x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
        if len(tiles) != (x1 - x0 + 1) * (z1 - z0 + 1):
            err.append('%s: %d rug tiles is not the %dx%d rectangle they span'
                       % (room, len(tiles), x1 - x0 + 1, z1 - z0 + 1))
        rows = []
        for (x, z), (n, angle) in sorted(tiles.items()):
            edge_x = x in (x0, x1)
            edge_z = z in (z0, z1)
            kind = 'corner' if (edge_x and edge_z) else ('side' if (edge_x or edge_z) else 'middle')
            g = hotgeo.get(n)
            # the ghost has to agree, unless it is one of the empty ones
            if g and g != (0, 0) and g != KINDGEO[kind]:
                err.append('%s (%d,%d): geometry says %s, the rectangle says %s' % (room, x, z, g, kind))
            rows.append((x, z, angle, kind))
        laid[room] = rows

    if err:
        print('\n'.join('  ERROR ' + e for e in err))
        sys.exit(1)

    ROOMKEY = {r: [k for k, v in roomname.items() if v == r][0] for r in laid}
    o = ['// Rugs: one piece of furniture over a whole rectangle of floor.',
         '//',
         '// GENERATED by tools/genrugs.py from the six template squares. Do not edit by hand.',
         '//',
         '// Five rooms have a Rug space and they are different sizes - 36 tiles in the Skill hall and',
         '// the Quest hall, 24 in the Bedroom, 16 in the Parlour, 10 in the Chapel - so the room has to',
         '// be looked up before anything is laid. Which piece goes on which tile is the rectangle\'s own',
         '// geometry, and the hotspot ghosts agree exactly: the first tier\'s three pieces ARE the three',
         '// ghost models, vertex for vertex, which is what names corner, side and middle rather than',
         '// leaving it to a guess. The generator refuses to write if the two ever stop agreeing.',
         '//',
         '// The rotation is done at runtime by ~poh_ring_tile and ~poh_ring_angle, which are the engine\'s',
         '// own zone maths (poh_combat_ring.rs2). Rugs and rings are the same problem and share it.',
         '', '// =========================================================================== the pieces', '',
         '[proc,poh_rug_loc](int $tier, int $kind)(loc)',
         'switch_int (calc($tier * 4 + $kind)) {']
    for ti, (tname, locs) in enumerate(TIERS, start=1):
        for ki, kind in enumerate(KINDS):
            o.append('    case %d : return(%s);   // %s %s' % (ti * 4 + ki, locs[ki], tname, kind))
    o += ['    case default : return(null);', '}', '',
          '[proc,poh_rug_lay](coord $base, int $rot, int $x, int $z, int $angle, int $tier, int $kind)',
          'loc_add(~poh_ring_tile($base, $rot, $x, $z), ~poh_rug_loc($tier, $kind), '
          '~poh_ring_angle($angle, $rot), grounddecor, ^poh_loc_duration);', '',
          '// =========================================================================== the rooms', '']
    for room, rows in sorted(laid.items()):
        key = re.sub(r'\W+', '_', room.lower())
        o.append('// %s: %d tiles' % (room, len(rows)))
        o.append('[proc,poh_rug_%s](coord $base, int $rot, int $tier)' % key)
        for x, z, angle, kind in rows:
            o.append('~poh_rug_lay($base, $rot, %d, %d, %d, $tier, ^poh_rug_%s);' % (x, z, angle, kind))
        o.append('')
    o += ['// =========================================================================== show and remove', '',
          '// The piece is stored at the anchor, ^poh_rug_anchor - the one tile of these five rooms that',
          '// carries no hotspot in any of them, so a rug and a statue can never want the same slot.',
          '// The tables below are in TEMPLATE coordinates, which start at the zone\'s own (0,0), so the',
          '// first thing to do is step back from the anchor to that corner. The anchor offset is in',
          '// instance space and does not turn with the room, which is why this subtraction is flat.',
          '[proc,poh_rug_place](coord $spot, int $angle, int $tier)',
          'def_coord $base = movecoord($spot, calc(0 - ^poh_rug_anchor), 0, calc(0 - ^poh_rug_anchor));',
          'def_int $rot = ~poh_ring_room_rot($base);',
          'switch_int (~poh_rug_room($base)) {']
    for room in sorted(laid):
        key = re.sub(r'\W+', '_', room.lower())
        o.append('    case %d : ~poh_rug_%s($base, $rot, $tier);   // %s' % (ROOMKEY[room], key, room))
    o += ['}', '',
          '// Which room this coord is in, as a poh_rooms.enum type.',
          '[proc,poh_rug_room](coord $spot)(int)',
          'if (%poh_instance = null) {', '    return(0);', '}',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'return(~poh_room_type(calc(divide($gx, 8) - ^poh_grid_origin), calc(divide($gz, 8) - ^poh_grid_origin)));', '',
          '// Taking one out. Any tile of the rug is a valid click, so the slot is looked up at the',
          '// anchor. ~poh_furn_relay re-lays the room, which clears the whole rug at once.',
          '[proc,poh_rug_remove]',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {', '    return;', '}',
          'def_int $gx = calc(coordx(loc_coord) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz(loc_coord) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $slot = ~poh_furn_at($rx, $rz, ^poh_rug_anchor, ^poh_rug_anchor);',
          'if ($slot < 0) {', '    mes("That isn\'t yours to take out.");', '    return;', '}',
          'def_int $item = ~poh_furn_item(~poh_furn_get($slot));',
          'def_int $option = ~p_choice2("Take out the <enum(int, string, poh_furn_name, $item)>.", 1, "Leave it.", 2);',
          'if ($option ! 1) {', '    return;', '}',
          '~poh_furn_set($slot, 0);',
          '~poh_furn_relay($rx, $rz);',
          'mes("You take out the <enum(int, string, poh_furn_name, $item)>.");', '',
          '// =========================================================================== the triggers', '']
    # every piece loc except the three the family itself owns (genfurn wires those)
    import json
    fam = next((f for f in json.load(open(os.path.join(ROOT, 'tools/furnspec.json')))['families']
                if f['key'] == 'rug'), None)
    claimed = {p['loc'] for p in fam['pieces']} if fam else set()
    for tname, locs in TIERS:
        for loc in locs:
            if loc not in claimed:
                o.append('[oploc5,%s] ~poh_rug_remove;' % loc)
    o.append('')
    write(OUT, o)
    print('%s: %s' % (OUT, ', '.join('%s %d tiles' % (r, len(v)) for r, v in sorted(laid.items()))))
    print('  kinds confirmed against the ghosts: %s' % KINDGEO)


main()
