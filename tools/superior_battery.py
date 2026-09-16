"""Battery for the superior slayer monsters - the "Bigger and Badder" unlock.

Sixteen imported monsters with no coverage at all until this file existed. What can silently break
here is not the fight, which is the engine's default combat, but the WIRING: a superior whose
slayer_category names the wrong task credits the wrong kill, one missing from ~superior_loot drops
nothing at all, and a model repointed at another mesh is still a monster at a glance. Every number
below is measured against tools/superiorspec.json, which records each one's OSRS npc id and its
CONVERTED vertex and face counts, so nothing here can pass by agreeing with itself.

WHAT IS DELIBERATELY NOT CHECKED. There is no invariant that a superior's vertex label groups
match the groups its borrowed animation set drives - it was tried and the data says no. A 377
skeleton is shared across many models and declares more groups than any one of them uses, so
twelve of the nineteen npcs here have animations driving groups their models do not have, and all
twelve are fine: an undriven group is a part that stays rigid, not a part that breaks. The one
place a rig claim IS made is the cave abomination, in group 6, because there it was measured
against the exact model it borrows from rather than assumed from a pattern.

    python3 tools/superior_battery.py
"""
import collections, json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def before(hay, a, b):
    """a appears before b - and False rather than an exception when either is missing."""
    return a in hay and b in hay and hay.index(a) < hay.index(b)

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

def shape(path):
    """vertex and face counts out of the .ob2's own footer, the way the client reads them."""
    b = open(os.path.join(C, path), 'rb').read(); n = len(b)
    return (b[n-18] << 8) | b[n-17], (b[n-16] << 8) | b[n-15]

def vertex_labels(path):
    """The vertex label byte per vertex. Section order is Model.java's, not the flag order: the
    walk is reconciled against the file length so a wrong order cannot return plausible bytes."""
    b = open(os.path.join(C, path), 'rb').read(); n = len(b); o = n - 18
    g2 = lambda i: (b[i] << 8) | b[i+1]
    vc, fc, tc = g2(o), g2(o+2), b[o+4]
    f_tex, f_pri, f_alpha, f_flabel, f_vlabel = b[o+5], b[o+6], b[o+7], b[o+8], b[o+9]
    xlen, ylen, zlen, flen = g2(o+10), g2(o+12), g2(o+14), g2(o+16)
    p = vc + fc
    if f_pri == 255: p += fc
    if f_flabel == 1: p += fc
    lab_at = p + (fc if f_tex == 1 else 0)
    walk = lab_at + (vc if f_vlabel == 1 else 0) + (fc if f_alpha == 1 else 0)
    walk += flen + fc * 2 + tc * 6 + xlen + ylen + zlen
    if walk != n - 18:
        raise ValueError('%s: section walk %d != body %d' % (path, walk, n - 18))
    if f_vlabel != 1: return None
    return collections.Counter(b[lab_at:lab_at+vc])

SPEC = json.loads(read('tools/superiorspec.json'))
SUPS = SPEC['superiors']
NPCB = blocks(read('scripts/skill_slayer/configs/superiors.npc'))
ENUM = read('scripts/skill_slayer/configs/superiors.enum')
RS2 = read('scripts/skill_slayer/scripts/superiors.rs2')
SPECIALS = read('scripts/skill_slayer/scripts/superior_specials.rs2')
HORROR = read('scripts/areas/area_mos_le_harmless/scripts/cave_horror.rs2')
REQ = read('scripts/skill_slayer/configs/slayer_req.enum')
MODELP, NPCP = pack('model.pack'), pack('npc.pack')
ANIMP = pack('anim.pack')

REQLEVEL = dict((m.group(1), int(m.group(2)))
                for m in re.finditer(r'(?m)^val=(\^\w+),(\d+)$', REQ))
ENUMROWS = re.findall(r'(?m)^val=(\^\w+),(\w+)$', ENUM)

# every [seq] block in the tree, so a borrowed animation can be proved to exist
SEQB = {}
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for f in sorted(fs):
        if f.endswith('.seq'):
            SEQB.update(blocks(open(os.path.join(root, f), newline='', errors='replace')
                               .read().replace('\r\n', '\n')))

def seqs_of(d):
    """Every animation a superior's config names, in config order."""
    out = list(d.get('readyanim', [])) + list(d.get('walkanim', []))
    for pv in d.get('param', []):
        k, _, v = pv.partition(',')
        if k in ('attack_anim', 'defend_anim', 'death_anim'): out.append(v)
    return out

def param(d, key):
    for pv in d.get('param', []):
        k, _, v = pv.partition(',')
        if k == key: return v
    return None

