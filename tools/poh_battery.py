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
# pack/enum.pack is GENERATED and gitignored - deploy.sh deletes it before every build - so the
# .enum sources are the only honest answer to "what will exist after the build". This used to
# prefer the pack when one happened to be lying around, and a STALE pack then reported twelve
# perfectly good tables as unresolved (and would just as happily have passed a table that had
# since been deleted). The sources are what the packer reads; read those, always.
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
# 1150-1152 are three debug varps that exist only in the laptop's working copy, so they are not
# in this list and the check does not demand contiguity - see the note above.
NEW = {'pack/varp.pack': list(range(876, 1150)) + [1153],
       'pack/loc.pack': [15296, 15297], 'pack/npc.pack': [3920, 3921, 3922, 3923]}
for f in ['pack/varp.pack', 'pack/loc.pack', 'pack/npc.pack']:
    ids = [int(l.split('=', 1)[0]) for l in open(os.path.join(C, f)).read().split('\n') if '=' in l]
    check(len(set(ids)) == len(ids), '%s has no duplicate id' % os.path.basename(f))
    check(all(ids.count(i) == 1 for i in NEW[f]), '%s: every id added here appears exactly once' % os.path.basename(f))
    # Was `== max(NEW[f])`, i.e. "the POH round is still the newest thing in this pack". That was
    # true when it was written and is a landmine for every round after it - bank tabs added varps
    # 1154-1162 and it went red for a reason that had nothing to do with Construction. The part
    # worth keeping is that this round's block is present, unduplicated and not stranded above the
    # top of the file, which >= still says.
    check(max(ids) >= max(NEW[f]), '%s: the new block is not stranded above the top of the file' % os.path.basename(f))

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

CONSTF = read('scripts/skill_construction/configs/construction.constant')
print('15. six towns: a portal on the map in each, on free tiles, next to where leaving lands you')
# There were five more of these as of the Relocate round, and the thing that makes them checkable is
# that the SAME anchor is written down twice - once in the .jm2 and once in poh_loc_portal, which is
# what the click test compares loc_coord against. If those two ever disagree, the portal in that town
# stops opening anybody's house and nothing else notices.
LOCENUM = read('scripts/skill_construction/configs/poh_locations.enum')

def coordtable(txt, name):
    b = txt.split('[%s]' % name)[1].split('\n[')[0]
    out = {}
    for m in re.finditer(r'^val=(\d+),(\d+)_(\d+)_(\d+)_(\d+)_(\d+)$', b, re.M):
        out[int(m.group(1))] = tuple(int(g) for g in m.groups()[1:])
    return out

