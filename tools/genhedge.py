#!/usr/bin/env python3
"""Generate scripts/skill_construction/scripts/poh_hedge.rs2 from the template squares.

The Formal garden's perimeter is TWO hotspots on the same twenty tiles, not one. Fencing sits on
the wall boundary (shapes 0 and 2, the wall layer); Hedging stands on the tile itself (shape 10),
so a garden can have both, which is what OSRS does. The fence shipped with the formal garden round;
this is the hedge.

WHICH PIECE GOES ON WHICH TILE is named by the hotspots, and the cache agrees. Three Hedging
hotspots are placed, and their models are:

   loc474_15370  248v/484f   116 x 64   two bushes, a straight run
   loc474_15371  248v/484f   116 x 64   two bushes, the mirror of it
   loc474_15372  124v/243f    76 x 80   one bush, offset into a corner

and THE FIRST TIER'S THREE PIECES ARE THOSE SAME THREE MODELS, vertex for vertex and box for box -
the thorny hedge is bare branches, which is what a ghost is. That is the cross-check this refuses
to write without, and it is what says the triple in poh.loc is ordered (15370, corner, 15371)
rather than assumed to be.

The other six tiers follow that order, and two of them prove it twice: the small box hedge and the
tall box hedge are the same three models at two heights, and so are the fancy hedge and the tall
fancy hedge. Both pairs come out small-then-tall under the file order, which is also the level
order, and that is not something a wrong ordering would give you.

Two tiers - the topiary and the tall fancy hedge - use ONE model for all three kinds, and say so in
poh.loc by pointing three locs at it. A lollipop tree looks the same on a corner.

    python3 tools/genhedge.py
"""
import os, re, sys, struct, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = 'scripts/skill_construction/scripts/poh_hedge.rs2'
SQUARES = [('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))]
ROOM = 'Formal garden'
HOTSPOT = 'Hedging'

# tier -> its three locs, in poh.loc file order, which is (kind 0, corner, kind 1). CHECKED below
# against the hotspot geometry rather than trusted.
TIERS = [
    ('thorny',     ['loc_13456', 'loc_13457', 'loc_13458']),
    ('nice',       ['loc_13459', 'loc_13460', 'loc_13461']),
    ('small box',  ['loc_13462', 'loc_13463', 'loc_13464']),
    ('topiary',    ['loc_13465', 'loc_13466', 'loc_13467']),
    ('fancy',      ['loc_13468', 'loc_13469', 'loc_13470']),
    ('tall fancy', ['loc_13471', 'loc_13472', 'loc_13473']),
    ('tall box',   ['loc_13474', 'loc_13475', 'loc_13476']),
]
# the ghost each kind is named by, in the same order as a tier's triple
GHOST = ['loc474_15370', 'loc474_15372', 'loc474_15371']
KINDS = ['a', 'corner', 'b']


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


def modelfile(model):
    d = os.path.join(ROOT, 'models/loc')
    fs = [f for f in os.listdir(d) if f.startswith(model + '_') and f.endswith('.ob2')]
    return os.path.join(d, sorted(fs)[0]) if fs else None


def geometry(model):
    """(vertices, faces) of a loc model, from the 377 .ob2 footer."""
    p = modelfile(model or '')
    if not p:
        return None
    b = open(p, 'rb').read()
    if len(b) < 18:
        return None
    v, f, _ = struct.unpack_from('>HHB', b, len(b) - 18)
    return (v, f)


def box(model):
    """(width in x, width in z) of a loc model - what tells a corner from a straight."""
    p = modelfile(model or '')
    if not p:
        return None
    sys.path.insert(0, os.path.join(ROOT, 'tools'))
    from ob2render import Model
    m = Model(p)
    return (max(m.vx) - min(m.vx), max(m.vz) - min(m.vz))


def main():
    P = cfg('scripts/skill_construction/configs/poh.loc')
    T = cfg('scripts/skill_construction/configs/poh_templates.loc')
    packname = {}
    for l in read('pack/loc.pack').split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            packname[int(i)] = n
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
    for tname, locs in TIERS:
        for l in locs:
            if l not in P:
                err.append('%s: %s is not in poh.loc' % (tname, l))
            elif P[l].get('name') != 'Hedge':
                err.append('%s: %s is called %r, not Hedge' % (tname, l, P[l].get('name')))
            elif 'Remove' not in (P[l].get('op5') or ''):
                err.append('%s: %s has no op5=Remove' % (tname, l))
    # THE CROSS-CHECK: tier 1's three pieces are the three ghosts, which is what names the kinds
    gg = [(geometry(g), box(g)) for g in GHOST]
    t1 = [(geometry((P[l].get('model') or '').split(',')[0]),
           box((P[l].get('model') or '').split(',')[0])) for l in TIERS[0][1]]
    if t1 != gg:
        err.append('the thorny hedge is %s but the ghosts are %s - the kind order is not confirmed'
                   % (t1, gg))
    # ...and in every other tier the corner is the one whose footprint is squarest, which is the
    # same thing said without reference to tier 1.
    for tname, locs in TIERS:
        boxes = [box((P[l].get('model') or '').split(',')[0]) for l in locs]
        if len(set(boxes)) == 1:
            continue            # one model for all three kinds - the topiary and the tall fancy
        squarest = min(range(3), key=lambda i: abs(boxes[i][0] - boxes[i][1]))
        if squarest != 1:
            err.append('%s: the corner-shaped piece is #%d, not the middle one: %s'
                       % (tname, squarest, boxes))
    if err:
        print('\n'.join('  ERROR ' + e for e in err)); sys.exit(1)

    # every hedging tile, from every style square, and they all have to agree
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
            if lv not in levels:
                continue
            if roomname.get(zone2room.get((x // 8) * 8 + (z // 8))) != ROOM:
                continue
            if T.get(n, {}).get('name') != HOTSPOT:
                continue
            shape = int(p[1]) if len(p) > 1 else 10
            angle = int(p[2]) if len(p) > 2 else 0
            if shape != 10:
                err.append('%s (%d,%d) is shape %d, not the ground layer' % (sq, x, z, shape))
            per[(sq, lv)][(x % 8, z % 8)] = (GHOST.index(n), angle)
    sigs = {k: sorted(v.items()) for k, v in per.items()}
    if not sigs:
        err.append('no Hedging hotspots found in the %s' % ROOM)
    else:
        first = sorted(sigs)[0]
        bad = [k for k, v in sigs.items() if v != sigs[first]]
        if bad:
            err.append('the hedge is laid differently in %s' % bad)
    if err:
        print('\n'.join('  ERROR ' + e for e in err)); sys.exit(1)
    rows = sorted(per[sorted(sigs)[0]].items())
    if len(rows) != 20:
        print('  ERROR the hedge is %d tiles, not 20' % len(rows)); sys.exit(1)
    ncorner = sum(1 for _, (k, _) in rows if k == 1)
    if ncorner != 4:
        print('  ERROR %d corner tiles, not 4' % ncorner); sys.exit(1)

    import json
    spec = json.load(open(os.path.join(ROOT, 'tools/furnspec.json')))
    fam = {f['key']: f for f in spec['families']}.get('hedge')
    if fam is None:
        print('  ERROR furnspec.json has no hedge family yet'); sys.exit(1)
    A = fam['anchor']
    if len(fam['pieces']) != len(TIERS):
        print('  ERROR furnspec has %d hedge tiers, this has %d'
              % (len(fam['pieces']), len(TIERS))); sys.exit(1)
    for pc, (tname, locs) in zip(fam['pieces'], TIERS):
        if pc['loc'] != locs[0]:
            print('  ERROR furnspec shows %s for the %s hedge, the triple starts %s'
                  % (pc['loc'], tname, locs[0])); sys.exit(1)

    o = ['// Hedging: the Formal garden\'s other perimeter.',
         '//',
         '// GENERATED by tools/genhedge.py from the six template squares and tools/furnspec.json.',
         '// Do not edit by hand.',
         '//',
         '// The garden\'s twenty perimeter tiles carry TWO hotspots, not one. Fencing sits on the wall',
         '// boundary and the hedge stands on the tile, so a garden can have both - which is what OSRS',
         '// does, and why the fence round\'s twenty tiles and these twenty are the same twenty.',
         '//',
         '// Seven tiers, three pieces each: two straights and a corner, named by the three hotspot',
         '// ghosts, which the thorny hedge\'s own three models match vertex for vertex. Like the rugs',
         '// and the fence this is one piece over many tiles, so it goes through the "show" hand-off',
         '// and an anchor, and shares ~poh_ring_tile / ~poh_ring_angle out of poh_combat_ring.rs2.',
         '//',
         '// THE ANCHOR IS IN furnspec.json AND NOWHERE ELSE - (%d, %d), which carries no hotspot in' % (A[0], A[1]),
         '// the formal garden and is not the fence\'s, so a garden can store one of each.',
         '',
         '[proc,poh_hedge_loc](int $tier, int $kind)(loc)',
         'switch_int (calc($tier * 3 + $kind)) {']
    for ti, (tname, locs) in enumerate(TIERS):
        for ki, loc in enumerate(locs):
            o.append('    case %d : return(%s);   // %s hedge, %s' % (ti * 3 + ki, loc, tname, KINDS[ki]))
    o += ['    case default : return(null);', '}', '',
          '[proc,poh_hedge_lay](coord $base, int $rot, int $x, int $z, int $angle, int $tier, int $kind)',
          'loc_add(~poh_ring_tile($base, $rot, $x, $z), ~poh_hedge_loc($tier, $kind), '
          '~poh_ring_angle($angle, $rot), centrepiece_straight, ^poh_loc_duration);', '',
          '[proc,poh_hedge_place](coord $spot, int $angle, int $tier)',
          'def_coord $base = movecoord($spot, %d, 0, %d);' % (-A[0], -A[1]),
          'def_int $rot = ~poh_ring_room_rot($base);']
    for (x, z), (kind, angle) in rows:
        o.append('~poh_hedge_lay($base, $rot, %d, %d, %d, $tier, ^poh_hedge_%s);'
                 % (x, z, angle, KINDS[kind]))
    o += ['',
          '[proc,poh_hedge_remove]',
          '~poh_decor_remove(%d, %d);' % (A[0], A[1]), '',
          '// The seven pieces furnspec NAMES are wired by genfurn.py, which emits one [oploc5] per',
          '// buildable loc and reads the family\'s own "remove" for the proc. These are the other',
          '// fourteen - the corner and the second straight of each tier, which are not in the spec',
          '// because the build window only ever shows one of the three. A trigger declared twice',
          '// does not compile, so the split has to be exact; battery group 63 checks both halves.']
    claimed = {pc['loc'] for pc in fam['pieces']}
    for tname, locs in TIERS:
        for loc in locs:
            if loc not in claimed:
                o.append('[oploc5,%s] ~poh_hedge_remove;' % loc)
    write(OUT, o)
    print('%s: %d tiles, %d corners, %d tiers x 3 pieces' % (OUT, len(rows), ncorner, len(TIERS)))
    print('  kinds confirmed against the ghosts: %s' % dict(zip(KINDS, [g[1] for g in gg])))
    print('  anchor from furnspec: %s' % (tuple(A),))


if __name__ == '__main__':
    main()
