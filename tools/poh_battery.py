"""Symbol and signature battery for the two new .rs2 files, from claude/rs2-compile-traps.md."""
import re, sys, os
C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['scripts/skill_construction/scripts/poh.rs2', 'scripts/skill_construction/scripts/poh_test.rs2',
         'scripts/skill_construction/scripts/poh_portal.rs2', 'scripts/skill_construction/scripts/poh_build.rs2',
         'scripts/skill_construction/scripts/sawmill.rs2']
fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

src = {f: read(f) for f in FILES}
def strip(t):
    t = re.sub(r'/\*.*?\*/', '', t, flags=re.S)
    out = []
    for line in t.split('\n'):
        line = re.sub(r'"[^"]*"', '""', line)
        out.append(line.split('//')[0])
    return '\n'.join(out)
clean = {f: strip(t) for f, t in src.items()}
alltext = '\n'.join(clean.values())

print('1. balance')
for f, t in clean.items():
    check(t.count('(') == t.count(')'), '%s parens %d/%d' % (os.path.basename(f), t.count('('), t.count(')')))
    check(t.count('{') == t.count('}'), '%s braces %d/%d' % (os.path.basename(f), t.count('{'), t.count('}')))

print('2. no @label jump inside a proc (trap 5b)')
bad = []
for f, t in clean.items():
    cur = None
    for ln in t.split('\n'):
        m = re.match(r'^\[(\w+),', ln)
        if m: cur = m.group(1)
        if re.search(r'@\w+[;(]', ln) and cur == 'proc': bad.append((f, ln.strip()))
check(not bad, 'none, got %s' % bad)

print('3. declared scripts are unique, and nothing is declared twice')
decl = re.findall(r'^\[(\w+),(\w+)\]', alltext, re.M)
check(len(decl) == len(set(decl)), 'no duplicate [kind,name] in the new files')
names = {n for k, n in decl}
print('   declares: ' + ', '.join('%s %s' % (k, n) for k, n in decl))

print('4. every ~proc call resolves')
# Against the WHOLE repo, not just these files: poh_portal.rs2 talks to the shared dialogue procs
# (~chatnpc, ~p_choice2) and a whitelist would only record that I believed they exist.
repo_procs = set()
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for fn in fs:
        if fn.endswith('.rs2'):
            with open(os.path.join(root, fn), encoding='utf-8', errors='replace') as fh:
                repo_procs |= set(re.findall(r'^\[(?:proc|label|debugproc),(\w+)\]', fh.read(), re.M))
called = set(re.findall(r'~(\w+)', alltext))
unknown = sorted(called - names - repo_procs)
check(not unknown, 'unresolved: %s' % unknown)

print('5. every %varp resolves against pack/varp.pack')
varps = {l.split('=', 1)[1] for l in open(C + '/pack/varp.pack').read().split('\n') if '=' in l}
used = set(re.findall(r'%(\w+)', alltext))
check(not (used - varps), 'unresolved: %s' % sorted(used - varps))
print('   uses: ' + ', '.join(sorted(used)))

print('6. every ^constant resolves')
consts = set()
for p in ['scripts/skill_construction/configs/construction.constant', 'scripts/engine.constant']:
    if os.path.exists(os.path.join(C, p)):
        consts |= set(re.findall(r'^\^(\w+)\s*=', read(p), re.M))
usedc = set(re.findall(r'\^(\w+)', alltext))
check(not (usedc - consts), 'unresolved: %s' % sorted(usedc - consts))

print('7. every enum name resolves against pack/enum.pack')
enums = {l.split('=', 1)[1] for l in open(C + '/pack/enum.pack').read().split('\n') if '=' in l}
usede = set(re.findall(r'enum\(\s*\w+\s*,\s*\w+\s*,\s*(\w+)\s*,', alltext))
check(not (usede - enums), 'unresolved: %s (used %s)' % (sorted(usede - enums), sorted(usede)))

print('8. the poh_hotspot category is really defined')
# pack/category.pack is GENERATED and gitignored - categories come from category= lines in the
# configs, so the pack in a working copy can be older than the content and proves nothing.
locs = read('scripts/skill_construction/configs/poh_templates.loc')
check(locs.count('category=poh_hotspot') > 0,
      '%d locs carry category=poh_hotspot' % locs.count('category=poh_hotspot'))

