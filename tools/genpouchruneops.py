#!/usr/bin/env python3
"""Teach the spellbook's client-side greying scripts to count runes in the rune pouch.

THE BUG THIS IS FOR. Every spell button in magic.if carries interface scripts like

    script1op1=inv_count,inventory:inv,airrune
    script1op2=inv_count,inventory:inv,smokerune
    script1op5=inv_contains,wornitems:worn,staff_of_air
    script1=gt,0

The client sums the ops and only draws the spell with its activegraphic - and only lets a
buttontype=target spell be selected - when every comparison passes. Those ops name inventory:inv
and nothing else, so a rune sitting in the rune pouch could not satisfy one: the server's
~rune_total was already right and the cast was being refused before a packet was ever sent. That
is what "runes in the pouch aren't seen by spells" was.

WHAT THIS DOES. Beside every `inv_count,inventory:inv,<rune>` op it writes a matching
`inv_count,rune_pouch_mirror:runes,<rune>` and renumbers the script's ops. The client's script
machine SUMS the ops before comparing, so pack and pouch simply add up - which is exactly the
arithmetic ~rune_total does on the server, and is why the two agree.

  * It only touches an inventory:inv count of an obj that is IN THE POUCH - the rune list comes
    out of rune_pouch.enum, the same list the pouch itself accepts. magic.if also counts a banana
    and a staff orb (Enchant and Charge Orb), and a pouch count beside those would be nonsense.
    Every `inv_contains` staff check and every `inv_count,wornitems:worn,...` is left alone.
  * It FINDS THE FILES ITSELF, every .if under scripts/. A hand-written list of the two spellbooks
    missed scripts/skill_combat/interfaces/magic/staff_spells.if - the autocast panel, which greys
    its spells exactly the same way - and that was only caught by decoding the packed archive
    afterwards. Six files count runes, not two: magic.if and ancient_magic.if, staff_spells.if
    (the autocast panel, opened by skill_combat/scripts/player/auto_cast.rs2),
    questscroll_itgronigen.if (a spellbook the unpacker mis-named, referenced by quests.rs2) and
    inter_233.if / inter_267.if, which nothing in content opens. The last two are treated the same
    as the rest anyway: "unused" is a guess, and being wrong about it costs exactly this bug
    again.
  * It is IDEMPOTENT: existing mirror ops are stripped first, so re-running is a no-op and the
    cache's own ops never drift.
  * The engine's interface packer reads ops 1..20 (tools/pack/interface/PackShared.ts) and stops.
    The worst spell here has 11 ops and goes to 15, so nothing falls off the end - and this
    refuses to write if any script would exceed the cap rather than silently losing a staff check.

rune_pouch_mirror is the interface nothing ever opens; tools/genrunepouch.py has the why.

    python3 tools/genpouchruneops.py            # rewrite both spellbooks
    python3 tools/genpouchruneops.py --check    # report only, exit 1 if a change is needed
"""
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNE_ENUM = 'scripts/storage_items/configs/rune_pouch.enum'
PACK_OP_CAP = 20            # PackShared.ts: for (let k = 1; k <= 20; k++)
INV = 'inv_count,inventory:inv,'
MIRROR = 'inv_count,rune_pouch_mirror:runes,'


def runes():
    """The objs the pouch holds, out of its own enum - so the two can never disagree."""
    out = set()
    for line in io.open(os.path.join(ROOT, RUNE_ENUM), encoding='utf-8').read().split(chr(10)):
        line = line.split('//')[0].strip()
        if line.startswith('val='):
            out.add(line.split(',', 1)[1].strip())
    if not out:
        raise SystemExit('no runes in ' + RUNE_ENUM)
    return out


def files():
    """Every .if under scripts/ that counts a pouch rune in the inventory."""
    want = runes()
    out = []
    for dirpath, _dirs, fs in os.walk(os.path.join(ROOT, 'scripts')):
        for fn in sorted(fs):
            if not fn.endswith('.if'):
                continue
            # POSIX separators, always. os.path.join gives backslashes on Windows, and this path
            # is not just used to open the file - it is PRINTED, and tools/pouch_battery.py reads
            # the printout to make one check per interface. A backslash there made the battery see
            # no files at all and go red on Windows while passing on Linux.
            rel = os.path.join(dirpath, fn)[len(ROOT) + 1:].replace(chr(92), '/')
            t = io.open(os.path.join(ROOT, rel), encoding='utf-8', newline='').read()
            t = t.replace(chr(13) + chr(10), chr(10))
            if any(INV + r + chr(10) in t for r in want):
                out.append(rel)
    return sorted(out), want


def rewrite(text, want):
    """Return (new text, number of ops added). Works line by line so nothing else moves."""
    out, added = [], 0
    block = []          # the script lines of the component being read

    def flush():
        nonlocal added
        if not block:
            return
        byscript = {}
        for line in block:
            m = re.match(r'script(\d+)op(\d+)=(.*)$', line)
            byscript.setdefault(int(m.group(1)), []).append((int(m.group(2)), m.group(3)))
        for j in sorted(byscript):
            ops = [v for _, v in sorted(byscript[j])]
            # idempotent: drop what a previous run added, then add it again
            ops = [v for v in ops if not v.startswith(MIRROR)]
            fresh = []
            for v in ops:
                fresh.append(v)
                if v.startswith(INV) and v[len(INV):] in want:
                    fresh.append(MIRROR + v[len(INV):])
                    added += 1
            if len(fresh) > PACK_OP_CAP:
                raise SystemExit('script%d would have %d ops, over the packer\'s cap of %d'
                                 % (j, len(fresh), PACK_OP_CAP))
            for k, v in enumerate(fresh, 1):
                out.append('script%dop%d=%s' % (j, k, v))
        block.clear()

    for line in text.split('\n'):
        if re.match(r'script\d+op\d+=', line):
            block.append(line)
            continue
        flush()
        out.append(line)
    flush()
    return '\n'.join(out), added


def main():
    check = '--check' in sys.argv
    FILES, want = files()
    total, changed = 0, []
    for rel in FILES:
        p = os.path.join(ROOT, rel)
        raw = io.open(p, encoding='utf-8', newline='').read()
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        new, added = rewrite(raw.replace('\r\n', '\n'), want)
        total += added
        same = new == raw.replace('\r\n', '\n')
        print('%-48s %4d pouch ops  %s' % (rel, added, 'unchanged' if same else 'rewritten'))
        if not same:
            changed.append(rel)
            if not check:
                io.open(p, 'w', encoding='utf-8', newline='').write(new.replace('\n', nl))
    print('%d pouch count ops across %d files' % (total, len(FILES)))
    if check and changed:
        print('OUT OF DATE: run python3 tools/genpouchruneops.py')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