PORTAL_AT = coordtable(LOCENUM, 'poh_loc_portal')
EXIT_AT = coordtable(LOCENUM, 'poh_loc_exit')
NTOWN = int(re.search(r'^\^poh_location_count\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(sorted(PORTAL_AT) == list(range(NTOWN)), 'poh_loc_portal covers all %d towns' % NTOWN)
check(sorted(EXIT_AT) == list(range(NTOWN)), 'poh_loc_exit covers all %d towns' % NTOWN)
check(len(set(PORTAL_AT.values())) == NTOWN, 'no two towns share a portal tile')
check(len(set(EXIT_AT.values())) == NTOWN, 'no two towns share a landing tile')

def readmap(mx, mz):
    sec, land, mlocs, mnpcs = None, {}, {}, {}
    for line in read('maps/m%d_%d.jm2' % (mx, mz)).split('\n'):
        if line.startswith('===='):
            sec = line.strip('= ').strip(); continue
        if ':' not in line:
            continue
        head, data = line.split(':', 1)
        parts = head.split()
        if len(parts) != 3:
            continue
        lv, x, z = (int(v) for v in parts)
        d = data.split()
        if sec == 'LOC':
            v = [int(t) for t in d]
            mlocs.setdefault((lv, x, z), []).append((v[0], v[1] if len(v) > 1 else 10, v[2] if len(v) > 2 else 0))
        elif sec == 'NPC':
            mnpcs.setdefault((lv, x, z), []).append(int(d[0]))
        elif sec == 'MAP':
            land[(lv, x, z)] = d
    return land, mlocs, mnpcs

PW = int(LOCCFG['poh_house_portal'].get('width', ['1'])[0])
PL = int(LOCCFG['poh_house_portal'].get('length', ['1'])[0])
TOWNS = []          # (town, mx, mz, anchor, angle, covered, land, mlocs, mnpcs)
for town in sorted(PORTAL_AT):
    lv, mx, mz, lx, lz = PORTAL_AT[town]
    land, mlocs, mnpcs = readmap(mx, mz)
    hits = [(k, e) for k, es in mlocs.items() for e in es if e[0] == LOCS['poh_house_portal']]
    check(len(hits) == 1, 'town %d (m%d_%d) has exactly one house portal on the map, got %d'
          % (town, mx, mz, len(hits)))
    if len(hits) != 1:
        continue
    (plv, px, pz), (_, pshape, pangle) = hits[0]
    check((plv, px, pz) == (lv, lx, lz),
          'town %d: the map and poh_loc_portal name the same tile (%s vs %s)'
          % (town, (plv, px, pz), (lv, lx, lz)))
    check(pshape == 10, 'town %d: it is centrepiece_straight (shape %d)' % (town, pshape))
    w, l = (PL, PW) if pangle % 2 else (PW, PL)
    covered = {(plv, px + dx, pz + dz) for dx in range(w) for dz in range(l)}
    for t in sorted(covered):
        others = [e for e in mlocs.get(t, []) if e[0] != LOCS['poh_house_portal'] and e[1] != 22]
        check(not others, 'town %d: tile %s carries nothing else that blocks: %s' % (town, t[1:], others))
        check(t in land, 'town %d: tile %s is real ground' % (town, t[1:]))
        # Flag bit 4 is the client's remove-roofs flag - it marks every tile under a roof, and it is
        # the only thing in the map that says INDOORS. "No solid loc on the footprint" does not:
        # walls sit on tile boundaries, so the inside of a house reads as ten free tiles, and the
        # Taverley portal was placed in the middle of somebody's kitchen on exactly that reasoning.
        flags = 0
        for tok in land.get(t, []):
            if tok.startswith('f') and tok[1:].isdigit():
                flags = int(tok[1:])
        check(not flags & 4, 'town %d: tile %s is outdoors (flag %d)' % (town, t[1:], flags))
    elv, emx, emz, ex, ez = EXIT_AT[town]
    check((emx, emz) == (mx, mz), 'town %d: the landing tile is on the portal\'s own square' % town)
    check((elv, ex, ez) not in covered, 'town %d: leaving does not land you inside the portal' % town)
    check(any(abs(ex - x) + abs(ez - z) == 1 for (_, x, z) in covered),
          'town %d: leaving lands you next to the portal, at %d,%d' % (town, ex, ez))
    check((elv, ex, ez) in land, 'town %d: the landing tile is real ground' % town)
    agents = [k for k, ids in mnpcs.items() for i in ids if i == NPCS['poh_estate_agent']]
    check(len(agents) == 1, 'town %d: exactly one estate agent stands there, got %d' % (town, len(agents)))
    for t in agents:
        check(t not in covered, 'town %d: the estate agent does not stand inside the portal' % town)
    TOWNS.append((town, mx, mz, (plv, px, pz), pangle, covered, land, mlocs, agents))

check(LOCS['poh_exit_portal'] not in
      [e[0] for _, _, _, _, _, _, _, ml, _ in TOWNS for es in ml.values() for e in es],
      'the exit portal is NOT on any map - it is spawned inside the house')

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

print('21. the ground under each of the six portals is what was signed off in game')
# THE CHECK THE FIRST PORTAL EARNED, now generalised. The OSRS house portal is five tiles wide -
# every variant in the cache is - and a 377 loc sits at ONE height with the ground running through
# it. The first Rimmington placements sat across a bank falling h35 to h12: buried at one end,
# floating at the other.
#
# A tile with no explicit h in the .jm2 is NOT unknown: the client generates it (World.method32) and
# tools/terrain377.py is that function transcribed, so every tile here has a height. Validated
# against the map itself - where an explicit tile borders a generated one the two agree closely.
#
# IT IS NO LONGER A THRESHOLD. The Rimmington round set the limit at a spread of 4 and that turned
# out to be one town's answer, not a law: Corey stood on all six of these in game and accepted
# spreads up to 32, because the portal model carries a chunky rock base that sits on a slope
# convincingly. What a number CAN do is notice a placement drifting onto ground nobody looked at, so
# each town records the spread that was actually judged and the check is that it has not moved.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from terrain377 import height_of

# town -> the height spread under the footprint as approved in game, 2026-09-14.
APPROVED_SPREAD = {0: 4, 1: 5, 2: 4, 3: 17, 4: 3, 5: 10}

def groundfn(land, mx, mz):
    def g(lv, x, z):
        d = land.get((lv, x, z))
        if d:
            for tok in d:
                if tok.startswith('h') and tok[1:].isdigit():
                    return int(tok[1:])
        return height_of(mx * 64 + x, mz * 64 + z)
    return g

# The transcription has to be right, or every number below is decoration. Measured where an explicit
# tile borders a generated one, against the same noise sampled 37 tiles away as a control.
#
# IT IS NOT EQUALLY GOOD EVERYWHERE, and that is worth knowing rather than averaging away.
# Rimmington - the square it was validated on - comes out at a ratio near 4. Yanille and Brimhaven
# are nearer 1.2, because those squares are so heavily hand-edited that most explicit/generated
# seams fall on a wall or a cliff where the two genuinely differ. Eight of Yanille's ten portal
# tiles are generated, so its spread below is the softest number here - which is exactly why these
# placements were judged by eye in game and the spread is recorded rather than thresholded.
seams, ctrl, ratios = [], [], []
for town, mx, mz, anchor, pangle, covered, land, mlocs, agents in TOWNS:
    exp = {}
    for (lv, x, z), d in land.items():
        if lv != 0:
            continue
        h = next((int(t[1:]) for t in d if t.startswith('h') and t[1:].isdigit()), None)
        exp[(x, z)] = h
    ss, cc = [], []
    for (x, z), h in exp.items():
        if h is None:
            continue
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, z + dz)
            if n in exp and exp[n] is None:
                ss.append(abs(h - height_of(mx * 64 + n[0], mz * 64 + n[1])))
                cc.append(abs(h - height_of(mx * 64 + n[0] + 37, mz * 64 + n[1] + 37)))
    if ss:
        ratios.append((town, len(ss), sum(ss) / len(ss), sum(cc) / len(cc)))
    seams += ss; ctrl += cc
for town, n, m1, m2 in ratios:
    print('       town %d: %5d seams, mean %.2f vs %.2f shifted (x%.2f)' % (town, n, m1, m2, m2 / m1))
rim = [r for r in ratios if r[0] == 0]
if rim:
    check(rim[0][2] < rim[0][3] / 2,
          'terrain377 still tracks the square it was validated on: Rimmington %.2f vs %.2f'
          % (rim[0][2], rim[0][3]))
mean = sum(seams) / len(seams) if seams else 99
cmean = sum(ctrl) / len(ctrl) if ctrl else 0
check(mean < cmean * 0.6, 'and beats shifted noise across all six: %d seams, mean %.2f vs %.2f'
      % (len(seams), mean, cmean))

for town, mx, mz, anchor, pangle, covered, land, mlocs, agents in TOWNS:
    g = groundfn(land, mx, mz)
    hs = [g(*t) for t in sorted(covered)]
    spread = max(hs) - min(hs)
    want = APPROVED_SPREAD.get(town)
    check(spread == want, 'town %d: the footprint spread is the %s that was looked at (got %d, h%d..%d)'
          % (town, want, spread, min(hs), max(hs)))
    ah = g(*anchor)
    elv, emx, emz, ex, ez = EXIT_AT[town]
    check(abs(g(elv, ex, ez) - ah) <= 12,
          'town %d: the landing tile is within 12 of the portal\'s own tile (h%d vs h%d)'
          % (town, g(elv, ex, ez), ah))
    for t in agents:
        check(abs(g(*t) - ah) <= 12, 'town %d: the estate agent stands within 12 of it (h%d vs h%d)'
              % (town, g(*t), ah))

print('22. each portal is turned the way it was turned in game')
# Angle is FACING, and which angle faces which way was settled by looking, not by reading the model:
# rotation 0 is north, 1 east, 2 south, 3 west. (claude/poh-portal-placement.md had it 180 out - it
# reasoned from the swirl sitting south of the frame's centre in model space.) The footprint swaps
# width and length on an odd angle, which is what makes the wide face run north-south.
APPROVED_ANGLE = {0: 3, 1: 3, 2: 2, 3: 2, 4: 3, 5: 0}
FACING = {0: 'north', 1: 'east', 2: 'south', 3: 'west'}
for town, mx, mz, anchor, pangle, covered, land, mlocs, agents in TOWNS:
    check(pangle == APPROVED_ANGLE.get(town),
          'town %d: angle %d, facing %s - the one that was approved (%s)'
          % (town, pangle, FACING[pangle], APPROVED_ANGLE.get(town)))
    xs = {x for lv, x, z in covered}; zs = {z for lv, x, z in covered}
    w, l = (PL, PW) if pangle % 2 else (PW, PL)
    check(len(xs) == w and len(zs) == l,
          'town %d: the footprint really is %d by %d on the ground' % (town, w, l))

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
check(COUNT == 16, '^poh_room_count is %s' % COUNT)
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
check('~poh_furn_restore' in click and click.index('~poh_place_zone') < click.index('~poh_furn_restore'),
      'the furniture - the exit portal included - is re-laid after the room changes')
rm = bd.split('[proc,poh_remove_room]')[1].split('\n[')[0]
check('~poh_room_total <= 1' in rm, 'the last room cannot be removed')
check('~poh_player_in_cell' in rm, 'you cannot remove the room you are standing in')
check('~poh_joined_count' in rm and '> 1' in rm, 'only a leaf room can be removed')
check('~poh_furn_restore' in rm, 'the furniture is re-laid after a removal too')
# and the room holding the last way out cannot be taken out at all, or the portal goes with it
check('~poh_furn_count_cell_item' in rm and '^poh_furn_exit_portal' in rm,
      'the room with the only exit portal in it is refused')
check(rm.index('~poh_furn_count_cell_item') < rm.index('~p_choice2'),
      'that refusal comes before the player is asked to confirm')

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
for t in ('poh_furn_fam', 'poh_furn_name', 'poh_furn_level', 'poh_furn_wood', 'poh_furn_planks',
          'poh_furn_xp', 'poh_furn_mat1', 'poh_furn_mat1n', 'poh_furn_need'):
    check(sorted(ftab.get(t, {})) == list(range(1, N + 1)), '%s covers every item 1..%d' % (t, N))
# aggregates, not a line each: %d items would bury everything else in the run
bad = [(i, v) for i, v in ftab['poh_furn_wood'].items() if not 0 <= int(v) <= 4]
check(not bad, 'every item has a wood, or 0 for the garden: %s' % (bad[:3] or '0..4 throughout'))
# A plank family costs planks and a garden family costs something else; what every piece has is a
# first material, a count and an experience number.
planky = {i for i, v in ftab['poh_furn_wood'].items() if int(v)}
bad = [(i, v) for i, v in ftab['poh_furn_planks'].items() if i in planky and int(v) <= 0]
check(not bad, 'every plank piece costs planks: %s' % (bad[:3] or '%d of them' % len(planky)))
bad = [(i, v) for i, v in ftab['poh_furn_planks'].items() if i not in planky and int(v) != 0]
check(not bad, 'a garden piece costs no planks: %s' % (bad[:3] or '%d of them' % (N - len(planky))))
bad = [(i, v) for i, v in ftab['poh_furn_mat1n'].items() if int(v) <= 0]
check(not bad, 'no piece costs zero of its material: %s' % (bad[:3] or 'all %d' % N))
bad = [(i, v) for i, v in ftab['poh_furn_xp'].items() if int(v) <= 0]
check(not bad, 'every piece pays experience: %s' % (bad[:3] or 'all %d' % N))
bad = [(i, v) for i, v in ftab['poh_furn_mat1'].items() if v not in OBJS]
bad += [(i, v) for i, v in ftab.get('poh_furn_mat2', {}).items() if v not in OBJS]
check(not bad, 'every material is an obj that exists: %s' % (bad[:3] or 'all of them'))
check(sorted(ftab.get('poh_furn_mat2', {})) == sorted(ftab.get('poh_furn_mat2n', {})),
      'the second material and its count go together: %d pieces need two'
      % len(ftab.get('poh_furn_mat2', {})))
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
# The exit portal is the garden's level-1 centrepiece, and it lives in the portal round's config.
POHLOC.update(blocks(read('scripts/skill_construction/configs/poh_portal.loc')))
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

# the bit layout has to be gapless and fit an int. The item number is in TWO ranges: the low byte at
# ^poh_furn_bit_item and the high seven above the lit bit, so that widening it from 8 bits could not
# move a field any existing save had already written.
bits = [(const('poh_furn_bit_rx'), 3), (const('poh_furn_bit_rz'), 3), (const('poh_furn_bit_lx'), 3),
        (const('poh_furn_bit_lz'), 3), (const('poh_furn_bit_angle'), 2), (const('poh_furn_bit_item'), 8),
        (const('poh_furn_bit_lit'), 1)]
hi_w = int(re.search(r'\^poh_furn_bit_item_hi \+ (\d+)\)', src['scripts/skill_construction/scripts/poh_furniture.rs2']).group(1)) + 1
bits.append((const('poh_furn_bit_item_hi'), hi_w))
at = 0; ok = True
for off, w in bits:
    if off != at: ok = False
    at = off + w
check(ok, 'the packed fields are contiguous from bit 0: %s' % bits)
check(at <= 31, 'a piece fits an int (%d bits)' % at)
check(N < (1 << (8 + hi_w)), '%d items fit the %d-bit item number (low byte plus %d above the lit bit)'
      % (N, 8 + hi_w, hi_w))
check(const('poh_furn_bit_item_hi') > const('poh_furn_bit_lit'),
      'the item high byte is above the lit bit, so an old record reads 0 there')
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
check(clickb.index('~poh_furn_have') < clickb.index('~poh_furn_take'), 'the materials are counted before they are taken')
check(clickb.index('~poh_furn_take') < clickb.index('~poh_furn_show'), 'the materials go before the furniture appears')
check(clickb.count('~poh_furn_have') >= 2, 'the materials are re-checked after the menu suspends')
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
          'observe': 'Observe', 'talk': 'Talk-to', 'preen': 'Preen',
          'wardrobe': 'Change-clothes', 'costume': 'Open'}


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
check(sorted(room_model) == list(range(1, COUNT + 1)),
      '~poh_room_model answers for every room 1..%d' % COUNT)
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
    'scripts/skill_construction/configs/poh_flatpacks.obj',
    'pack/obj.pack',
    'pack/varp.pack']}
# poh_flatpacks.obj and obj.pack belong in that list for a reason that cost an afternoon: this
# group runs genfurn.py IN PLACE, so any generated file missing from kept2 is quietly rewritten
# here and every later group reads the regenerated copy. Group 52's obj.pack check could not go
# red because group 38 had already undone the break. A generated file that is not listed above
# is not checked by anything - it is un-checkable.
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
fneed = enumtable(FURNE, 'poh_furn_need')
fname, flvl, fplank, fwood = (enumtable(FURNE, t) for t in
                              ('poh_furn_name', 'poh_furn_level', 'poh_furn_planks', 'poh_wood_name'))