print('9. every command call matches its engine.rs2 signature')
sig = {}
for m in re.finditer(r'^\[command,(\w+)\]\s*(\(([^)]*)\))?\s*(\(([^)]*)\))?', read('scripts/engine.rs2'), re.M):
    name, args, rets = m.group(1), m.group(3), m.group(5)
    if args is None:
        sig[name] = (None, None)
    else:
        n = 0 if args.strip() == '' else len([a for a in args.split(',') if a.strip()])
        sig[name] = (n, (rets or '').strip())
def top_args(s):
    """split a call's argument text on top-level commas"""
    out, depth, cur = [], 0, ''
    for ch in s:
        if ch == '(': depth += 1
        elif ch == ')': depth -= 1
        if ch == ',' and depth == 0:
            out.append(cur); cur = ''
        else:
            cur += ch
    if cur.strip(): out.append(cur)
    return out
bad = []
for f, t in clean.items():
    body = '\n'.join(l for l in t.split('\n') if not l.startswith('[command,'))
    for m in re.finditer(r'(?<![~$%^\w])(\w+)\(', body):
        name = m.group(1)
        if name not in sig: continue
        want = sig[name][0]
        if want is None: continue
        # find the matching close paren
        i = m.end(); depth = 1
        while i < len(body) and depth:
            if body[i] == '(': depth += 1
            elif body[i] == ')': depth -= 1
            i += 1
        got = len(top_args(body[m.end():i - 1]))
        if got != want:
            bad.append('%s: %s takes %d, given %d' % (os.path.basename(f), name, want, got))
check(not bad, 'arity mismatches: %s' % bad)
used_cmds = sorted({m.group(1) for f, t in clean.items() for m in re.finditer(r'(?<![~$%^\w])(\w+)\(', t) if m.group(1) in sig})
print('   commands used: ' + ', '.join(used_cmds))

print('10. no bare call to a command that returns something (trap 2)')
bad = []
for f, t in clean.items():
    for ln in t.split('\n'):
        s2 = ln.strip()
        m = re.match(r'^(\w+)\(.*\);$', s2)
        if m and m.group(1) in sig and sig[m.group(1)][1]:
            bad.append('%s: %s' % (os.path.basename(f), s2))
check(not bad, 'discarded returns: %s' % bad)

print('11. line endings')
for f in FILES + ['scripts/skill_construction/configs/poh_rooms.enum',
                  'scripts/skill_construction/configs/construction.varp',
                  'scripts/skill_construction/configs/construction.constant',
                  'scripts/skill_construction/configs/poh_portal.loc',
                  'scripts/skill_construction/configs/poh_portal.npc',
                  'maps/m46_50.jm2']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r\r' not in b and b.count(b'\n') == b.count(b'\r\n'), '%s is clean CRLF' % os.path.basename(f))
for f in ['pack/varp.pack', 'pack/enum.pack', 'pack/loc.pack', 'pack/npc.pack']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r' not in b and b.endswith(b'\n'), '%s is LF and ends with a newline' % os.path.basename(f))

print('12. pack ids are unique, and the new ones sit above what was there')
# Not contiguity: varp.pack is missing id 746 upstream and has always built fine. What matters is
# that nothing is claimed twice and that the ids added here were free.
NEW = {'pack/varp.pack': list(range(876, 894)), 'pack/enum.pack': [128, 129, 130, 131, 132],
       'pack/loc.pack': [15296, 15297], 'pack/npc.pack': [3920, 3921]}
for f in ['pack/varp.pack', 'pack/enum.pack', 'pack/loc.pack', 'pack/npc.pack']:
    ids = [int(l.split('=', 1)[0]) for l in open(os.path.join(C, f)).read().split('\n') if '=' in l]
    check(len(set(ids)) == len(ids), '%s has no duplicate id' % os.path.basename(f))
    check(all(ids.count(i) == 1 for i in NEW[f]), '%s: every id added here appears exactly once' % os.path.basename(f))
    check(max(ids) == max(NEW[f]), '%s: the new block is the top of the file' % os.path.basename(f))

# =========================================================================== the portal round

def packmap(f):
    out = {}
    for l in open(os.path.join(C, f)).read().split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            out[n] = int(i)
    return out

LOCS = packmap('pack/loc.pack')
NPCS = packmap('pack/npc.pack')
MODELS = set(packmap('pack/model.pack'))
SEQS = set(packmap('pack/seq.pack'))
OBJS = set(packmap('pack/obj.pack'))

