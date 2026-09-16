"""Battery for the King Black Dragon's art and the six boss pets'.

The helmet round's lesson, applied from the start: a config that names the wrong art is perfectly
self-consistent, so every model here is measured against tools/bossartspec.json, which records
each one's OSRS id and its CONVERTED vertex and face counts. A model repointed at another mesh
changes those numbers; a model repointed at nothing fails to exist. Neither can pass by agreeing
with itself.

    python3 tools/bossart_battery.py
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

SPEC = json.loads(read('tools/bossartspec.json'))
DRAGONS = read('scripts/npc/configs/dragons.npc')
PETS = read('scripts/npc/configs/boss_pets.npc') + '\n' + read('scripts/npc/configs/skill_pets.npc')
PETOBJ = read('scripts/npc/configs/boss_pets.obj') + '\n' + read('scripts/npc/configs/skill_pets.obj')
DSEQ = read('scripts/npc/configs/dragons.seq')
PSEQ = read('scripts/npc/configs/boss_pets.seq') + '\n' + read('scripts/npc/configs/skill_pets.seq')
PETRS2 = read('scripts/npc/scripts/boss_pets.rs2')

def blocks(txt):
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[([\w.]+)\]', b)
        if not m: continue
        d = {}
        for l in b.split('\n')[1:]:
            l = l.split('//')[0].strip()
            if '=' in l:
                k, v = l.split('=', 1)
                d.setdefault(k, []).append(v)
        out[m.group(1)] = d
    return out

def pack(name):
    return {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/' + name).split('\n') if '=' in l)}

NPCB = blocks(DRAGONS); NPCB.update(blocks(PETS))
OBJB = blocks(PETOBJ)
SEQB = blocks(DSEQ); SEQB.update(blocks(PSEQ))
MODELP, NPCP, OBJP = pack('model.pack'), pack('npc.pack'), pack('obj.pack')
ANIMP, SETP, BASEP, SEQP = pack('anim.pack'), pack('animset.pack'), pack('base.pack'), pack('seq.pack')

def shape(path):
    """vertex and face counts read out of the .ob2's own footer, the way the client reads them."""
    b = open(os.path.join(C, path), 'rb').read()
    n = len(b)
    return (b[n-18] << 8) | b[n-17], (b[n-16] << 8) | b[n-15]

# ============================================================================ 1
print('1. every model the new art names exists, and is the mesh the spec measured')
for kind, table, sub in (('npc', SPEC['npcs'], 'npc'), ('obj', SPEC['items'], 'obj')):
    for name, s in sorted(table.items()):
        models = s['models'] if kind == 'npc' else {'obj_' + name: s['model']}
        for mn, want in sorted(models.items()):
            path = 'models/%s/%s.ob2' % (sub, mn)
            here = os.path.exists(os.path.join(C, path))
            check(here, '%s is a file on disk' % mn)
            check(mn in MODELP, '...and is registered in model.pack')
            if here:
                v, f = shape(path)
                check((v, f) == (want['verts'], want['faces']),
                      '...and is the mesh the spec measured: %d verts %d faces%s'
                      % (v, f, '' if (v, f) == (want['verts'], want['faces'])
                         else ' - SPEC SAYS %d/%d' % (want['verts'], want['faces'])))

# The other half of that: the CONFIG has to name exactly those models. Group 1 walks the spec, so
# on its own it proves the imported art exists and is the right shape - not that anything wears it.
# A mole pointed at the Dagannoth's mesh passed both halves separately and neither together.
for name, sp in sorted(SPEC['npcs'].items()):
    want = sorted(sp['models'])
    got = sorted(v for k, v in NPCB[name].items() if re.match(r'(model|head)\d+$', k) for v in v)
    check(got == want, '%s names exactly the models the spec measured%s'
          % (name, '' if got == want else ': %s vs spec %s' % (got, want)))