# ============================================================================ 1
print('1. every superior is a real npc wearing the mesh the spec measured')
for name, s in sorted(SUPS.items()):
    check(name in NPCB, '%s has a config block' % name)
    check(name in NPCP, '...and is registered in npc.pack')
    for mn, want in sorted(s['models'].items()):
        path = 'models/%s/%s.ob2' % ('npc', mn)
        here = os.path.exists(os.path.join(C, path))
        check(here, '%s is a file on disk' % mn)
        check(mn in MODELP, '...and is registered in model.pack')
        if here:
            v, f = shape(path)
            check((v, f) == (want['verts'], want['faces']),
                  '...and is the mesh the spec measured: %d verts %d faces%s'
                  % (v, f, '' if (v, f) == (want['verts'], want['faces'])
                     else ' - SPEC SAYS %d/%d' % (want['verts'], want['faces'])))
    # the other half: the CONFIG has to name exactly those models, or the spec walks past art
    # nothing wears
    named = sorted(m for k in sorted(NPCB.get(name, {}))
                   if re.fullmatch(r'model\d|head\d', k) for m in NPCB[name][k])
    check(named == sorted(s['models']),
          '%s names exactly the spec\'s models: %s' % (name, ', '.join(named) or '(none)'))

# ============================================================================ 2
print('2. the combat numbers are the cache\'s, not remembered ones')
for name, s in sorted(SUPS.items()):
    d = NPCB.get(name, {})
    check(d.get('vislevel', [None])[0] == str(s['level']),
          '%s is level %d' % (name, s['level']))
    got = [d.get(k, ['1'])[0] for k in ('attack', 'defence', 'strength', 'hitpoints', 'ranged', 'magic')]
    check(got == [str(v) for v in s['stats']],
          '...with the cache\'s stats %s' % (','.join(got)))
    # size 1 is the config default and is written only when it is not 1
    check(d.get('size', ['1'])[0] == str(s['size']), '...and is %d tiles' % s['size'])

# ============================================================================ 3
print('3. the table, the configs and the slayer requirements agree in both directions')
enum_names = [n for _, n in ENUMROWS]
check(sorted(enum_names) == sorted(SUPS),
      'every spec\'d superior has exactly one enum row and no row is a stranger')
check(len(enum_names) == len(set(enum_names)), 'no superior appears twice in the table')
for task, name in ENUMROWS:
    check(task in REQLEVEL, '%s is a task slayer_req.enum knows' % task)
    check(SUPS.get(name, {}).get('task') == task, '...and the spec keys %s on it' % name)
    check(param(NPCB.get(name, {}), 'slayer_category') == task,
          '...and %s credits kills to it' % name)
levels = [REQLEVEL.get(t, -1) for t, _ in ENUMROWS]
check(levels == sorted(levels),
      'the table is in ascending slayer-requirement order, so a new row lands where it belongs')
# the three chaotic death spawns are npcs in this file that are NOT superiors, and must not become
# rollable by being given a category
for name in sorted(NPCB):
    if name in SUPS: continue
    check(param(NPCB[name], 'slayer_category') is None,
          '%s is not a superior and carries no slayer_category' % name)

# ============================================================================ 4
print('4. every superior dies, and dying drops its cousin\'s table')
for name in sorted(SUPS):
    direct = '[ai_queue3,%s] @superior_death;' % name in RS2
    staged = ('[ai_queue4,%s] @superior_death;' % name in RS2
              and re.search(r'\[ai_queue3,%s\]' % name, RS2) is not None)
    check(direct or staged, '%s reaches @superior_death when it dies' % name)
LOOT = RS2.split('[proc,superior_loot]', 1)[-1].split('[proc,', 1)[0]
for name in sorted(SUPS):
    m = re.search(r'case %s : ~(\w+);' % name, LOOT)
    check(m is not None, '%s has a case in ~superior_loot' % name)
    if m:
        check('[proc,%s]' % m.group(1) in RS2 + SPECIALS + HORROR
              or any('[proc,%s]' % m.group(1) in read(os.path.join('scripts/drop_tables/scripts', f))
                     for f in os.listdir(os.path.join(C, 'scripts/drop_tables/scripts'))
                     if f.endswith('.rs2')),
              '...and the proc it names exists: ~%s' % m.group(1))
check(LOOT.count('case ') == len(SUPS),
      '~superior_loot has exactly as many cases as there are superiors')
check(before(RS2, '~superior_loot($type);\n~superior_loot($type);\n~superior_loot($type);',
             '[proc,superior_loot]'),
      'the table is rolled three times per kill, as OSRS rolls it')