def blocks(text):
    """[name] -> {key: [values]} for a config file"""
    out, cur = {}, None
    for line in text.split('\n'):
        line = line.split('//')[0].strip()
        if not line:
            continue
        if line.startswith('['):
            cur = line.strip('[]')
            out[cur] = {}
        elif '=' in line and cur:
            k, v = line.split('=', 1)
            out[cur].setdefault(k, []).append(v)
    return out

print('13. the new locs and npc are registered and used by name')
LOCCFG = blocks(read('scripts/skill_construction/configs/poh_portal.loc'))
NPCCFG = blocks(read('scripts/skill_construction/configs/poh_portal.npc'))
check(sorted(LOCCFG) == ['poh_exit_portal', 'poh_house_portal'], 'poh_portal.loc defines %s' % sorted(LOCCFG))
check(sorted(NPCCFG) == ['poh_estate_agent'], 'poh_portal.npc defines %s' % sorted(NPCCFG))
for n in LOCCFG:
    check(n in LOCS, '%s is in loc.pack (id %s)' % (n, LOCS.get(n)))
for n in NPCCFG:
    check(n in NPCS, '%s is in npc.pack (id %s)' % (n, NPCS.get(n)))

print('14. every model, anim and obj the round names really exists')
# The loc packer looks up the bare name first and falls back to name_8 (LocConfig.ts); npc models
# are looked up as written.
for n, cfg in LOCCFG.items():
    for k in ('model', 'model2', 'model3', 'model4', 'model5'):
        for v in cfg.get(k, []):
            check(v in MODELS or (v + '_8') in MODELS, '%s %s=%s resolves' % (n, k, v))
    for v in cfg.get('anim', []):
        check(v in SEQS, '%s anim=%s is in seq.pack' % (n, v))
for n, cfg in NPCCFG.items():
    for k, vs in cfg.items():
        if re.match(r'^(model|head)\d+$', k):
            for v in vs:
                check(v in MODELS, '%s %s=%s resolves' % (n, k, v))
objs_used = set(re.findall(r'inv_(?:total|del|add)\(\s*\w+\s*,\s*(\w+)', alltext))
for o in sorted(objs_used):
    check(o in OBJS, 'obj %s is in obj.pack' % o)

print('15. Rimmington: the portal is on the map, on free tiles, next to where leaving lands you')
MAPF = 'maps/m46_50.jm2'
mlines = read(MAPF).split('\n')
sec, land, mlocs, mnpcs = None, {}, {}, {}
for line in mlines:
    if line.startswith('===='):
        sec = line.strip('= ')
        continue
    if ':' not in line:
        continue
    head, data = line.split(':', 1)
    lv, x, z = (int(v) for v in head.split())
    d = data.split()
    if sec == 'LOC':
        parts = [int(v) for v in d]
        shape = parts[1] if len(parts) > 1 else 10
        angle = parts[2] if len(parts) > 2 else 0
        mlocs.setdefault((lv, x, z), []).append((parts[0], shape, angle))
    elif sec == 'NPC':
        mnpcs.setdefault((lv, x, z), []).append(int(d[0]))
    elif sec == 'MAP':
        land[(lv, x, z)] = d

placed = [(k, e) for k, es in mlocs.items() for e in es if e[0] == LOCS['poh_house_portal']]
check(len(placed) == 1, 'the house portal is placed exactly once, got %d' % len(placed))
agent = [k for k, ids in mnpcs.items() for i in ids if i == NPCS['poh_estate_agent']]
check(len(agent) == 1, 'the estate agent is placed exactly once, got %d' % len(agent))
check(LOCS['poh_exit_portal'] not in [e[0] for es in mlocs.values() for e in es],
      'the exit portal is NOT on the map - it is spawned inside the house')