for name, sp in sorted(SPEC['items'].items()):
    got = OBJB[name].get('model', [])
    check(got == ['obj_' + name], '%s draws the model the spec measured%s'
          % (name, '' if got == ['obj_' + name] else ': %s' % got))

# ============================================================================ 2
print('2. the King Black Dragon is the OSRS mesh, and nothing else moved with it')
kd = NPCB['king_dragon']
check(kd['model1'] == ['npc_king_dragon_1'] and 'model5' in kd,
      'it carries all five imported models')
check(not [k for k in kd if k.startswith('recol')],
      'and no recol pairs - osrs2ob2 baked them into the mesh, so a pair here would repaint it twice')
check('resizeh' not in kd and 'resizev' not in kd,
      'and no resize: the cache states 128 and the mesh is authored at its own size')
check(kd['size'] == ['5'], 'it is still a 5x5 npc')
# the 377 mesh is SHARED - Elvarg and the chromatics must still be on it
# The 377 mesh is SHARED. The spec records who else wears it, so the check names them rather than
# counting them: a dragon dragged onto the OSRS art with the KBD would quietly keep a count happy.
others = sorted(n for n, d in NPCB.items()
                if n != 'king_dragon' and 'npc_king_dragon' in sum(d.values(), []))
want = sorted(SPEC['shares_377_mesh'])
check(others == want, 'the 377 mesh is still worn by exactly the dragons that shared it: %s'
      % (others if others == want else '%s vs spec %s' % (others, want)))
check('npc_king_dragon' in MODELP, '...and is still registered, not deleted')
for n in want:
    on = sum(NPCB.get(n, {}).values(), [])
    check('npc_king_dragon' in on and 'npc_king_dragon_1' not in on,
          '%s did not follow the KBD onto the OSRS mesh' % n)

# ============================================================================ 3
print('3. the KBD\'s five animations are the ones the spec names, with their own timing')
kdseq = {'readyanim': 'osrs_seq_90', 'walkanim': 'osrs_seq_4635'}
for k, v in kdseq.items():
    check(kd.get(k) == [v], 'its %s is %s' % (k, v))
for p, v in (('attack_anim', 'osrs_seq_91'), ('defend_anim', 'osrs_seq_89'),
             ('death_anim', 'osrs_seq_92')):
    check('%s,%s' % (p, v) in kd.get('param', []), 'its %s is %s' % (p, v))
check(not [x for x in kd.get('param', []) if re.match(r'(attack|defend|death)_anim,dragon_', x)],
      'and none of the three still points at a 377 dragon anim')
for name, s in sorted(SPEC['seqs'].items()):
    check(name in SEQB, '%s is declared' % name)
    if name not in SEQB: continue
    b = SEQB[name]
    nums = sorted(int(k[5:]) for k in b if re.match(r'frame\d+$', k))
    got = len(nums)
    check(got == s['frames'] and nums == list(range(1, got + 1)),
          '...with the %d frames OSRS seq %d has, numbered 1..%d%s'
          % (s['frames'], s['osrs'], s['frames'],
             '' if got == s['frames'] and nums == list(range(1, got + 1))
             else ' - GOT %d, %s' % (got, nums[-3:])))
    check(b.get('priority', [None])[0] == (str(s['priority']) if s['priority'] else None),
          '...and its own priority (%s)' % s['priority'])
    check(b.get('loops', [None])[0] == (str(s['loops']) if s['loops'] else None),
          '...and its own loop count (%s)' % s['loops'])
    check(name in SEQP, '...and is registered in seq.pack')
    missing = [f for k, f in b.items() if k.startswith('frame') for f in f if f not in ANIMP]
    check(not missing, '...and every frame is in anim.pack: %s' % (missing[:3] or 'all %d' % got))

# ============================================================================ 4
print('4. every animation set and base the conversion wrote is registered')
sets = sorted({re.match(r'(anim_osrs_\d+)_\d+$', f).group(1)
               for b in SEQB.values() for k, v in b.items() if k.startswith('frame')
               for f in v if re.match(r'anim_osrs_\d+_\d+$', f)})