SHOWN = [
    ('poh_roommenu', 'r0name', ['%s: Lvl %s' % (rname[k], rlvl[k]) for k in rname]),
    ('poh_roommenu', 'r0cost', ['%s coins' % rcost[k] for k in rcost]),
    ('poh_furnmenu', 's0lvl',  ['Level %s' % flvl[k] for k in flvl]),
    ('poh_furnmenu', 's0name', [fname[k] for k in fname]),
    ('poh_furnmenu', 's0need', list(fneed.values())),
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

print('41. the tablet objs are the real OSRS ones, and they stack')
OBJTAB = blocks(read('scripts/skill_construction/configs/poh_tablets.obj'))
check(sorted(OBJTAB) == sorted(t['obj'] for t in TABS),
      'poh_tablets.obj defines exactly the %d tablets in the spec' % len(TABS))
bad = [n for n in OBJTAB if n not in OBJS]
check(not bad, 'every tablet obj is in obj.pack: %s' % (bad or 'all %d' % len(OBJTAB)))
bad = [TABE['poh_tab_obj'][n + 1] for n, t in enumerate(TABS)
       if TABE['poh_tab_obj'][n + 1] != t['obj']]
check(not bad, 'poh_tab_obj names the spec\'s objs: %s' % (bad or 'all 14'))
# STACKABLE is the point of the round: OSRS tablets stack, and a lectern that makes ten of them
# is only useful if they land in one slot.
bad = [n for n in OBJTAB if OBJTAB[n].get('stackable', [None])[0] != 'yes']
check(not bad, 'every tablet is stackable: %s' % (bad or 'all %d' % len(OBJTAB)))
# Each one is its own OSRS model, on disk and in model.pack - a name in a pack is not a file, and a
# miss shows up in game as an invisible item rather than an error (claude/osrs-cache.md).
mods = {n: OBJTAB[n].get('model', [None])[0] for n in OBJTAB}
want = {t['obj']: t['model'] for t in TABS}
check(mods == want, 'every tablet carries the model the spec imported for it: %s'
      % ('all %d, one each' % len(want) if mods == want
         else sorted(k for k in want if mods.get(k) != want[k])))
check(len(set(mods.values())) == len(mods),
      'no two tablets share a model: %d distinct' % len(set(mods.values())))
bad = [m for m in mods.values() if m not in MODELS]
check(not bad, 'every tablet model is registered in model.pack: %s' % (bad or 'all 14'))
bad = [m for m in mods.values() if not os.path.exists(os.path.join(C, 'models/obj/%s.ob2' % m))]
check(not bad, 'every tablet model is a file on disk: %s' % (bad or 'all 14'))
# no recolour anywhere: the art is the real item, so there is nothing to tint
bad = [n for n in OBJTAB if any(k.startswith('recol') for k in OBJTAB[n])]
check(not bad, 'no tablet recolours anything any more: %s' % (bad or 'none of them'))
# the icon camera is the cache's own, field for field
bad = []
for t in TABS:
    for k, v in t['icon'].items():
        if OBJTAB[t['obj']].get(k, [None])[0] != str(v):
            bad.append('%s %s' % (t['obj'], k))
check(not bad, 'every tablet keeps the 2d camera the OSRS config gave it: %s' % (bad or 'all 14'))
bad = [t['obj'] for t in TABS if OBJTAB[t['obj']].get('name', [None])[0] != t['name']]
check(not bad, 'every obj name is the OSRS name: %s' % (bad or 'all 14'))
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
d = IFF['poh_tabletmenu'][1]['t0model']
rowc = IFF['poh_tabletmenu'][1][d['layer']]
cw, ch = int(d['width']), int(d['height'])
cx, cy = int(d['x']) + cw // 2, int(d['y']) + ch // 2
# Fourteen models with fourteen cameras now, so every one is measured, not just the first. The
# zoom is what if_setobject works out: the obj's own 2dzoom x 100 / scale.
worst, bad = None, []
for t in TABS:
    zoom = int(t['icon']['2dzoom']) * 100 // scale
    hw, rise, drop = ifmodels.extent(ifmodels.R.Model(
        os.path.join(C, 'models/obj/%s.ob2' % t['model'])), cw, ch,
        int(t['icon'].get('2dxan', 0)), int(t['icon'].get('2dyan', 0)), zoom)
    if not (cx - hw >= 0 and cx + hw <= int(rowc['width'])
            and cy - rise >= 0 and cy + drop <= int(rowc['height'])):
        bad.append('%s x %.0f..%.0f y %.0f..%.0f' % (t['obj'], cx - hw, cx + hw, cy - rise, cy + drop))
    if worst is None or (rise + drop) > worst[0]:
        worst = (rise + drop, t['obj'], hw, rise, drop)
check(not bad, 'all %d tablet icons at scale %d land inside their %sx%s row: %s'
      % (len(TABS), scale, rowc['width'], rowc['height'],
         bad or 'tallest is %s at %.0f x %.0f, y %.0f..%.0f'
         % (worst[1], worst[2] * 2, worst[0], cy - worst[3], cy + worst[4])))

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

print('44. breaking a tablet plays the tablet-break animation, not the spell')
# The whole point of the round: every break path used to play the CAST - human_castteleport and
# teleport_casting for a teleport, the enchant's own pair for an enchant - which is the animation
# for casting the spell, not for smashing a tablet. One proc plays OSRS's break pair now.
BRK = TSPEC['break']
BRKSEQ = 'scripts/skill_construction/configs/poh_tab_break.seq'
BRKSPOT = 'scripts/skill_construction/configs/poh_tab_break.spotanim'
banim = TABRS.split('[proc,poh_tab_breakanim]')[1].split('\n[')[0] if '[proc,poh_tab_breakanim]' in TABRS else ''
check('anim(%s, 0);' % BRK['anim'] in banim,
      '~poh_tab_breakanim plays %s' % BRK['anim'])
check('spotanim_pl(%s, %d, 0);' % (BRK['spot'], BRK['height']) in banim,
      '~poh_tab_breakanim plays %s at height %d' % (BRK['spot'], BRK['height']))
for proc in ('poh_tab_teleport', 'poh_tab_gohome', 'poh_tab_convert', 'poh_tab_enchant'):
    body = TABRS.split('[proc,%s]' % proc)[1].split('\n[')[0]
    check('~poh_tab_breakanim;' in body, '~%s breaks with the break animation' % proc)
    bad = re.findall(r'anim\((human_castteleport|teleport_casting|\$anim|\$spotanim)', body)
    check(not bad, '~%s plays no cast animation of its own: %s' % (proc, bad or 'none'))
check('~player_teleport_normal' not in TABRS,
      'nothing calls ~player_teleport_normal, which would play the cast (it teleports via ~p_telejump_safe)')
check('~p_telejump_safe(' in TABRS, 'the teleport still goes through ~p_telejump_safe, with its own checks')
# the art chain, the same sweep as check 19: a name in a pack is not a file
seqd = set(re.findall(r'^\[(\w+)\]', read(BRKSEQ), re.M))
check(BRK['anim'] in seqd and BRK['spot'] in seqd,
      'poh_tab_break.seq declares both %s and %s' % (BRK['anim'], BRK['spot']))
check(BRK['anim'] in SEQS and BRK['spot'] in SEQS, 'both are registered in seq.pack')
SPOTS = set(packmap('pack/spotanim.pack'))
spotcfg = blocks(read(BRKSPOT))
check(BRK['spot'] in spotcfg and BRK['spot'] in SPOTS,
      '%s is a spotanim config and is in spotanim.pack' % BRK['spot'])
smodel = spotcfg[BRK['spot']].get('model', [None])[0]
check(smodel in MODELS, 'the break graphic model %s is in model.pack' % smodel)
check(os.path.exists(os.path.join(C, 'models/spot/%s.ob2' % smodel)),
      '%s.ob2 is on disk' % smodel)
check(spotcfg[BRK['spot']].get('anim', [None])[0] in SEQS,
      'the break graphic animates on a seq that is registered')
bframes = re.findall(r'^frame\d+=(\S+)$', read(BRKSEQ), re.M)
bdelays = re.findall(r'^delay\d+=', read(BRKSEQ), re.M)
check(len(bframes) > 0 and len(bdelays) == len(bframes),
      'every one of the %d break frames has a delay' % len(bframes))
ANIMS2 = set(packmap('pack/anim.pack'))
ANIMSETS2 = set(packmap('pack/animset.pack'))
BASES2 = set(packmap('pack/base.pack'))
bad = [f for f in bframes if f not in ANIMS2]
check(not bad, 'every break frame is in anim.pack: %s' % (bad or 'all %d' % len(bframes)))
for st_ in sorted({f.rsplit('_', 1)[0] for f in bframes}):
    check(st_ in ANIMSETS2, '%s is in animset.pack' % st_)
    check(st_.replace('anim_', 'base_', 1) in BASES2, '%s base is in base.pack' % st_)
    fp = os.path.join(C, 'models', st_ + '.anim')
    check(os.path.exists(fp) and os.path.getsize(fp) > 0, '%s.anim is on disk' % st_)

print('45. Make 1 / 5 / 10 / X')
QSTEPS = TSPEC['quantities']['steps']
QMAX = const('poh_tab_qty_max')
order, coms = IFF['poh_tabletmenu']
btns = ['qty%d' % n for n in QSTEPS] + ['qtyx']
missing = [b for b in btns + ['qtylabel'] if b not in coms]
check(not missing, 'the window has a button for every quantity: %s' % (missing or ', '.join(btns)))
bad = [b for b in btns if coms[b].get('buttontype') != 'normal']
check(not bad, 'every quantity button is a button: %s' % (bad or 'all %d' % len(btns)))
bad = [b for b in btns if coms[b].get('type') != 'text' or 'layer' in coms[b]]
check(not bad, 'each is a top-level text component, so if_settext really reaches it: %s' % (bad or 'all four'))
# they must not sit under the rows, or a click lands on both
rowtop = min(int(coms[c]['y']) for c in coms if re.fullmatch(r'row\d+', c))
bad = [b for b in btns if int(coms[b]['y']) + int(coms[b]['height']) > rowtop]
check(not bad, 'the buttons sit above the first row (y %d): %s' % (rowtop, bad or 'all four'))
pick = src[MENUS].split('[proc,poh_tab_pick]')[1].split('\n[')[0]
bad = [b for b in btns if 'if_addresumebutton(poh_tabletmenu:%s);' % b not in pick]
check(not bad, 'every quantity button is a resume target: %s' % (bad or 'all four'))
for n in QSTEPS:
    check('case poh_tabletmenu:qty%d : %%poh_tab_qty = %d;' % (n, n) in pick,
          'clicking %d sets the quantity to %d' % (n, n))
check('case poh_tabletmenu:qtyx : ~poh_tab_qty_ask;' in pick, 'X asks for a number')
ask = src[MENUS].split('[proc,poh_tab_qty_ask]')[1].split('\n[')[0]
check('p_countdialog;' in ask, 'Make X uses p_countdialog, the prompt Cook X uses')
check('if (last_int < 1) {' in ask, 'a cancelled prompt (0) leaves the quantity alone')
check('if (%poh_tab_qty > ^poh_tab_qty_max) {' in ask, 'Make X is clamped to ^poh_tab_qty_max (%d)' % QMAX)
draw = src[MENUS].split('[proc,poh_tab_qty_draw]')[1].split('\n[')[0]
bad = [b for b in btns if 'if_settext(poh_tabletmenu:%s, "@whi@' % b not in draw]
check(not bad, 'every button is redrawn white before one is picked out: %s' % (bad or 'all four'))
check(draw.count('@gre@') == len(QSTEPS) + 1,
      'exactly one of the %d can be green at a time' % len(btns))
TAGS = set(re.findall(r'@(\w{3})@', draw))
check(TAGS <= KNOWN, 'the quantity tints are tags PixFont.evaluateTag knows: %s' % sorted(TAGS))
# the making loop: bounded, and it stops at the first refusal rather than repeating the message
mk = TABRS.split('[proc,poh_tab_make_n]')[1].split('\n[')[0]
check('while ($i < $count & $i < ^poh_tab_qty_max) {' in mk,
      'the make loop is bounded by both the count and ^poh_tab_qty_max')
check('if (~poh_tab_make($tab) = false) {' in mk and 'return;' in mk,
      'it stops at the first tablet it cannot make')
check('[proc,poh_tab_make](int $tab)(boolean)' in TABRS,
      '~poh_tab_make answers whether it made one')
check('while (true)' not in TABRS and 'def_string' not in TABRS,
      'no unproven idiom in the tablet script (claude/rs2-compile-traps.md)')
# the window comes down before the animation and the loop puts it back
after = pick.split('if ($pick > 0) {')[1]
check(after.index('if_close;') < after.index('~poh_tab_make_n('),
      'the window closes before the tablets are made, so the animation is visible')
# the quantity lives in a temp varp: it is a setting for this visit, not part of the house
check('poh_tab_qty' in varps, '%poh_tab_qty is registered in varp.pack')
qvarp = blocks(read('scripts/skill_construction/configs/construction.varp')).get('poh_tab_qty', {})
check('scope' not in qvarp, '%poh_tab_qty is temp - it is a setting, not part of the saved house')
p12q = ifrender.font('b12_full')
wide = max((p12q.width(str(n)) for n in list(QSTEPS) + [QMAX]))
check(wide <= int(coms['qty1']['width']),
      'the widest number a quantity button can show is %dpx in a %spx box' % (wide, coms['qty1']['width']))

def ftabn(loc):
    """The item number of the piece built from this loc, out of ~poh_furn_show's own switch."""
    m = re.search(r'case (\d+) : loc_add\(\$spot, %s, ' % loc, fu)
    return int(m.group(1)) if m else None

print('46. the garden: the supplier, her prices, and the way out')
GNPC = blocks(read('scripts/skill_construction/configs/poh_garden.npc'))
GINV = read('scripts/skill_construction/configs/poh_garden.inv')
GRS = read('scripts/skill_construction/scripts/poh_garden.rs2')
GOBJ = blocks(read('scripts/skill_construction/configs/poh_garden_mats.obj'))
sup = GNPC.get('poh_garden_supplier', {})
check(bool(sup) and 'poh_garden_supplier' in NPCS, 'the Garden supplier is a config and is in npc.pack')
# her art, all the way to the files: a name in a pack is not a model on disk
ON_DISK2 = set()
for root, _, fs in os.walk(os.path.join(C, 'models')):
    for fn in fs:
        if fn.endswith('.ob2'): ON_DISK2.add(fn[:-4])
mods = [v for k, vs in sup.items() if re.match(r'^(model|head)\d+$', k) for v in vs]
check(len(mods) == 11, 'she has %d models and chatheads' % len(mods))
bad = [m for m in mods if m not in MODELS]
check(not bad, 'every one is in model.pack: %s' % (bad or 'all %d' % len(mods)))
bad = [m for m in mods if m not in ON_DISK2]
check(not bad, 'every one is a .ob2 on disk: %s' % (bad or 'all %d' % len(mods)))
# no dead op, and no op without a trigger
ops = sorted(int(k[2:]) for k in sup if re.match(r'^op\d+$', k))
trig = sorted(int(m) for m in re.findall(r'^\[opnpc(\d+),poh_garden_supplier\]', GRS, re.M))
check(ops == trig, 'every op she has is wired: declares %s, triggers %s' % (ops, trig))
# the comment at the top of the file mentions it too, so count the calls rather than the mentions
check(len(re.findall(r'^\s*~openshop_activenpc;$', GRS, re.M)) == 2,
      'both ways in open her own shop through her npc params')
# the shop: her params, the inv, and the prices
check((sup.get('param') or []) and any(v == 'owned_shop,poh_garden_shop' for v in sup['param']),
      'she owns poh_garden_shop')
prm = dict(v.split(',', 1) for v in sup.get('param', []))
check(prm.get('shop_sell_multiplier') == str(const('poh_garden_sell')),
      'her selling multiplier is ^poh_garden_sell (%s)' % const('poh_garden_sell'))
check(prm.get('shop_buy_multiplier') == str(const('poh_garden_buy')),
      'her buying multiplier is ^poh_garden_buy (%s)' % const('poh_garden_buy'))
check(prm.get('shop_delta') == '0', 'shop_delta is 0, so the price does not drift off the OSRS number')
check('[poh_garden_shop]' in GINV and 'restock=yes' in GINV, 'poh_garden_shop restocks')
# THE ONE THE BUILD CAUGHT: an inv needs an id in pack/inv.pack before an npc param can name it.
# Without it the packer says "Invalid property value: param=owned_shop,..." and carries on, so the
# shop simply would not open in game.
INVS = set(packmap('pack/inv.pack'))
check('poh_garden_shop' in INVS, 'poh_garden_shop has an id in inv.pack')
stock = dict((m.group(2), (int(m.group(3)), int(m.group(4))))
             for m in re.finditer(r'^stock(\d+)=(\w+),(\d+),(\d+)$', GINV, re.M))
check(len(stock) == 10, 'she stocks %d things' % len(stock))
bad = [k for k in stock if k not in GOBJ]
check(not bad, 'every line of stock is one of the garden materials: %s' % (bad or 'all ten'))
bad = [(k, v) for k, v in stock.items() if v != (20, 100)]
check(not bad, 'twenty of each, restocking a unit a minute: %s' % (bad or 'all ten'))
# THE PRICES ARE THE CACHE'S, at 40%: the wiki's numbers are knowledge, the costs are data, and the
# multiplier is what ties them together. If they ever disagree, one of the three moved.
WIKI = {'poh_bag_dead_tree': 400, 'poh_bag_nice_tree': 800, 'poh_bag_oak_tree': 2000,
        'poh_bag_willow_tree': 4000, 'poh_bag_maple_tree': 6000, 'poh_bag_yew_tree': 8000,
        'poh_bag_magic_tree': 20000, 'poh_bag_plant_1': 400, 'poh_bag_plant_2': 2000,
        'poh_bag_plant_3': 4000}
bad = []
for k, want in WIKI.items():
    cost = int((GOBJ.get(k, {}).get('cost') or ['0'])[0])
    got = cost * const('poh_garden_sell') // 1000
    if got != want:
        bad.append((k, cost, got, want))
check(not bad, 'every price comes out at the OSRS number: %s' % (bad[:3] or 'all ten, 400-20,000 coins'))
# where she stands: once, on a tile with nothing solid on it
GMAP = 'maps/m46_52.jm2'
sec = None; spots = []; solid = {}
for line in read(GMAP).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCS['poh_garden_supplier']: spots.append((lv, x, z))
    if sec == 'LOC':
        d = data.split()
        if (len(d) < 2 or int(d[1]) != 22) and lv == 0: solid.setdefault((x, z), []).append(int(d[0]))
check(len(spots) == 1, 'she is placed exactly once, got %d' % len(spots))
if spots:
    lv, x, z = spots[0]
    check(lv == 0 and (x, z) not in solid,
          'her tile (local %d,%d = %d,%d) carries nothing solid' % (x, z, 2944 + x, 3328 + z))
    ring = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in solid]
    check(not ring, 'and neither do the eight tiles around her: %s' % (ring or 'all clear'))

