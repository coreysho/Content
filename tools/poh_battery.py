"""Symbol and signature battery for the two new .rs2 files, from claude/rs2-compile-traps.md."""
import re, sys, os
C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ['scripts/skill_construction/scripts/poh.rs2', 'scripts/skill_construction/scripts/poh_test.rs2',
         'scripts/skill_construction/scripts/poh_portal.rs2', 'scripts/skill_construction/scripts/poh_build.rs2',
         'scripts/skill_construction/scripts/sawmill.rs2',
         'scripts/skill_construction/scripts/poh_furniture.rs2',
         'scripts/skill_construction/scripts/poh_menus.rs2',
         'scripts/skill_construction/scripts/poh_furn_ops.rs2',
         'scripts/skill_construction/scripts/poh_tablets.rs2']
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
kinds = {}
for k, n in decl:
    kinds[k] = kinds.get(k, 0) + 1
print('   declares: ' + ', '.join('%d %s' % (v, k) for k, v in sorted(kinds.items())))

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
# Against every .constant in the repo, for the same reason check 4 walks every .rs2: this round
# reaches into the spell book's constants (^varrock_teleport, ^enchant_lvl1) and the quest ones
# (^elena_complete), and a hand-kept list of files would only record which ones I remembered.
consts = set()
for _root, _, _fs in os.walk(os.path.join(C, 'scripts')):
    for _fn in _fs:
        if _fn.endswith('.constant'):
            consts |= set(re.findall(r'^\^(\w+)\s*=', read(os.path.relpath(os.path.join(_root, _fn), C)), re.M))
consts |= set(re.findall(r'^\^(\w+)\s*=', read('scripts/engine.constant'), re.M))
usedc = set(re.findall(r'\^(\w+)', alltext))
check(not (usedc - consts), 'unresolved: %s' % sorted(usedc - consts))

print('7. every enum name resolves')
# pack/enum.pack is GENERATED and gitignored - deploy.sh deletes it before every build - so a
# clean clone has none and the one in a working copy proves nothing about what will be built.
# The .enum sources are what the packer reads, so read those.
if os.path.exists(C + '/pack/enum.pack'):
    enums = {l.split('=', 1)[1] for l in open(C + '/pack/enum.pack').read().split('\n') if '=' in l}
else:
    enums = set()
    for root, _, fs in os.walk(os.path.join(C, 'scripts')):
        for fn in fs:
            if fn.endswith('.enum'):
                with open(os.path.join(root, fn), encoding='utf-8', errors='replace') as fh:
                    enums |= set(re.findall(r'^\[(\w+)\]', fh.read(), re.M))
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
                  'scripts/skill_construction/configs/poh_furniture.enum',
                  'scripts/skill_construction/interfaces/poh_roommenu.if',
    'scripts/skill_construction/interfaces/poh_tabletmenu.if',
                  'scripts/skill_construction/interfaces/poh_furnmenu.if',
                  'scripts/skill_construction/configs/construction.varp',
                  'scripts/skill_construction/configs/construction.constant',
                  'scripts/skill_construction/configs/poh_portal.loc',
                  'scripts/skill_construction/configs/poh_portal.npc',
                  'maps/m46_50.jm2']:
    b = open(os.path.join(C, f), 'rb').read()
    # .gitattributes sets `* text=auto`, so the repo stores LF and a Windows working copy has
    # CRLF. Either is correct; a file with SOME of each is a hand edit that will diff whole.
    crlf, lf = b.count(b'\r\n'), b.count(b'\n')
    check(b'\r\r' not in b and crlf in (0, lf), '%s has one line ending throughout (%s)'
          % (os.path.basename(f), 'CRLF' if crlf else 'LF'))
for f in ['pack/varp.pack', 'pack/loc.pack', 'pack/npc.pack', 'pack/interface.pack']:
    b = open(os.path.join(C, f), 'rb').read()
    check(b'\r' not in b and b.endswith(b'\n'), '%s is LF and ends with a newline' % os.path.basename(f))

print('12. pack ids are unique, and the new ones sit above what was there')
# Not contiguity: varp.pack is missing id 746 upstream and has always built fine. What matters is
# that nothing is claimed twice and that the ids added here were free.
NEW = {'pack/varp.pack': list(range(876, 1150)),
       'pack/loc.pack': [15296, 15297], 'pack/npc.pack': [3920, 3921]}
for f in ['pack/varp.pack', 'pack/loc.pack', 'pack/npc.pack']:
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
# The trailing [,)] is load-bearing: without it `inv_add(inv, enum(int, obj, ...))` reports that
# there is no obj called "enum". A name followed by "(" is a call, not an item.
objs_used = set(re.findall(r'inv_(?:total|del|add)\(\s*\w+\s*,\s*(\w+)\s*[,)]', alltext))
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

print('28. furniture: the tables, the triggers and the bit layout')
FURN = read('scripts/skill_construction/configs/poh_furniture.enum')
ftab = {}
cur = None
for line in FURN.split('\n'):
    line = line.split('//')[0].strip()
    if line.startswith('['):
        cur = line.strip('[]'); ftab[cur] = {}
    else:
        m = re.match(r'^val=(\d+),(.*)$', line)
        if m and cur: ftab[cur][int(m.group(1))] = m.group(2)
N = const('poh_furn_items')
SLOTS = const('poh_furn_slots')
check(N and N > 0, '^poh_furn_items is %s' % N)
for t in ('poh_furn_fam', 'poh_furn_name', 'poh_furn_level', 'poh_furn_wood', 'poh_furn_planks', 'poh_wood_name'):
    check(sorted(ftab.get(t, {})) == list(range(1, N + 1)), '%s covers every item 1..%d' % (t, N))
# aggregates, not a line each: %d items would bury everything else in the run
bad = [(i, v) for i, v in ftab['poh_furn_wood'].items() if not 1 <= int(v) <= 4]
check(not bad, 'every item has a wood the script can pay for: %s' % (bad[:3] or '1..4 throughout'))
bad = [(i, v) for i, v in ftab['poh_furn_planks'].items() if int(v) <= 0]
check(not bad, 'every item costs planks: %s' % (bad[:3] or 'all of them'))
bad = [(i, v) for i, v in ftab['poh_furn_level'].items() if not 1 <= int(v) <= 99]
check(not bad, 'every level is reachable: %s (highest %d)'
      % (bad[:3] or 'all 1..99', max(int(v) for v in ftab['poh_furn_level'].values())))
