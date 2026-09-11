#!/usr/bin/env python3
"""Generate the whole furniture layer from tools/furnspec.json.

WRITES
  scripts/skill_construction/configs/poh_furniture.enum   the six item tables + the family names
  scripts/skill_construction/configs/construction.varp    the ^poh_furn_slots storage varps
  scripts/skill_construction/configs/construction.constant  the ^poh_fam_* block and the counts
  pack/varp.pack                                          ids for any varp that is new
  scripts/skill_construction/scripts/poh_furniture.rs2     all of it

WHY GENERATED. 238 pieces means a 238-case switch for the loc, another for the model, 238 removal
triggers and six enum tables of 238 rows, all of which have to agree with each other and with the
hotspot list. Twelve families were hand-checkable; fifty-one are not.

THE RULES, all in one place because they are the tunable part and not cache data:
  wood    the loc's own name when it says one (Oak bench, Gilded wardrobe -> mahogany), otherwise
          split positionally across the family's tiers
  level   family base + 7 per wood step + 3 per tier within that wood
  planks  one count per family, the same at every tier, as OSRS mostly does
  xp      planks x the per-plank value in construction.constant - not a table at all

WHAT IT CHECKS BEFORE WRITING ANYTHING (it refuses rather than emitting something that will not
compile or will not work):
  - every loc exists in poh.loc, carries op5=Remove, and is used by exactly one family
  - every hotspot id exists, is category=poh_hotspot, and carries the shape the family declares -
    a wrong shape puts loc_add on a different LAYER and the hotspot is not replaced, so you get the
    furniture AND the hotspot standing in the same tile
  - no hotspot is a door hotspot, and no hotspot is claimed twice
  - every item number fits the 8-bit item field
  - the labels inside a family are distinct, because a menu with two identical rows is a coin toss
"""

import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'furnspec.json')

def read(p):
    return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')