if len(placed) == 1:
    (plv, px, pz), (_, pshape, pangle) = placed[0]
    width = int(LOCCFG['poh_house_portal'].get('width', ['1'])[0])
    length = int(LOCCFG['poh_house_portal'].get('length', ['1'])[0])
    if pangle % 2 == 1:
        width, length = length, width
    covered = {(plv, px + dx, pz + dz) for dx in range(width) for dz in range(length)}
    check(pshape == 10, 'it is centrepiece_straight (shape %d)' % pshape)
    for t in sorted(covered):
        others = [e for e in mlocs.get(t, []) if e[0] != LOCS['poh_house_portal'] and e[1] != 22]
        check(not others, 'tile %s carries nothing else that blocks: %s' % (t[1:], others))
        check(t in land, 'tile %s is real ground' % (t[1:],))
    # ^poh_exit is level_mx_mz_lx_lz
    exitc = re.search(r'^\^poh_exit\s*=\s*(\d+)_(\d+)_(\d+)_(\d+)_(\d+)',
                      read('scripts/skill_construction/configs/construction.constant'), re.M)
    check(exitc is not None, '^poh_exit parses')
    if exitc:
        elv, emx, emz, ex, ez = (int(g) for g in exitc.groups())
        check((emx, emz) == (46, 50), '^poh_exit is in the square the portal is on (m%d_%d)' % (emx, emz))
        check((elv, ex, ez) not in covered, 'leaving does not land you inside the portal')
        check(any(abs(ex - x) + abs(ez - z) == 1 for (_, x, z) in covered),
              'leaving lands you next to the portal, at %d,%d' % (ex, ez))
        check((elv, ex, ez) in land, 'the landing tile is real ground')
    for t in agent:
        check(t not in covered, 'the estate agent does not stand inside the portal')

print('16. inside the house: the exit portal fits in a garden')
CONST = read('scripts/skill_construction/configs/construction.constant')
def const(name):
    m = re.search(r'^\^%s\s*=\s*(-?\d+)\s*$' % name, CONST, re.M)
    return int(m.group(1)) if m else None
EX, EZ = const('poh_exit_portal_x'), const('poh_exit_portal_z')
SX, SZ = const('poh_spawn_x'), const('poh_spawn_z')
DUR = const('poh_loc_duration')
check(DUR is not None and DUR >= 1, '^poh_loc_duration=%s (the engine rejects 0)' % DUR)
ewidth = int(LOCCFG['poh_exit_portal'].get('width', ['1'])[0])
elength = int(LOCCFG['poh_exit_portal'].get('length', ['1'])[0])
ecov = {(EX + dx, EZ + dz) for dx in range(ewidth) for dz in range(elength)}
check(all(0 <= x <= 7 and 0 <= z <= 7 for x, z in ecov), 'it stays inside the room: %s' % sorted(ecov))
check((SX, SZ) not in ecov, 'it does not stand on the tile the player lands on')
check(min(abs(SX - x) + abs(SZ - z) for x, z in ecov) == 1, 'it is next to that tile')

# the garden template itself: everything in that zone must be grass decor or a hotspot, or the
# portal could land on top of something solid.
tmpl = re.search(r'^\^poh_templates_a\s*=\s*(\d+)_(\d+)_(\d+)_(\d+)_(\d+)', CONST, re.M)
gz = None
for m in re.finditer(r'^val=(\d+),(\d+)$', read('scripts/skill_construction/configs/poh_rooms.enum'), re.M):
    if int(m.group(1)) == const('poh_room_garden'):
        gz = int(m.group(2))
        break