# labels have to tell two tiers of the SAME family apart, or the menu is a coin toss
byfam = {}
for i, f in ftab['poh_furn_fam'].items():
    byfam.setdefault(int(f), []).append(ftab['poh_furn_name'][i])
bad = [(f, [n for n in names if names.count(n) > 1]) for f, names in sorted(byfam.items())
       if len(names) != len(set(names))]
check(not bad, '%d families, every one with a distinct label per tier: %s'
      % (len(byfam), bad[:2] or 'no family repeats a label'))

fu = clean[FILES[5]]
ops = clean['scripts/skill_construction/scripts/poh_furn_ops.rs2']
def procbody(src, name):
    return src.split('[proc,%s]' % name, 1)[1].split('\n[', 1)[0]
show = procbody(fu, 'poh_furn_show')
showlit = procbody(fu, 'poh_furn_show_lit')
placed = sorted(int(m) for m in re.findall(r'^    case (\d+) : loc_add\(', show, re.M))
check(placed == list(range(1, N + 1)), '~poh_furn_show places every item 1..%d' % N)
# the lit twins are a SUBSET, and every one of them has to be an item that really can be lit
litcase = sorted(int(m) for m in re.findall(r'^    case (\d+) : loc_add\(', showlit, re.M))
lightable = sorted(int(m) for m in re.findall(r'^    case (\d+) : return\(true\);',
                   procbody(ops, 'poh_furn_lightable'), re.M)) if '[proc,poh_furn_lightable]' in ops else litcase
check(litcase and set(litcase) <= set(placed),
      '~poh_furn_show_lit covers %d of the %d pieces, all of them real items' % (len(litcase), N))
