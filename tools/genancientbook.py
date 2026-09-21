#!/usr/bin/env python3
"""Build the Ancient Magicks spellbook from the 377 cache's own panel.

WHAT THIS REPLACES. scripts/skill_magic/interfaces/ancient_magic.if was a reconstruction, built
by hand because - in its own header's words - "the real spellbook panel art and its exact button
coordinates are not in this checkout". They were. scripts/interfaces/inter_267.if IS Jagex's
Ancient Magicks panel; it sat unrecognised because an unpacked interface contains no word you
would grep for, every component being com_<n>. tools/interfaceindex.py is what found it, by
printing the strings a player would read.

WHAT THE REAL ONE HAS THAT THE RECONSTRUCTION DID NOT

  - Jagex's LAYOUT. The reconstruction is a tidy 4x4 block of combat spells with the eight
    teleports in two rows under it. The real book interleaves them on a wider grid, which is what
    an ancient spellbook is supposed to look like.
  - A BORDERED DESCRIPTION PANEL under the grid - com_1..com_4, four nested rects, the only four
    components the reconstruction has no counterpart for - that the hover layers draw into. The
    reconstruction's hover text floated on bare background.
AND WHAT IS EXACTLY THE SAME, MEASURED RATHER THAN ASSUMED. An earlier draft of this comment
claimed the real buttons carry longer staff-substitution lists, because a key-set diff showed
script3op3..op13 only on the cache side. That was wrong: the two files distribute the same operands
across different script slots. Counted, the reconstruction and the cache panel have 760 script ops,
180 `inv_contains,wornitems:worn,` staff checks, 278 rune-pouch-mirror reads and 73 rune models
EACH. The reconstruction was a faithful copy of the logic. What it could not copy was the picture.

WHAT IT DID NOT HAVE, AND THIS ADDS. The eight teleport buttons carry no `option=`. PackShared
writes `?? ''` for a missing one, so they would pack as an EMPTY right-click row - the button still
fires on left click, because a normal button's option is appended last and the last option is the
left click, but the menu would show a blank line. magic.if, out of the same cache, carries
"Cast @gre@Varrock teleport" on its teleports, so this puts the reconstruction's own wording back.
That is the only thing here that is not the cache's.

THE RENAME IS A JOIN, NOT A GUESS. Every button in both files carries `graphic=magicoff2,<n>`, and
that sprite index is the key. For the sixteen combat buttons the real panel ALSO carries
`action=Ice Barrage` and the like, so the join is checked against Jagex's own words for it; a
disagreement is refused rather than resolved. Only the 24 buttons and their 24 hover layers are
renamed - every other component keeps its com_<n>, because nothing names them.

    python3 tools/genancientbook.py
    python3 tools/ifrender.py scripts/skill_magic/interfaces/ancient_magic.if /tmp/book.png
"""
import os, re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'scripts/interfaces/inter_267.if')
DST = os.path.join(ROOT, 'scripts/skill_magic/interfaces/ancient_magic.if')
PACK = os.path.join(ROOT, 'pack/interface.pack')
ORDER = os.path.join(ROOT, 'pack/interface.order')
IFACE = 'ancient_magic'
PANEL = 'info_%s'          # the hover layer that belongs to a spell, the reconstruction's own name


def read(p):
    return open(p, newline='').read()


def nl_of(t):
    return '\r\n' if t.count('\r\n') > t.count('\n') / 2 else '\n'


def blocks(text):
    """[(name, {k: v}, [raw lines])] in file order, preserving everything."""
    out, cur, kv, buf = [], None, None, []
    for ln in text.replace('\r\n', '\n').split('\n'):
        m = re.match(r'^\[([A-Za-z0-9_]+)\]\s*$', ln)
        if m:
            if cur is not None:
                out.append([cur, kv, buf])
            cur, kv, buf = m.group(1), {}, [ln]
            continue
        if cur is None:
            out.append([None, {}, [ln]])
            continue
        buf.append(ln)
        if '=' in ln and not ln.lstrip().startswith('//'):
            k, v = ln.split('=', 1)
            kv.setdefault(k.strip(), v.strip())
    if cur is not None:
        out.append([cur, kv, buf])
    return out


def buttons(bs):
    """sprite index -> (name, kv). A button is the thing with a graphic and a buttontype."""
    out = {}
    for n, kv, _ in bs:
        if not n or 'buttontype' not in kv:
            continue
        m = re.match(r'^magicoff2,(\d+)$', kv.get('graphic', ''))
        if not m:
            raise SystemExit('%s is a button but its graphic is %r, not a magicoff2 frame'
                             % (n, kv.get('graphic')))
        i = int(m.group(1))
        if i in out:
            raise SystemExit('two buttons share sprite magicoff2,%d: %s and %s' % (i, out[i][0], n))
        out[i] = (n, kv)
    return out