print('47. the garden: the centrepiece, and the exit portal that lives in it')
GFAMS = [f for f in FSPEC['families'] if f.get('room') == 'garden']
check(len(GFAMS) == 7, 'seven garden families: %s' % [f['key'] for f in GFAMS])
GHOT = {h for f in GFAMS for h in f['hotspots']}
want = {LOCS['loc474_153%d' % n] for n in range(61, 68)}
check(GHOT == want, 'they claim exactly the garden\'s seven hotspots')
# every garden piece: a real material, a level and an experience number that rise with the tier
for f in GFAMS:
    lv = [p['level'] for p in f['pieces']]
    xp = [p['xp'] for p in f['pieces']]
    check(lv == sorted(lv), '%s: levels rise (%s)' % (f['key'], lv))
    check(xp == sorted(xp), '%s: experience rises (%s)' % (f['key'], xp))
    bad = [m for p in f['pieces'] for m in p['mats'] if m[0] not in OBJS]
    check(not bad, '%s: every material exists (%s)' % (f['key'], bad or 'yes'))
# the exit portal is the level-1 centrepiece, and the only piece that is
cp = next(f for f in GFAMS if f['key'] == 'centrepiece')
first = cp['pieces'][0]
check(first['loc'] == 'poh_exit_portal' and first['level'] == 1,
      'the exit portal is the centrepiece you can build at level 1')
check(const('poh_furn_exit_portal') == ftabn('poh_exit_portal'),
      '^poh_furn_exit_portal (%s) is that piece\'s own item number' % const('poh_furn_exit_portal'))
check('Remove' in (POHLOC.get('poh_exit_portal', {}).get('op5') or []),
      'the portal carries op5=Remove, so it can be replaced by a pond')
# the tile it goes on, read out of all six template squares rather than remembered
CPID = LOCS['loc474_15361']
tiles, angles = set(), set()
for sq, levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    sec = None
    for line in read('maps/%s.jm2' % sq).split('\n'):
        if line.startswith('===='):
            sec = line.strip('= '); continue
        if sec != 'LOC' or ':' not in line: continue
        head, data = line.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        d = data.split()
        if int(d[0]) != CPID or lv not in levels or not (0 <= x < 8 and 8 <= z < 16): continue
        tiles.add((x % 8, z % 8)); angles.add((sq, lv, int(d[2]) if len(d) > 2 else 0))
check(tiles == {(const('poh_garden_cp_x'), const('poh_garden_cp_z'))},
      'every style has its Centrepiece space at ^poh_garden_cp_x/z (%s)' % sorted(tiles))
turned = {lv for sq, lv, a in angles if a and sq == 'm29_79'}
check(turned == {0} and all(a == 0 for sq, lv, a in angles if (sq, lv) != ('m29_79', 0)),
      'only style 0 has it turned, which is what ~poh_garden_cp_angle says')
ang = GRS.split('[proc,poh_garden_cp_angle]')[1].split('\n[')[0]
check('%poh_style = 0' in ang and 'return(1);' in ang and 'return(0);' in ang,
      '~poh_garden_cp_angle answers 1 for style 0 and 0 for the rest')
# the grant, and the guards around it
ens = GRS.split('[proc,poh_ensure_exit]')[1].split('\n[')[0]
check('~poh_furn_count_item(^poh_furn_exit_portal) > 0' in ens,
      'a house that already has a portal is left alone')
check('~poh_furn_at(' in ens, 'a centrepiece that is already built on is left alone')
check('~poh_furn_pack(' in ens and '^poh_garden_cp_x' in ens,
      'the portal is stored as furniture on the centrepiece tile')
