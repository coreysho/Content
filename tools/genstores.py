#!/usr/bin/env python3
"""Generate the costume room's five storage spaces - the tables, the inv and the item lists.

  cape rack          six tiers, 54-99, 87 capes and hoods
  magic wardrobe     seven tiers, 42-96, 58 robes and staves
  armour case        three tiers, 46-82, 53 pieces of armour
  toy box            three tiers, 50-86, 37 toys
  fancy dress box    three tiers, 44-80, 72 costume pieces

THEY ARE ALL ONE MECHANISM. The treasure chest that shipped with the costume room already does
storage the way this repo does storage - a perm inv, a flat item enum, and first/last windows that
make a set addressable without an enum per set. These five are the same thing five more times, so
rather than five copies of poh_costume.rs2 there is ONE set of procs in poh_stores.rs2 and the
store index picks the window. All five share a single perm inv and each store owns a contiguous run
of it, because the item list has to be flat either way - "take out a set" needs first/last windows
into it. (The first version of this file said an inv cannot be passed to a proc and that nothing in
the repo takes one. Both are false: ~inv_slotspace in general/scripts/misc/inv_procs.rs2 takes two.
The shape here still stands; the reason given for it did not.)

WHAT GOES IN EACH ONE is the part worth arguing about, and the rule here is: it has to already
exist in this repo, it has to be something you WEAR rather than something you use, and it must not
already be in the treasure chest. The last one is checked, not assumed - four items (the three
berets and the highwayman mask) are clue rewards and live in the chest, so they are not in the
fancy dress box. Battery group 62 re-checks all three rules on every run.

    python3 tools/genstores.py
"""
import os, sys, json, io

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ENUM = 'scripts/skill_construction/configs/poh_store.enum'
OUT_INV = 'scripts/skill_construction/configs/poh_store.inv'
SPEC = os.path.join(ROOT, 'tools', 'storespec.json')


def read(p):
    return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')


def crlf(p):
    raw = open(os.path.join(ROOT, p), 'rb').read()
    return raw.count(b'\r\n') > raw.count(b'\n') / 2


def write(p, lines):
    path = os.path.join(ROOT, p)
    nl = '\r\n' if (os.path.exists(path) and crlf(p)) else '\n'
    open(path, 'wb').write((nl.join(lines).rstrip('\r\n') + nl).encode('utf-8'))


def packnames(p):
    out = set()
    for l in read(p).split('\n'):
        if '=' in l:
            out.add(l.split('=', 1)[1].strip())
    return out


def chest_items():
    """The treasure chest's own list, so nothing is in two places."""
    out, cur = set(), None
    for l in read('scripts/skill_construction/configs/poh_costume.enum').split('\n'):
        l = l.strip()
        if l.startswith('[') and l.endswith(']'):
            cur = l[1:-1]
        elif cur == 'poh_costume_item' and l.startswith('val='):
            out.add(l.split(',', 1)[1])
    return out


def table(name, out_t, rows, note=(), in_t='int'):
    o = list(note) + ['[%s]' % name, 'inputtype=%s' % in_t, 'outputtype=%s' % out_t,
                      'default=null']
    for k, v in rows:
        o.append('val=%s,%s' % (k, v))
    return o + ['']