def main():
    src_raw, dst_raw = read(SRC), read(DST)
    nl = nl_of(dst_raw)
    src, old = blocks(src_raw), blocks(dst_raw)
    sb, ob = buttons(src), buttons(old)

    if set(sb) != set(ob):
        raise SystemExit('the two panels do not carry the same 24 sprites: cache has %s, the '
                         'reconstruction has %s' % (sorted(sb), sorted(ob)))
    if len(sb) != 24:
        raise SystemExit('expected 24 buttons, found %d' % len(sb))

    # THE CHECK THAT MAKES THIS A JOIN. Where Jagex names the spell, its name and the
    # reconstruction's symbol have to be the same spell, spelled the same way.
    rename, options, mismatched = {}, {}, []
    for i in sorted(sb):
        src_name, src_kv = sb[i]
        new_name, old_kv = ob[i]
        act = src_kv.get('action')
        if act and act.lower().replace(' ', '_') != new_name:
            mismatched.append((i, act, new_name))
        rename[src_name] = new_name
        ov = src_kv.get('overlayer')
        if ov:
            rename[ov] = PANEL % new_name
        if 'option' not in src_kv and old_kv.get('option'):
            options[src_name] = old_kv['option']
    if mismatched:
        raise SystemExit('the cache and the reconstruction disagree about what a sprite is: %s'
                         % mismatched)

    # rewrite line by line: only the headers, the references to them, and the eight options
    out, cur = [], None
    for name, kv, buf in src:
        cur = name
        for ln in buf:
            m = re.match(r'^\[([A-Za-z0-9_]+)\]\s*$', ln)
            if m and m.group(1) in rename:
                out.append('[%s]' % rename[m.group(1)])
                continue
            m = re.match(r'^(layer|overlayer)=([A-Za-z0-9_]+)\s*$', ln)
            if m and m.group(2) in rename:
                out.append('%s=%s' % (m.group(1), rename[m.group(2)]))
                continue
            out.append(ln)
        if cur in options:
            while out and not out[-1].strip():
                out.pop()
            out.append('option=%s' % options[cur])
            out.append('')

    head = [
        '// Ancient Magicks spellbook - THE 377 CACHE\'S OWN PANEL, not a reconstruction.',
        '//',
        '// GENERATED by tools/genancientbook.py from scripts/interfaces/inter_267.if, which is',
        '// Jagex\'s Ancient Magicks interface as it came out of the cache. Edit the generator.',
        '//',
        '// Only the 24 buttons and their 24 hover layers are renamed, by joining on each button\'s',
        '// magicoff2 sprite index and checking that join against the cache\'s own action= text.',
        '// Every other component keeps its com_<n>, because nothing names them.',
        '//',
        '// The eight teleports\' option= strings are the one thing here that is not the cache\'s:',
        '// the real panel has none, which would pack as a blank right-click row. See the generator.',
        '',
    ]
    body = nl.join(head + [l for l in out]).rstrip('\r\n') + nl
    open(DST, 'wb').write(body.encode('utf-8'))

    names = [n for n, _, _ in blocks(body) if n]
    ids = repack(names)
    print('%s: %d components from inter_267, ids %d..%d' % (IFACE, len(names), min(ids), max(ids)))
    print('  renamed %d buttons and %d panels; added %d teleport options'
          % (len(sb), len(rename) - len(sb), len(options)))


def repack(names):
    """Re-take every ancient_magic:<component> id. The interface's OWN id is kept, because
    login.rs2 and magic_combat_debug.rs2 name it and a tab interface's id is what if_settab
    sends."""
    pack = [l for l in read(PACK).replace('\r\n', '\n').split('\n') if l]
    order_raw = read(ORDER)
    onl = nl_of(order_raw)
    ids_order = [l for l in order_raw.replace('\r\n', '\n').split('\n') if l.strip()]
    existing, keep, dropped = {}, [], set()
    own = None
    for l in pack:
        i, nm = l.split('=', 1)
        if nm == IFACE:
            own = int(i)
            keep.append(l)
            continue
        if nm.startswith(IFACE + ':'):
            existing[nm] = i
            dropped.add(i)
            continue
        keep.append(l)
    if own is None:
        raise SystemExit('%s has no id in interface.pack' % IFACE)
    ids_order = [l for l in ids_order if l not in dropped]
    used = {int(l.split('=', 1)[0]) for l in keep}
    nxt = max(used) + 1
    mine = []
    for n in names:
        nm = '%s:%s' % (IFACE, n)
        i = existing.get(nm)
        if i is None or int(i) in used:
            while nxt in used:
                nxt += 1
            i = str(nxt); nxt += 1
        used.add(int(i))
        keep.append('%s=%s' % (i, nm))
        ids_order.append(i)
        mine.append(int(i))
    keep.sort(key=lambda l: int(l.split('=', 1)[0]))
    ids_order.sort(key=int)
    ids = [l.split('=', 1)[0] for l in keep]
    assert len(ids) == len(set(ids)), 'duplicate interface id'
    nms = [l.split('=', 1)[1] for l in keep]
    assert len(nms) == len(set(nms)), 'duplicate interface name'
    assert set(ids_order) == set(ids), 'interface.order and interface.pack disagree'
    open(PACK, 'w', encoding='utf-8', newline='').write('\n'.join(keep) + '\n')
    open(ORDER, 'w', encoding='utf-8', newline='').write(onl.join(ids_order) + onl)
    return mine


main()
