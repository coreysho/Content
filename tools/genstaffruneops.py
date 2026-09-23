#!/usr/bin/env python3
"""Put every rune-providing staff into every spell script that counts that rune.

    python3 tools/genstaffruneops.py            # add what is missing
    python3 tools/genstaffruneops.py --check    # exit 1 if anything would be added

WHY. A spell button greys itself client-side: its script sums inv_count ops over the runes it
needs, plus one `inv_contains,wornitems:worn,<staff>` op per staff that supplies that rune, and
lights up when the total clears the cost. So a staff the server knows about (magic_staff.dbrow) but
the script does not name leaves the spell greyed and unclickable, though the cast would succeed.

HOW A SCRIPT'S ELEMENT IS FOUND: by the plain elemental staff it already names - staff_of_air in an
air count, and so on - which every rune-counting script in these files has. Each staff below is then
added to each script counting any element it supplies, after that script's last op. Existing ops
are never touched or renumbered, so re-running adds nothing.

Kept in step with magic_staff.dbrow by hand; this file is the client half of the same fact.
"""
import os
import re
import sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['scripts/skill_magic/interfaces/magic.if',
         'scripts/skill_magic/interfaces/ancient_magic.if',
         'scripts/skill_magic/interfaces/lunar_magic.if',
         'scripts/skill_combat/interfaces/magic/staff_spells.if',
         'scripts/interfaces/questscroll_itgronigen.if',
         'scripts/interfaces/inter_233.if',
         'scripts/interfaces/inter_267.if']

ELEMENT_STAFF = {'air': 'staff_of_air', 'water': 'staff_of_water', 'earth': 'staff_of_earth', 'fire': 'staff_of_fire'}
# staff -> the elements it supplies; only the staves this tool is responsible for adding
STAVES = {}
for k, els in (('smoke', ('air', 'fire')), ('mist', ('air', 'water')), ('dust', ('air', 'earth')), ('steam', ('water', 'fire'))):
    STAVES['%s_battlestaff' % k] = els
    STAVES['mystic_%s_staff' % k] = els
STAVES['twinflame_staff'] = ('water', 'fire')

MAX_OPS = 20  # the packer reads at most this many ops per script (tools/genpouchruneops.py)
OP = re.compile(r'^script(\d+)op(\d+)=(.*)$')


def process(txt):
    lines = txt.split('\n')
    out = []
    added = 0
    i = 0
    while i < len(lines):
        out.append(lines[i])
        m = OP.match(lines[i])
        if m:
            # gather this script's consecutive op lines
            sn = m.group(1)
            ops = [m.group(3)]
            last = int(m.group(2))
            while i + 1 < len(lines):
                n = OP.match(lines[i + 1])
                if not n or n.group(1) != sn:
                    break
                i += 1
                out.append(lines[i])
                ops.append(n.group(3))
                last = max(last, int(n.group(2)))
            els = [e for e, st in ELEMENT_STAFF.items() if 'inv_contains,wornitems:worn,%s' % st in ops]
            for staff, sels in STAVES.items():
                if any(e in els for e in sels) and 'inv_contains,wornitems:worn,%s' % staff not in ops:
                    last += 1
                    if last > MAX_OPS:
                        raise SystemExit('script%s would need %d ops, over the packer cap of %d' % (sn, last, MAX_OPS))
                    out.append('script%sop%d=inv_contains,wornitems:worn,%s' % (sn, last, staff))
                    added += 1
        i += 1
    return '\n'.join(out), added


def main():
    check = '--check' in sys.argv
    total = 0
    for f in FILES:
        path = os.path.join(C, f)
        raw = open(path, newline='').read()
        crlf = '\r\n' in raw
        new, added = process(raw.replace('\r\n', '\n'))
        total += added
        if added and not check:
            open(path, 'w', newline='').write(new.replace('\n', '\r\n') if crlf else new)
        print('%-55s %d op(s) %s' % (f, added, 'missing' if check else 'added'))
    if check and total:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
