#!/usr/bin/env python3
"""Generate scripts/skill_construction/scripts/poh_decor.rs2 - three multi-tile pieces.

  the Formal garden's FENCING       20 tiles of perimeter, seven tiers, one loc each
  the Throne room's FLOOR           a 2x2 in the middle, and the art is your house style's
  the Chapel's WINDOWS              six tiles, and the art is your style's and your choice of nine

All three are one piece over several tiles, so all three go through the "show" hand-off and an
anchor, the way the combat ring and the rugs do. The tile tables and the anchors are read from the
templates and from tools/furnspec.json - the anchor is in the spec and NOWHERE ELSE, so the click
and the removal cannot drift apart.

THE WINDOWS ARE THE INTERESTING ONE. poh_dynamic_window is the shell the templates place 116 times
per house, and its children are the 54 windows - six styles times nine glazings. The children carry
op5=Remove, a multiloc shell shows its active child's ops, and NOTHING ANSWERED IT: every window in
every house has had a Remove that did nothing since the shell was resolved. Both ends are answered
here. A window on a chapel Window space is a piece of furniture and comes out; a window in the wall
of any other room is part of the house and says so.

Building one also sets %poh_window, so the whole house reglazes - which is what that varp is for
and what ~poh_window_refresh already preserves across a redecorate.

    python3 tools/gendecor.py
"""
import os, re, sys, json, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = 'scripts/skill_construction/scripts/poh_decor.rs2'
SQUARES = [('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))]
SHAPE = {0: 'wall_straight', 2: 'wall_l', 22: 'grounddecor'}

# The six styles in %poh_style order, and the town each one's art is named after. Read out of
# poh_styles.enum's own comment block, which read it out of the template squares' wall sets.
STYLE_TOWN = ['rimmington', 'lumbridge', 'pollnivneach', 'rellekka', 'brimhaven', 'yanille']
# The nine glazings, in the order poh_dynamic_window's multiloc table lists them - that order IS
# %poh_window's low digit, so it cannot be reordered here without reordering the shell.
GLAZING = ['shutters', 'bob', 'saradomin', 'guthix', 'zamorak',
           'bob2', 'saradomin2', 'guthix2', 'zamorak2']
FENCE = ['loc_13449', 'loc_13450', 'loc_13451', 'loc_13452', 'loc_13453', 'loc_13454', 'loc_13455']


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
            out[cur].setdefault(k, []).append(v)
    return out


def tiles(name, room):
    """Every placement of a named hotspot in a named room, per style square, as template tiles."""
    packname = {}
    for l in read('pack/loc.pack').split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            packname[int(i)] = n
    T = cfg('scripts/skill_construction/configs/poh_templates.loc')
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
            if roomname.get(zone2room.get((x // 8) * 8 + (z // 8))) != room:
                continue
            if (T.get(n, {}).get('name') or [''])[0] != name:
                continue
            shape = int(p[1]) if len(p) > 1 else 10
            angle = int(p[2]) if len(p) > 2 else 0
            per[(sq, lv)][(x % 8, z % 8)] = (shape, angle)
    sigs = {k: sorted(v.items()) for k, v in per.items()}
    first = sorted(sigs)[0]
    bad = [k for k, v in sigs.items() if v != sigs[first]]
    return sorted(per[first].items()), bad


def main():
    spec = json.load(open(os.path.join(ROOT, 'tools/furnspec.json')))
    fam = {f['key']: f for f in spec['families']}
    err = []
    for k in ('fence', 'thronefloor', 'chapelwindow'):
        if k not in fam:
            err.append('furnspec.json has no %s family yet' % k)
    if err:
        print('\n'.join('  ERROR ' + e for e in err)); sys.exit(1)

    fence, bad1 = tiles('Fencing', 'Formal garden')
    floor, bad2 = tiles('Floor space', 'Throne room')
    window, bad3 = tiles('Window space', 'Chapel')
    for what, bad in (('fencing', bad1), ('the throne room floor', bad2), ('the chapel windows', bad3)):
        if bad:
            err.append('%s is laid differently in %s' % (what, bad))
    if len(fence) != 20:
        err.append('the garden fence is %d tiles, not 20' % len(fence))
    if len(floor) != 4:
        err.append('the throne room floor is %d tiles, not 4' % len(floor))
    if len(window) != 6:
        err.append('the chapel has %d window tiles, not 6' % len(window))
    P = cfg('scripts/skill_construction/configs/poh.loc')
    for style in STYLE_TOWN:
        if 'poh_floordecor_%s' % style not in P:
            err.append('no floor decoration for %s' % style)
        for g in GLAZING:
            if 'poh_%s_window_%s' % (style, g) not in P:
                err.append('no %s window for %s' % (g, style))
    # the glazing order has to be the shell's own, or building one picks a different window
    shell = re.findall(r'^multiloc=(\d+),(\w+)$', '\n'.join(
        read('scripts/skill_construction/configs/poh.loc')
        .split('[poh_dynamic_window]')[1].split('\n[')[0].split('\n')), re.M)
    want = ['poh_%s_window_%s' % (s, g) for s in STYLE_TOWN for g in GLAZING]
    if [n for _, n in shell] != want:
        err.append('poh_dynamic_window lists its children in a different order from this table')
    if err:
        print('\n'.join('  ERROR ' + e for e in err)); sys.exit(1)

    def lay(proc, rows, extra):
        o = []
        for (x, z), (shape, angle) in rows:
            args = '$base, $rot, %d, %d, %d' % (x, z, angle)
            if extra:
                args += ', ' + extra
            o.append('~%s(%s);' % (proc[SHAPE[shape]], args))
        return o

    FA = fam['fence']['anchor']; TA = fam['thronefloor']['anchor']; WA = fam['chapelwindow']['anchor']
    o = ['// Fencing, the throne room floor and the chapel windows.',
         '//',
         '// GENERATED by tools/gendecor.py from the six template squares and tools/furnspec.json.',
         '// Do not edit by hand. Each of the three is one piece over several tiles, so each goes',
         '// through the "show" hand-off and an anchor, the way the combat ring and the rugs do, and',
         '// each shares their rotation maths - ~poh_ring_tile and ~poh_ring_angle in',
         '// poh_combat_ring.rs2, which are the engine\'s own zone arithmetic.',
         '//',
         '// THE ANCHOR IS IN furnspec.json AND NOWHERE ELSE. The click reads it there and the numbers',
         '// below are written from it, so the two cannot drift - which is the mistake the rug round',
         '// left open and a mutation caught.',
         '', '// =========================================================================== the fence', '',
         '// Seven tiers, one loc each, over the garden\'s twenty perimeter tiles - sixteen straight and',
         '// four corners, which is why there are two helpers: the shape picks the LAYER a loc goes on.',
         '[proc,poh_fence_loc](int $tier)(loc)', 'switch_int ($tier) {']
    for i, loc in enumerate(FENCE, start=1):
        o.append('    case %d : return(%s);' % (i, loc))
    o += ['    case default : return(null);', '}', '',
          '[proc,poh_fence_wall](coord $base, int $rot, int $x, int $z, int $angle, int $tier)',
          'loc_add(~poh_ring_tile($base, $rot, $x, $z), ~poh_fence_loc($tier), '
          '~poh_ring_angle($angle, $rot), wall_straight, ^poh_loc_duration);', '',
          '[proc,poh_fence_corner](coord $base, int $rot, int $x, int $z, int $angle, int $tier)',
          'loc_add(~poh_ring_tile($base, $rot, $x, $z), ~poh_fence_loc($tier), '
          '~poh_ring_angle($angle, $rot), wall_l, ^poh_loc_duration);', '',
          '[proc,poh_fence_place](coord $spot, int $angle, int $tier)',
          'def_coord $base = movecoord($spot, %d, 0, %d);' % (-FA[0], -FA[1]),
          'def_int $rot = ~poh_ring_room_rot($base);']
    o += lay({'wall_straight': 'poh_fence_wall', 'wall_l': 'poh_fence_corner'}, fence, '$tier')
    o += ['',
          '[proc,poh_fence_remove]',
          '~poh_decor_remove(%d, %d);' % (FA[0], FA[1]), '',
          '// =========================================================================== the throne floor', '',
          '// One tier - OSRS\'s other four are a steel cage, a trapdoor and two magic cages, and all of',
          '// them drop the loser into an oubliette this one-storey build does not have. The ART is your',
          '// house style\'s: six floor decorations, one per style, named after the same six towns the',
          '// windows are.',
          '[proc,poh_thronefloor_loc](int $style)(loc)', 'switch_int ($style) {']
    for i, town in enumerate(STYLE_TOWN):
        o.append('    case %d : return(poh_floordecor_%s);   // %s' % (i, town, town))
    o += ['    case default : return(poh_floordecor_%s);' % STYLE_TOWN[0], '}', '',
          '[proc,poh_thronefloor_mat](coord $base, int $rot, int $x, int $z, int $angle)',
          'loc_add(~poh_ring_tile($base, $rot, $x, $z), ~poh_thronefloor_loc(%poh_style), '
          '~poh_ring_angle($angle, $rot), grounddecor, ^poh_loc_duration);', '',
          '[proc,poh_thronefloor_place](coord $spot, int $angle, int $tier)',
          'def_coord $base = movecoord($spot, %d, 0, %d);' % (-TA[0], -TA[1]),
          'def_int $rot = ~poh_ring_room_rot($base);']
    o += lay({'grounddecor': 'poh_thronefloor_mat'}, floor, '')
    o += ['',
          '[proc,poh_thronefloor_remove]',
          '~poh_decor_remove(%d, %d);' % (TA[0], TA[1]), '',
          '// =========================================================================== the windows', '',
          '// Fifty-four: six styles times nine glazings, in poh_dynamic_window\'s own child order,',
          '// because that order IS the low digit of %poh_window.',
          '[proc,poh_window_loc](int $style, int $choice)(loc)',
          'switch_int (calc($style * ^poh_window_kinds + $choice)) {']
    for si, town in enumerate(STYLE_TOWN):
        for gi, g in enumerate(GLAZING):
            o.append('    case %d : return(poh_%s_window_%s);' % (si * 9 + gi, town, g))
    o += ['    case default : return(poh_%s_window_%s);' % (STYLE_TOWN[0], GLAZING[0]), '}', '',
          '[proc,poh_window_pane](coord $base, int $rot, int $x, int $z, int $angle, int $choice)',
          'loc_add(~poh_ring_tile($base, $rot, $x, $z), ~poh_window_loc(%poh_style, $choice), '
          '~poh_ring_angle($angle, $rot), wall_straight, ^poh_loc_duration);', '',
          '// The tier IS the choice, one to nine, so the whole house reglazes to whatever was built',
          '// here. That is what %poh_window is for, and ~poh_window_refresh already carries the choice',
          '// across a redecorate while swapping the style.',
          '[proc,poh_window_place](coord $spot, int $angle, int $tier)',
          'def_coord $base = movecoord($spot, %d, 0, %d);' % (-WA[0], -WA[1]),
          'def_int $rot = ~poh_ring_room_rot($base);',
          'def_int $choice = calc($tier - 1);',
          '%poh_window = calc(%poh_style * ^poh_window_kinds + $choice);']
    o += lay({'wall_straight': 'poh_window_pane'}, window, '$choice')
    o += ['',
          '[proc,poh_window_remove]',
          '~poh_decor_remove(%d, %d);' % (WA[0], WA[1]), '',
          '// A window in any other wall of the house is the shell, not a piece of furniture. It has',
          '// carried a Remove since the shell was resolved - a multiloc shows its active child\'s ops -',
          '// and until now nothing answered it, which is the engine\'s "Nothing interesting happens" on',
          '// every window in the house.',
          '[oploc5,poh_dynamic_window]',
          'mes("The windows are part of the house itself.");',
          'mes("Build a window in a chapel to change them, or ask the estate agent to redecorate.");', '',
          '// =========================================================================== shared', '',
          '// All three are stored at their room\'s anchor rather than under the tile that was clicked,',
          '// so all three come out the same way: find the slot at the anchor, clear it, re-lay the room.',
          '[proc,poh_decor_remove](int $ax, int $az)',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {', '    return;', '}',
          'def_int $gx = calc(coordx(loc_coord) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz(loc_coord) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $slot = ~poh_furn_at($rx, $rz, $ax, $az);',
          'if ($slot < 0) {', '    mes("That isn\'t yours to take out.");', '    return;', '}',
          'def_int $item = ~poh_furn_item(~poh_furn_get($slot));',
          'def_int $option = ~p_choice2("Take out the <enum(int, string, poh_furn_name, $item)>.", 1, "Leave it.", 2);',
          'if ($option ! 1) {', '    return;', '}',
          '~poh_furn_set($slot, 0);',
          '~poh_furn_relay($rx, $rz);',
          'mes("You take out the <enum(int, string, poh_furn_name, $item)>.");', '',
          '// =========================================================================== the triggers', '']
    claimed = {p['loc'] for k in ('fence', 'thronefloor', 'chapelwindow') for p in fam[k]['pieces']}
    for loc in FENCE:
        if loc not in claimed:
            o.append('[oploc5,%s] ~poh_fence_remove;' % loc)
    o.append('')
    for town in STYLE_TOWN:
        loc = 'poh_floordecor_%s' % town
        if loc not in claimed:
            o.append('[oploc5,%s] ~poh_thronefloor_remove;' % loc)
    o.append('')
    for town in STYLE_TOWN:
        for g in GLAZING:
            loc = 'poh_%s_window_%s' % (town, g)
            if loc not in claimed:
                o.append('[oploc5,%s] ~poh_window_remove;' % loc)
    o.append('')
    write(OUT, o)
    print('%s: fence %d tiles, throne floor %d, chapel windows %d' % (OUT, len(fence), len(floor), len(window)))
    print('  anchors from furnspec: fence %s, floor %s, window %s' % (FA, TA, WA))


main()
