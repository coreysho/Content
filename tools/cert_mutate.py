#!/usr/bin/env python3
"""Mutation test for tools/certcheck.py. Same runner as pouch_mutate.py.

    python3 tools/cert_mutate.py
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'cert_mutate_work')

ALL = 'scripts/_unpack/377/all.obj'
REC = 'tools/certrenames.json'
PACK = 'pack/obj.pack'
WITCH = 'scripts/areas/area_mos_le_harmless/configs/witchwood_icon.obj'

MUTS = [
 # 1 - a link the packer would make to something that is not a note. This is the bug itself: the
 # obj on the other end of cert_<name> has to carry certtemplate or the link is a lie.
 # A real note losing its certtemplate. It stops being linked at all, which is the silent version
 # of this bug: the item simply cannot be noted any more and nothing says so. There is no exception
 # list to hide in now, so the claim fails outright.
 (ALL, '[cert_torch_lit]\ncertlink=torch_lit\ncerttemplate=template_for_cert',
       '[cert_torch_lit]\ncertlink=torch_lit_base_only',
  '1 every obj named cert_* really is a certificate'),
 # An obj that arrives wearing the prefix without earning it, which is how all 132 got here.
 (PACK, '1459=rotten_net', '1459=cert_law_talisman',
  '1 every obj named cert_* really is a certificate'),
 # An id moved rather than a name. Nothing in a save, a drop table or a map would follow it.
 (PACK, '1459=rotten_net\n', '',
  '4 every renamed obj sits at the id it always had'),
 (REC, '"to": "rotten_net"', '"to": "pretty_girl"',
  '4 ...and no two of them were given the same name'),
 (ALL, '[cert_lit_candle]\ncertlink=lit_candle\ncerttemplate=template_for_cert',
       '[cert_lit_candle]\ncertlink=torch_lit\ncerttemplate=template_for_cert',
  '1 ...and every one of them names its own base back'),
 (ALL, '[cert_torch_lit]\ncertlink=torch_lit\ncerttemplate=template_for_cert',
       '[cert_torch_lit]\ncertlink=torch_lit\ncerttemplate=template_for_cert_typo',
  '1 ...on the one template this cache has'),
 # 2 - oc_cert and oc_uncert stop being inverses
 (ALL, '[cert_lit_candle]\ncertlink=lit_candle\n',
       '[cert_lit_candle]\ncertlink=lit_candle_that_is_not_an_obj\n',
  '2 every note names a base that exists'),
 (ALL, '[cert_drill_top]\ncertlink=drill_top\n',
       '[cert_drill_top]\ncertlink=drill_helm\n',
  '2 and no base has two notes'),
 # A note of a note: oc_cert would answer a note and oc_uncert would then disagree with it.
 (ALL, '[cert_lit_candle]\ncertlink=lit_candle\n',
       '[cert_lit_candle]\ncertlink=cert_torch_lit\n',
  '2 and no note is itself a note\'s base'),
 # Noting something that already stacks is nonsense, and would double as a way to stack it twice.
 (ALL, '[cert_lit_candle]\ncertlink=lit_candle\n',
       '[cert_lit_candle]\ncertlink=coins\n',
  '2 and nothing already stackable has a note'),
 # 3 - a note with a perfectly good config and no line in the pack is never packed AT ALL, and
 # nothing says so. This is how the witchwood icon lost its note.
 (PACK, '8375=cert_witchwood_icon\n', '',
  '3 every note has a line in pack/obj.pack'),
 (WITCH, 'certlink=witchwood_icon', 'certlink=witchwood_icon_not_an_obj',
  '3 ...and so does every base it points at'),
 # 4 - a hand-written forward link. Always either a no-op or a disagreement, because the packer
 # derives it; two sat in all.obj for a round on the strength of a wrong guess.
 (ALL, '[bucket_compost]\nname=Compost', '[bucket_compost]\ncertlink=cert_bucket_compost\nname=Compost',
  '5 no base config carries certlink'),
]


def main():
    if os.path.exists(W):
        shutil.rmtree(W)
    shutil.copytree(C, W, ignore=shutil.ignore_patterns('.git', '__pycache__'))
    only = sys.argv[1] if len(sys.argv) > 1 else None
    muts = [m for m in MUTS if not only or only in m[3]]
    fails = loose = 0
    for path, find, repl, why in muts:
        p = os.path.join(W, path)
        original = open(p, 'rb').read()
        raw = original.decode('utf-8')
        nl = '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'
        f, r2 = find.replace('\n', nl), repl.replace('\n', nl)
        if f not in raw:
            print('  SKIP (pattern not found) %-30s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'certcheck.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:54] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-58s %s' % (state, why, note))
    print()
    if fails:
        print('%d MUTATIONS SURVIVED' % fails)
    elif loose:
        print('every mutation was caught, but %d by a check other than its own' % loose)
    else:
        print('every mutation was caught, each by its own check')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