def crlf(p):
    raw = open(os.path.join(ROOT, p), 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2

def write(p, lines, nl=None):
    path = os.path.join(ROOT, p)
    if nl is None:
        nl = '\r\n' if (os.path.exists(path) and crlf(p)) else '\n'
    open(path, 'wb').write((nl.join(lines).rstrip('\r\n') + nl).encode('utf-8'))

def cfg(path):
    """A .loc / .npc style config file -> {name: {key: first value}}."""
    out = {}
    for b in re.split(r'\n(?=\[)', read(path)):
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

def packmap(p):
    out = {}
    for l in read(p).split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            out[n] = int(i)
    return out

# --------------------------------------------------------------------------- the rules

WOOD = {1: 'Wooden', 2: 'Oak', 3: 'Teak', 4: 'Mahogany'}
WOOD_PLANK = {1: 'planks', 2: 'oak planks', 3: 'teak planks', 4: 'mahogany planks'}

# The three sizes the first twelve families used. Kept verbatim: the wood decides the level and the
# plank type, so changing a split would move items that are already standing in someone's house.
LEGACY_SPLIT = {3: [1, 2, 3], 6: [1, 2, 2, 3, 3, 4], 7: [1, 2, 2, 3, 3, 4, 4]}

def split(n):
    if n in LEGACY_SPLIT:
        return LEGACY_SPLIT[n]
    if n == 1:
        return [1]
    if n == 2:
        return [1, 2]
    return [min(4, 1 + i * 4 // n) for i in range(n)]

def wood_from_name(nm):
    l = nm.lower()
    if 'mahogany' in l or 'gilded' in l or 'opulent' in l:
        return 4
    if 'teak' in l:
        return 3
    if 'oak' in l:
        return 2
    if 'wooden' in l:
        return 1
    return None

SHAPE_INDEX = ['centrepiece_straight', 'centrepiece_diagonal',
               'walldecor_straight_offset', 'grounddecor']

# How wide a name may be, measured in the client's own font. Read out of the window rather than
# typed, so moving the slot columns moves this with them.
def _namebox():
    src = read('scripts/skill_construction/interfaces/poh_furnmenu.if')
    b = src.split('[s0name]')[1].split('\n[')[0]
    return (int(re.search(r'^width=(\d+)$', b, re.M).group(1)),
            re.search(r'^font=(\w+)$', b, re.M).group(1))

NAME_PX, NAME_FONT = _namebox()

def width(s):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ifrender
    return ifrender.font(NAME_FONT).width(s)

# --------------------------------------------------------------------------- build the tables

def build():
    spec = json.load(open(SPEC))
    fams = spec['families']
    global OVERRIDE
    OVERRIDE = {k: v for k, v in spec.get('labels', {}).items() if k != '_'}
    P = cfg('scripts/skill_construction/configs/poh.loc')
    T = cfg('scripts/skill_construction/configs/poh_templates.loc')
    LOCS = packmap('pack/loc.pack')
    byid = {v: k for k, v in LOCS.items()}
    MODELS = packmap('pack/model.pack')

    err = []
    seen_loc, seen_hot = {}, {}
    items = []
    for fi, f in enumerate(fams, start=1):
        if f['shape'] not in SHAPE_INDEX:
            err.append('%s: shape %s is not one of %s' % (f['key'], f['shape'], SHAPE_INDEX))
        for h in f['hotspots']:
            nm = byid.get(h)
            d = T.get(nm, {})
            if nm is None or d.get('category') != 'poh_hotspot':
                err.append('%s: hotspot %d is not a poh_hotspot loc' % (f['key'], h))
            elif d.get('name') == 'Door hotspot':
                err.append('%s: hotspot %d is a DOOR hotspot' % (f['key'], h))
            if h in seen_hot:
                err.append('hotspot %d claimed by both %s and %s' % (h, seen_hot[h], f['key']))
            seen_hot[h] = f['key']
        raw = []
        for t, loc in enumerate(f['locs'], start=1):
            d = P.get(loc)
            if d is None:
                err.append('%s: %s is not in poh.loc' % (f['key'], loc))
                continue
            if d.get('op5') != 'Remove':
                err.append('%s: %s has no op5=Remove' % (f['key'], loc))
            if loc in seen_loc:
                err.append('%s used by both %s and %s' % (loc, seen_loc[loc], f['key']))
            seen_loc[loc] = f['key']
            raw.append((t, loc, OVERRIDE.get(loc, d.get('name', '?'))))
        sp = split(len(raw))
        woods = [wood_from_name(nm) or sp[i] for i, (t, loc, nm) in enumerate(raw)]
        # A menu label has to tell two tiers apart, and the loc's own name often cannot - seven locs
        # in a row all called "Bed". So: the loc's name when it is unique inside its family, the wood
        # in front of it when it is not, and a numeral after that when even the wood does not separate
        # them (two oak tables). Families whose names are already distinct - Firepit, Small oven, Iron
        # range - keep the cache's own words, and so does a name that already says its wood, or the
        # two Oak tables would come out as "Oak oak table".
        dupe_name = {nm: [x[2] for x in raw].count(nm) for _, _, nm in raw}
        base_labels = []
        for (t, loc, nm), w in zip(raw, woods):
            plain = dupe_name[nm] == 1 or wood_from_name(nm) is not None
            base_labels.append(nm if plain else '%s %s' % (WOOD[w], nm[0].lower() + nm[1:]))
        # ...and if the wood in front makes it too long for the window's name column, fall back to a
        # numeral instead. "Mahogany clockmaker's bench" is 171px in a 126px box; check 36 catches it
        # in the battery, but by then it is already shipped, so decide it here.
        if any(width(b) > NAME_PX for b in base_labels):
            base_labels = [nm for _, _, nm in raw]
        dupe = {b: base_labels.count(b) for b in base_labels}
        used = {}
        for i, ((t, loc, nm), w, bl) in enumerate(zip(raw, woods, base_labels)):
            if dupe[bl] > 1:
                used[bl] = used.get(bl, 0) + 1
                label = '%s %d' % (bl, used[bl])
            else:
                label = bl
            pos = sum(1 for ww in woods[:i] if ww == w)
            level = f['base'] + 7 * (w - 1) + 3 * pos
            model = resolve_model(P[loc].get('model', '').split(',')[0], MODELS)
            if model is None:
                err.append('%s: no model.pack entry for %s' % (f['key'], loc))
            items.append(dict(n=len(items) + 1, fam=fi, famkey=f['key'], tier=t, loc=loc,
                              label=label, wood=w, level=level, planks=f['planks'],
                              model=model, modelid=MODELS.get(model, 0)))
        labels = [it['label'] for it in items if it['fam'] == fi]
        if len(set(labels)) != len(labels):
            err.append('%s: two tiers share a label: %s' % (f['key'], labels))
        for l in labels:
            if width(l) > NAME_PX:
                err.append('%s: "%s" is %dpx in the window\'s %dpx name column'
                           % (f['key'], l, width(l), NAME_PX))
    if len(items) > 255:
        err.append('%d items, but the item field is 8 bits - 255 is the ceiling' % len(items))
    if err:
        print('\n'.join('  ERROR ' + e for e in err))
        raise SystemExit('%d problems in furnspec.json; nothing written' % len(err))
    return fams, items

def resolve_model(base, MODELS):
    if not base:
        return None
    c = sorted(n for n in MODELS if n == base or n.startswith(base + '_'))
    return c[0] if c else None

# --------------------------------------------------------------------------- shapes vs the map

def map_shapes():
    """Every shape each hotspot loc is actually placed with in the six style squares."""
    SHAPE = {0:'wall_straight',1:'wall_diagonalcorner',2:'wall_l',3:'wall_squarecorner',
             4:'walldecor_straight_nooffset',5:'walldecor_straight_offset',
             6:'walldecor_diagonal_offset',7:'walldecor_diagonal_nooffset',
             8:'walldecor_diagonal_both',9:'wall_diagonal',10:'centrepiece_straight',
             11:'centrepiece_diagonal',22:'grounddecor'}
    out = {}
    for p in ('maps/m29_79.jm2', 'maps/m30_79.jm2'):
        sec = None
        for l in read(p).split('\n'):
            if l.startswith('===='):
                sec = l.strip('= ')
                continue
            if sec != 'LOC' or ':' not in l:
                continue
            data = (l.split(':', 1)[1].split() + ['10', '0'])[:3]
            out.setdefault(int(data[0]), set()).add(SHAPE.get(int(data[1]), data[1]))
    return out

# --------------------------------------------------------------------------- emit

# The packed record. APPEND ONLY, and only above bit 21: a save written before a field existed has
# zero in it, so a new field at the top is free and a field inserted anywhere else would misread
# every house that already exists. `lit` went in at 22 for exactly that reason - an old record reads
# as unlit, which is what it was.
BITS = [('rx', 3), ('rz', 3), ('lx', 3), ('lz', 3), ('angle', 2), ('item', 8), ('lit', 1)]

def emit_enum(fams, items, path):
    o = ['// Everything that can be built into a furniture hotspot, one row per buildable thing.',
         '//',
         '// GENERATED by tools/genfurn.py from tools/furnspec.json - %d pieces across %d families is'
         % (len(items), len(fams)),
         '// six tables that have to agree with each other, with %d hotspot triggers and with %d'
         % (sum(len(f['hotspots']) for f in fams), len(items)),
         '// removal triggers. Edit the spec, not this file.',
         '//',
         '// poh_furn_name is the loc\'s OWN name= out of poh.loc - the 474 import brought the furniture',
         '// in with its real names attached, so these are data, not memory. Where a family gives several',
         '// tiers the same name (seven locs all called "Bed"), the wood of its planks disambiguates; a',
         '// name that already says its wood is left alone.',
         '//',
         '// poh_furn_level and poh_furn_wood are a RULE, not OSRS\'s table, and are the tunable part:',
         '//   wood   - taken from the loc\'s name when it says one, otherwise split positionally',
         '//   level  - family base + 7 per wood step + 3 per tier within that wood',
         '//   planks - one count per family, the same at every tier, as OSRS mostly does',
         '// Experience is not a table at all: it is planks x the per-plank value in construction.constant.',
         '']
    def table(name, out, rows, head=None):
        if head:
            o.extend(head)
        o.append('[%s]' % name)
        o.append('inputtype=int')
        o.append('outputtype=%s' % out)
        o.extend('val=%s,%s' % r for r in rows)
        o.append('')
    table('poh_furn_fam', 'int', [(i['n'], i['fam']) for i in items])
    table('poh_furn_name', 'string', [(i['n'], i['label']) for i in items])
    table('poh_furn_level', 'int', [(i['n'], i['level']) for i in items])
    table('poh_furn_wood', 'int', [(i['n'], i['wood']) for i in items])
    table('poh_furn_planks', 'int', [(i['n'], i['planks']) for i in items])
    table('poh_furn_tier', 'int', [(i['n'], i['tier']) for i in items],
          ['// Which step of its own family a piece is, 1-based. The altar reads it to work out what it',
           '// pays for a set of bones.'])
    table('poh_wood_name', 'string', [(i['n'], WOOD_PLANK[i['wood']]) for i in items],
          ['// What to ask for in the build window: the plank type this piece is made of, worded for a',
           '// sentence ("4 oak planks").'])
    table('poh_fam_name', 'string', [(n, f['label']) for n, f in enumerate(fams, 1)],
          ['// What the Furniture creation window calls each hotspot family, for its title bar.'])
    write(path, o)

def emit_varp(fams, items, slots, path):
    o = read(path).split('\n')
    cut = next(i for i, l in enumerate(o) if l.startswith('// ---- furniture'))
    o = o[:cut]
    o += ['// ---- furniture (skill_construction/scripts/poh_furniture.rs2) ----',
          '//',
          '// One piece each, packed into %d bits: the room cell in the grid (%d+%d), the tile inside that'
          % (sum(w for _, w in BITS), BITS[0][1], BITS[1][1]),
          '// room (%d+%d), the angle (%d) and which of the %d buildable things it is (%d).'
          % (BITS[2][1], BITS[3][1], BITS[4][1], len(items), BITS[5][1]),
          '//',
          '// %d of them, which is the ceiling on how much furniture one house can hold. The save writes' % slots,
          '// varps sparsely by id, so an unfurnished house costs nothing and only what is actually built',
          '// is ever written - which is why the ceiling can be raised without costing anyone anything.',
          '//',
          '// Perm: this is the house.', '']
    for i in range(slots):
        o += ['[poh_furn_%d]' % i, 'scope=perm', '']
    write(path, o)

def emit_varp_pack(slots, path='pack/varp.pack'):
    rows = [(int(l.split('=', 1)[0]), l.split('=', 1)[1]) for l in read(path).split('\n') if '=' in l]
    keep = [(i, n) for i, n in rows if not re.fullmatch(r'poh_furn_\d+', n)]
    have = {n: i for i, n in rows}
    nxt = max(i for i, _ in rows) + 1      # past EVERY id, not just the ones being kept
    for s in range(slots):
        n = 'poh_furn_%d' % s
        if n in have:                       # never renumber one that already exists: it is in a save
            keep.append((have[n], n))
        else:
            keep.append((nxt, n))
            nxt += 1
    keep.sort()
    ids = [i for i, _ in keep]
    if len(set(ids)) != len(ids):
        raise SystemExit('varp.pack would have a duplicate id')
    write(path, ['%d=%s' % kv for kv in keep], nl='\n')
    return keep

def emit_constant(fams, items, slots, path='scripts/skill_construction/configs/construction.constant'):
    src = read(path).split('\n')
    a = next(i for i, l in enumerate(src) if l.startswith('// ---- furniture'))
    b = next(i for i, l in enumerate(src) if l.startswith('// ---- the build windows'))
    block = ['// ---- furniture (poh_furniture.rs2) ----',
             '// GENERATED by tools/genfurn.py from tools/furnspec.json, along with the varps, the enum',
             '// tables and all of poh_furniture.rs2.',
             '//',
             '// How many pieces one house can hold, and how many buildable things there are.',
             '^poh_furn_slots = %d' % slots,
             '^poh_furn_items = %d' % len(items),
             '',
             '// The bit layout of one packed piece. %d bits, so it fits an int with room to spare.'
             % sum(w for _, w in BITS)]
    bit = 0
    for name, width in BITS:
        block.append('^poh_furn_bit_%s = %d' % (name, bit))
        bit += width
    block += ['',
              '// Construction experience per plank. OSRS\'s furniture xp is very nearly planks x this, so it',
              '// is one rule rather than %d rows of remembered numbers - and it is the obvious thing to tune.' % len(items),
              '^poh_xp_plank = 29',
              '^poh_xp_oak = 60',
              '^poh_xp_teak = 90',
              '^poh_xp_mahogany = 140',
              '',
              '',
              '// ---- what the furniture does (poh_furn_ops.rs2) ----',
              '// What a house altar pays for bones, as a percentage of the burying experience: the base for',
              '// the plainest altar, a step per tier above it, and a bonus for every lit thing in the same',
              '// room. OSRS pays 250% to 350% and another 50% a burner. NOT cache data - tune away.',
              '^poh_altar_base = 250',
              '^poh_altar_step = 15',
              '^poh_altar_burner = 25',
              '',
              '// The furniture families, one per hotspot kind. A hotspot\'s trigger passes its own family in,',
              '// so nothing has to look one up. NEVER REORDER: item numbers follow family order and item',
              '// numbers are what is stored in a save.']
    for n, f in enumerate(fams, 1):
        block.append('^poh_fam_%s = %d' % (f['key'], n))
    block.append('')
    write(path, src[:a] + block + src[b:])

RS2_HEAD = '''// Furniture: building into a hotspot, and remembering what was built.
//
// GENERATED by tools/genfurn.py from tools/furnspec.json. {items} pieces across {fams} families means a
// {items}-case switch for the loc, another for the model, {items} removal triggers and six enum tables of
// {items} rows, all of which have to agree with each other and with the {hots} hotspot triggers. Twelve
// families were hand-checkable; fifty-one are not. Edit the spec, not this file.
//
// WHERE IT LIVES. {slots} perm varps, one piece each, packed into {bits} bits - the room cell (3+3), the
// tile inside that room (3+3), the angle (2) and which of the {items} buildable things it is (8). The
// tile inside the zone is what identifies the hotspot, and it is exactly what loc_coord gives, so
// nothing has to enumerate hotspots or number them. Same trick as the room grid: the save writes
// varps sparsely by id, so an unfurnished house costs nothing. No engine change, no save bump.
//
// HOW IT APPEARS. loc_add at the hotspot's own coord and angle. World.changeLoc swaps the type in
// place, so the hotspot BECOMES the furniture - and it then survives instance_loccategory(...,
// poh_hotspot, false), because that only removes locs whose TYPE's category is poh_hotspot, which
// the furniture's is not. ~poh_build places furniture after the zone loop and before the hide.
//
// TAKING IT BACK OUT re-lays the whole zone rather than trying to put the hotspot back. The template
// is the exact truth about what was there; reconstructing it from a family id would be a guess, and
// several of these families have more than one hotspot loc.
//
// THE SHAPE IS NOT STORED. Every piece of a family is placed with one shape, a literal in the switch
// below, so it can only ever be placed as the shape its own hotspot carries - correct by
// construction rather than by bookkeeping. genfurn.py checks each family's shape against the six
// style squares and refuses to emit a family whose shape would land on a different LAYER from its
// hotspot, because then the hotspot would not be replaced and both would stand in the same tile.
'''

def emit_rs2(fams, items, slots, path='scripts/skill_construction/scripts/poh_furniture.rs2'):
    byfam = {f['key']: f for f in fams}
    o = RS2_HEAD.format(items=len(items), fams=len(fams), slots=slots,
                        bits=sum(w for _, w in BITS),
                        hots=sum(len(f['hotspots']) for f in fams)).split('\n')
    o += ['// =========================================================================== storage', '',
          '// %d cases because RuneScript cannot index a varp by number.' % slots,
          '[proc,poh_furn_get](int $i)(int)', 'switch_int ($i) {']
    o += ['    case %d : return(%%poh_furn_%d);' % (i, i) for i in range(slots)]
    o += ['    case default : return(0);', '}', '',
          '[proc,poh_furn_set](int $i, int $value)', 'switch_int ($i) {']
    o += ['    case %d : %%poh_furn_%d = $value;' % (i, i) for i in range(slots)]
    o += ['    case default : return;', '}', '']
    o += ['[proc,poh_furn_pack](int $rx, int $rz, int $lx, int $lz, int $angle, int $item)(int)',
          'def_int $v = 0;']
    for name, width in BITS:
        if name == 'lit':
            continue                     # never set at build time; ~poh_furn_light flips it later
        if name == 'angle':
            o.append('$v = setbit_range_toint($v, modulo($angle, 4), ^poh_furn_bit_angle, calc(^poh_furn_bit_angle + %d));' % (width - 1))
        elif name == 'item':
            o.append('return(setbit_range_toint($v, $item, ^poh_furn_bit_item, calc(^poh_furn_bit_item + %d)));' % (width - 1))
        else:
            o.append('$v = setbit_range_toint($v, $%s, ^poh_furn_bit_%s, calc(^poh_furn_bit_%s + %d));'
                     % (name, name, name, width - 1))
    o += ['', '[proc,poh_furn_field](int $v, int $bit, int $width)(int)',
          'return(getbit_range($v, $bit, calc($bit + $width - 1)));', '',
          '// The slot holding the piece on this tile, or -1. A linear scan over %d is nothing - switch_int' % slots,
          '// is a jump table, not a chain of comparisons - and it is the only lookup this design needs.',
          '[proc,poh_furn_at](int $rx, int $rz, int $lx, int $lz)(int)',
          'def_int $i = 0;',
          'while ($i < ^poh_furn_slots) {',
          '    def_int $v = ~poh_furn_get($i);',
          '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '            if (~poh_furn_field($v, ^poh_furn_bit_lx, 3) = $lx & ~poh_furn_field($v, ^poh_furn_bit_lz, 3) = $lz) {',
          '                return($i);', '            }', '        }', '    }',
          '    $i = calc($i + 1);', '}', 'return(-1);', '',
          '[proc,poh_furn_free]()(int)', 'def_int $i = 0;',
          'while ($i < ^poh_furn_slots) {', '    if (~poh_furn_get($i) = 0) {', '        return($i);',
          '    }', '    $i = calc($i + 1);', '}', 'return(-1);', '',
          '// Everything in one room goes when the room does.',
          '[proc,poh_furn_clear_cell](int $rx, int $rz)', 'def_int $i = 0;',
          'while ($i < ^poh_furn_slots) {', '    def_int $v = ~poh_furn_get($i);', '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '            ~poh_furn_set($i, 0);', '        }', '    }', '    $i = calc($i + 1);', '}', '',
          '// =========================================================================== materials', '',
          '[proc,poh_furn_plank_total](int $wood)(int)', 'switch_int ($wood) {',
          '    case 2 : return(inv_total(inv, oak_plank));',
          '    case 3 : return(inv_total(inv, teak_plank));',
          '    case 4 : return(inv_total(inv, mahogany_plank));',
          '    case default : return(inv_total(inv, plank));', '}', '',
          '[proc,poh_furn_plank_take](int $wood, int $count)', 'switch_int ($wood) {',
          '    case 2 : inv_del(inv, oak_plank, $count);',
          '    case 3 : inv_del(inv, teak_plank, $count);',
          '    case 4 : inv_del(inv, mahogany_plank, $count);',
          '    case default : inv_del(inv, plank, $count);', '}', '',
          '[proc,poh_furn_xp](int $wood, int $count)(int)', 'switch_int ($wood) {',
          '    case 2 : return(calc($count * ^poh_xp_oak));',
          '    case 3 : return(calc($count * ^poh_xp_teak));',
          '    case 4 : return(calc($count * ^poh_xp_mahogany));',
          '    case default : return(calc($count * ^poh_xp_plank));', '}', '',
          '// =========================================================================== putting it there', '',
          '// One case per buildable thing. The loc AND its shape are literals here, so a piece can only ever',
          '// be placed as the shape its own hotspot was - there is no shape to store and none to get wrong.',
          '//',
          '// A piece that has been lit goes down as its lit twin instead, which is what makes a fire still',
          '// be burning after you build a room somewhere else in the house.',
          '[proc,poh_furn_show](int $item, coord $spot, int $angle, int $lit)',
          'if ($lit = 1) {',
          '    if (~poh_furn_show_lit($item, $spot, $angle) = true) {',
          '        return;',
          '    }',
          '}',
          'switch_int ($item) {']
    for i in items:
        o.append('    case %d : loc_add($spot, %s, $angle, %s, ^poh_loc_duration);'
                 % (i['n'], i['loc'], byfam[i['famkey']]['shape']))
    o += ['    case default : return;', '}', '',
          '// The lit twin of anything that can be lit, and false for everything else.',
          '[proc,poh_furn_show_lit](int $item, coord $spot, int $angle)(boolean)',
          'switch_int ($item) {']
    for i in items:
        f = byfam[i['famkey']]
        op = f.get('op1') or {}
        if op.get('kind') == 'light':
            o.append('    case %d : loc_add($spot, %s, $angle, %s, ^poh_loc_duration); return(true);'
                     % (i['n'], op['lit'][i['tier'] - 1], f['shape']))
    o += ['    case default : return(false);', '}', '']
    return o, byfam

def emit_rs2_tail(fams, items, byfam):
    o = ['// Lay every saved piece back into a freshly built house. Called from ~poh_build after the rooms and',
         '// before the hotspots are hidden, so each piece lands on the hotspot it belongs to and changes it.',
         '[proc,poh_furn_restore](coord $base)', 'def_int $i = 0;',
         'while ($i < ^poh_furn_slots) {', '    def_int $v = ~poh_furn_get($i);', '    if ($v ! 0) {',
         '        def_int $rx = ~poh_furn_field($v, ^poh_furn_bit_rx, 3);',
         '        def_int $rz = ~poh_furn_field($v, ^poh_furn_bit_rz, 3);',
         '        if (~poh_room_type($rx, $rz) = 0) {',
         '            // its room is gone - so is it', '            ~poh_furn_set($i, 0);',
         '        } else {',
         '            def_coord $spot = movecoord($base, calc((^poh_grid_origin + $rx) * 8 + ~poh_furn_field($v, ^poh_furn_bit_lx, 3)), 0, calc((^poh_grid_origin + $rz) * 8 + ~poh_furn_field($v, ^poh_furn_bit_lz, 3)));',
         '            ~poh_furn_show(~poh_furn_field($v, ^poh_furn_bit_item, 8), $spot, ~poh_furn_field($v, ^poh_furn_bit_angle, 2), ~poh_furn_field($v, ^poh_furn_bit_lit, 1));',
         '        }', '    }', '    $i = calc($i + 1);', '}', '',
         '// Re-lay one room and put its furniture back. The template is the truth about what a hotspot was, so',
         '// taking something out is a re-lay rather than an attempt to reconstruct the hotspot by hand.',
         '[proc,poh_furn_relay](int $rx, int $rz)',
         '~poh_place_zone(%poh_instance, $rx, $rz);',
         '~poh_furn_restore(%poh_instance);',
         '~poh_spawn_exit(%poh_instance);', '',
         '// =========================================================================== the menu', '',
         '// The nth (0-based) piece in this family, whatever the player\'s level. The window shows the whole',
         '// family and dims the tiers above you - see ~poh_furn_slot0 - so the level is not a filter here.',
         '[proc,poh_furn_nth](int $fam, int $n)(int)', 'def_int $item = 1;', 'def_int $seen = 0;',
         'while ($item <= ^poh_furn_items) {',
         '    if (enum(int, int, poh_furn_fam, $item) = $fam) {',
         '        if ($seen = $n) {', '            return($item);', '        }',
         '        $seen = calc($seen + 1);', '    }', '    $item = calc($item + 1);', '}', 'return(0);', '',
         '// =========================================================================== what the window shows', '',
         '// The model each piece is shown by in poh_furnmenu: the first model its loc names, resolved',
         '// through model.pack. if_setmodel takes a RAW id, not a symbol, so these are numbers - and',
         '// battery check 30 reads every one back out of model.pack and fails if a name ever moves under',
         '// them. The zoom that frames each of these is ~poh_furn_zoom, next to the window it fills.',
         '[proc,poh_furn_model](int $item)(int)', 'switch_int ($item) {']
    for i in items:
        o.append('    case %d : return(%d);   // %s' % (i['n'], i['modelid'], i['model']))
    o += ['    case default : return(0);', '}', '',
          '// =========================================================================== the click', '',
          '[proc,poh_furn_click](int $fam)',
          'if (%poh_instance = null) {', '    mes("You can only build in your own house.");', '    return;', '}',
          'def_coord $spot = loc_coord;',
          'if (instance_find($spot) ! %poh_instance) {',
          '    mes("You can only build in your own house.");', '    return;', '}',
          'if (inv_total(inv, hammer) < 1 | inv_total(inv, saw) < 1) {',
          '    mes("You need a hammer and a saw to build furniture.");', '    return;', '}',
          'def_int $angle = loc_angle;',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $lx = modulo($gx, 8);', 'def_int $lz = modulo($gz, 8);',
          'if (~poh_furn_free < 0) {',
          '    mes("Your house is as full of furniture as it will hold.");', '    return;', '}',
          'def_int $item = ~poh_furn_pick($fam);',
          'if ($item = 0) {', '    mes("There\'s nothing you can build here yet.");', '    return;', '}',
          'def_int $wood = enum(int, int, poh_furn_wood, $item);',
          'def_int $need = enum(int, int, poh_furn_planks, $item);',
          'if (~poh_furn_plank_total($wood) < $need) {',
          '    mes("You need <tostring($need)> <enum(int, string, poh_wood_name, $item)> to build that.");',
          '    return;', '}',
          '// re-check after the menu: it suspends, and the slot or the planks can go while it is open',
          'def_int $slot = ~poh_furn_free;',
          'if ($slot < 0 | ~poh_furn_at($rx, $rz, $lx, $lz) ! -1) {',
          '    mes("Something is in the way.");', '    return;', '}',
          '~poh_furn_plank_take($wood, $need);',
          '~poh_furn_set($slot, ~poh_furn_pack($rx, $rz, $lx, $lz, $angle, $item));',
          '~poh_furn_show($item, $spot, $angle, 0);',
          'stat_advance(construction, ~poh_furn_xp($wood, $need));',
          'mes("You build the <enum(int, string, poh_furn_name, $item)>.");', '',
          '// Taking a piece out. No refund and no planks back, as in OSRS.',
          '[proc,poh_furn_remove]',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {', '    return;', '}',
          'def_coord $spot = loc_coord;',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'def_int $rx = calc(divide($gx, 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide($gz, 8) - ^poh_grid_origin);',
          'def_int $slot = ~poh_furn_at($rx, $rz, modulo($gx, 8), modulo($gz, 8));',
          'if ($slot < 0) {', '    mes("That isn\'t yours to take out.");', '    return;', '}',
          'def_int $item = ~poh_furn_field(~poh_furn_get($slot), ^poh_furn_bit_item, 8);',
          'def_int $option = ~p_choice2("Take out the <enum(int, string, poh_furn_name, $item)>.", 1, "Leave it.", 2);',
          'if ($option ! 1) {', '    return;', '}',
          '~poh_furn_set($slot, 0);', '~poh_furn_relay($rx, $rz);',
          'mes("You take out the <enum(int, string, poh_furn_name, $item)>. The materials are gone.");', '',
          '// =========================================================================== triggers',
          '//',
          '// Each hotspot passes its own family in, so nothing has to look one up from a loc id. The hotspot',
          '// locs and the shapes they are placed at were read out of the six style squares, not assumed.', '']
    byid = {v: k for k, v in packmap('pack/loc.pack').items()}
    for f in fams:
        for h in f['hotspots']:
            o += ['[oploc5,%s]' % byid[h], '~poh_furn_click(^poh_fam_%s);' % f['key'], '']
    o += ['// One per buildable thing: every piece keeps its own op5=Remove from poh.loc.', '']
    for i in items:
        o += ['[oploc5,%s]' % i['loc'], '~poh_furn_remove;', '']
    return o

OPS_HEAD = """// What the furniture DOES. One [oploc1] per piece, generated from the op1 block of each family in
// tools/furnspec.json.
//
// Every op these locs carry sits at op1 - checked across all {n} pieces - so the trigger is always
// oploc1 and there is no per-family index to get wrong. The op's WORDS are in the spec too: a
// generator that invents flavour text is a generator nobody can review.
//
// WHAT IS NOT HERE. Study (lecterns) is teleport tablets and needs the tablet objs; Work-at
// (workbenches) is flatpacks and needs one obj per piece of furniture; Craft, Open, Change-clothes,
// Upgrade, Activate, Set-up, Shoot-at, Throw-at, Challenge-mode, Pull, Use and Make-helmet each need
// new objects, a new interface, or a servant. The spec says so next to each family.
"""

def q(s):
    return '"%s"' % s.replace('"', "'")

def emit_ops(fams, items, byfam, path='scripts/skill_construction/scripts/poh_furn_ops.rs2'):
    lit_items = [i for i in items if (byfam[i['famkey']].get('op1') or {}).get('kind') == 'light']
    o = OPS_HEAD.format(n=len(items)).split('\n')

    o += ['// =========================================================================== lighting', '',
          '// Lighting is REMEMBERED - bit %d of the packed record - so a fire is still burning after you'
          % dict((n, sum(w for _, w in BITS[:i])) for i, (n, w) in enumerate(BITS))['lit'],
          '// build a room somewhere else and the house is laid out again. A record written before this',
          '// field existed has 0 there, which reads as unlit, which is what it was.',
          '[proc,poh_furn_light](string $mes)',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {', '    return;', '}',
          'if (inv_total(inv, tinderbox) < 1) {',
          '    mes("You need a tinderbox to light that.");', '    return;', '}',
          'def_coord $spot = loc_coord;',
          'def_int $gx = calc(coordx($spot) - coordx(%poh_instance));',
          'def_int $gz = calc(coordz($spot) - coordz(%poh_instance));',
          'def_int $slot = ~poh_furn_at(calc(divide($gx, 8) - ^poh_grid_origin), calc(divide($gz, 8) - ^poh_grid_origin), modulo($gx, 8), modulo($gz, 8));',
          'if ($slot < 0) {', '    return;', '}',
          'def_int $v = ~poh_furn_get($slot);',
          'if (~poh_furn_field($v, ^poh_furn_bit_lit, 1) = 1) {',
          '    mes("It is already lit.");', '    return;', '}',
          '~poh_furn_set($slot, setbit_range_toint($v, 1, ^poh_furn_bit_lit, ^poh_furn_bit_lit));',
          'anim(human_pickupfloor, 0);',
          'sound_synth(tinderbox_strike, 1, 0);',
          '~poh_furn_show_lit(~poh_furn_field($v, ^poh_furn_bit_item, 8), $spot, ~poh_furn_field($v, ^poh_furn_bit_angle, 2));',
          'mes($mes);', '',
          '// =========================================================================== the altar', '',
          '// What the altar pays for a set of bones, as a percentage of what burying them gives. OSRS pays',
          '// 250% at a plain altar and 350% at the best one, and another 50% for each of the two burners',
          '// beside it. NOT cache data - the tunable part, like the room prices.',
          '[proc,poh_furn_altar_bonus](int $item)(int)',
          'def_int $pct = calc(^poh_altar_base + calc(enum(int, int, poh_furn_tier, $item) - 1) * ^poh_altar_step);',
          'return(calc($pct + ~poh_furn_lit_in_room * ^poh_altar_burner));', '',
          '// How many lit things stand in the room the player is standing in. A linear scan, like every',
          '// other question this design asks about the furniture.',
          '[proc,poh_furn_lit_in_room]()(int)',
          'def_int $rx = calc(divide(calc(coordx(coord) - coordx(%poh_instance)), 8) - ^poh_grid_origin);',
          'def_int $rz = calc(divide(calc(coordz(coord) - coordz(%poh_instance)), 8) - ^poh_grid_origin);',
          'def_int $i = 0;', 'def_int $n = 0;',
          'while ($i < ^poh_furn_slots) {',
          '    def_int $v = ~poh_furn_get($i);',
          '    if ($v ! 0) {',
          '        if (~poh_furn_field($v, ^poh_furn_bit_lit, 1) = 1) {',
          '            if (~poh_furn_field($v, ^poh_furn_bit_rx, 3) = $rx & ~poh_furn_field($v, ^poh_furn_bit_rz, 3) = $rz) {',
          '                $n = calc($n + 1);', '            }', '        }', '    }',
          '    $i = calc($i + 1);', '}', 'return($n);', '',
          '// Anything with a bone_exp param may be offered, which is the same test burying uses - so a bone',
          '// added to the game later works here without this file knowing it exists.',
          '[proc,poh_furn_offer](int $item)',
          'if (%poh_instance = null | instance_find(loc_coord) ! %poh_instance) {', '    return;', '}',
          'def_obj $bone = last_useitem;',
          'if (oc_param($bone, bone_exp) <= 0) {',
          '    mes("The gods have no use for that.");', '    return;', '}',
          'def_int $pct = ~poh_furn_altar_bonus($item);',
          'inv_del(inv, $bone, 1);',
          'anim(human_pray, 0);',
          'sound_synth(prayer_recharge, 1, 0);',
          'stat_advance(prayer, calc(oc_param($bone, bone_exp) * $pct / 100));',
          'mes("You offer the bones. The gods are pleased.");', '',
          '// =========================================================================== the triggers', '']

    KIND = {}
    def add(fam, item, lines):
        KIND.setdefault(fam, []).append((item, lines))
    for i in items:
        f = byfam[i['famkey']]
        op = f.get('op1')
        if not op:
            continue
        k = op['kind']
        if k == 'sit':
            body = ['anim(%s, 0);' % op['seq'], 'mes(%s);' % q(op['mes'])]
        elif k == 'light':
            body = ['~poh_furn_light(%s);' % q(op['mes'])]
        elif k == 'altar':
            body = ['@pray_at_altar(stat_base(prayer));']
        elif k == 'jingle':
            body = ['midi_jingle(%s);' % q(op['midi']), 'mes(%s);' % q(op['mes'])]
        elif k == 'clock':
            body = ['mes("The clock says it is <tostring(divide(modulo(map_clock, 6000), 250))> o\'clock.");']
        elif k == 'observe':
            body = ['switch_int (random(%d)) {' % len(op['lines'])]
            for n, l in enumerate(op['lines']):
                body.append('    case %d : mes(%s);' % (n, q(l)))
            body.append('    case default : mes(%s);' % q(op['lines'][0]))
            body.append('}')
        elif k == 'talk':
            body = ['mes(%s);' % q(op['lines'][min(i['tier'], len(op['lines'])) - 1])]
        elif k == 'preen':
            body = ['anim(%s, 0);' % op['seq'], 'mes(%s);' % q(op['mes'])]
        elif k == 'mes':
            body = ['mes(%s);' % q(l) for l in op['lines']]
        else:
            raise SystemExit('unknown op kind %r on %s' % (k, f['key']))
        o += ['[oploc1,%s]' % i['loc']] + body + ['']
        if k == 'light':
            o += ['[oploc5,%s]' % op['lit'][i['tier'] - 1], '~poh_furn_remove;', '']
        if k == 'altar':
            o += ['[oplocu,%s]' % i['loc'], '~poh_furn_offer(%d);' % i['n'], '']
    write(path, o)
    return lit_items

if __name__ == '__main__':
    SLOTS = int(sys.argv[1]) if len(sys.argv) > 1 else 256
    fams, items = build()
    shapes = map_shapes()
    bad = []
    for f in fams:
        for h in f['hotspots']:
            have = shapes.get(h, set())
            if f['shape'] not in have:
                bad.append((f['key'], h, f['shape'], sorted(have)))
    allowed = {(x['family'], x['hotspot']) for x in json.load(open(SPEC)).get('shape_allowances', [])}
    unexplained = [b for b in bad if (b[0], b[1]) not in allowed]
    for b in bad:
        print('  %s hotspot %d: family says %s, the templates say %s%s'
              % (b[0], b[1], b[2], b[3], '' if (b[0], b[1]) in allowed else '   <-- NOT ALLOWED'))
    if unexplained:
        raise SystemExit('%d hotspot shapes disagree with the templates and are not in '
                         'shape_allowances; nothing written' % len(unexplained))
    emit_enum(fams, items, 'scripts/skill_construction/configs/poh_furniture.enum')
    emit_varp(fams, items, SLOTS, 'scripts/skill_construction/configs/construction.varp')
    ids = emit_varp_pack(SLOTS)
    emit_constant(fams, items, SLOTS)
    head, byfam = emit_rs2(fams, items, SLOTS)
    write('scripts/skill_construction/scripts/poh_furniture.rs2', head + emit_rs2_tail(fams, items, byfam))
    lit = emit_ops(fams, items, byfam)
    print('%d pieces answer op1, %d of them can be lit' %
          (sum(1 for i in items if byfam[i['famkey']].get('op1')), len(lit)))
    print('%d families, %d items, %d hotspots, %d slots (varp ids up to %d)'
          % (len(fams), len(items), sum(len(f['hotspots']) for f in fams), SLOTS, max(i for i, _ in ids)))
