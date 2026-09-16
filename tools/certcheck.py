#!/usr/bin/env python3
"""Every cert_* obj really is a certificate, and every certificate can be swapped back.

WHY THIS EXISTS. The engine has no forward note link in the cache: a note names its base in
certlink and its template in certtemplate, and the base names nothing. tools/pack writes the
forward link at pack time by looking up cert_<debugname> - and a name is not evidence. 132 objs in
this cache are called cert_<something> without being certificates: the unpacker names an obj after
whatever sits at the previous id, so the obj one past a law talisman is "cert_law_talisman" while
really being a Rotten net. Withdrawing a law talisman as a note handed over the Rotten net.

The packer now only writes the link when the other end carries certtemplate. This checks the data
that rule reads:

  1. Every obj named cert_* that the packer WOULD link carries certtemplate, so the link is real.
  2. Every note names a base that exists, and no base has two notes - oc_cert and oc_uncert are
     inverses or they are nothing.
  3. No note is missing from pack/obj.pack. A config with no pack line is never packed at all, and
     that is silent: cert_witchwood_icon had a perfectly good note config and no line, so the
     witchwood icon simply could not be noted.
  4. No base carries a hand-written certlink. The packer derives it; a line in a config is either a
     no-op or a disagreement, and two of them sat in all.obj for a round because of a wrong guess
     about how noting worked.

It also lists the cert_* objs that are NOT certificates, so the 132 misleading names stay visible
rather than being quietly excused by the packer's new guard. They are reported, not failed: renaming
them is a separate decision, and tools/obtainable.py currently hides all 132 behind the ^cert_ rule
in its TEMPLATE regex.

    python3 tools/certcheck.py
"""
import collections, io, json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok:
        fails += 1


def objblocks():
    """name -> (file, {key: value}) across every .obj config in the tree."""
    out = {}
    for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
        for fn in sorted(files):
            if not fn.endswith('.obj'):
                continue
            rel = os.path.join(dirpath, fn)[len(C) + 1:].replace(chr(92), '/')
            t = io.open(os.path.join(C, rel), encoding='utf-8', newline='').read()
            cur = None
            for line in t.replace('\r\n', '\n').split('\n'):
                line = line.split('//')[0].strip()
                if line.startswith('[') and line.endswith(']'):
                    cur = line[1:-1]
                    out[cur] = (rel, {})
                elif cur and '=' in line:
                    k, v = line.split('=', 1)
                    out[cur][1].setdefault(k, v)
    return out


def main():
    pack = {}
    for line in io.open(os.path.join(C, 'pack/obj.pack'), encoding='utf-8').read().split('\n'):
        if '=' in line:
            i, n = line.split('=', 1)
            pack[n.strip()] = int(i)
    cfg = objblocks()

    print('1. every link the packer would make is to a real certificate')
    # The packer's own rule: for obj X, if cert_X is in obj.pack, link it - but only if cert_X
    # carries certtemplate. So every cert_X in the pack is either a note or nothing.
    linkable = [n for n in pack if 'cert_' + n in pack]
    notes, aliens = [], []
    for base in linkable:
        note = 'cert_' + base
        keys = cfg.get(note, ('', {}))[1]
        (notes if 'certtemplate' in keys else aliens).append(base)
    print('     %d objs have a cert_ sibling: %d are notes, %d are not'
          % (len(linkable), len(notes), len(aliens)))
    check(len(notes) > 2000, 'the game has its notes: %d' % len(notes))
    # The 132 are an enumerated set, not a count, and that is the point: if a REAL note loses its
    # certtemplate it becomes one of these, and a count would have absorbed it silently. Anything
    # new here is a failure until somebody records it on purpose.
    spec = json.loads(io.open(os.path.join(C, 'tools/certaliens.json'), encoding='utf-8').read())
    known = set(spec['objs'])
    got = set('cert_' + b for b in aliens)
    # The count goes at the END. A mutation harness matches a check by its wording, so a number
    # interpolated into the middle of the claim changes the claim every time the number moves -
    # which is how removing one spec entry stopped matching the check that caught it.
    check(got == known,
          'exactly the cert_* objs recorded in certaliens.json are not certificates: %s'
          % (('new: %s' % sorted(got - known) if got - known else '')
             + ('  gone: %s' % sorted(known - got) if known - got else '')
             or 'the same %d' % len(known)))
    for base in sorted(notes):
        keys = cfg['cert_' + base][1]
        if keys.get('certlink') != base:
            check(False, 'cert_%s names %s as its base, not %s'
                  % (base, keys.get('certlink'), base))
        if keys.get('certtemplate') != 'template_for_cert':
            check(False, 'cert_%s uses template %s' % (base, keys.get('certtemplate')))
    check(all(cfg['cert_' + b][1].get('certlink') == b for b in notes),
          '...and every one of them names its own base back')
    check(all(cfg['cert_' + b][1].get('certtemplate') == 'template_for_cert' for b in notes),
          '...on the one template this cache has')

    print('2. oc_cert and oc_uncert are inverses')
    allnotes = {n: k.get('certlink') for n, (f, k) in cfg.items() if 'certtemplate' in k}
    check(all(b in cfg for b in allnotes.values() if b),
          'every note names a base that exists: %s'
          % ([b for b in allnotes.values() if b and b not in cfg] or 'all %d' % len(allnotes)))
    dupes = [b for b, c in collections.Counter(allnotes.values()).items() if c > 1]
    check(not dupes, 'and no base has two notes: %s' % (dupes or 'none'))
    chains = [n for n, b in allnotes.items() if b in allnotes]
    check(not chains, 'and no note is itself a note\'s base: %s' % (chains or 'none'))
    stack = [b for b in allnotes.values() if b in cfg and 'stackable' in cfg[b][1]]
    check(not stack, 'and nothing already stackable has a note: %s' % (stack or 'none'))

    print('3. every note is registered, or it is never packed at all')
    unreg = sorted(n for n in allnotes if n not in pack)
    check(not unreg, 'every note has a line in pack/obj.pack: %s'
          % (unreg or 'all %d' % len(allnotes)))
    orphan = sorted(n for n, b in allnotes.items() if b and b not in pack)
    check(not orphan, '...and so does every base it points at: %s' % (orphan or 'all of them'))

    print('4. nothing hand-writes a forward link, because the packer derives it')
    hand = sorted(n for n, (f, k) in cfg.items() if 'certlink' in k and 'certtemplate' not in k)
    check(not hand, 'no base config carries certlink: %s' % (hand or 'none'))

    print()
    print('The %d cert_* objs that are not certificates are recorded in tools/certaliens.json.' % len(aliens))
    print('The packer no longer links them; the names still lie, and tools/obtainable.py hides')
    print('them behind its ^cert_ rule. A few, to keep them in view:')
    for base in sorted(aliens)[:6]:
        note = 'cert_' + base
        print('    %-34s %-22s of %s' % (note, cfg.get(note, ('', {}))[1].get('name', '(no name)'), base))
    print()
    print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