check(len(sets) >= 8, 'the ten seqs come out of %d frame sets' % len(sets))
for s in sets:
    check(s in SETP, '%s is in animset.pack' % s)
    check('base_' + s.replace('anim_', '') in BASEP or s.replace('anim_osrs_', 'base_osrs_') in BASEP,
          '...and its base is in base.pack')
    check(os.path.exists(os.path.join(C, 'models', s + '.anim')), '...and the blob is on disk')

# ============================================================================ 5
print('5. every pet is the cache\'s own art at the cache\'s own scale')
PETNAMES = [n for n in SPEC['npcs'] if n.startswith(('bosspet_', 'skillpet_'))]
check(len(PETNAMES) == 18, 'there are eighteen of them, ten boss and eight skilling: %d'
      % len(PETNAMES))
for n in sorted(PETNAMES):
    s = SPEC['npcs'][n]; b = NPCB[n]
    got = [v for k, v in sorted(b.items()) if re.match(r'model\d$', k) for v in v]
    check(got == sorted(s['models'], key=lambda x: int(x.rsplit('_', 1)[1]) if x.rsplit('_',1)[1].isdigit() else 0)
          or len(got) == len([m for m in s['models'] if '_head' not in m]),
          '%s carries its %d model(s)' % (n, len(got)))
    for k, want in (('resizeh', s['resizeh']), ('resizev', s['resizev'])):
        have = b.get(k, [None])[0]
        check(have == (str(want) if want else None),
              '...%s is the cache\'s %s' % (k, want if want else 'default (absent)'))
    check(b.get('readyanim') == ['osrs_seq_%d' % s['ready']], '...ready is OSRS seq %d' % s['ready'])
    check(b.get('walkanim') == ['osrs_seq_%d' % s['walk']], '...walk is OSRS seq %d' % s['walk'])
    check(b.get('size') == ['1'], '...and it is still a 1x1 follower')
    check(b.get('vislevel') == ['hide'] and b.get('timer') == ['20'],
          '...with no combat level and the timer that drives [ai_timer,_bosspet]')
    check(b.get('category') == ['bosspet'], '...on the category the drop trigger fires on')

# ============================================================================ 6
print('6. the placeholders are gone, all of them')
for junk, what in (('obj_bird_egg_red', 'the recoloured bird egg'),
                   ('npc_1158', 'the shrunk Kalphite Queen'),
                   ('npc_2881', 'the shrunk Dagannoth'),
                   ('npc_2882', 'the shrunk Dagannoth'),
                   ('npc_3341', 'the 377 baby mole'),
                   ('npc_king_dragoni2', 'the 377 dragon wing')):
    check(junk not in PETOBJ and junk not in PETS, '%s (%s) appears in neither pet config' % (junk, what))
check('PLACEHOLDER ICONS' not in PETOBJ, 'and the note that flagged them is gone with them')

# ============================================================================ 7
print('7. the icons are the items\' own OSRS art, camera included')
for n, s in sorted(SPEC['items'].items()):
    b = OBJB[n]
    check(b.get('model') == ['obj_' + n], '%s draws obj_%s' % (n, n))
    for k, want in (('2dzoom', s['zoom2d']), ('2dxan', s['xan2d']), ('2dyan', s['yan2d']),
                    ('2dzan', s['zan2d']), ('2dxof', s['xof2d']), ('2dyof', s['yof2d'])):
        have = b.get(k, [None])[0]
        check(have == (str(want) if want is not None else None),
              '...%s is the cache\'s %s' % (k, want if want is not None else 'default (absent)'))
    pairs = len([k for k in b if re.match(r'recol\d s?$'.replace(' ', ''), k)])
    check(pairs == s['recols'], '...and carries the cache\'s %d recolour pair(s)' % s['recols'])
    check(n in OBJP, '...and is registered in obj.pack')