check(gz is not None and tmpl is not None, 'the garden template zone is %s of m%s_%s' % (gz, tmpl and tmpl.group(2), tmpl and tmpl.group(3)))
if gz is not None and tmpl is not None:
    tlv, tmx, tmz = int(tmpl.group(1)), int(tmpl.group(2)), int(tmpl.group(3))
    gx0, gz0 = (gz // 8) * 8, (gz % 8) * 8
    hotspots = set()
    TL = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
    TLIDS = packmap('pack/loc.pack')
    for n, cfg in TL.items():
        if 'poh_hotspot' in cfg.get('category', []):
            hotspots.add(TLIDS.get(n))
    tsec, tlocs = None, {}
    for line in read('maps/m%d_%d.jm2' % (tmx, tmz)).split('\n'):
        if line.startswith('===='):
            tsec = line.strip('= ')
            continue
        if tsec != 'LOC' or ':' not in line:
            continue
        head, data = line.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        d = [int(v) for v in data.split()]
        tlocs.setdefault((lv, x, z), []).append((d[0], d[1] if len(d) > 1 else 10))
    blockers = []
    for x, z in sorted(ecov | {(SX, SZ)}):
        for lid, shape in tlocs.get((tlv, gx0 + x, gz0 + z), []):
            if shape != 22 and lid not in hotspots:
                blockers.append((x, z, lid, shape))
    check(not blockers, 'no solid template loc under the exit portal or the landing tile: %s' % blockers)

print('17. ~poh_enter and ~poh_build are always called with the build-mode flag')
bad = []
for f, t in clean.items():
    for m in re.finditer(r'~(poh_enter|poh_build)\b(\()?', t):
        if m.group(2) is None:
            bad.append('%s: bare ~%s' % (os.path.basename(f), m.group(1)))
check(not bad, 'no bare calls: %s' % bad)
check(re.search(r'^\[proc,poh_enter\]\(boolean \$\w+\)', clean[FILES[0]], re.M) is not None,
      '[proc,poh_enter] takes a boolean')
check(re.search(r'^\[proc,poh_build\]\(boolean \$\w+\)\(coord\)', clean[FILES[0]], re.M) is not None,
      '[proc,poh_build] takes a boolean and returns a coord')

print('18. %poh_owned is a gate, not something entering grants')
enter_body = clean[FILES[0]].split('[proc,poh_enter]')[1].split('[proc,')[0]
check('%poh_owned = 0' in enter_body and 'return' in enter_body,
      'poh_enter turns away a player who owns nothing')
check('%poh_owned = 1' not in enter_body, 'poh_enter does not hand out ownership')

print('19. the imported OSRS art: every model, frame and base actually on disk')
# claude/osrs-cache.md's pre-ship sweep, narrowed to this round. A name in a .pack is not a file:
# every earlier import batch was checked this way before it shipped, and this one has three chained
# registries behind it (seq -> anim -> animset/base) where a miss shows up in game as an invisible
# loc rather than an error.
ON_DISK = set()
for root, _, fs in os.walk(os.path.join(C, 'models')):
    for fn in fs:
        if fn.endswith('.ob2'): ON_DISK.add(fn[:-4])
ANIMS = set(packmap('pack/anim.pack'))
ANIMSETS = set(packmap('pack/animset.pack'))
BASES = set(packmap('pack/base.pack'))
SUFFIX = ['_1', '_2', '_3', '_4', '_q', '_w', '_r', '_e', '_t', '_5', '_8', '_9',
          '_a', '_s', '_d', '_f', '_g', '_h', '_z', '_x', '_c', '_v', '_0']

named = []
for n, cfg in LOCCFG.items():
    for k, vs in cfg.items():
        if re.match(r'^model\d*$', k): named += [(n, k, v, True) for v in vs]
for n, cfg in NPCCFG.items():
    for k, vs in cfg.items():
        if re.match(r'^(model|head)\d+$', k): named += [(n, k, v, False) for v in vs]
for n, k, v, is_loc in named:
    hit = v in ON_DISK or (is_loc and any((v + sfx) in ON_DISK for sfx in SUFFIX))
    check(hit, '%s %s=%s has a .ob2 on disk' % (n, k, v))

SEQF = 'scripts/skill_construction/configs/poh_portal.seq'
seqs_declared = set(re.findall(r'^\[(\w+)\]', read(SEQF), re.M))
anims_used = {v for cfg in LOCCFG.values() for v in cfg.get('anim', [])}
for a in sorted(anims_used):
    check(a in seqs_declared or a in SEQS, '%s is declared (poh_portal.seq) or already in seq.pack' % a)
    check(a in SEQS, '%s is registered in seq.pack' % a)

frames = re.findall(r'^frame\d+=(\S+)$', read(SEQF), re.M)
check(len(frames) > 0, 'poh_portal.seq names %d frames' % len(frames))
delays = re.findall(r'^delay\d+=', read(SEQF), re.M)
check(len(delays) == len(frames), 'every frame has a delay (%d/%d)' % (len(delays), len(frames)))
sets_needed = set()
for f in frames:
    check(f in ANIMS, 'frame %s is in anim.pack' % f)
    sets_needed.add(f.rsplit('_', 1)[0])
for st_ in sorted(sets_needed):
    check(st_ in ANIMSETS, '%s is in animset.pack' % st_)
    check(st_.replace('anim_', 'base_', 1) in BASES, '%s base is in base.pack' % st_)
    path = os.path.join(C, 'models', st_ + '.anim')
    check(os.path.exists(path) and os.path.getsize(path) > 0, '%s.anim is on disk' % st_)

print('20. no pack gained a CR, a duplicate name or a duplicate id')
for f in ['pack/model.pack', 'pack/anim.pack', 'pack/animset.pack', 'pack/base.pack',
          'pack/seq.pack', 'pack/loc.pack', 'pack/npc.pack']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r' not in b and b.endswith(b'\n'), '%s is LF and ends with a newline' % os.path.basename(f))
    rows = [l for l in b.decode().split('\n') if '=' in l]
    ids = [l.split('=', 1)[0] for l in rows]; nms = [l.split('=', 1)[1] for l in rows]
    check(len(set(ids)) == len(ids), '%s has no duplicate id' % os.path.basename(f))
    check(len(set(nms)) == len(nms), '%s has no duplicate name' % os.path.basename(f))

print('21. the ground under the portal is level')
# THE CHECK THIS ROUND EARNED. The OSRS house portal is five tiles wide - every variant in the cache
# is, so there is no smaller one to fall back to - and a 377 loc sits at ONE height taken from its
# footprint, with the ground running through it. The first placements put it across the bank west of
# the Rimmington road, where the ground falls h35 to h12 over the five tiles it needs: its west end
# was buried and its east end floated. Nothing in the pipeline had ever looked at terrain.
#
# A tile with no explicit h in the .jm2 is NOT unknown: the client generates it (World.method32), and
# tools/terrain377.py is that function transcribed, so every tile has a height here. Validated
# against the map itself - at the 801 places an explicit tile borders a generated one the two agree
# to a mean of 2.3, against 9.1 for the same noise sampled 37 tiles away.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain377 import height_of

EXPLICIT = {}
sec = None
for line in read(MAPF).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if sec != 'MAP' or ':' not in line:
        continue
    head, data = line.split(':', 1)
    lv, x, z = (int(v) for v in head.split())
    if lv != 0:
        continue
    m = re.search(r'(?:^| )h(\d+)', data)
    EXPLICIT[(x, z)] = int(m.group(1)) if m else None

MSQ = re.match(r'maps/m(\d+)_(\d+)\.jm2', MAPF)
MX, MZ = int(MSQ.group(1)), int(MSQ.group(2))
def ground(x, z):
    h = EXPLICIT.get((x, z))
    return h if h is not None else height_of(MX * 64 + x, MZ * 64 + z)

# the transcription has to be right, or every number below is decoration
seams = []
for (x, z), h in EXPLICIT.items():
    if h is None: continue
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + dx, z + dz)
        if n in EXPLICIT and EXPLICIT[n] is None:
            seams.append(abs(h - height_of(MX * 64 + n[0], MZ * 64 + n[1])))