check('stat(construction)' not in ens and 'inv_del' not in ens,
      'the first one is free and needs no level - OSRS starts a house with it built')
pohrs = clean[FILES[0]]
ent = pohrs.split('[proc,poh_enter]')[1].split('\n[')[0]
check('~poh_ensure_exit' in ent and ent.index('~poh_ensure_exit') < ent.index('~poh_build'),
      '~poh_enter makes sure of the portal before it builds the house')
check('~poh_spawn_exit' not in pohrs + clean[FILES[3]],
      'nothing loc_adds a loose portal any more')
rmf = fu.split('[proc,poh_furn_remove]')[1].split('\n[')[0]
check('^poh_furn_exit_portal' in rmf and '~poh_furn_count_item' in rmf,
      'the last exit portal cannot be taken out')

print('48. the Stonemason, and the formal garden he supplies')
SNPC = blocks(read('scripts/skill_construction/configs/poh_stone.npc'))
SINV = read('scripts/skill_construction/configs/poh_stone.inv')
SRS = read('scripts/skill_construction/scripts/poh_stone.rs2')
mason = SNPC.get('poh_stonemason', {})
check(bool(mason) and 'poh_stonemason' in NPCS, 'the Stonemason is a config and is in npc.pack')
mods = [v for k, vs in mason.items() if re.match(r'^(model|head)\d+$', k) for v in vs]
bad = [m for m in mods if m not in MODELS or m not in ON_DISK2]
check(mods and not bad, 'all %d of his models are in model.pack and on disk: %s' % (len(mods), bad or 'yes'))
check((mason.get('readyanim') or [''])[0].startswith('dwarf'),
      'he animates as the dwarf he is (%s)' % (mason.get('readyanim') or ['?'])[0])
ops = sorted(int(k[2:]) for k in mason if re.match(r'^op\d+$', k))
trig = sorted(int(m) for m in re.findall(r'^\[opnpc(\d+),poh_stonemason\]', SRS, re.M))
check(ops == trig, 'every op he has is wired: declares %s, triggers %s' % (ops, trig))
check(len(re.findall(r'^\s*~openshop_activenpc;$', SRS, re.M)) == 2, 'both ways in open his store')
prm = dict(v.split(',', 1) for v in mason.get('param', []))
check(prm.get('owned_shop') == 'poh_stone_shop', 'he owns poh_stone_shop')
check('poh_stone_shop' in INVS, 'poh_stone_shop has an id in inv.pack')
check(prm.get('shop_sell_multiplier') == str(const('poh_stone_sell')),
      'his selling multiplier is ^poh_stone_sell (%s)' % const('poh_stone_sell'))
check(prm.get('shop_buy_multiplier') == str(const('poh_stone_buy')),
      'his buying multiplier is ^poh_stone_buy (%s)' % const('poh_stone_buy'))
check(prm.get('shop_delta') == '0', 'a fixed-price shop, like the Garden Centre')
sstock = dict((m.group(2), (int(m.group(3)), int(m.group(4))))
              for m in re.finditer(r'^stock(\d+)=(\w+),(\d+),(\d+)$', SINV, re.M))
check(len(sstock) == 2, 'he stocks %d things' % len(sstock))
bad = [k for k in sstock if k not in OBJS]
check(not bad, 'every line of stock is a real obj: %s' % (bad or ', '.join(sstock)))
# the OSRS prices again: their cache costs are exactly twice what he charges
# Gold leaf and magic stone are his in OSRS and not here: 377's are unpriced placeholders and
# nothing built today wants them. See the note in poh_stone.inv.
SWIKI = {'limestonebrick': 10, 'poh_marble_block': 125000}
ALLOBJ = dict(OBJCFG)
ALLOBJ.update(blocks(read('scripts/skill_construction/configs/poh_formal_mats.obj')))
ALLOBJ.update(blocks(read('scripts/_unpack/377/all.obj')))
bad = []
for k, want in SWIKI.items():
    cost = int((ALLOBJ.get(k, {}).get('cost') or ['0'])[0])
    got = cost * const('poh_stone_sell') // 1000
    if got != want:
        bad.append((k, cost, got, want))
check(not bad, 'both come out at the OSRS price: %s' % (bad[:3] or '10 and 125,000 coins'))
check(sorted(sstock) == sorted(SWIKI), 'and he stocks exactly those two')
# OSRS's own quantities, and the same one-a-minute restock the Garden Centre uses
SQTY = {'limestonebrick': 1000, 'poh_marble_block': 20}
bad = [(k, v) for k, v in sstock.items() if v != (SQTY.get(k), 100)]
check(not bad, 'a thousand bricks and twenty blocks, restocking a unit a minute: %s'
      % (bad or 'both lines'))
# where he stands: western Keldagrim, on nothing, with room around him
KMAP = 'maps/m44_159.jm2'
sec = None; spots = []; ksolid = set()
for line in read(KMAP).split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCS['poh_stonemason']: spots.append((lv, x, z))
    if sec == 'LOC' and lv == 0:
        d = data.split()
        if len(d) < 2 or int(d[1]) != 22: ksolid.add((x, z))
check(len(spots) == 1, 'he is placed exactly once, got %d' % len(spots))
if spots:
    lv, x, z = spots[0]
    ring = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in ksolid]
    check(lv == 0 and not ring, 'his tile (%d,%d) and the eight around it are clear: %s'
          % (2816 + x, 10176 + z, ring or 'all nine'))

print('49. the formal garden room, and what goes in it')
FGFAMS = [f for f in FSPEC['families'] if f.get('room') == 'formal garden']
check(len(FGFAMS) == 5, 'five formal garden families: %s' % [f['key'] for f in FGFAMS])
FGHOT = {h for f in FGFAMS for h in f['hotspots']}
check(FGHOT == {LOCS['loc474_15368']} | {LOCS['loc474_1537%d' % n] for n in (3, 4, 5, 6)},
      'they claim the formal garden\'s centrepiece and its four flower spaces')
# the room is real: its zone, its doors and its price
check(const('poh_room_formal_garden') == 16 and COUNT == 16,
      'the formal garden is room type %s of %s' % (const('poh_room_formal_garden'), COUNT))
ZONE = enumtable(ROOMS, 'poh_room_zone'); DOORS = enumtable(ROOMS, 'poh_room_doors')
check(int(ZONE[16]) == 2 * 8 + 1, 'its template zone is 2,1 (%s)' % ZONE[16])
# the door mask, read out of all six template squares rather than believed
DOORIDS = {LOCS['loc474_%d' % n] for n in range(15305, 15318)}
sides = set()
for sq, levels in (('m29_79', (0, 1, 2, 3)), ('m30_79', (0, 1))):
    sec = None
    for line in read('maps/%s.jm2' % sq).split('\n'):
        if line.startswith('===='):
            sec = line.strip('= '); continue
        if sec != 'LOC' or ':' not in line: continue
        head, data = line.split(':', 1)
        lv, x, z = (int(v) for v in head.split())
        if int(data.split()[0]) not in DOORIDS or lv not in levels: continue
        if not (16 <= x < 24 and 8 <= z < 16): continue
        lx, lz = x - 16, z - 8
        sides.add(1 if lz == 7 else 2 if lx == 7 else 4 if lz == 0 else 8 if lx == 0 else 0)
check(0 not in sides and sum(sides) == int(DOORS[16]),
      'its door mask (%s) is the sides the six template squares actually have doors on (%s)'
      % (DOORS[16], sum(sides)))
check(int(enumtable(ROOMS, 'poh_room_level')[16]) == 55
      and int(enumtable(ROOMS, 'poh_room_cost')[16]) == 75000,
      'level 55 and 75,000 coins, as in OSRS')
# the centrepiece: a way out at level 1, then the gazebo and the three fountains
fc = next(f for f in FGFAMS if f['key'] == 'formalcentre')
check(fc['pieces'][0]['loc'] == 'poh_exit_portal' and fc['pieces'][0]['level'] == 1,
      'a formal garden can hold a way out too, at level 1')
marble = [p for p in fc['pieces'] if any(m[0] == 'poh_marble_block' for m in p['mats'])]
check(len(marble) == 3 and [len(p['mats']) for p in marble] == [1, 1, 1],
      'the three fountains are the marble ones: %s' % [p['label'] for p in marble])
check([m[1] for p in marble for m in p['mats']] == [1, 2, 3],
      'one, two and three blocks, as OSRS charges')
check('poh_exit_portal' in {k for k in FSPEC.get('loc_allowances', {}) if k != '_'},
      'the portal being in two families is a named allowance, not an accident')
# one removal trigger per loc, or it would not compile
dup = [l for l in re.findall(r'^\[oploc5,(\w+)\]', fu, re.M)]
check(len(dup) == len(set(dup)), 'no loc has two removal triggers: %d triggers' % len(dup))


# ============================================================================ 50
print('50. the windows are built once per click, not once per row (the instruction budget)')
# ScriptRunner allows a script 500,000 opcodes and does NOT reset the count across the
# p_pausebutton a window waits on, so everything a player does with one window comes out of one
# budget. The room window used to ask "what is the nth room that fits" seven times a page, each
# question walking the whole room ladder and each rung scanning all 64 grid slots: 913,000 opcodes
# over three pages, and "branch Too many instructions" thrown out of poh.rs2 on More rooms.
# claude/poh-menu-opcount.md has the measurements and how they were taken.
poh = clean[FILES[0]]
bd = clean[FILES[3]]
mn = clean[FILES[6]]
cp = poh.split('[proc,poh_can_place]', 1)[1].split('\n[', 1)[0]
check('~poh_room_total' not in cp and '~poh_house_empty' in cp,
      '~poh_can_place asks ~poh_house_empty, not ~poh_room_total')
he = poh.split('[proc,poh_house_empty]', 1)[1].split('\n[', 1)[0]
check('^poh_type_mask' in he and '~poh_word_get' in he,
      'and ~poh_house_empty masks whole layout words rather than decoding slots')
check(int(re.search(r'\^poh_type_mask\s*=\s*(\d+)', CONST).group(1)) == 0x3f3f3f3f,
      '^poh_type_mask covers the four 6-bit type fields of a word, nothing else')
check('return(false)' in he, 'it stops at the first room it finds')
fm = bd.split('[proc,poh_fit_mask]', 1)[1].split('\n[', 1)[0]
check('~poh_room_fits' in fm and '$bit = calc($bit * 2)' in fm,
      '~poh_fit_mask turns the ladder into one bitmask')