# ============================================================================ 5
print('5. every animation a superior borrows exists, frame by frame')
for name in sorted(SUPS):
    d = NPCB.get(name, {})
    names = seqs_of(d)
    check(len(names) == 5, '%s names five animations: ready, walk, attack, defend, death' % name)
    unknown = [sn for sn in names if sn not in SEQB]
    check(not unknown, '...and every one is a [seq] block in the tree: %s' % (', '.join(unknown) or 'yes'))
    empty, astray = [], []
    for sn in names:
        if sn not in SEQB: continue
        frames = [f for k in sorted(SEQB[sn]) if re.fullmatch(r'frame\d+', k) for f in SEQB[sn][k]]
        if not frames: empty.append(sn)
        astray += [f for f in frames if f not in ANIMP]
    check(not empty, '...each with at least one frame: %s' % (', '.join(empty) or 'yes'))
    check(not astray, '...and every frame of every one is in anim.pack: %s'
          % (', '.join(sorted(set(astray))[:4]) or 'yes'))

# ============================================================================ 6
print('6. the cave abomination, the sixteenth, and the rig it borrows')
RIG = SPEC['abomination_rig']
ab = vertex_labels('models/npc/%s.ob2' % RIG['model'])
horror = collections.Counter()
for mn in RIG['horror_models']:
    horror += vertex_labels('models/npc/%s.ob2' % mn)
check(ab is not None and horror, 'both meshes carry vertex labels at all')
check(sorted(set(ab) - {RIG['unlabelled']}) == RIG['shared_groups'],
      'the abomination is rigged on exactly the groups the spec recorded: %d of them'
      % len(RIG['shared_groups']))
check(sorted(set(horror)) == sorted(set(ab) - {RIG['unlabelled']}),
      '...which is exactly the set the cave horror\'s two meshes use - the two meshes compared with each other, not both with the spec')
check(ab[RIG['unlabelled']] == RIG['unlabelled_verts'],
      '...and its unlabelled vertices are the flat ground plate, which no frame moves: %d'
      % ab[RIG['unlabelled']])
check(horror.get(RIG['unlabelled'], 0) == 0,
      '...which the horror does not have, so 255 is the abomination\'s alone')
# the fingerprint: the small groups are the same SIZE in both meshes, which is what says the
# labels mean the same body parts rather than merely running to the same number
for g, want in sorted((int(k), v) for k, v in RIG['fingerprint'].items()):
    check(horror.get(g) == want and ab.get(g) == want,
          '...group %d is the same size in both meshes: horror %s, abomination %s, spec %s'
          % (g, horror.get(g), ab.get(g), want))
ABOM = NPCB.get('superior_cave_abomination', {})
for k in ('readyanim', 'walkanim'):
    check(ABOM.get(k, [''])[0].startswith('cave_horror_'),
          'its %s is the cave horror\'s own' % k)
for k in ('attack_anim', 'defend_anim', 'death_anim'):
    check((param(ABOM, k) or '').startswith('cave_horror_'),
          'its %s is the cave horror\'s own' % k)
check(param(ABOM, 'strengthbonus') is None,
      'strengthbonus is left unset, as it is on the other fifteen')
# the screech, and the one item that stops it
AP = RS2.split('[ai_applayer2,superior_cave_abomination]', 1)[-1].split('[ai_', 1)[0]
OP = RS2.split('[ai_opplayer2,superior_cave_abomination]', 1)[-1].split('[ai_', 1)[0]
check('[ai_queue1,superior_cave_abomination] gosub(npc_default_retaliate_ap);' in RS2,
      'it retaliates like the banshee and the cockatrice do')
check('witchwood_icon' in AP and '~cave_horror_screech;' in AP,
      'with no witchwood icon worn it screeches instead of attacking')
check('witchwood_icon' in OP and 'npc_setmode(applayer2);' in OP,
      'and taking the icon off mid-fight sends it back to screeching')
check('gosub(npc_default_attack);' in OP, 'with the icon on it fights normally')
for wrong in ('slayer_earmuffs', '~slayer_helm_worn', 'slayer_mirror_shield'):
    check(wrong not in AP and wrong not in OP,
          'no %s: earmuffs, the helm and the shield do nothing down there' % wrong.strip('~'))
check('case superior_cave_abomination : ~cave_horror_drop_table_loot;' in LOOT,
      'it rolls the cave horror\'s own table, the proc that was split out for it')
check('[proc,cave_horror_drop_table_loot]' in HORROR,
      '...which still lives in area_mos_le_harmless and is still a proc')
check(REQLEVEL.get('^slayer_cavehorror') == 58,
      'and the unique roll reads its 58 Slayer out of slayer_req.enum')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
