#!/usr/bin/env python3
"""Generate scripts/skill_construction/scripts/poh_combat_ring.rs2 from the template squares.

WHY GENERATED. The combat ring is not one loc on one hotspot. The template lays 43 hotspot
placements in the Combat room - a 6x6 wall perimeter with floor mats inside it - and building a
ring has to put a piece on every one of them, each with that tile's own shape and rotation. Four
ring types times up to 36 tiles is a table nobody should type, and one that has to agree with the
map exactly or a rope hangs in mid-air.

WHAT THE HOTSPOTS ARE. Nineteen distinct locs, and their MODELS say what each is for - matched by
size against the pieces in poh.loc rather than guessed:

  1785-byte wall models  the ring wall, 20 tiles: four corners (wall_squarecorner) and sixteen
                         straights (wall_straight)
  577-byte mat models    the four corner mats
  335-byte mat models    the eight side mats
  45-byte mat model      the four middle mats
  18-byte models         EMPTY. Three of the nineteen are zero-length .ob2 files, so they render
                         nothing and cannot be clicked. They are not hotspots at all, they are
                         placement targets: loc474_15285's three tiles are where the balance beam
                         goes, and loc474_15283/15284's four are OSRS's Ranging pedestals, which
                         this cache has no art for. That is why the Combat room looked like it had
                         nineteen dead hotspots when it really has sixteen.

The geometric reading and the cache's own grouping are cross-checked against each other below: if
the corner mats are not exactly the four interior corners, this refuses to write.

ROTATION. The table is in TEMPLATE space and the rotation is done at runtime, because a room can
be built at any of four rotations. The arithmetic is the engine's own, transcribed from
GameMap.rotateZoneX/Z and the newAngle line beside them:

    rot 0 (x, z)   rot 1 (z, 7-x)   rot 2 (7-x, 7-z)   rot 3 (7-z, x)      angle = (angle + rot) & 3

    python3 tools/gencombatring.py
"""
import os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = 'scripts/skill_construction/scripts/poh_combat_ring.rs2'
ZONE = 28          # the Combat room's template zone, from poh_rooms.enum poh_room_zone val=11,28
SQUARES = [('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))]

# Which piece goes on which kind of tile. All four ring types use the same 36 tiles; the balance
# beam uses three of the seven invisible ones.
#
# BOXING'S FOUR WALL LOCS are one model and three recolours - white and "corner" are byte-identical,
# red and blue recolour the rope. Which tile wears which is recorded nowhere in the cache, so this
# is an INFERENCE from what a boxing ring actually looks like: a red corner and a blue corner
# opposite each other, the other two neutral, white rope between them. If it looks wrong in game,
# swap names in this table and nothing else changes.
RINGS = {
    'boxing': {
        'corner': {(1, 1): 'poh_boxing_ringwall_red', (6, 6): 'poh_boxing_ringwall_blue',
                   (6, 1): 'poh_boxing_ringwall_corner', (1, 6): 'poh_boxing_ringwall_corner'},
        'wall': 'poh_boxing_ringwall_white',
        'mat_corner': 'poh_boxing_ring_mat_corner',
        'mat_side': 'poh_boxing_ring_mat_side',
        'mat_middle': 'poh_boxing_ring_mat_middle',
    },
    'fencing': {
        'corner': {}, 'wall': 'poh_fencing_ringwall',
        'mat_corner': 'poh_fencing_ring_mat_corner',
        'mat_side': 'poh_fencing_ring_mat_side',
        'mat_middle': 'poh_fencing_ring_mat_middle',
    },
    'combat': {
        'corner': {}, 'wall': 'poh_combat_ringwall',
        'mat_corner': 'poh_combat_mat_corner',
        'mat_side': 'poh_combat_mat_side',
        'mat_middle': 'poh_combat_mat_middle',
    },
}
# west to east along the beam's row
BEAM = ['poh_balancebeam_endl', 'poh_balancebeam_middle', 'poh_balancebeam_endr']

SHAPE = {0: 'wall_straight', 3: 'wall_squarecorner', 22: 'grounddecor'}


def read(p):
    return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')


def crlf(p):
    raw = open(os.path.join(ROOT, p), 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2


def write(p, lines):
    path = os.path.join(ROOT, p)
    nl = '\r\n' if (os.path.exists(path) and crlf(p)) else '\n'
    open(path, 'wb').write((nl.join(lines).rstrip('\r\n') + nl).encode('utf-8'))


def templates():
    """Every Combat ring space placement in template space, from all six styles."""
    packname = {}
    for l in read('pack/loc.pack').split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            packname[int(i)] = n
    tl, cur = {}, None
    for l in read('scripts/skill_construction/configs/poh_templates.loc').split('\n'):
        l = l.strip()
        m = re.match(r'^\[(\w+)\]$', l)
        if m:
            cur = m.group(1); tl[cur] = {}
        elif cur and '=' in l:
            k, v = l.split('=', 1)
            tl[cur].setdefault(k, v)
    per = {}
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
            lid = int(p[0])
            shape = int(p[1]) if len(p) > 1 else 10
            angle = int(p[2]) if len(p) > 2 else 0
            n = packname.get(lid)
            if lv in levels and (x // 8) * 8 + (z // 8) == ZONE \
                    and (tl.get(n, {}).get('name')) == 'Combat ring space':
                per.setdefault((sq, lv), []).append((n, x % 8, z % 8, shape, angle))
    return per, tl


def main():
    per, tl = templates()
    err = []
    sigs = {k: sorted((r[1], r[2], r[3], r[4]) for r in v) for k, v in per.items()}
    base_key = ('m29_79', 0)
    for k, v in sigs.items():
        if v != sigs[base_key]:
            err.append('%s lays the ring differently from %s' % (k, base_key))
    rows = sorted(per[base_key])

    # empty models are placement targets, not hotspots
    empty, visible = set(), set()
    for n, _, _, _, _ in rows:
        mdl = (tl[n].get('model') or '').split(',')[0]
        sizes = [os.path.getsize(os.path.join(ROOT, 'models/loc', f))
                 for f in os.listdir(os.path.join(ROOT, 'models/loc'))
                 if f.startswith(mdl + '_') and f.endswith('.ob2')]
        (empty if sizes and max(sizes) <= 32 else visible).add(n)

    walls = [r for r in rows if r[3] in (0, 3) and r[0] in visible]
    mats = [r for r in rows if r[3] == 22]
    spare = [r for r in rows if r[0] in empty]
    # The beam is the invisible group whose tiles are three in an unbroken line; the pedestals are
    # four scattered points. Counting three is not enough - two of the groups have three tiles.
    def collinear(ts):
        ts = sorted(ts)
        xs = {t[0] for t in ts}; zs = {t[1] for t in ts}
        return (len(xs) == 1 and sorted(zs) == list(range(min(zs), min(zs) + 3))) or \
               (len(zs) == 1 and sorted(xs) == list(range(min(xs), min(xs) + 3)))
    beam_locs = {r[0] for r in spare
                 if collinear({(s[1], s[2]) for s in spare if s[0] == r[0]})}
    beam = sorted([r for r in spare if r[0] in beam_locs], key=lambda r: (r[2], r[1]))
    pedestals = [r for r in spare if r[0] not in beam_locs]

    # the ring's own bounds, measured rather than assumed
    xs = [r[1] for r in walls]; zs = [r[2] for r in walls]
    x0, x1, z0, z1 = min(xs), max(xs), min(zs), max(zs)
    if (x1 - x0, z1 - z0) != (5, 5):
        err.append('the wall perimeter is %dx%d, not 6x6' % (x1 - x0 + 1, z1 - z0 + 1))
    if len(walls) != 20:
        err.append('%d perimeter tiles, and a 6x6 ring has 20' % len(walls))
    if len(mats) != 16:
        err.append('%d mat tiles, and the inside of a 6x6 ring is 16' % len(mats))
    if len(beam) != 3:
        err.append('the balance beam is %d tiles, and there are three beam locs' % len(beam))

    # geometry and the cache's own grouping have to agree about which mat is which
    corners = {(x0 + 1, z0 + 1), (x1 - 1, z0 + 1), (x0 + 1, z1 - 1), (x1 - 1, z1 - 1)}
    middles = {(x, z) for x in (x0 + 2, x1 - 2) for z in (z0 + 2, z1 - 2)}
    kind = {}
    for n, x, z, shape, angle in mats:
        kind[(x, z)] = 'mat_corner' if (x, z) in corners else \
                       'mat_middle' if (x, z) in middles else 'mat_side'
    bygroup = collections.defaultdict(set)
    for n, x, z, shape, angle in mats:
        bygroup[n].add(kind[(x, z)])
    bad = {n: k for n, k in bygroup.items() if len(k) != 1}
    if bad:
        err.append('a mat hotspot loc covers two kinds of tile: %s' % bad)

    if err:
        print('\n'.join('  ERROR ' + e for e in err))
        sys.exit(1)

    def lay(x, z, angle, loc, shape):
        proc = {'wall_straight': 'poh_ring_wall', 'wall_squarecorner': 'poh_ring_corner',
                'grounddecor': 'poh_ring_mat'}[SHAPE[shape]]
        return '~%s($base, $rot, %d, %d, %d, %s);' % (proc, x, z, angle, loc)

    o = ['// The Combat room\'s ring: four things to build, and 36 tiles under each of them.',
         '//',
         '// GENERATED by tools/gencombatring.py from the six template squares. Do not edit by hand -',
         '// every tile, shape and rotation below is the template\'s own, and the generator refuses to',
         '// write if the six styles ever stop agreeing about where the ring is.',
         '//',
         '// A ring is ONE piece of furniture standing on 36 tiles, which is not something the furniture',
         '// system could express: ~poh_furn_show has one loc_add per item. It goes through the "show"',
         '// hand-off in tools/furnspec.json instead - the same door the portal frames use - and the',
         '// piece is anchored at the room\'s local (0,0) rather than at the tile that was clicked, so',
         '// that whichever of the sixteen hotspots you click, the ring is stored, found and removed in',
         '// the same place. Nothing is ever built at (0,0): the ring starts at (1,1).',
         '//',
         '// THE ROTATION IS DONE HERE, not baked in, because a room can be built at any of four',
         '// rotations. ~poh_ring_tile and ~poh_ring_angle are transcriptions of the engine\'s own',
         '// GameMap.rotateZoneX/rotateZoneZ and the newAngle line beside them.',
         '', '// =========================================================================== the arithmetic', '',
         '[proc,poh_ring_tile](coord $base, int $rot, int $x, int $z)(coord)',
         'switch_int ($rot) {',
         '    case 1 : return(movecoord($base, $z, 0, calc(7 - $x)));',
         '    case 2 : return(movecoord($base, calc(7 - $x), 0, calc(7 - $z)));',
         '    case 3 : return(movecoord($base, calc(7 - $z), 0, $x));',
         '    case default : return(movecoord($base, $x, 0, $z));',
         '}', '',
         '[proc,poh_ring_angle](int $angle, int $rot)(int)',
         'return(modulo(calc($angle + $rot), 4));', '',
         '// One per shape, because the shape decides the LAYER a loc goes on and a proc cannot take',
         '// a locshape. Getting one wrong leaves the hotspot standing in the same tile as the piece.',
         '[proc,poh_ring_wall](coord $base, int $rot, int $x, int $z, int $angle, loc $loc)',
         'loc_add(~poh_ring_tile($base, $rot, $x, $z), $loc, ~poh_ring_angle($angle, $rot), wall_straight, ^poh_loc_duration);', '',
         '[proc,poh_ring_corner](coord $base, int $rot, int $x, int $z, int $angle, loc $loc)',
         'loc_add(~poh_ring_tile($base, $rot, $x, $z), $loc, ~poh_ring_angle($angle, $rot), wall_squarecorner, ^poh_loc_duration);', '',
         '[proc,poh_ring_mat](coord $base, int $rot, int $x, int $z, int $angle, loc $loc)',
         'loc_add(~poh_ring_tile($base, $rot, $x, $z), $loc, ~poh_ring_angle($angle, $rot), grounddecor, ^poh_loc_duration);', '',
         '// =========================================================================== the four rings', '']

    for key in ('boxing', 'fencing', 'combat'):
        r = RINGS[key]
        o.append('[proc,poh_ring_%s](coord $base, int $rot)' % key)
        for n, x, z, shape, angle in sorted(walls, key=lambda t: (t[3], t[2], t[1])):
            loc = r['corner'].get((x, z), r['wall']) if shape == 3 else r['wall']
            o.append(lay(x, z, angle, loc, shape))
        for n, x, z, shape, angle in sorted(mats, key=lambda t: (t[2], t[1])):
            o.append(lay(x, z, angle, r[kind[(x, z)]], shape))
        o.append('')

    o.append('// The beam is three tiles of the seven the template keeps blank inside the ring. The other')
    o.append('// four are OSRS\'s Ranging pedestals, and this cache has no art for them.')
    o.append('[proc,poh_ring_beam](coord $base, int $rot)')
    for (n, x, z, shape, angle), loc in zip(beam, BEAM):
        o.append(lay(x, z, angle, loc, shape))
    o.append('')

    o += ['// =========================================================================== show and remove', '',
          '// $base is the room\'s local (0,0) - the anchor the piece is stored at - so the whole ring is',
          '// laid from it without needing to know which hotspot was clicked.',
          '[proc,poh_combat_ring_place](coord $base, int $angle, int $tier)',
          'def_int $rot = ~poh_ring_room_rot($base);',
          'switch_int ($tier) {',
          '    case 1 : ~poh_ring_boxing($base, $rot);',
          '    case 2 : ~poh_ring_fencing($base, $rot);',
          '    case 3 : ~poh_ring_combat($base, $rot);',
          '    case 4 : ~poh_ring_beam($base, $rot);',
          '}', '',
          '// The room a coord is in, and how that room was turned. The ring is laid in template space',
          '// and turned to match, so this is the only thing the table needs from the house.',
          '[proc,poh_ring_room_rot](coord $spot)(int)',
          'if (%poh_instance = null) {',
          '    return(0);',
          '}',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'return(~poh_room_rot(calc(divide($gx, 8) - ^poh_grid_origin), calc(divide($gz, 8) - ^poh_grid_origin)));', '',
          '// Taking one out. Any tile of the ring is a valid click, so the slot is looked up at the',
          '// anchor rather than under the piece that was clicked - which is the whole reason for the',
          '// anchor. ~poh_furn_relay then re-lays the room, which clears all 36 locs at once.',
          '[proc,poh_combat_ring_remove]',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {',
          '    return;',
          '}',
          'def_int $gx = calc(coordx(loc_coord) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz(loc_coord) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $slot = ~poh_furn_at($rx, $rz, 0, 0);',
          'if ($slot < 0) {',
          '    mes("That isn\'t yours to take out.");',
          '    return;',
          '}',
          'def_int $item = ~poh_furn_item(~poh_furn_get($slot));',
          'def_int $option = ~p_choice2("Take out the <enum(int, string, poh_furn_name, $item)>.", 1, "Leave it.", 2);',
          'if ($option ! 1) {',
          '    return;',
          '}',
          '~poh_furn_set($slot, 0);',
          '~poh_furn_relay($rx, $rz);',
          'mes("You take out the <enum(int, string, poh_furn_name, $item)>.");', '',
          '// =========================================================================== the triggers', '']

    allocs = sorted({r['wall'] for r in RINGS.values()}
                    | {v for r in RINGS.values() for v in r['corner'].values()}
                    | {r[k] for r in RINGS.values() for k in ('mat_corner', 'mat_side', 'mat_middle')}
                    | set(BEAM))
    # genfurn.py already wires the family's four PIECE locs to ~poh_combat_ring_remove (the
    # "remove" key in furnspec.json). Wiring them here too is a duplicate trigger, which does not
    # compile - so this file covers only the other locs the ring puts down.
    import json as _json
    claimed = set()
    for _f in _json.load(open(os.path.join(ROOT, 'tools/furnspec.json')))['families']:
        if _f['key'] == 'combat_ring':
            claimed = {_p['loc'] for _p in _f['pieces']}
    for loc in allocs:
        if loc in claimed:
            continue
        o.append('[oploc5,%s] ~poh_combat_ring_remove;' % loc)
    o.append('')
    o.append('// Climbing into the ring. Every ring type has the same wall op, and the wall is what you')
    o.append('// climb - the mats have no op of their own.')
    for loc in sorted({r['wall'] for r in RINGS.values()}
                      | {v for r in RINGS.values() for v in r['corner'].values()}):
        o.append('[oploc1,%s] ~poh_ring_climb;' % loc)
    o.append('')
    for loc in BEAM:
        o.append('[oploc1,%s] ~poh_ring_beam_stand;' % loc)
    for loc in BEAM:
        o.append('[oploc4,%s] ~poh_ring_beam_down;' % loc)
    o.append('')
    write(OUT, o)
    print('%s: %d perimeter tiles, %d mats, %d beam tiles, %d pedestal tiles with no art'
          % (OUT, len(walls), len(mats), len(beam), len(pedestals)))
    print('  %d locs wired for Remove, %d rings + the beam' % (len(allocs), len(RINGS)))


main()
