#!/usr/bin/env python3
"""Rename the objs called cert_<something> that are not certificates.

WHY. tools/pack/config/ObjConfig.ts derives the forward note link from the NAME cert_<debugname>,
and the unpacker names an obj after whatever sits at the previous id. So the obj one past a law
talisman was called cert_law_talisman while really being a Rotten net, and 132 objs carried a name
that was simply false. The packer now refuses to link one that has no certtemplate, so the bug is
fixed either way - but the names still lied, and two things followed from that:

  * the next person to read obj.pack would believe them, and the next tool to key off cert_ would
    make the same mistake the packer did;
  * tools/obtainable.py skips anything matching ^cert_ in its TEMPLATE regex, because a note is its
    base item and not a thing to find a source for. All 132 were hidden from the orphan sweep by a
    name that was not true.

WHAT A NEW NAME IS. The obj's own name= field, slugged. Where that slug is taken - by a real item,
or by another of these, since fourteen of them are called "Whoopsie" - the obj id is appended, so
every name is still traceable to exactly one obj. Where the obj has no name at all it becomes
unused_objN, which is the word this repo already uses for a cache slot nothing fills, and which
obtainable.py's ^unused rule then skips for the right reason rather than a wrong one.

SAFE BECAUSE NOTHING POINTS AT THEM. Checked before writing: no .rs2, .if, .enum, .dbrow, .struct,
.param, .npc, .loc, .inv, .constant, .dbtable, no map, nothing in the engine and nothing in the
client mentions any of the 132. The only places a name appears are pack/obj.pack and the config
block that defines it. Ids do not move, so nothing in any save or drop table is affected.

IDEMPOTENT. After a run no obj is named cert_* without being a note, so a second run finds nothing.
The mapping is written to tools/certrenames.json as the record of what happened.

    python3 tools/renamecerts.py --dry-run
    python3 tools/renamecerts.py
"""
import collections, io, json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = 'pack/obj.pack'
RECORD = 'tools/certrenames.json'


def read(rel):
    return io.open(os.path.join(C, rel), encoding='utf-8', newline='').read()


def write(rel, text, nl):
    io.open(os.path.join(C, rel), 'w', encoding='utf-8', newline='').write(
        text.replace('\r\n', '\n').replace('\n', nl))


def newline_of(rel):
    raw = read(rel)
    return '\r\n' if raw.count('\r\n') > raw.count('\n') / 2 else '\n'


def blocks():
    """name -> (file, {key: value}) across every .obj config in the tree."""
    out = {}
    for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
        for fn in sorted(files):
            if not fn.endswith('.obj'):
                continue
            rel = os.path.join(dirpath, fn)[len(C) + 1:].replace(chr(92), '/')
            cur = None
            for line in read(rel).replace('\r\n', '\n').split('\n'):
                line = line.split('//')[0].strip()
                if line.startswith('[') and line.endswith(']'):
                    cur = line[1:-1]
                    out[cur] = (rel, {})
                elif cur and '=' in line:
                    k, v = line.split('=', 1)
                    out[cur][1].setdefault(k, v)
    return out


def slug(name):
    if not name:
        return None
    s = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
    return s or None


def plan():
    pack = {}
    for line in read(PACK).replace('\r\n', '\n').split('\n'):
        if '=' in line:
            i, n = line.split('=', 1)
            pack[n.strip()] = int(i)
    cfg = blocks()

    # The packer's own rule, so this renames exactly what it would refuse to link.
    aliens = []
    for base in pack:
        note = 'cert_' + base
        if note not in pack:
            continue
        if 'certtemplate' in cfg.get(note, ('', {}))[1]:
            continue
        aliens.append(note)

    taken = set(pack) - set(aliens)
    slugs = collections.Counter(slug(cfg.get(n, ('', {}))[1].get('name')) for n in aliens)
    out = {}
    for note in sorted(aliens, key=lambda n: pack[n]):
        i = pack[note]
        s = slug(cfg.get(note, ('', {}))[1].get('name'))
        if s is None:
            new = 'unused_obj%d' % i
        elif slugs[s] > 1 or s in taken:
            new = '%s_obj%d' % (s, i)
        else:
            new = s
        if new in taken:
            raise SystemExit('name collision on %s' % new)
        taken.add(new)
        out[note] = {'id': i, 'to': new,
                     'name': cfg.get(note, ('', {}))[1].get('name'),
                     'file': cfg.get(note, ('(no config)', {}))[0]}
    return out


def main():
    dry = '--dry-run' in sys.argv
    ren = plan()
    if not ren:
        print('nothing named cert_* that is not a certificate - nothing to do')
        return 0

    shape = collections.Counter(
        'unused' if d['to'].startswith('unused_obj')
        else ('disambiguated' if re.search(r'_obj\d+$', d['to']) else 'plain')
        for d in ren.values())
    print('%d renames: %s' % (len(ren), dict(shape)))
    for old, d in list(ren.items())[:8]:
        print('  %5d  %-36s -> %-26s %s' % (d['id'], old, d['to'], d['name']))
    if len(ren) > 8:
        print('  ... %d more' % (len(ren) - 8))
    if dry:
        print('dry run - nothing written')
        return 0

    # pack/obj.pack: the id stays, only the name changes.
    nl = newline_of(PACK)
    lines = read(PACK).replace('\r\n', '\n').split('\n')
    byold = {old: d for old, d in ren.items()}
    for k, line in enumerate(lines):
        if '=' not in line:
            continue
        i, n = line.split('=', 1)
        if n.strip() in byold:
            lines[k] = '%s=%s' % (i, byold[n.strip()]['to'])
    write(PACK, '\n'.join(lines), nl)

    # the config block headers
    byfile = collections.defaultdict(list)
    for old, d in ren.items():
        byfile[d['file']].append((old, d['to']))
    for rel, pairs in byfile.items():
        if rel == '(no config)':
            continue
        nl = newline_of(rel)
        t = read(rel).replace('\r\n', '\n')
        for old, new in pairs:
            head = '[%s]\n' % old
            if head not in t:
                raise SystemExit('%s: no [%s] block' % (rel, old))
            t = t.replace(head, '[%s]\n' % new, 1)
        write(rel, t, nl)
        print('  %-58s %d headers' % (rel, len(pairs)))

    rec = collections.OrderedDict()
    rec['_'] = ('Objs that were named cert_<something> without being certificates, and what they '
                'are called now. Written by tools/renamecerts.py.')
    rec['why'] = ('The unpacker names an obj after whatever sits at the previous id, so the obj one '
                  'past a law talisman was called cert_law_talisman while really being a Rotten '
                  'net. tools/pack/config/ObjConfig.ts derives the forward note link from that '
                  'name, so it linked them: withdrawing a law talisman as a note handed over the '
                  'Rotten net. The packer now requires certtemplate on the other end, and these '
                  'names no longer claim something untrue.')
    rec['ids'] = 'unchanged - only the name moved, so no save, drop table or map is affected'
    rec['renames'] = collections.OrderedDict(
        (old, {'id': d['id'], 'to': d['to'], 'name': d['name']}) for old, d in ren.items())
    io.open(os.path.join(C, RECORD), 'w', encoding='utf-8', newline='\n').write(
        json.dumps(rec, indent=1) + '\n')
    print('  %-58s %d recorded' % (RECORD, len(ren)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