# every loc it places is registered, and every one is a real furniture loc from poh.loc
POHLOC = blocks(read('scripts/skill_construction/configs/poh.loc'))
placements = re.findall(r'loc_add\(\$spot, (\w+), \$angle, (\w+),', fu)
bad = [l for l, _ in placements if l not in LOCS]
check(not bad, 'every placed loc is in loc.pack: %s' % (bad[:3] or '%d checked' % len(placements)))
bad = [l for l, _ in placements if l not in POHLOC]
check(not bad, 'every placed loc is a real furniture loc: %s' % (bad[:3] or 'all of them'))
bad = [l for l, _ in placements if 'Remove' not in (POHLOC.get(l, {}).get('op5') or [])]
check(not bad, 'every placed loc carries op5=Remove: %s' % (bad[:3] or 'all of them'))
# a piece can only be taken out if its own op5 is wired
# the lit twins are placed by poh_furniture.rs2 and taken out by poh_furn_ops.rs2, so both files
rm = sorted(set(re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_furn_remove;', fu + '\n' + ops, re.M)))
placed_locs = sorted({m.group(1) for m in re.finditer(r'loc_add\(\$spot, (\w+), \$angle,', fu)})
check(rm == placed_locs, 'every placeable piece has a Remove trigger: %d placed, %d wired'
      % (len(placed_locs), len(rm)))
# and a lit twin nobody can take out is a piece of furniture welded to the floor
POHLOC2 = blocks(read('scripts/skill_construction/configs/poh.loc'))
bad = [l for l in {m.group(1) for m in re.finditer(r'loc_add\(\$spot, (\w+), \$angle,', showlit)}
       if 'Remove' not in (POHLOC2.get(l, {}).get('op5') or [])]
check(not bad, 'every lit twin carries op5=Remove: %s' % (bad[:3] or 'all of them'))
# hotspot triggers pass a family and nothing looks one up
hot = re.findall(r'^\[oploc5,(\w+)\]\s*\n~poh_furn_click\(\^poh_fam_(\w+)\);', fu, re.M)
check(len(hot) > 0, '%d furniture hotspot triggers' % len(hot))
bad = [l for l, _ in hot if l not in LOCS]
check(not bad, 'every hotspot trigger names a loc in loc.pack: %s' % (bad[:3] or 'all %d' % len(hot)))
bad = [f for _, f in hot if const('poh_fam_' + f) is None]
check(not bad, 'every ^poh_fam_* it passes resolves: %s' % (bad[:3] or 'all of them'))
bad = [l for l, _ in hot if 'poh_hotspot' not in (TEMPL.get(l, {}).get('category') or [])]
check(not bad, 'every one is category=poh_hotspot: %s' % (bad[:3] or 'all of them'))
check(len({l for l, _ in hot} & set(doors)) == 0, 'no door hotspot is wired to furniture')
check(len({l for l, _ in hot}) == len(hot), 'no hotspot is wired twice')

# THE ONE THIS ROUND EARNED. loc_add's shape decides which LAYER the loc lands on, and World.changeLoc
# only replaces a loc already on that layer. Place a centrepiece on a grounddecor hotspot and you get
# the furniture AND the hotspot standing in the same tile. So every family's shape has to be the shape
# its own hotspots carry in the six style squares - read from the maps, not assumed.
SHAPES = {0: 'wall_straight', 4: 'walldecor_straight_nooffset', 5: 'walldecor_straight_offset',
          10: 'centrepiece_straight', 11: 'centrepiece_diagonal', 22: 'grounddecor'}
mapshape = {}
for mp in ('maps/m29_79.jm2', 'maps/m30_79.jm2'):
    sec = None
    for l in read(mp).split('\n'):
        if l.startswith('===='):
            sec = l.strip('= '); continue
        if sec != 'LOC' or ':' not in l:
            continue
        d = (l.split(':', 1)[1].split() + ['10', '0'])[:3]
        mapshape.setdefault(int(d[0]), set()).add(SHAPES.get(int(d[1]), d[1]))
famshape = {}
for i, f in ftab['poh_furn_fam'].items():
    famshape.setdefault(int(f), set()).add(dict(placements and [(int(a), b) for a, b in
        re.findall(r'^    case (\d+) : loc_add\(\$spot, \w+, \$angle, (\w+),', fu, re.M)])[i])
ALLOWED = {('chair', 15214), ('chair', 15215)}   # see shape_allowances in tools/furnspec.json
bad = []
for loc, fam in hot:
    want = famshape.get(const('poh_fam_' + fam), set())
    have = mapshape.get(LOCS[loc], set())
    if len(want) != 1:
        bad.append((fam, 'places %s - a family must have ONE shape' % sorted(want)))
    elif not (want & have) and (fam, LOCS[loc]) not in ALLOWED:
        bad.append((fam, '%d: places %s, template has %s' % (LOCS[loc], sorted(want), sorted(have))))
check(not bad, 'every family is placed with its hotspots\' own shape: %s'
      % (bad[:3] or '%d hotspots checked' % len(hot)))

# the bit layout has to be gapless and fit an int
bits = [(const('poh_furn_bit_rx'), 3), (const('poh_furn_bit_rz'), 3), (const('poh_furn_bit_lx'), 3),
        (const('poh_furn_bit_lz'), 3), (const('poh_furn_bit_angle'), 2), (const('poh_furn_bit_item'), 8)]
at = 0; ok = True
for off, w in bits:
    if off != at: ok = False
    at = off + w
check(ok, 'the packed fields are contiguous from bit 0: %s' % bits)
check(at <= 31, 'a piece fits an int (%d bits)' % at)
check(N < (1 << 8), '%d items fit the 8-bit item field' % N)
check(SLOTS and SLOTS <= 256, '^poh_furn_slots is %s' % SLOTS)
varps = {l.split('=', 1)[1] for l in read('pack/varp.pack').split('\n') if '=' in l}
missing = [i for i in range(SLOTS) if ('poh_furn_%d' % i) not in varps]
check(not missing, 'every furniture slot has a varp: missing %s' % missing[:5])
gs = sorted(int(m) for m in re.findall(r'^    case (\d+) : return\(%poh_furn_\d+\);', fu, re.M))
ss = sorted(int(m) for m in re.findall(r'^    case (\d+) : %poh_furn_\d+ = \$value;', fu, re.M))
check(gs == list(range(SLOTS)) and ss == list(range(SLOTS)), 'get and set cover all %d slots' % SLOTS)
for m in re.finditer(r'case (\d+) : return\(%poh_furn_(\d+)\);', fu):
    if m.group(1) != m.group(2): check(False, 'get case %s reads varp %s' % (m.group(1), m.group(2)))
for m in re.finditer(r'case (\d+) : %poh_furn_(\d+) = \$value;', fu):
    if m.group(1) != m.group(2): check(False, 'set case %s writes varp %s' % (m.group(1), m.group(2)))

# A trigger declared twice will not compile, and 238 generated [oploc5] on names as ordinary as
# loc_13581 is exactly how you collide with something in another skill. Checked repo-wide, not just
# in these files, because the collision would be with a file nobody was looking at.
seen_trig = {}
dup_trig = []
for root, _, fs in os.walk(os.path.join(C, 'scripts')):
    for fn in fs:
        if not fn.endswith('.rs2'):
            continue
        fp = os.path.join(root, fn)
        with open(fp, encoding='utf-8', errors='replace') as fh:
            for m in re.finditer(r'^\[(\w+),([\w+.]+)\]', fh.read().replace('\r\n', '\n'), re.M):
                if m.group(1) in ('proc', 'label', 'debugproc', 'command', 'queue', 'timer'):
                    continue
                k = m.groups()
                if k in seen_trig:
                    dup_trig.append((k, seen_trig[k], fp))
                seen_trig[k] = fp
check(not dup_trig, 'no trigger is declared twice anywhere in the repo: %s'
      % (dup_trig[:2] or '%d checked' % len(seen_trig)))

print('29. furniture: materials leave before the thing arrives, and a room takes its own with it')
clickb = fu.split('[proc,poh_furn_click]')[1].split('\n[')[0]
check(clickb.index('~poh_furn_plank_total') < clickb.index('~poh_furn_plank_take'), 'the planks are counted before they are taken')
check(clickb.index('~poh_furn_plank_take') < clickb.index('~poh_furn_show'), 'the planks go before the furniture appears')
check(clickb.index('~poh_furn_set') < clickb.index('stat_advance'), 'it is saved before the xp is paid')
check('inv_total(inv, hammer)' in clickb and 'inv_total(inv, saw)' in clickb, 'a hammer and a saw are required')
check('~poh_furn_free' in clickb and clickb.count('~poh_furn_free') >= 2, 'a free slot is re-checked after the menu suspends')
rmb = fu.split('[proc,poh_furn_remove]')[1].split('\n[')[0]
check('~poh_furn_set($slot, 0)' in rmb and '~poh_furn_relay' in rmb, 'removing clears the slot and re-lays the room')
bd = clean[FILES[3]]
check('~poh_furn_clear_cell' in bd, 'removing a ROOM clears its furniture too')
pb = clean[FILES[0]]
check('~poh_furn_restore' in pb, '~poh_build puts the furniture back')
build_body = pb.split('[proc,poh_build]')[1].split('\n[')[0]
check(build_body.index('~poh_furn_restore') < build_body.index('instance_loccategory'),
      'furniture is placed BEFORE the hotspots are hidden, so it changes them in place')

print('39. what the furniture does: every trigger is on an op the loc really has')
# A trigger on an op the loc does not carry is not an error - it simply never fires, which is the
# quietest kind of broken. The op TEXT has to match the kind too: [oploc1] on a "light" family must
# be a loc whose op1 really says Light.
import json as _json
FSPEC = _json.load(open(os.path.join(C, 'tools/furnspec.json')))
KINDOP = {'sit': 'Sit-on', 'light': 'Light', 'altar': 'Pray', 'jingle': 'Play',
          'observe': 'Observe', 'talk': 'Talk-to', 'preen': 'Preen'}


OPSRC = src['scripts/skill_construction/scripts/poh_furn_ops.rs2']
fired = sorted(set(re.findall(r'^\[oploc1,(\w+)\]', OPSRC, re.M)))
bad = [l for l in fired if not (POHLOC.get(l, {}).get('op1') or [])]
check(not bad, 'every [oploc1] is on a loc that carries an op1: %s' % (bad[:3] or '%d checked' % len(fired)))
want = {}
for f in FSPEC['families']:
    if 'op1' in f:
        for n, l in enumerate(f['locs']):
            want[l] = (f['key'], f['op1']['kind'])
bad = [(l, want[l][1], (POHLOC[l].get('op1') or ['?'])[0]) for l in fired
       if want[l][1] in KINDOP and (POHLOC[l].get('op1') or ['?'])[0] != KINDOP[want[l][1]]]
check(not bad, 'the kind matches the op the loc advertises: %s' % (bad[:3] or 'all of them'))
check(sorted(want) == fired, 'every family with an op1 in the spec has a trigger for every tier: %d'
      % len(fired))
# the altar's use-item trigger is on the altars and nothing else
users = sorted(set(re.findall(r'^\[oplocu,(\w+)\]', OPSRC, re.M)))
altars = sorted(l for l in want if want[l][1] == 'altar')
check(users == altars, 'the offer-bones trigger is on the %d altars and nothing else: %s'
      % (len(altars), users[:3] if users != altars else 'yes'))
check('oc_param($bone, bone_exp)' in OPSRC,
      'it tests bone_exp, the same param burying uses, rather than a list of bones')

print('30. the build windows: registered, in file order, and the old chat panel gone')
IFACE = {}
for l in read('pack/interface.pack').split('\n'):
    if '=' in l:
        i, n = l.split('=', 1); IFACE[n] = int(i)
order = [int(l) for l in read('pack/interface.order').split('\n') if l.strip()]
check(len(order) == len(set(order)), 'interface.order has no duplicate id')
check(set(IFACE.values()) == set(order), 'interface.pack and interface.order hold the same id set')
check(not [n for n in IFACE if n.startswith('poh_buildmenu')], 'poh_buildmenu is out of interface.pack')
check(not os.path.exists(os.path.join(C, 'scripts/skill_construction/interfaces/poh_buildmenu.if')),
      'poh_buildmenu.if is deleted')
check('poh_buildmenu' not in alltext, 'no script still names poh_buildmenu')

def parse_if(path):
    """-> file order, and each component's key/values. Same grammar as PackShared.ts."""
    o, coms, cur = [], {}, None
    for line in read(path).split('\n'):
        line = line.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('['):
            cur = line[1:line.index(']')]; coms[cur] = {}; o.append(cur)
        elif '=' in line and cur:
            k, v = line.split('=', 1); coms[cur][k] = v
    return o, coms

MENUS = 'scripts/skill_construction/scripts/poh_menus.rs2'
menu = clean[MENUS]
IFF = {}
for w in ('poh_roommenu', 'poh_furnmenu', 'poh_tabletmenu'):
    o, coms = parse_if('scripts/skill_construction/interfaces/%s.if' % w)
    IFF[w] = (o, coms)
    check(len(o) == len(set(o)), '%s.if has %d distinct components' % (w, len(set(o))))
    check(w in IFACE, '%s is in interface.pack' % w)
    want = [IFACE[w] + 1 + i for i in range(len(o))]
    got = [IFACE.get('%s:%s' % (w, c)) for c in o]
    check(got == want, '%s: its components are numbered in file order from %d' % (w, IFACE[w] + 1))
    used = sorted(set(re.findall(r'%s:(\w+)' % w, menu)))
    for c in used:
        check(c in coms, '%s: the script drives :%s, which the .if defines' % (w, c))

print('31. the build windows: the client only obeys these on the right kind of component')
# THE CHECK THIS ROUND EARNED. Client.drawInterface tests hide on the LAYER it is drawing and
# never on a child, so if_sethide on a text or a model does nothing at all - which is what the
# chat panel did, and why its empty slots stayed on screen. The other three are the same class
# of mistake: a call whose component is the wrong type fails silently rather than loudly.
for w, (o, coms) in IFF.items():
    for c in sorted(set(re.findall(r'if_sethide\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'layer',
              '%s:%s is a LAYER, so if_sethide can hide it' % (w, c))
    for c in sorted(set(re.findall(r'if_setmodel\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'model', '%s:%s is a model component' % (w, c))
    for c in sorted(set(re.findall(r'if_setangle\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'model', '%s:%s is a model component' % (w, c))
    for c in sorted(set(re.findall(r'if_settext\(%s:(\w+),' % w, menu))):
        check(coms.get(c, {}).get('type') == 'text', '%s:%s is a text component' % (w, c))
    for c in sorted(set(re.findall(r'if_addresumebutton\(%s:(\w+)\)' % w, menu))):
        bt = coms.get(c, {}).get('buttontype')
        check(bt == 'normal', '%s:%s is buttontype=normal, so a click can resume the script' % (w, c))
    for c in sorted(set(re.findall(r'case %s:(\w+) :' % w, menu))):
        check(c in coms, '%s: switch_component names :%s, which exists' % (w, c))

print('32. the build windows: nothing is drawn outside the window')
# The window is the smithing frame's box. Text or a border past it hangs over bare viewport,
# which is exactly what put More and Cancel off the bottom of the chat panel last round.
WIN = (12, 20, 500, 320)
for w, (o, coms) in IFF.items():
    out = []
    for c in o:
        d = coms[c]
        if d.get('type') == 'graphic':
            continue        # the frame's studs deliberately straddle the edge
        x, y = int(d.get('x', 0)), int(d.get('y', 0))
        cw, ch = int(d.get('width', 0)), int(d.get('height', 0))
        if 'layer' in d:
            p = coms[d['layer']]
            x += int(p['x']); y += int(p['y'])
            if d.get('type') == 'model':
                # a model component is deliberately twice its icon's height (see genmenus.py);
                # what must fit is the icon, which is its top half
                ch = ch // 2
        if x < WIN[0] or y < WIN[1] or x + cw > WIN[2] or y + ch > WIN[3]:
            out.append((c, x, y, cw, ch))
    check(not out, '%s: every component is inside %s: %s' % (w, WIN, out[:3] or 'all inside'))

print('33. the model icons are framed by their own geometry, and land inside their row')
sys.path.insert(0, os.path.join(C, 'tools'))
import ifmodels
MODELS_BY_ID = {}
for l in read('pack/model.pack').split('\n'):
    if '=' in l:
        i, n = l.split('=', 1); MODELS_BY_ID[int(i)] = n

def table(proc, pat=r'case (\d+) : return\((\d+)\);'):
    body = menu.split('[proc,%s]' % proc)[1].split('\n[')[0]
    return {int(a): int(b) for a, b in re.findall(pat, body)}

room_model, room_zoom = table('poh_room_model'), table('poh_room_zoom')
furn_model = {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);',
              clean[FILES[5]].split('[proc,poh_furn_model]')[1].split('\n[')[0])}
furn_zoom = table('poh_furn_zoom')
check(sorted(room_model) == list(range(1, 16)), '~poh_room_model answers for every room 1..15')
check(sorted(room_zoom) == sorted(room_model), '~poh_room_zoom covers the same rooms')
check(sorted(furn_zoom) == sorted(furn_model), '~poh_furn_zoom covers every item ~poh_furn_model does')

XAN, YAN = const('poh_menu_xan'), const('poh_menu_yan')
# the pictures are turned face-on, so the zoom that frames them was solved with THEIR camera and
# has to be measured with it too
def cam_table(proc, dflt):
    body = menu.split('[proc,%s]' % proc)[1].split('\n[')[0]
    return {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);', body)}, dflt
fam_xan, _ = cam_table('poh_furn_xan', XAN)
fam_yan, _ = cam_table('poh_furn_yan', YAN)
FAMOF = {int(k): int(v) for k, v in ftab['poh_furn_fam'].items()}
def camera(label, k):
    if label != 'furniture':
        return XAN, YAN
    f = FAMOF[k]
    return fam_xan.get(f, XAN), fam_yan.get(f, YAN)
for label, models, zooms, comp, win in [
        ('room', room_model, room_zoom, 'r0model', 'poh_roommenu'),
        ('furniture', furn_model, furn_zoom, 's0model', 'poh_furnmenu')]:
    d = IFF[win][1][comp]
    row = IFF[win][1][d['layer']]
    rw, rh = int(row['width']), int(row['height'])
    cw, ch = int(d['width']), int(d['height'])
    # the client centres the model on the component and clips it to the LAYER: at the bottom
    # only (Pix3D's rasterisers clamp to Pix2D.bottom and to nothing else), so anything that
    # overruns the top or the sides is drawn over whatever is next to it
    cx, cy = int(d['x']) + cw // 2, int(d['y']) + ch // 2
    bad = []
    for k in sorted(models):
        name = MODELS_BY_ID.get(models[k])
        path = ifmodels.ob2path(name) if name else None
        if path is None:
            bad.append((k, models[k], name, 'no .ob2'))
            continue
        m = ifmodels.R.Model(path)
        hw, rise, drop = ifmodels.extent(m, cw, ch, *camera(label, k), zooms[k])
        if cx - hw < 0 or cx + hw > rw or cy - rise < 0 or cy + drop > rh:
            bad.append((k, name, 'x %.0f..%.0f of %d, y %.0f..%.0f of %d'
                        % (cx - hw, cx + hw, rw, cy - rise, cy + drop, rh)))
    check(not bad, '%s: all %d icons are drawn inside their %dx%d row: %s'
          % (label, len(models), rw, rh, bad[:3] or 'all inside'))

print('34. the room prices are written twice and say the same thing')
ROOMS = read('scripts/skill_construction/configs/poh_rooms.enum')
def enumtable(txt, name):
    b = txt.split('[%s]' % name)[1]
    b = b.split('\n[')[0]
    return {int(m.group(1)): m.group(2) for m in re.finditer(r'^val=(\d+),(.*)$', b, re.M)}
cost = enumtable(ROOMS, 'poh_room_cost')
costtext = enumtable(ROOMS, 'poh_room_cost_text')
check(sorted(cost) == sorted(costtext), 'poh_room_cost_text covers every room poh_room_cost does')
wrong = [(k, cost[k], costtext.get(k)) for k in cost
         if (costtext.get(k) or '').replace(',', '') != cost[k]]
check(not wrong, 'every grouped price is its own number: %s' % (wrong[:3] or 'all agree'))
FAMS = enumtable(read('scripts/skill_construction/configs/poh_furniture.enum'), 'poh_fam_name')
NFAM = len(re.findall(r'^\^poh_fam_\w+\s*=', read('scripts/skill_construction/configs/construction.constant'), re.M))
check(sorted(FAMS) == list(range(1, NFAM + 1)), 'poh_fam_name names all %d hotspot families' % NFAM)

print('38. the furniture generator still produces exactly what is checked in')
kept2 = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_construction/configs/poh_furniture.enum',
    'scripts/skill_construction/configs/construction.varp',
    'scripts/skill_construction/configs/construction.constant',
    'scripts/skill_construction/scripts/poh_furniture.rs2',
    'pack/varp.pack']}
import subprocess as _sp
r = _sp.run([sys.executable, os.path.join(C, 'tools/genfurn.py'), str(SLOTS)],
            capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/genfurn.py runs clean' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
moved = [f for f in kept2 if open(os.path.join(C, f), 'rb').read() != kept2[f]]
for f in moved:
    open(os.path.join(C, f), 'wb').write(kept2[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
# and the varps a save already holds must never be renumbered under it
vp = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in read('pack/varp.pack').split('\n') if '=' in l}
check(all(vp.get('poh_furn_%d' % i) == 894 + i for i in range(64)),
      'poh_furn_0..63 still have the ids the first 64-slot houses were saved with')

print('36. every string these windows can show fits the box it is shown in')
# Not hypothetical: the chat panel's names ran into each other at 90px, and its More and
# Cancel fell off the bottom. The fonts here are the client's own sheets and the advance rule
# is PixFont's, so these widths are the widths the client will draw.
import ifrender
FURNE = read('scripts/skill_construction/configs/poh_furniture.enum')
TABLE_ = read('scripts/skill_construction/configs/poh_tablets.enum')
TABE = {t: enumtable(TABLE_, t) for t in
        ('poh_tab_obj', 'poh_tab_name', 'poh_tab_spell', 'poh_tab_level', 'poh_tab_need',
         'poh_lectern_name')}
rname, rlvl, rcost = (enumtable(ROOMS, t) for t in ('poh_room_name', 'poh_room_level', 'poh_room_cost_text'))
fname, flvl, fplank, fwood = (enumtable(FURNE, t) for t in
                              ('poh_furn_name', 'poh_furn_level', 'poh_furn_planks', 'poh_wood_name'))
SHOWN = [
    ('poh_roommenu', 'r0name', ['%s: Lvl %s' % (rname[k], rlvl[k]) for k in rname]),
    ('poh_roommenu', 'r0cost', ['%s coins' % rcost[k] for k in rcost]),
    ('poh_furnmenu', 's0lvl',  ['Level %s' % flvl[k] for k in flvl]),
    ('poh_furnmenu', 's0name', [fname[k] for k in fname]),
    ('poh_furnmenu', 's0need', ['%s %s' % (fplank[k], fwood[k]) for k in fplank]),
    ('poh_furnmenu', 'title',  list(FAMS.values())),
    ('poh_tabletmenu', 't0name', list(TABE['poh_tab_name'].values())),
    ('poh_tabletmenu', 't0need', list(TABE['poh_tab_need'].values())),
    ('poh_tabletmenu', 't0lvl',  ['Level %s' % v for v in TABE['poh_tab_level'].values()]),
    ('poh_tabletmenu', 'title',  list(TABE['poh_lectern_name'].values())),
]
for win, comp, strings in SHOWN:
    d = IFF[win][1][comp]
    f = ifrender.font(d.get('font', 'p12_full'))
    w = int(d['width'])
    over = sorted(((f.width(t) - w, t) for t in strings if f.width(t) > w), reverse=True)
    check(not over, '%s:%s fits %dpx: widest is %dpx (%s)%s'
          % (win, comp, w, max(f.width(t) for t in strings),
             max(strings, key=f.width), '' if not over else ' OVER by %d: %s' % over[0]))
# and the fixed text the .if itself carries
for win, (o, coms) in IFF.items():
    over = []
    for c in o:
        t = coms[c].get('text')
        if not t or coms[c].get('type') != 'text':
            continue
        f = ifrender.font(coms[c].get('font', 'p12_full'))
        if f.width(t) > int(coms[c]['width']):
            over.append((c, t, f.width(t), int(coms[c]['width'])))
    check(not over, '%s: its own labels fit: %s' % (win, over or 'all fit'))

print('37. the dim/highlight tags are ones the client actually knows')
# PixFont.evaluateTag returns -1 for anything it does not recognise and drawStringTag then just
# swallows the five characters: an unknown tag is INVISIBLE, not an error, and the run silently
# keeps the previous colour. A typo would show as "the greying stopped working" and nothing else.
KNOWN = {'red', 'gre', 'blu', 'yel', 'cya', 'mag', 'whi', 'bla', 'lre', 'dre', 'dbl',
         'or1', 'or2', 'or3', 'gr1', 'gr2', 'gr3', 'str', 'end'}
TINTS = read('scripts/skill_construction/configs/poh_menus.enum')
STATES = {n: v for n, v in re.findall(r'^\^(poh_state_\w+)\s*=\s*(\d+)$',
                                     read('scripts/skill_construction/configs/construction.constant'), re.M)}
check(len(STATES) == 3, 'there are %d ^poh_state_* constants: %s' % (len(STATES), sorted(STATES)))
for t in ('poh_tint_name', 'poh_tint_level', 'poh_tint_need'):
    rows = enumtable(TINTS, t)
    check(sorted(rows) == sorted(int(v) for v in STATES.values()),
          '%s answers for every ^poh_state_* and nothing else' % t)
    bad = [(k, v) for k, v in rows.items()
           if not re.fullmatch(r'@(\w{3})@', v) or re.fullmatch(r'@(\w{3})@', v).group(1) not in KNOWN]
    check(not bad, '%s: every value is a tag PixFont.evaluateTag knows: %s' % (t, bad or 'all known'))
# and the rows really use them - a table nothing reads is not a feature
for win, comp, tables in [('poh_roommenu', 'r0', ('poh_tint_name', 'poh_tint_level', 'poh_tint_need')),
                          ('poh_furnmenu', 's0', ('poh_tint_name', 'poh_tint_level', 'poh_tint_need')),
                          ('poh_tabletmenu', 't0', ('poh_tint_name', 'poh_tint_level', 'poh_tint_need'))]:
    proc = {'poh_roommenu': 'poh_room_row0', 'poh_furnmenu': 'poh_furn_slot0',
            'poh_tabletmenu': 'poh_tab_row0'}[win]
    # src, not clean: `clean` blanks string literals and the enum lookups live inside if_settext's
    body = src[MENUS].split('[proc,%s]' % proc)[1].split('\n[')[0]
    for t in tables:
        check(t in body, '%s: %s reads %s' % (win, proc, t))
    check('^poh_state_locked' in body and '^poh_state_poor' in body,
          '%s: %s sets both the poor and the locked state' % (win, proc))

print('35. the generator still produces exactly what is checked in')
import subprocess, filecmp, tempfile, shutil
kept = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_construction/interfaces/poh_roommenu.if',
    'scripts/skill_construction/interfaces/poh_tabletmenu.if',
    'scripts/skill_construction/interfaces/poh_furnmenu.if',
    'scripts/skill_construction/scripts/poh_menus.rs2',
    'pack/interface.pack', 'pack/interface.order',
    'scripts/skill_construction/configs/poh_rooms.enum',
    'scripts/skill_construction/configs/poh_furniture.enum']}
spec = os.path.join(C, 'tools/menuspec.json')
if os.path.exists(spec):
    r = subprocess.run([sys.executable, os.path.join(C, 'tools/genmenus.py'), spec],
                       capture_output=True, text=True, cwd=C)
    check(r.returncode == 0, 'tools/genmenus.py runs clean' + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
    same = [f for f in kept if open(os.path.join(C, f), 'rb').read() != kept[f]]
    for f in same:
        open(os.path.join(C, f), 'wb').write(kept[f])
    check(not same, 're-running it changes nothing: %s' % (same or 'byte-identical'))
else:
    check(False, 'tools/menuspec.json is missing, so the generator cannot be re-run')

# THE ONE THAT MATTERS: if_setmodel takes a raw id, so every literal in ~poh_furn_model has to still
# be the model.pack id of the model its own loc names. model.pack is append-only in practice, but
# "in practice" is not a check.
MODELS_BY_ID = {}
for l in read('pack/model.pack').split('\n'):
    if '=' in l:
        i, n = l.split('=', 1); MODELS_BY_ID[int(i)] = n
SUF = ['', '_8', '_1', '_2', '_3', '_4', '_q', '_w', '_r', '_e', '_t', '_5', '_9',
       '_a', '_s', '_d', '_f', '_g', '_h', '_z', '_x', '_c', '_v', '_0']
mbody = clean[FILES[5]].split('[proc,poh_furn_model]')[1].split('\n[')[0]
cases = {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);', mbody)}
check(sorted(cases) == list(range(1, N + 1)), '~poh_furn_model answers for every item 1..%d' % N)
placer = clean[FILES[5]].split('[proc,poh_furn_show]')[1].split('\n[')[0]
loc_of = {int(a): b for a, b in re.findall(r'case (\d+) : loc_add\(\$spot, (\w+),', placer)}
wrong = []
for item, mid in sorted(cases.items()):
    loc = loc_of.get(item)
    want_model = (POHLOC.get(loc, {}).get('model') or [None])[0]
    have = MODELS_BY_ID.get(mid)
    if want_model is None or have is None or have not in [want_model + s for s in SUF]:
        wrong.append((item, loc, want_model, mid, have))
check(not wrong, 'every raw model id is still its own loc\'s model: %d checked, %s'
      % (len(cases), wrong[:3] or 'all correct'))

print('40. the tablets say exactly what the spell rows say')
# A tablet IS a spell, stored. Its level, its runes and the experience making it pays are copied
# into the enum tables because the window cannot run a db_find per row - so this reads them back
# out of magic_spell_table and fails if the two have drifted. The copy is the risk this check
# exists for; nothing else about a tablet is duplicated anywhere.
import json as _json
TSPEC = _json.load(open(os.path.join(C, 'tools/tabletspec.json')))
TABS = TSPEC['tablets']
SPELLROW = {}
for _b in read('scripts/skill_magic/configs/magic_spells.dbrow').split('\n['):
    _m = re.search(r'data=spell,\^(\w+)', _b)
    if not _m:
        continue
    _d = {}
    for _l in _b.split('\n'):
        if _l.startswith('data='):
            _k, _v = _l[5:].split(',', 1)
            _d.setdefault(_k, []).append(_v)
    SPELLROW[_m.group(1)] = _d
RUNEWORD = TSPEC['rune_words']
def _runes(name):
    p = SPELLROW[name]['runesrequired'][0].split(',')
    return [(p[i], int(p[i + 1])) for i in range(0, len(p) - 1, 2) if p[i] != 'null']
check(len(TABS) == const('poh_tab_items'),
      '^poh_tab_items is %d, the number of tablets in the spec' % const('poh_tab_items'))
check(sorted(TABE['poh_tab_name']) == list(range(1, len(TABS) + 1)),
      'the tablet tables are numbered 1..%d with no gaps' % len(TABS))
bad = [t['spell'] for t in TABS if t['spell'] not in SPELLROW]
check(not bad, 'every tablet names a spell that has a magic_spell_table row: %s' % (bad or 'all 14'))
bad = [(n + 1, TABE['poh_tab_level'][n + 1], SPELLROW[t['spell']]['levelrequired'][0])
       for n, t in enumerate(TABS)
       if TABE['poh_tab_level'][n + 1] != SPELLROW[t['spell']]['levelrequired'][0]]
check(not bad, 'poh_tab_level is the spell row\'s levelrequired: %s' % (bad[:3] or 'all 14 agree'))
bad = []
for n, t in enumerate(TABS):
    want = ', '.join(['%d %s' % (c, RUNEWORD[o]) for o, c in _runes(t['spell'])] + ['1 soft clay'])
    if TABE['poh_tab_need'][n + 1] != want:
        bad.append((t['key'], TABE['poh_tab_need'][n + 1], want))
check(not bad, 'poh_tab_need is the spell row\'s runes plus the clay: %s' % (bad[:3] or 'all 14 agree'))
bad = [t['key'] for n, t in enumerate(TABS)
       if TABE['poh_tab_spell'][n + 1] != '^' + t['spell']]
check(not bad, 'poh_tab_spell names the same spell the spec does: %s' % (bad or 'all 14'))
# and each kind needs the field its break path reads
bad = [t['key'] for t in TABS if t['kind'] == 'teleport' and 'tele_coord' not in SPELLROW[t['spell']]]
check(not bad, 'every teleport tablet\'s spell row carries a tele_coord: %s' % (bad or 'all 6'))
bad = [t['key'] for t in TABS if t['kind'] in ('convert', 'enchant')
       and 'convertobj' not in SPELLROW[t['spell']]]
check(not bad, 'every enchant and bones tablet\'s row carries a convertobj: %s' % (bad or 'all 7'))
TABRS = clean['scripts/skill_construction/scripts/poh_tablets.rs2']
check('~staff_runes' not in TABRS,
      'making a tablet does NOT go through ~staff_runes - a staff pays for casting, not for binding')
check('~give_spell_xp' not in TABRS and 'stat_advance(magic' in TABRS,
      'making pays the spell row\'s own experience, and reads it from the row')
mk = TABRS.split('[proc,poh_tab_make]')[1].split('\n[')[0]
check(mk.index('inv_del(inv, softclay') < mk.index('inv_add(inv,'),
      'the clay and the runes go before the tablet arrives')
for prc in ('poh_tab_teleport', 'poh_tab_gohome'):
    body = TABRS.split('[proc,%s]' % prc)[1].split('\n[')[0]
    check('~wilderness_level(coord) > 20' in body, '%s keeps the level 20 wilderness ceiling' % prc)
    check('~pre_tele_checks(coord)' in body, '%s runs the same pre-tele checks a spell does' % prc)
for prc in ('poh_tab_teleport', 'poh_tab_gohome', 'poh_tab_convert', 'poh_tab_enchant'):
    body = TABRS.split('[proc,%s]' % prc)[1].split('\n[')[0]
    check('stat(magic)' not in body, '%s asks for no Magic level - a tablet is broken, not cast' % prc)
    check('stat_advance' not in body, '%s pays no experience' % prc)
    check('inv_total(inv, $tab) < 1' in body, '%s re-checks the tablet is still held' % prc)

print('41. the tablet objs are real, and their recolours really match the model')
OBJTAB = blocks(read('scripts/skill_construction/configs/poh_tablets.obj'))
check(sorted(OBJTAB) == sorted(t['obj'] for t in TABS),
      'poh_tablets.obj defines exactly the %d tablets in the spec' % len(TABS))
bad = [n for n in OBJTAB if n not in OBJS]
check(not bad, 'every tablet obj is in obj.pack: %s' % (bad or 'all %d' % len(OBJTAB)))
bad = [TABE['poh_tab_obj'][n + 1] for n, t in enumerate(TABS)
       if TABE['poh_tab_obj'][n + 1] != t['obj']]
check(not bad, 'poh_tab_obj names the spec\'s objs: %s' % (bad or 'all 14'))
# THE TRAP claude/obj-recolours.md names: a recolour SOURCE that is not one of the model's own
# face colours does nothing at all, silently, and the item just renders in the base colours.
srcs = {int(OBJTAB[n]['recol1s'][0]) for n in OBJTAB} | {int(OBJTAB[n]['recol2s'][0]) for n in OBJTAB}
check(srcs == set(TSPEC['recol_src']),
      'every tablet recolours off the same two sources the spec names: %s' % sorted(srcs))
import ob2render as _ob
_m = _ob.Model(os.path.join(C, 'models/obj/%s.ob2' % TSPEC['model']))
_faces = set(int(x) for x in _m.colour.tolist())
bad = [(v, _ob.rgb15_to_hsl16(v)) for v in sorted(srcs) if _ob.rgb15_to_hsl16(v) not in _faces]
check(not bad, 'each source really is one of the model\'s own face colours, in HSL16: %s'
      % (bad or 'both of them'))
bad = [n for n in OBJTAB if OBJTAB[n].get('model', [None])[0] != TSPEC['model']]
check(not bad, 'every tablet is the same model: %s' % (bad or TSPEC['model']))
dst = {n: (int(OBJTAB[n]['recol1d'][0]), int(OBJTAB[n]['recol2d'][0])) for n in OBJTAB}
check(len(set(dst.values())) == len(dst),
      'no two tablets are the same colour: %d distinct pairs' % len(set(dst.values())))
# iop1 exactly on the ones that do something by themselves
want_break = {t['obj'] for t in TABS if t['kind'] != 'enchant'}
have_break = {n for n in OBJTAB if OBJTAB[n].get('iop1', [None])[0] == 'Break'}
check(want_break == have_break,
      'Break is on the nine tablets that need no target, and only those: %s'
      % (sorted(want_break ^ have_break) or 'exact'))
# and the triggers match the ops - a trigger on an op the obj does not carry never fires
fired1 = set(re.findall(r'^\[opheld1,(\w+)\]', TABRS, re.M))
firedu = set(re.findall(r'^\[opheldu,(\w+)\]', TABRS, re.M))
check(fired1 == want_break, 'every [opheld1] is on a tablet that carries iop1=Break: %s'
      % (sorted(fired1 ^ want_break) or 'exact'))
check(firedu == {t['obj'] for t in TABS if t['kind'] == 'enchant'},
      'the five enchant tablets are the [opheldu] ones and have no Break')

print('42. the lectern window and the seven lecterns')
LECT = TSPEC['lecterns']
MAXT = const('poh_tab_max')
over = [(l['name'], len(l['tablets'])) for l in LECT if len(l['tablets']) > MAXT]
check(not over, 'no lectern lists more than ^poh_tab_max (%d) tablets: %s'
      % (MAXT, over or 'largest is %d' % max(len(l['tablets']) for l in LECT)))
check(len([c for c in IFF['poh_tabletmenu'][0] if re.fullmatch(r'row\d+', c)]) == MAXT,
      'poh_tabletmenu has exactly %d rows, one per listable tablet' % MAXT)
nth = TABRS.split('[proc,poh_tab_nth]')[1].split('\n[')[0]
got = {int(a): int(b) for a, b in re.findall(r'case (\d+) : return\((\d+)\);', nth)}
idx = {t['key']: n + 1 for n, t in enumerate(TABS)}
want = {l['tier'] * MAXT + i: idx[k] for l in LECT for i, k in enumerate(l['tablets'])}
check(got == want, '~poh_tab_nth is exactly the spec\'s seven lists: %d entries%s'
      % (len(want), '' if got == want else ' MISMATCH %s' % sorted(set(got.items()) ^ set(want.items()))[:3]))
check(sorted(TABE['poh_lectern_name']) == sorted(l['tier'] for l in LECT),
      'poh_lectern_name names all %d lecterns' % len(LECT))
# Study really opens it, on every lectern, and the loc really carries that op
studies = {int(a): int(b) for a, b in
           re.findall(r'\[oploc1,poh_lectern_?(\d)\]\n~poh_tab_pick\((\d)\);',
                      src['scripts/skill_construction/scripts/poh_furn_ops.rs2'])}
check(studies == {l['tier']: l['tier'] for l in LECT},
      'all seven lecterns Study their own tier: %s' % (studies if len(studies) != 7 else 'yes'))
bad = [l['loc'] for l in LECT if (POHLOC.get(l['loc'], {}).get('op1') or [None])[0] != 'Study']
check(not bad, 'every lectern loc really advertises op1=Study: %s' % (bad or 'all seven'))
# the row procs drive the window through if_setobject, which is the obj path and not if_setmodel
row0 = src[MENUS].split('[proc,poh_tab_row0]')[1].split('\n[')[0]
check('if_setobject(' in row0 and 'if_setmodel(' not in row0,
      'the icons come from if_setobject, which takes the obj and reads its own 2d camera')
scale = int(re.search(r'if_setobject\(poh_tabletmenu:t0model, .*, (\d+)\);', row0).group(1))
zoom = int(TSPEC['icon']['2dzoom']) * 100 // scale
d = IFF['poh_tabletmenu'][1]['t0model']
rowc = IFF['poh_tabletmenu'][1][d['layer']]
cw, ch = int(d['width']), int(d['height'])
hw, rise, drop = ifmodels.extent(ifmodels.R.Model(
    os.path.join(C, 'models/obj/%s.ob2' % TSPEC['model'])), cw, ch,
    int(TSPEC['icon']['2dxan']), int(TSPEC['icon']['2dyan']), zoom)
cx, cy = int(d['x']) + cw // 2, int(d['y']) + ch // 2
check(cx - hw >= 0 and cx + hw <= int(rowc['width']) and cy - rise >= 0 and cy + drop <= int(rowc['height']),
      'the tablet icon at scale %d lands inside its %sx%s row: x %.0f..%.0f, y %.0f..%.0f'
      % (scale, rowc['width'], rowc['height'], cx - hw, cx + hw, cy - rise, cy + drop))

print('43. the tablet generator still produces exactly what is checked in')
kept3 = {f: open(os.path.join(C, f), 'rb').read() for f in [
    'scripts/skill_construction/configs/poh_tablets.obj',
    'scripts/skill_construction/configs/poh_tablets.enum',
    'scripts/skill_construction/scripts/poh_tablets.rs2',
    'scripts/skill_construction/configs/construction.constant',
    'scripts/skill_combat/configs/magic/spells.constant',
    'scripts/skill_magic/configs/magic_spells.dbrow',
    'pack/obj.pack']}
r = _sp.run([sys.executable, os.path.join(C, 'tools/gentablets.py')],
            capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/gentablets.py runs clean'
      + ('' if r.returncode == 0 else ': ' + r.stderr[-400:]))
moved = [f for f in kept3 if open(os.path.join(C, f), 'rb').read() != kept3[f]]
for f in moved:
    open(os.path.join(C, f), 'wb').write(kept3[f])
check(not moved, 're-running it changes nothing: %s' % (moved or 'byte-identical'))
op = {l.split('=', 1)[1]: int(l.split('=', 1)[0]) for l in read('pack/obj.pack').split('\n') if '=' in l}
check(op.get('saw') == 8191 and min(op[t['obj']] for t in TABS) == 8192,
      'the tablets took the ids after the saw, and nothing already in a bank moved')


print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