mean = sum(seams) / len(seams) if seams else 99
ctrl = []
for (x, z), h in EXPLICIT.items():
    if h is None: continue
    for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        n = (x + dx, z + dz)
        if n in EXPLICIT and EXPLICIT[n] is None:
            ctrl.append(abs(h - height_of(MX * 64 + n[0] + 37, MZ * 64 + n[1] + 37)))
cmean = sum(ctrl) / len(ctrl) if ctrl else 0
check(mean < cmean / 2, 'terrain377 tracks the map: %d seams, mean |diff| %.2f vs %.2f for shifted noise'
      % (len(seams), mean, cmean))

MAX_SPREAD = 4          # ~0.25 of a tile of elevation across the whole footprint
if len(placed) == 1:
    hs = [ground(x, z) for lv, x, z in sorted(covered)]
    check(max(hs) - min(hs) <= MAX_SPREAD,
          'the footprint is level: heights %d..%d, spread %d (max %d)' % (min(hs), max(hs), max(hs) - min(hs), MAX_SPREAD))
    if exitc:
        eh = ground(ex, ez)
        check(abs(eh - min(hs)) <= 12, 'the landing tile is at a sane height next to it (h%d vs h%d)' % (eh, min(hs)))
    for lv, x, z in agent:
        check(abs(ground(x, z) - min(hs)) <= 12, 'the estate agent stands at a sane height (h%d vs h%d)' % (ground(x, z), min(hs)))

print('22. the portal is rotated so it faces the road')
# Placed at angle 3 with width 5 and length 2: an odd rotation swaps them, so the five-tile face runs
# NORTH-SOUTH and the portal looks east, down the bank at the Rimmington road. Check 15 already reads
# the footprint from the config with that swap applied; this is the intent, written down.
if len(placed) == 1:
    check(pangle in (1, 3), 'it is on an odd rotation (angle %d), so its wide face runs north-south' % pangle)
    w = int(LOCCFG['poh_house_portal'].get('width', ['1'])[0])
    l = int(LOCCFG['poh_house_portal'].get('length', ['1'])[0])
    xs = {x for lv, x, z in covered}; zs = {z for lv, x, z in covered}
    check(len(xs) == l and len(zs) == w,
          'the footprint is %d wide by %d deep on the ground (config %dx%d)' % (len(xs), len(zs), w, l))

