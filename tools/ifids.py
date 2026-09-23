#!/usr/bin/env python3
"""Make pack/interface.pack and pack/interface.order match an interface's .if file.

    python tools/ifids.py clanchat [friends ...]

Every interface and every component has a number, and the packer (Engine-TS
tools/pack/interface/PackShared.ts) refuses a component the pack has no name for. Adding one by hand
means picking a free number and writing it into two files that must agree. This does it from the
.if file itself, for each interface named:

  * the interface keeps its id and every component that is still in the file keeps its id - so a
    relayout does not renumber anything that did not change;
  * a component that is new gets the next id above everything in the pack;
  * a component that is gone from the file is dropped from both files, because the packer would
    otherwise build an empty component for it;
  * interface.order is rewritten as exactly the set of ids in interface.pack, ascending, which is the
    shape every other generator here (genxplock.py and friends) leaves it in.

A new interface - a .if file the pack has never heard of - gets an id too.

It only ever touches names that start "<ifname>" or "<ifname>:", so running it for one interface
cannot disturb another.
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(ROOT, 'pack', 'interface.pack')
ORDER = os.path.join(ROOT, 'pack', 'interface.order')


def read(p):
    with open(p, encoding='utf-8', newline='') as f:
        return f.read()


def find_if(name):
    hits = []
    for base, dirs, files in os.walk(os.path.join(ROOT, 'scripts')):
        if name + '.if' in files:
            hits.append(os.path.join(base, name + '.if'))
    if len(hits) != 1:
        raise SystemExit('%s.if: %s' % (name, 'not found under scripts/' if not hits else 'found twice: ' + ', '.join(hits)))
    return hits[0]


def components(path):
    names = []
    for line in read(path).replace('\r\n', '\n').split('\n'):
        m = re.match(r'^\[(.+)\]$', line)
        if m:
            names.append(m.group(1))
    if len(names) != len(set(names)):
        dup = sorted({n for n in names if names.count(n) > 1})
        raise SystemExit('%s: component named twice: %s' % (path, ', '.join(dup)))
    return names


def sync(ifnames):
    raw = read(PACK)
    pack = [l for l in raw.replace('\r\n', '\n').split('\n') if l]
    order_raw = read(ORDER)
    order_nl = '\r\n' if '\r\n' in order_raw else '\n'

    by_name = {}
    for l in pack:
        i, nm = l.split('=', 1)
        by_name[nm] = int(i)
    used = set(by_name.values())
    nxt = max(used) + 1

    report = []
    for ifname in ifnames:
        wanted = [ifname] + ['%s:%s' % (ifname, c) for c in components(find_if(ifname))]
        mine = {nm for nm in by_name if nm == ifname or nm.startswith(ifname + ':')}
        dropped = mine - set(wanted)
        for nm in dropped:
            used.discard(by_name.pop(nm))
        added = 0
        for nm in wanted:
            if nm in by_name:
                continue
            while nxt in used:
                nxt += 1
            by_name[nm] = nxt
            used.add(nxt)
            nxt += 1
            added += 1
        report.append('%s: %d components, %d new, %d dropped' % (ifname, len(wanted) - 1, added, len(dropped)))

    lines = sorted(('%d=%s' % (i, nm) for nm, i in by_name.items()), key=lambda l: int(l.split('=', 1)[0]))
    ids = [l.split('=', 1)[0] for l in lines]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    with open(PACK, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(lines) + '\n')
    with open(ORDER, 'w', encoding='utf-8', newline='') as f:
        f.write(order_nl.join(ids) + order_nl)
    return report


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for line in sync(sys.argv[1:]):
        print(line)