nf = bd.split('[proc,poh_nth_fit]', 1)[1].split('\n[', 1)[0]
check('~poh_' not in nf, '~poh_nth_fit calls nothing - it just reads bits')
RC = int(re.search(r'\^poh_room_count\s*=\s*(\d+)', CONST).group(1))
check(RC <= 31, 'the %d room types fit in the bits of one mask (31 is the ceiling)' % RC)
pick = mn.split('[proc,poh_pick_room]', 1)[1].split('\n[', 1)[0]
check('[proc,poh_pick_room](int $mask)(int)' in mn,
      '~poh_pick_room is handed the mask rather than the cell it is for')
check('~poh_fit_mask' not in pick and '~poh_nth_room' not in pick,
      'and derives nothing while paging')
ROWS_ = int(re.search(r'\^poh_menu_rows\s*=\s*(\d+)', CONST).group(1))
check(pick.count('~poh_nth_fit') == ROWS_ + 1,
      'it reads its %d rows and the More rooms button straight out of the mask' % ROWS_)
hc = bd.split('[proc,poh_hotspot_click]', 1)[1].split('\n[', 1)[0]
check(hc.count('~poh_fit_mask') == 1, 'the click builds the mask exactly once')
check('~poh_nth_room' not in alltext, 'the per-row walk is gone from the build, not just unused')

# ============================================================================ 51
print('51. and the furniture window pages by arithmetic, for the same reason')
fn = fu.split('[proc,poh_furn_nth]', 1)[1].split('\n[', 1)[0]
check('while' not in fn, '~poh_furn_nth does not walk every piece in the game per row')
check('poh_fam_first' in fn and 'poh_fam_last' in fn, "it adds the row to the family's first piece")
ffirst = enumtable(FURNE, 'poh_fam_first')
flast = enumtable(FURNE, 'poh_fam_last')
ffam = enumtable(FURNE, 'poh_furn_fam')
byfam = {}
for item, f in ffam.items():
    byfam.setdefault(int(f), []).append(int(item))
check(len(ffirst) == len(byfam) and len(flast) == len(byfam),
      'every one of the %d families has a first and a last' % len(byfam))
bad = [f for f, items in byfam.items()
       if sorted(items) != list(range(int(ffirst[f]), int(flast[f]) + 1))]
check(not bad, "and each family's pieces really are consecutive - the arithmetic depends on it")
check(all(sorted(byfam[f])[0] == int(ffirst[f]) for f in byfam),
      'first is the lowest piece id in the family')
check(all(sorted(byfam[f])[-1] == int(flast[f]) for f in byfam),
      'last is the highest')

# ============================================================================ 52
print('52. flatpacks: 84 items on 15 shared models, and the enum that joins them')
FLATOBJ = read('scripts/skill_construction/configs/poh_flatpacks.obj')
import json as _json
_spec = _json.load(open(os.path.join(C, 'tools/furnspec.json')))
flatkeys = [f['key'] for f in _spec['families'] if f.get('flatpack')]
check(len(flatkeys) == 15, '15 families are marked flatpackable (%d)' % len(flatkeys))

flatblocks = re.findall(r'^\[(poh_flat_\w+)\]', FLATOBJ, re.M)
check(len(flatblocks) == len(set(flatblocks)), 'no flatpack obj is declared twice')
missing = [n for n in flatblocks if n not in OBJS]
check(not missing, 'every flatpack obj is registered in obj.pack: %s' % missing[:4])

# the enum is the join, and it must name exactly the blocks in the .obj - no more, no fewer
flatenum = enumtable(FURNE, 'poh_furn_flat')
check(sorted(flatenum.values()) == sorted(flatblocks),
      'poh_furn_flat names exactly the %d objs in poh_flatpacks.obj' % len(flatblocks))
check('default=null' in FURNE.split('[poh_furn_flat]', 1)[1].split('\n[', 1)[0],
      'poh_furn_flat declares default=null - a namedobj enum answers obj 0 without it')

# every piece of a flatpackable family has one, and no piece of any other family does
ffam2 = enumtable(FURNE, 'poh_furn_fam')
famname = enumtable(FURNE, 'poh_fam_name')
famnum = {v: int(k) for k, v in famname.items()}
speclabel = {f['key']: f['label'] for f in _spec['families']}
want = {famnum[speclabel[k]] for k in flatkeys if speclabel[k] in famnum}
should = {int(i) for i, f in ffam2.items() if int(f) in want}
check(set(int(i) for i in flatenum) == should,
      'exactly the %d pieces of those families have a flatpack (%d in the table)'
      % (len(should), len(flatenum)))

# the models: 15 files, all registered, all referenced
mdl = sorted(set(re.findall(r'^model=(obj_poh_flat_\w+)', FLATOBJ, re.M)))
check(len(mdl) == 15, '15 distinct models carry them (%d)' % len(mdl))
check(all(m in MODELS for m in mdl), 'every one is in model.pack')
check(all(os.path.exists(os.path.join(C, 'models/obj', m + '.ob2')) for m in mdl),
      'and every one has an .ob2 on disk')

# the workbench is not itself flatpackable, and the Work-at triggers exist for all five tiers
check('workbench' not in flatkeys, 'a workbench cannot be flatpacked')
FLATRS = read('scripts/skill_construction/scripts/poh_flatpacks.rs2')
POHLOC = read('scripts/skill_construction/configs/poh.loc')
for loc in ('loc_13704', 'loc_13705', 'loc_13706', 'loc_13707', 'loc_13708'):
    blk = POHLOC.split('[%s]' % loc, 1)[1].split('\n[', 1)[0]
    check('op1=Work-at' in blk, '%s carries op1=Work-at' % loc)
    check('[oploc1,%s]' % loc in FLATRS, '%s has an oploc1 - a trigger on an op that is not there never fires' % loc)

# ============================================================================ 53
print('53. redecorating: six styles, six template levels, and prices that are OSRS\'s')
STYLEE = read('scripts/skill_construction/configs/poh_styles.enum')
stab = enumtable(STYLEE, 'poh_style_name')
slvl = enumtable(STYLEE, 'poh_style_level')
scost = enumtable(STYLEE, 'poh_style_cost')
check(sorted(stab) == list(range(6)), 'poh_style_name covers 0-5 with no gaps')
check(sorted(slvl) == list(range(6)), 'poh_style_level covers 0-5')
check(sorted(scost) == list(range(6)), 'poh_style_cost covers 0-5')
# A miss on any of these is a real answer without default=: style 0 is Basic wood, level 0 reads as
# "no requirement" and cost 0 reads as free. That is rule 17's lesson in a table it does not cover.
for t in ('poh_style_name', 'poh_style_level', 'poh_style_cost'):
    blk = STYLEE.split('[%s]' % t, 1)[1].split('\n[', 1)[0]
    check('default=null' in blk, '%s declares default=null - a miss must not answer style 0' % t)
lv = [int(slvl[i]) for i in range(6)]
cs = [int(scost[i]) for i in range(6)]
check(lv == sorted(lv) and cs == sorted(cs), 'the ladder only ever goes up: %s at %s' % (lv, cs))
check(lv == [1, 10, 20, 30, 40, 50], "the levels are OSRS's own: %s" % lv)
check(cs == [5000, 5000, 7500, 10000, 15000, 25000], "and so are the prices: %s" % cs)

# ~poh_style_origin has to answer a DIFFERENT template square/level for each of the six, or two
# styles are the same house and one of the prices buys nothing.
POHRS = read('scripts/skill_construction/scripts/poh.rs2')
org = POHRS.split('[proc,poh_style_origin]', 1)[1].split('\n[', 1)[0]
cases = re.findall(r'case (\d+|default) : return\(([^;]+)\);', org)
check(len(cases) == 6, '~poh_style_origin answers all six styles (%d cases)' % len(cases))
check(len({c[1].strip() for c in cases}) == 6,
      'each style is cut from a different square and level: %d distinct origins' % len({c[1].strip() for c in cases}))
check('^poh_templates_a' in org and '^poh_templates_b' in org, 'both template squares are used')

# the dialogue: every style reachable, the charge taken once, and the level tested before the coins
PORTRS = read('scripts/skill_construction/scripts/poh_portal.rs2')
pick = PORTRS.split('[proc,poh_style_pick]', 1)[1].split('\n[', 1)[0]
named = {int(m) for m in re.findall(r'poh_style_name, (\d)\)', pick)}
check(named == set(range(6)), 'the two menu pages between them offer all six styles: %s' % sorted(named))
check('while (true)' not in pick, 'the pager is a bounded loop - while (true) has no precedent here')
do = PORTRS.split('[proc,poh_redecorate_to]', 1)[1].split('\n[', 1)[0]
check(do.index('stat(construction)') < do.index('inv_del'), 'the level is tested before the coins are taken')
check(do.count('inv_del(inv, coins') == 1, 'the coins come out exactly once')
check(do.count('inv_total(inv, coins)') == 2,
      'the purse is re-checked AFTER the confirm box - it is a suspend, and coins can leave during it')
check(do.index('%poh_style = $style') > do.index('inv_del'), 'and the style only changes once it is paid for')
check('$style = %poh_style' in do, 'buying the style you already have is refused')

# ============================================================================ 54
print('54. relocating: six towns, one of them yours, and five that say so')
lname = enumtable(LOCENUM, 'poh_loc_name')
llvl = enumtable(LOCENUM, 'poh_loc_level')
lcost = enumtable(LOCENUM, 'poh_loc_cost')
check(sorted(lname) == list(range(6)), 'poh_loc_name covers 0-5')
for t in ('poh_loc_name', 'poh_loc_level', 'poh_loc_cost', 'poh_loc_exit', 'poh_loc_portal'):
    blk = LOCENUM.split('[%s]' % t, 1)[1].split('\n[', 1)[0]
    check('default=null' in blk, '%s declares default=null - a miss must not answer town 0' % t)
lv = [int(llvl[i]) for i in range(6)]
cs = [int(lcost[i]) for i in range(6)]
check(lv == [1, 10, 20, 30, 40, 50], "the levels are OSRS's own: %s" % lv)
check(cs == [5000, 5000, 7500, 10000, 15000, 25000], "and so are the prices: %s" % cs)
check(lname[0] == 'Rimmington', 'town 0 is Rimmington - a save written before %poh_location existed reads 0')

# the varp has to be perm and registered, or every house moves back on logout
VARPF = read('scripts/skill_construction/configs/construction.varp')
vblk = VARPF.split('[poh_location]', 1)[1].split('\n[', 1)[0]
check('scope=perm' in vblk, '%poh_location is scope=perm')
check(VARPF.index('[poh_location]') < VARPF.index('// ---- furniture'),
      'and it sits ABOVE the furniture marker - genfurn.py truncates the file there')
check('poh_location' in {l.split('=', 1)[1] for l in read('pack/varp.pack').split('\n') if '=' in l},
      'it is registered in varp.pack')