print('23. build mode: every door hotspot has a trigger, and nothing else does')
# The click has to resolve to a grid cell and a side, and only a door hotspot carries both. A
# "Door space" or a "Centrepiece space" wired to the same proc would compute a side of 0 and dead-end.
TEMPL = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
doors = sorted(n for n, cfg in TEMPL.items() if (cfg.get('name') or [''])[0] == 'Door hotspot')
trig = sorted(re.findall(r'^\[oploc5,(\w+)\]', clean[FILES[3]], re.M))
check(trig == doors, '%d door hotspot locs, %d triggered, same set: %s'
      % (len(doors), len(trig), 'yes' if trig == doors else sorted(set(doors) ^ set(trig))))
for n in trig:
    check(n in LOCS, '%s is registered in loc.pack' % n)
    check('poh_hotspot' in (TEMPL.get(n, {}).get('category') or []), '%s carries category=poh_hotspot' % n)
    check('Build' in (TEMPL.get(n, {}).get('op5') or []), '%s has op5=Build for the trigger to fire on' % n)

print('24. build mode: the tables are complete and the idioms are ones this repo has compiled')
ENUMF = read('scripts/skill_construction/configs/poh_rooms.enum')
tables = {}
cur = None
for line in ENUMF.split('\n'):
    line = line.split('//')[0].strip()
    if line.startswith('['):
        cur = line.strip('[]'); tables[cur] = {}
    else:
        m = re.match(r'^val=(\d+),(.*)$', line)
        if m and cur: tables[cur][int(m.group(1))] = m.group(2)
COUNT = const('poh_room_count')
check(COUNT == 15, '^poh_room_count is %s' % COUNT)
for t in ('poh_room_zone', 'poh_room_doors', 'poh_room_name', 'poh_room_cost', 'poh_room_level'):
    check(t in tables, '%s exists' % t)
    have = sorted(tables.get(t, {}))
    check(have == list(range(1, COUNT + 1)), '%s covers every room type 1..%d' % (t, COUNT))
for i, v in tables.get('poh_room_cost', {}).items():
    check(int(v) > 0, 'room %d costs something (%s)' % (i, v))
for i, v in tables.get('poh_room_level', {}).items():
    check(1 <= int(v) <= 99, 'room %d has a sane level (%s)' % (i, v))

# the four idioms that have no precedent in this repo, per claude/rs2-compile-traps.md
bad = []
for f, t in clean.items():
    if 'def_string' in t: bad.append('%s: def_string' % os.path.basename(f))
    if 'while (true)' in t: bad.append('%s: while (true)' % os.path.basename(f))
    if re.search(r'\)\(string\)', t): bad.append('%s: a proc returning a string' % os.path.basename(f))
    if re.search(r'<\$\w+>', src[f]): bad.append('%s: interpolating a string variable' % os.path.basename(f))
check(not bad, 'no unproven idiom: %s' % bad)

print('25. build mode: the money and the grid are touched in the right order')
bd = clean[FILES[3]]
click = bd.split('[proc,poh_hotspot_click]')[1].split('\n[')[0]
check(click.index('inv_del') < click.index('~poh_room_set'), 'the coins go before the room does')
check(click.index('~poh_room_rot_for') < click.index('inv_del'), 'the rotation is re-checked before charging')
check(click.index('inv_total') < click.index('inv_del'), 'the purse is checked before it is emptied')
check('~poh_spawn_exit' in click and click.index('~poh_place_zone') < click.index('~poh_spawn_exit'),
      'the way out is re-spawned after the room changes')
rm = bd.split('[proc,poh_remove_room]')[1].split('\n[')[0]
check('~poh_room_total <= 1' in rm, 'the last room cannot be removed')
check('~poh_player_in_cell' in rm, 'you cannot remove the room you are standing in')
check('~poh_joined_count' in rm and '> 1' in rm, 'only a leaf room can be removed')
check('~poh_spawn_exit' in rm, 'the way out is re-spawned after a removal too')