# ============================================================================ 8
print('8. the item and the npc still name each other, which is what makes a pet work')
for n in sorted(PETNAMES):
    item = n + '_item'
    check('pet_item_id,%s' % item in NPCB[n].get('param', []), '%s names %s' % (n, item))
    check('follower_id,%s' % n in OBJB[item].get('param', []), '...and %s names it back' % item)
    check(OBJB[item].get('tradeable') == ['no'], '...and the item is untradeable, as the cats are')
check('[opheld5,_bosspet]' in PETRS2 and '[opnpc1,_bosspet]' in PETRS2,
      'and the drop and pick-up triggers are still on the category, not on items')

# ============================================================================ 9
print('9. no pack gained a duplicate, a CR or a stranded id')
for p in ('model.pack', 'npc.pack', 'obj.pack', 'anim.pack', 'animset.pack', 'base.pack', 'seq.pack'):
    raw = open(os.path.join(C, 'pack', p), 'rb').read()
    check(b'\r' not in raw, '%s is LF' % p)
    check(raw.endswith(b'\n'), '...and ends with a newline')
    d = pack(p)
    ids = list(d.values())
    check(len(set(ids)) == len(ids), '...and has no duplicate id')
    check(len(set(d)) == len(d), '...and no duplicate name')
for f in ('scripts/npc/configs/dragons.npc', 'scripts/npc/configs/dragons.seq',
          'scripts/npc/configs/boss_pets.npc', 'scripts/npc/configs/boss_pets.seq',
          'scripts/npc/configs/boss_pets.obj', 'scripts/npc/configs/skill_pets.npc',
          'scripts/npc/configs/skill_pets.seq', 'scripts/npc/configs/skill_pets.obj',
          'scripts/npc/configs/skill_pets.constant', 'scripts/npc/scripts/skill_pets.rs2',
          'tools/bossartspec.json', 'tools/petspec.json'):
    raw = open(os.path.join(C, f), 'rb').read()
    crlf = raw.count(b'\r\n'); lf = raw.count(b'\n') - crlf
    check(not (crlf and lf), '%s has one kind of line ending (%s)'
          % (os.path.basename(f), 'CRLF' if crlf else 'LF'))

# ============================================================================ 10
print('10. every pet is obtainable, or declared not to be, and the sweep agrees')
import subprocess
r = subprocess.run([sys.executable, os.path.join(C, 'tools/obtainable.py')],
                   capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/obtainable.py runs clean')
check('WARNING' not in r.stdout,
      'and finds no disagreement between the specs and what the game can give out')
# Every pet item is either ROLLED by something or DECLARED as having no source on purpose - never
# neither. The sweep's own hard list cannot carry a pet, because a pet is always mentioned by its
# two configs and so reads as "reachable, probably" to the loose pass; this is the claim that
# actually bites. (The first version of this check asked the hard list and could not fail at all.)
bydesign = r.stdout.split('BUILT WITH NO SOURCE ON PURPOSE', 1)[-1] \
                   .split('NOTHING ANYWHERE MENTIONS', 1)[0]
rolled = ''
for dirpath, _dirs, files in os.walk(os.path.join(C, 'scripts')):
    for fn in files:
        if fn.endswith('.rs2'):
            rel = os.path.join(dirpath, fn)[len(C) + 1:]
            rolled += '\n'.join(l.split('//')[0] for l in read(rel).split('\n'))
stray = []
for n in SPEC['items']:
    can_get = re.search(r'~(boss|skill)pet_roll(_each)?\(%s\b' % n, rolled) is not None
    declared = re.search(r'\b%s\b' % n, bydesign) is not None
    if can_get == declared:
        stray.append('%s (%s)' % (n, 'both' if can_get else 'neither'))
check(not stray, 'every pet item is either rolled by something or declared sourceless, '
                 'never both and never neither: %s' % (stray or 'all 18'))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