# the click: five portals that are not yours must not open your house
PORTRS2 = read('scripts/skill_construction/scripts/poh_portal.rs2')
clk = PORTRS2.split('[proc,poh_portal_click]', 1)[1].split('\n[', 1)[0]
check('loc_coord' in clk and 'poh_loc_portal' in clk,
      'the click compares loc_coord against poh_loc_portal')
check(clk.index('mes(') < clk.index('~poh_enter'),
      'and refuses before it enters, rather than entering and then complaining')
check('[oploc1,poh_house_portal]' in PORTRS2 and '~poh_enter' not in
      PORTRS2.split('[oploc1,poh_house_portal]', 1)[1].split('\n\n', 1)[0],
      'the trigger goes through the check, not straight to ~poh_enter')

# the move itself
mv = PORTRS2.split('[proc,poh_relocate_to]', 1)[1].split('\n[', 1)[0]
check(mv.index('stat(construction)') < mv.index('inv_del'), 'the level is tested before the coins are taken')
check(mv.count('inv_del(inv, coins') == 1, 'the coins come out exactly once')
check(mv.count('inv_total(inv, coins)') == 2, 'the purse is re-checked after the confirm box')
check(mv.index('~poh_free') < mv.index('%poh_location = $town'),
      'the instance is freed BEFORE the move - someone standing in their house would come out the wrong door')
check('$town = %poh_location' in mv, 'moving to where you already are is refused')
pick = PORTRS2.split('[proc,poh_location_pick]', 1)[1].split('\n[', 1)[0]
named = {int(m) for m in re.findall(r'poh_loc_name, (\d)\)', pick)}
check(named == set(range(6)), 'the two menu pages between them offer all six towns: %s' % sorted(named))

# leaving has to follow the house, and the fallback has to be a real place
POHRS2 = read('scripts/skill_construction/scripts/poh.rs2')
check('p_telejump(^poh_exit)' not in POHRS2, 'nothing teleports to the hardcoded Rimmington exit any more')
ec = POHRS2.split('[proc,poh_exit_coord]', 1)[1].split('\n[', 1)[0]
check('poh_loc_exit' in ec and '^poh_exit' in ec,
      'the exit reads the table and falls back to the constant if it answers null')
check(POHRS2.count('~poh_exit_coord') >= 2, 'both leaving and logging in use it')