print('26. the sawmill: the items, the npc and where he stands')
OBJCFG = blocks(read('scripts/skill_construction/configs/construction.obj'))
SAWNPC = blocks(read('scripts/skill_construction/configs/sawmill.npc'))
check(sorted(OBJCFG) == ['mahogany_plank', 'oak_plank', 'plank', 'saw', 'teak_plank'],
      'construction.obj defines %s' % sorted(OBJCFG))
for n in OBJCFG:
    check(n in OBJS, '%s is in obj.pack' % n)
    for v in (OBJCFG[n].get('model') or []):
        check(v in MODELS and v in ON_DISK, '%s model=%s is packed and on disk' % (n, v))
    for k in ('manwear', 'womanwear'):
        for v in (OBJCFG[n].get(k) or []):
            mv = v.split(',')[0]
            check(mv in MODELS and mv in ON_DISK, '%s %s=%s is packed and on disk' % (n, k, mv))
check('sawmill_operator' in SAWNPC and 'sawmill_operator' in NPCS, 'sawmill_operator is in npc.pack')
for k, vs in SAWNPC.get('sawmill_operator', {}).items():
    if re.match(r'^(model|head)\d+$', k):
        for v in vs:
            check(v in MODELS and v in ON_DISK, 'sawmill_operator %s=%s is packed and on disk' % (k, v))
# the importer leaves a TODO on every block it cannot fill; none may ship
left = re.findall(r'^// TODO by hand:.*$', read('scripts/skill_construction/configs/construction.obj'), re.M)
check(not left, 'no unanswered importer TODO line left in construction.obj: %s' % left)
# no dead op: every op the sawmill npc declares has a trigger
sw = clean[FILES[4]]
ops = sorted(int(k[2:]) for k in SAWNPC.get('sawmill_operator', {}) if re.match(r'^op\d+$', k))
trig = sorted(int(m) for m in re.findall(r'^\[opnpc(\d+),sawmill_operator\]', sw, re.M))
check(ops == trig, 'every op the sawmill operator has is wired: declares %s, triggers %s' % (ops, trig))

SAWMAP = 'maps/m51_54.jm2'
sec = None; spots = []
for line in read(SAWMAP).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if sec != 'NPC' or ':' not in line: continue
    head, data = line.split(':', 1)
    lv, x, z = (int(v) for v in head.split())
    if int(data) == NPCS['sawmill_operator']: spots.append((lv, x, z))
check(len(spots) == 1, 'the sawmill operator is placed exactly once, got %d' % len(spots))

print('27. the sawmill: the fees are the cache\'s own, and nothing is free')
for name, c in (('plank', 'sawmill_fee_plank'), ('oak_plank', 'sawmill_fee_oak'),
                ('teak_plank', 'sawmill_fee_teak'), ('mahogany_plank', 'sawmill_fee_mahogany')):
    fee = const(c)
    cost = OBJCFG[name].get('cost')
    check(fee is not None and fee > 0, '^%s is %s' % (c, fee))
    if cost:
        check(int(cost[0]) == fee, '%s: the fee (%s) is the item\'s own cache cost (%s)' % (name, fee, cost[0]))
for c in ('sawmill_cost_saw', 'sawmill_cost_hammer'):
    check((const(c) or 0) > 0, '^%s is set' % c)
# every log and plank the script names resolves, and the pairing is log -> its own plank
pairs = re.findall(r'~sawmill_cut\((\w+), (\w+), \^(\w+)\)', sw)
check(len(pairs) == 4, 'four log/plank pairs, got %d' % len(pairs))
for log, plank, fee in pairs:
    check(log in OBJS, '%s is in obj.pack' % log)
    check(plank in OBJS, '%s is in obj.pack' % plank)
    check(plank in OBJCFG, '%s is one of the new planks' % plank)
    check(const(fee) is not None, '^%s resolves' % fee)
    stem = plank.replace('_plank', '')
    check(log.startswith(stem) or (plank == 'plank' and log == 'logs'),
          '%s is cut from %s' % (plank, log))
cut = sw.split('[proc,sawmill_cut]')[1].split('\n[')[0]
check(cut.index('inv_del') < cut.index('inv_add'), 'the logs and the coins go before the planks arrive')
check('inv_total(inv, coins)' in cut, 'the purse is read before it is charged')
check('divide($coins, $fee)' in cut, 'a half-funded batch is cut down, not refused')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