def main():
    spec = json.load(open(SPEC))
    stores = spec['stores']
    # The TIERS are not here. They are the furniture, and the furniture lives in furnspec.json,
    # which is what genfurn.py builds the build-menu rows from; reading them back from there is what
    # keeps the capacity table and the pieces you can actually build from drifting apart.
    fams = {f['key']: f for f in json.load(open(os.path.join(ROOT, 'tools', 'furnspec.json')))['families']}
    for st in stores:
        f = fams.get(st['family'])
        if f is None:
            raise SystemExit('%s: no family %r in furnspec.json' % (st['key'], st['family']))
        st['tiers'] = f.get('pieces') or f.get('locs')
    objpack = packnames('pack/obj.pack')
    chest = chest_items()

    err = []
    items, sets = [], []
    for si, st in enumerate(stores):
        st['first'] = len(items)
        st['setfirst'] = len(sets)
        for sn in st['sets']:
            sets.append(dict(store=si, name=sn['name'], first=len(items), last=None))
            for o in sn['items']:
                if o not in objpack:
                    err.append('%s / %s: %s is not in pack/obj.pack' % (st['key'], sn['name'], o))
                if o in chest:
                    err.append('%s / %s: %s is already in the treasure chest' % (st['key'], sn['name'], o))
                if o in [i['obj'] for i in items]:
                    err.append('%s / %s: %s is in two stores' % (st['key'], sn['name'], o))
                items.append(dict(obj=o, store=si, set=len(sets) - 1))
            sets[-1]['last'] = len(items) - 1
            if sets[-1]['last'] < sets[-1]['first']:
                err.append('%s: set "%s" is empty' % (st['key'], sn['name']))
        st['last'] = len(items) - 1
        st['setlast'] = len(sets) - 1
    if err:
        for e in err:
            print('  ' + e)
        raise SystemExit('%d problems with the store lists; nothing written' % len(err))

    # Capacity: a tier holds its share of its own store's list, so the last tier holds all of it and
    # the first holds 1/n. Exactly what poh_costume_cap does for the chest's four tiers, expressed
    # as arithmetic rather than four hand-written numbers.
    caps = []
    for si, st in enumerate(stores):
        n = st['last'] - st['first'] + 1
        nt = len(st['tiers'])
        for t in range(1, nt + 1):
            caps.append((si * 8 + t, (n * t + nt - 1) // nt))

    o = [
        '// The costume room\'s five storage spaces: the cape rack, the magic wardrobe, the armour',
        '// case, the toy box and the fancy dress box.',
        '//',
        '// GENERATED BY tools/genstores.py FROM tools/storespec.json - do not hand-edit. The lists',
        '// are checked against pack/obj.pack and against the treasure chest\'s own list before',
        '// anything is written, so a name that does not exist, or an item that is already in the',
        '// chest, stops the generator instead of shipping.',
        '//',
        '// The shape is the treasure chest\'s, one level up. poh_costume_item is a flat list of 72',
        '// with first/last windows per set; this is a flat list of %d with first/last windows per' % len(items),
        '// SET and per STORE, because five stores share one inv and the store index picks the',
        '// window, so poh_stores.rs2 has one copy of the store/check/take procs rather than five.',
        '//',
        '// %d items in %d sets across %d stores.' % (len(items), len(sets), len(stores)),
        '',
    ]
    o += table('poh_store_item', 'namedobj', [(i, it['obj']) for i, it in enumerate(items)],
               ['// Every item any of the five spaces holds, in store order then set order. The index',
                '// into this list is also the slot the item occupies in poh_store_inv.'])
    o += table('poh_store_name', 'string', [(i, st['label']) for i, st in enumerate(stores)],
               ['// What to call each space in a message.'])
    o += table('poh_store_first', 'int', [(i, st['first']) for i, st in enumerate(stores)],
               ['// The run of poh_store_item that belongs to each store.'])
    o += table('poh_store_last', 'int', [(i, st['last']) for i, st in enumerate(stores)])
    o += table('poh_store_setfirst', 'int', [(i, st['setfirst']) for i, st in enumerate(stores)],
               ['// ...and the run of sets.'])
    o += table('poh_store_setlast', 'int', [(i, st['setlast']) for i, st in enumerate(stores)])
    o += table('poh_store_set_name', 'string', [(i, s['name']) for i, s in enumerate(sets)],
               ['// The sets, flat across all five stores.'])
    o += table('poh_store_set_first', 'int', [(i, s['first']) for i, s in enumerate(sets)])
    o += table('poh_store_set_last', 'int', [(i, s['last']) for i, s in enumerate(sets)])
    o += table('poh_store_cap', 'int', caps,
               ['// How much each tier holds, keyed store x 8 + tier. A better piece of furniture',
                '// holds more, the way a better treasure chest does; the top tier holds the lot.'])
    write(OUT_ENUM, o)

    write(OUT_INV, [
        '// The one perm inv behind all five costume-room storage spaces. scope=perm because the',
        '// whole point is that it is still there next login, and one slot per item in',
        '// poh_store_item because every one of them is stored one-of-each: a second gold-trimmed',
        '// anything is not part of a costume.',
        '//',
        '// GENERATED BY tools/genstores.py - size is the length of poh_store_item.',
        '',
        '[poh_store_inv]',
        'scope=perm',
        'size=%d' % len(items),
        'protect=no',
    ])

    print('%s: %d items, %d sets, %d stores' % (OUT_ENUM, len(items), len(sets), len(stores)))
    for si, st in enumerate(stores):
        print('  %-16s items %3d..%3d  sets %2d..%2d  tiers %d  caps %s'
              % (st['key'], st['first'], st['last'], st['setfirst'], st['setlast'],
                 len(st['tiers']), [c[1] for c in caps if c[0] // 8 == si]))
    return stores, items, sets


if __name__ == '__main__':
    main()