# ============================================================================ 55
print('55. the costume chest, the wardrobe and the mounted glory')
COST = read('scripts/skill_construction/configs/poh_costume.enum')
citem = enumtable(COST, 'poh_costume_item')
csetn = enumtable(COST, 'poh_costume_set_name')
cfirst = enumtable(COST, 'poh_costume_set_first')
clast = enumtable(COST, 'poh_costume_set_last')
NITEM = int(re.search(r'^\^poh_costume_items\s*=\s*(\d+)', CONSTF, re.M).group(1))
NSET = int(re.search(r'^\^poh_costume_sets\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(sorted(citem) == list(range(NITEM)), 'poh_costume_item is 0..%d with no gaps' % (NITEM - 1))
check(sorted(csetn) == list(range(NSET)), 'poh_costume_set_name covers all %d sets' % NSET)
check(len(set(citem.values())) == NITEM, 'no item is listed twice')
check(all(o in OBJS for o in citem.values()), 'every one is in obj.pack: %s'
      % ([o for o in citem.values() if o not in OBJS][:3] or 'all %d' % NITEM))

# THE LIST IS DERIVED, AND THIS IS WHERE IT IS RE-DERIVED. Everything in the chest has to be a clue
# reward, and every clue reward that is a god/trimmed/gold/heraldic VARIANT has to be in the chest -
# otherwise a reward added to the tables later is quietly unstorable and nobody finds out.
rewards = set()
for f in sorted(os.listdir(os.path.join(C, 'scripts/minigames/game_trail/scripts'))):
    d = os.path.join(C, 'scripts/minigames/game_trail/scripts', f)
    if not os.path.isdir(d):
        continue
    for g in sorted(os.listdir(d)):
        if not g.endswith('_reward.rs2'):
            continue
        txt = '\n'.join(l.split('//')[0] for l in
                        open(os.path.join(d, g), newline='').read().replace('\r\n', '\n').split('\n'))
        rewards |= set(re.findall(r'inv_add\(trail_rewardinv,\s*([a-z0-9_]+)', txt))
check(len(rewards) > 100, 'the three clue reward tables were found and parsed (%d objs)' % len(rewards))
notreward = [o for o in citem.values() if o not in rewards]
check(not notreward, 'everything in the chest is a treasure trail reward: %s' % (notreward[:3] or 'all of them'))
variant = {o for o in rewards if re.search(r'_(trim|gold|guthix|saradomin|zamorak)$|heraldic', o)}
missing = sorted(variant - set(citem.values()))
check(not missing, 'and every god/trimmed/gold/heraldic reward is in it: %s' % (missing or 'all %d' % len(variant)))
# The other half of the rule, and the one that covers the seventeen costume pieces no name pattern
# can describe: a costume is something clues are the ONLY source of. If a shop stocks it, it is
# ordinary kit and the chest is not where it belongs - that is what keeps this from drifting into a
# second bank one plausible-looking item at a time.
stocked = set()
for root, _, files in os.walk(os.path.join(C, 'scripts')):
    for g in files:
        if not g.endswith('.inv'):
            continue
        for line in open(os.path.join(root, g), newline='').read().replace('\r\n', '\n').split('\n'):
            m = re.match(r'^stock\d*=([a-z0-9_]+)', line.strip())
            if m:
                stocked.add(m.group(1))
check(len(stocked) > 500, 'the shop stock lists were found (%d objs)' % len(stocked))
sold = sorted(o for o in citem.values() if o in stocked)
check(not sold, 'and nothing in the chest is something a shop sells: %s' % (sold[:3] or 'none of the %d' % NITEM))

# the set windows have to tile the item list exactly, or a set silently holds the wrong pieces
spans = [(int(cfirst[i]), int(clast[i])) for i in range(NSET)]
check(spans[0][0] == 0, 'the first set starts at item 0')
check(spans[-1][1] == NITEM - 1, 'the last set ends at item %d' % (NITEM - 1))
check(all(a <= b for a, b in spans), 'no set ends before it starts')
check(all(spans[i + 1][0] == spans[i][1] + 1 for i in range(NSET - 1)),
      'the sets are consecutive and leave no item out: %s' % spans[:3])

INV = read('scripts/skill_construction/configs/poh_costume.inv')
blk = INV.split('[poh_costume_store]', 1)[1]
check('scope=perm' in blk, 'poh_costume_store is scope=perm - the whole point is that it survives logout')
check('size=%d' % NITEM in blk, 'and it has exactly one slot per item (size=%d)' % NITEM)
check('poh_costume_store' in {l.split('=', 1)[1] for l in read('pack/inv.pack').split('\n') if '=' in l},
      'it is registered in inv.pack')
ccap = enumtable(COST, 'poh_costume_cap')
caps = [int(ccap[t]) for t in sorted(ccap)]
check(sorted(ccap) == [1, 2, 3, 4], 'every chest tier has a capacity')
check(caps == sorted(caps) and caps[-1] == NITEM,
      'the capacities only go up and the best chest holds the lot: %s' % caps)

COSTRS = read('scripts/skill_construction/scripts/poh_costume.rs2')
# comments stripped: both these files TALK about the things they must not contain
COSTCODE = '\n'.join(l.split('//')[0] for l in COSTRS.split('\n'))
check('while (true)' not in COSTCODE, 'the set pager is a bounded loop')
st = COSTRS.split('[proc,poh_costume_store]', 1)[1].split('\n[', 1)[0]
check('inv_total(poh_costume_store, $item) = 0' in st,
      'storing puts ONE of each in - a second gold-trimmed platebody is not part of a costume')
check('$held < $cap' in st, 'and it stops at the capacity of the chest that was clicked')
wd = COSTRS.split('[proc,poh_costume_withdraw]', 1)[1].split('\n[', 1)[0]
check('inv_freespace(inv) > 0' in wd, 'withdrawing checks for room and leaves the rest in the chest')

# the wardrobe, and the tutorial handler it has to share
WARD = COSTRS.split('[proc,poh_wardrobe]', 1)[1].split('\n[', 1)[0]
check('allowdesign(true)' in WARD and 'if_openmain(player_kit)' in WARD,
      'the wardrobe opens the character-design screen')
TUT = read('scripts/tutorial/scripts/tutorial.rs2')
q = TUT.split('[queue,tutorial_designed_character]', 1)[1].split('\n[', 1)[0]
check('if (%tutorial = ^newbie_basics_instructor_start)' in q,
      'the shared close handler only advances a player who is still IN the tutorial - a wardrobe '
      'must not reset a finished one')
check('allowdesign(false)' in q and q.index('allowdesign(false)') > q.index('}'),
      'and it always turns allowdesign back off, guarded or not')
TUTCODE = '\n'.join(l.split('//')[0] for l in TUT.split('\n'))
check(TUTCODE.count('[if_close,player_kit]') == 1,
      'there is exactly one close handler in the repo - two is a build error')

# the mounted glory
GLORY = read('scripts/skill_construction/scripts/poh_glory.rs2')
check('[oploc1,poh_trophy_amuletofglory_4]' in GLORY, 'the glory trigger is on the amulet trophy')
TROPHY = blocks(read('scripts/skill_construction/configs/poh.loc'))
check((TROPHY.get('poh_trophy_amuletofglory_4', {}).get('op1') or [''])[0] == 'Rub',
      'which is the only one of the three trophies that carries op1=Rub')
for n in ('poh_trophy_antidragonbreath_4', 'poh_trophy_legendscape_4'):
    check(not (TROPHY.get(n, {}).get('op1') or []), '%s really has no op1' % n)
for n in ('poh_trophy_antidragonbreath_4', 'poh_trophy_legendscape_4'):
    check(n not in GLORY, '%s has no op1, so it gets no trigger' % n)
check('~poh_free' in GLORY, 'and the instance is freed on the way out, or it holds a slot until logout')
AOG = read('scripts/general/scripts/enchanted_jewellry/amulet_of_glory.rs2')
check('[proc,glory_teleport]' in AOG, 'the choice and the teleport are a proc now')
AOGCODE = '\n'.join(l.split('//')[0] for l in AOG.split('\n'))
lab = AOGCODE.split('[label,amulet_of_glory_interface]', 1)[1].split('\n[', 1)[0]
tel = AOGCODE.split('[proc,glory_teleport]', 1)[1].split('\n[', 1)[0]
check('inv_setslot' in lab and 'inv_setslot' not in tel,
      'the charge is eaten by the LABEL - a loc trigger has no last_slot worth writing to')

# ============================================================================ 56
print('56. every op a piece of house furniture advertises is answered by something')
# THE POINT OF THE LAST ROUND. A trigger on an op a loc does not carry never fires, which check 39
# has covered since the furniture round - this is the other direction, and it is the one that was
# never checked: an op the loc DOES carry with no trigger anywhere is a click that does nothing,
# and a click that does nothing is indistinguishable from a bug.
#
# Not every op has to be an activity. Several of these answer "you need someone else in the house"
# or "those items do not exist in this world yet" - which is the honest answer and still an answer.
GAMES = read('scripts/skill_construction/scripts/poh_games.rs2')
LOCCFG2 = blocks(read('scripts/skill_construction/configs/poh.loc'))
TEMPL2 = blocks(read('scripts/skill_construction/configs/poh_templates.loc'))
OPFILES = [read('scripts/skill_construction/scripts/poh_furn_ops.rs2'), GAMES,
           read('scripts/skill_construction/scripts/poh_costume.rs2'),
           read('scripts/skill_construction/scripts/poh_glory.rs2'),
           read('scripts/skill_construction/scripts/poh_flatpacks.rs2'),
           read('scripts/skill_construction/scripts/poh_furniture.rs2'),
           read('scripts/skill_construction/scripts/poh_tablets.rs2'),
           read('scripts/skill_construction/scripts/poh_build.rs2'),
           read('scripts/skill_construction/scripts/poh_portal.rs2')]
TRIG = set()
for t in OPFILES:
    TRIG |= set(re.findall(r'^\[oploc([1-5]),(\w+)\]', t, re.M))

# only the locs the furniture actually places - poh.loc also holds hotspots and scenery
FAM = _json.load(open(os.path.join(C, 'tools/furnspec.json')))['families']
# the spec carries a family's pieces either as a flat "locs" list or as "pieces" objects
placed = sorted({l for f in FAM for l in
                 (f.get('locs') or [p['loc'] for p in f.get('pieces', [])])})
check(len(placed) > 200, 'the spec places %d locs' % len(placed))
dead = []
for l in placed:
    cfg = LOCCFG2.get(l) or TEMPL2.get(l) or {}
    for k in cfg:
        m = re.match(r'^op([1-5])$', k)
        if m and (m.group(1), l) not in TRIG:
            dead.append('%s %s=%s' % (l, k, cfg[k][0]))
check(not dead, 'no op on a placed piece is a dead click: %s' % (dead[:6] or 'all %d answered' % len(TRIG)))

# the two that are real activities
check(len(re.findall(r'^\[oploc1,poh_archery_target', GAMES, re.M)) == 2, 'both archery targets shoot')
check(len(re.findall(r'^\[oploc1,poh_dartboard', GAMES, re.M)) == 2, 'both dartboards throw')
shoot = GAMES.split('[proc,poh_range_shoot]', 1)[1].split('\n[', 1)[0]
check(shoot.index('inv_del') < shoot.index('random(100)'),
      'the ammunition is spent before the roll - a miss has to cost something')
check(shoot.count('stat_advance(ranged') == 2, 'and the experience is only paid on a hit or a bullseye')
arch = GAMES.split('[proc,poh_archery]', 1)[1].split('\n[', 1)[0]
check('attackrange' in arch, 'the target asks for a bow by attackrange, not by a list of bows')

AMMO = read('scripts/skill_construction/configs/poh_games.enum')
ammo = enumtable(AMMO, 'poh_range_ammo')
fx = enumtable(AMMO, 'poh_range_fx')
check(sorted(ammo) == sorted(fx), 'every piece of ammunition has a launch effect')
check(all(o in OBJS for o in ammo.values()), 'every one is in obj.pack')
SPOT = set(packmap('pack/spotanim.pack'))
check(all(v in SPOT for v in fx.values()), 'every launch effect is in spotanim.pack: %s'
      % ([v for v in fx.values() if v not in SPOT][:3] or 'all %d' % len(fx)))
# and it is the RIGHT one. Every launch spotanim in the cache is its ammunition's name with _launch
# on the end, so the two tables can be checked against each other rather than just for existence -
# without this, a dart that launches an arrow passes everything.
wrongfx = sorted(ammo[i] for i in ammo if fx.get(i) != ammo[i] + '_launch')
check(not wrongfx, 'and it is the effect for that ammunition: %s' % (wrongfx[:3] or 'all %d match' % len(fx)))
AF = int(re.search(r'^\^poh_arrow_first\s*=\s*(\d+)', CONSTF, re.M).group(1))
AL = int(re.search(r'^\^poh_arrow_last\s*=\s*(\d+)', CONSTF, re.M).group(1))
DF = int(re.search(r'^\^poh_dart_first\s*=\s*(\d+)', CONSTF, re.M).group(1))
DL = int(re.search(r'^\^poh_dart_last\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(AL + 1 == DF and DL == max(ammo), 'the arrow and dart ranges tile the table with no gap')
check(all(ammo[i].endswith('_arrow') for i in range(AF, AL + 1)), 'the arrow range really is arrows')
check(all(ammo[i].endswith('_dart') for i in range(DF, DL + 1)), 'and the dart range really is darts')

# every one of these is inside somebody's house
for proc in ('poh_archery', 'poh_darts', 'poh_lever_pull', 'poh_needs_company', 'poh_no_parts',
             'poh_prize_chest'):
    body = GAMES.split('[proc,%s]' % proc, 1)[1].split('\n[', 1)[0]
    check('~poh_in_own_house' in body, '%s checks you are in your own house' % proc)

# ============================================================================ 57
print('57. the windows resolve, in all six styles')
# THE BUG THIS EARNED. poh_dynamic_window shipped as a single loc whose model is a wall with a
# window-shaped HOLE in it and whose desc read "This should have resolved!". There are 116 of them
# per style in the templates, so every house had 116 holes in its walls.
#
# A multiloc shell with no entry at the current value renders nothing and carries no ops, so the
# table has to be COMPLETE - all 6 styles times 9 kinds - and each child has to be the window for
# the style its index claims, or a stone house grows wooden windows.
WSTYLE = ['rimmington', 'lumbridge', 'pollnivneach', 'rellekka', 'brimhaven', 'yanille']
WKIND = ['shutters', 'bob', 'saradomin', 'guthix', 'zamorak',
         'bob2', 'saradomin2', 'guthix2', 'zamorak2']
NKIND = int(re.search(r'^\^poh_window_kinds\s*=\s*(\d+)', CONSTF, re.M).group(1))
check(NKIND == len(WKIND), '^poh_window_kinds is %d' % NKIND)
wblk = read('scripts/skill_construction/configs/poh.loc').split('[poh_dynamic_window]', 1)[1].split('\n[', 1)[0]
check('multivar=poh_window_state' in wblk, 'it is a multiloc over poh_window_state')
kids = {int(m.group(1)): m.group(2) for m in re.finditer(r'^multiloc=(\d+),(\w+)$', wblk, re.M)}
check(sorted(kids) == list(range(6 * NKIND)),
      'all %d states are listed with no gap (%d found)' % (6 * NKIND, len(kids)))
wrong = [(i, kids[i], 'poh_%s_window_%s' % (WSTYLE[i // NKIND], WKIND[i % NKIND]))
         for i in sorted(kids) if kids[i] != 'poh_%s_window_%s' % (WSTYLE[i // NKIND], WKIND[i % NKIND])]
check(not wrong, 'each child is the window for its own style and kind: %s' % (wrong[:2] or 'all %d' % len(kids)))
check(all(k in LOCS for k in kids.values()), 'every child is in loc.pack: %s'
      % ([k for k in kids.values() if k not in LOCS][:3] or 'all of them'))
check('This should have resolved' not in wblk, 'and the placeholder description is gone')

# the varp, the varbit, and the one proc that writes them
VB = read('scripts/skill_construction/configs/construction.varbit').split('[poh_window_state]', 1)[1]
check('basevar=poh_window' in VB, 'poh_window_state reads %poh_window')
bits = (int(re.search(r'endbit=(\d+)', VB).group(1)) - int(re.search(r'startbit=(\d+)', VB).group(1)) + 1)
check(2 ** bits > 6 * NKIND - 1, 'and it is %d bits, enough for %d states' % (bits, 6 * NKIND))
check('poh_window' in {l.split('=', 1)[1] for l in read('pack/varp.pack').split('\n') if '=' in l},
      '%poh_window is in varp.pack')
check('poh_window_state' in {l.split('=', 1)[1] for l in read('pack/varbit.pack').split('\n') if '=' in l},
      'poh_window_state is in varbit.pack')
vwin = read('scripts/skill_construction/configs/construction.varp').split('[poh_window]', 1)[1].split('\n[', 1)[0]
check('scope=perm' in vwin, 'and it is perm - a house does not reglaze itself on logout')
POHRS3 = read('scripts/skill_construction/scripts/poh.rs2')
ref = POHRS3.split('[proc,poh_window_refresh]', 1)[1].split('\n[', 1)[0]
check('%poh_style * ^poh_window_kinds' in ref, 'the refresh is style * kinds + choice')
writers = [f for f in ('scripts/skill_construction/scripts/poh.rs2',
                       'scripts/skill_construction/scripts/poh_portal.rs2',
                       'scripts/skill_construction/scripts/poh_test.rs2',
                       'scripts/skill_construction/scripts/poh_menus.rs2',
                       'scripts/skill_construction/scripts/poh_furniture.rs2')
           if '%poh_window =' in read(f)]
check(writers == ['scripts/skill_construction/scripts/poh.rs2'],
      'and it is the ONLY thing that writes %%poh_window: %s' % writers)
for f, why in (('scripts/skill_construction/scripts/poh_portal.rs2', 'redecorating'),
               ('scripts/skill_construction/scripts/poh.rs2', 'buying a house'),
               ('scripts/skill_construction/scripts/poh_test.rs2', '::~pohstyle')):
    check('~poh_window_refresh' in read(f), '%s calls it - the windows are part of the style' % why)

# the sit, which was playing beside the chair rather than on it
SIT = read('scripts/skill_construction/scripts/poh_furn_ops.rs2').split('[proc,poh_furn_sit]', 1)[1].split('\n[', 1)[0]
check('p_walk($seat)' in SIT, 'sitting walks onto the chair - an oploc1 click only gets you adjacent')
check('facesquare' in SIT, 'and turns to face the way the chair faces')
check(SIT.index('p_walk') < SIT.index('anim('), 'before the pose plays, not after')
check(len(re.findall(r'~poh_furn_sit\(', read('scripts/skill_construction/scripts/poh_furn_ops.rs2'))) == 24,
      'all 24 seats go through it')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
