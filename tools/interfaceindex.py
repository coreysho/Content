#!/usr/bin/env python3
"""What is in the unpacked interface pool.

scripts/interfaces/ holds 280 interfaces straight out of the 377 cache. The ones that were
identified have real names; the rest are still inter_<id>.if with every component called com_<n>.
Nothing in them is searchable: an interface that IS the ancient spellbook does not contain the
word "ancient" anywhere, so a grep for the thing you are looking for finds nothing and you
conclude the cache does not have it. That happened - the ancient book was rebuilt by hand with an
invented layout while inter_267.if sat in the repo with Jagex's own grid in it.

The strings a player would SEE are the way in. An interface's action verbs, options and tooltips
say what it is in plain English. So: print them, one interface at a time, and the pool reads as a
list of features rather than a list of numbers.

    python3 tools/interfaceindex.py            # every unidentified interface that says anything
    python3 tools/interfaceindex.py teleport   # only those whose text matches
    python3 tools/interfaceindex.py --all      # named interfaces too

Run it from the content root.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ('scripts',)
# An interface still carrying its cache id, rather than one somebody has identified and renamed.
UNIDENTIFIED = re.compile(r'^inter_\d+$')
# The fields that hold text a player reads. Not `name=` - that is a component's own label in some
# interfaces and a colour name in others.
SAYS = re.compile(r'^(?:action|option|actionverb|tooltip|text)=(.+)$', re.M)
# Layout filler, not a clue. "line3" and "%1" are the slots a script writes into, and every
# interface in the cache has a Close Window. Leaving them in buries the one line that identifies
# the interface under twenty that do not.
NOISE = re.compile(r'^(?:line\s?\d+|text|%\d+%?|-|\.\.\.|close window|close|ok|cancel|'
                   r'click here to continue|please wait\.*|null)$', re.I)


def interfaces():
    for dp, _dirs, files in os.walk(os.path.join(ROOT, DIRS[0])):
        for fn in sorted(files):
            if fn.endswith('.if'):
                yield os.path.join(dp, fn)


def strings(text):
    """Player-visible text, in file order, without the duplicates."""
    out = []
    for m in SAYS.finditer(text):
        s = m.group(1).strip()
        # colour tags and the empty labels that pad a layout
        s = re.sub(r'@\w{3}@', '', s).strip()
        if s and not NOISE.match(s) and s not in out:
            out.append(s)
    return out


def main():
    args = [a for a in sys.argv[1:]]
    show_named = '--all' in args
    if show_named:
        args.remove('--all')
    needle = args[0].lower() if args else None

    shown = 0
    for path in interfaces():
        rel = os.path.relpath(path, ROOT)
        name = os.path.basename(path)[:-3]
        if not show_named and not UNIDENTIFIED.match(name):
            continue
        text = open(path, encoding='utf-8', errors='replace').read()
        said = strings(text)
        if not said:
            continue
        if needle and needle not in ' '.join(said).lower() and needle not in name:
            continue
        shown += 1
        print('%s  (%s, %d components)' % (name, rel, text.count('\n[')))
        for s in said[:24]:
            print('    %s' % s[:90])
        if len(said) > 24:
            print('    ... and %d more' % (len(said) - 24))
        print()
    print('%d interface%s' % (shown, '' if shown == 1 else 's'))


if __name__ == '__main__':
    main()
