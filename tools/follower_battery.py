"""Battery for the FOLLOWER LIFECYCLE and Probita's bureau.

tools/pet_battery.py covers where pets come from (rates and base chances) and
tools/bossart_battery.py covers what they look like. Neither covers what happens to one after you
get it, which is how a pet could be destroyed by a bad tick of the Kalphite Queen and how every
boss pet in the game said "Meow!" every ninety seconds for as long as anyone had one out.

Against tools/followerspec.json. Six groups:

  1. one owner for the slot - the lifecycle scripts, and who calls them
  2. no pet gets cat behaviour - the dispatch, and the categories it dispatches on
  3. death - the pet goes to Probita, the cat goes for good, and the ordering that makes that safe
  4. ownership - one answer to "owns this pet", used everywhere, counting all four places
  5. Probita herself - her record, her art, and where she stands
  6. her window - the .if, the packs, the script, and that nothing is ever charged

    python3 tools/follower_battery.py
"""
import hashlib, json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt):
    """The source with its comments gone. A claim in a comment is not a claim in the game."""
    return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

def blocks(txt):
    """[name] blocks -> {name: body}, for a .npc/.obj/.if/.inv config."""
    out = {}
    for b in re.split(r'(?m)^(?=\[)', txt):
        m = re.match(r'\[([\w+]+)\]', b)
        if m: out[m.group(1)] = code(b)
    return out

def trigger(txt, head):
    """The body of one [trigger,subject] block: from its header to the next [ at column 0."""
    m = re.search(r'(?m)^\[' + re.escape(head) + r'\][^\n]*\n(.*?)(?=^\[|\Z)', txt, re.S)
    return code(m.group(1)) if m else None

SPEC = json.loads(read('tools/followerspec.json'))
LOST, PROB = SPEC['lostpet'], SPEC['probita']

FOLLOWER = read('scripts/npc/scripts/follower.rs2')
CATRS2   = read('scripts/quests/quest_fluffs/scripts/pet.rs2')
BOSSRS2  = read('scripts/npc/scripts/boss_pets.rs2')
SKILLRS2 = read('scripts/npc/scripts/skill_pets.rs2')
EXCH     = read('scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2')
LOGIN    = read('scripts/login_logout/scripts/login.rs2')
LOGOUT   = read('scripts/login_logout/scripts/logout.rs2')
DEATH    = read('scripts/player/scripts/death.rs2')
PROBRS2  = read('scripts/npc/scripts/probita.rs2')
PROBNPC  = read('scripts/npc/configs/probita.npc')
INV      = read('scripts/npc/configs/follower.inv')
IFACE    = read('scripts/npc/interfaces/%s.if' % PROB['iface'])
MAP      = read('maps/%s.jm2' % PROB['map'])
PETOBJ   = read('scripts/npc/configs/boss_pets.obj') + '\n' + read('scripts/npc/configs/skill_pets.obj')
ALLOBJ   = read('scripts/_unpack/377/all.obj')
DAVE     = read('scripts/quests/quest_100/scripts/hundred_dave.rs2')

# Every .rs2 in the tree, for the "this is the only place that does X" claims.
RS2 = {}
for root, _, files in os.walk(os.path.join(C, 'scripts')):
    for f in files:
        if f.endswith('.rs2'):
            p = os.path.relpath(os.path.join(root, f), C)
            RS2[p] = code(read(p))

def defines(name):
    """Which files define this proc/queue/label, by its header."""
    pat = re.compile(r'(?m)^\[(?:proc|queue|label|timer),' + re.escape(name) + r'\]')
    return sorted(p for p, t in RS2.items() if pat.search(t))

def callers(pat):
    return sorted(p for p, t in RS2.items() if re.search(pat, t))

print('\n-- 1. one owner for the follower slot ------------------------------------------')

for name, kind in (('follower_spawn', 'proc'), ('follower_logout', 'proc'),
                   ('follower_death', 'proc'), ('follower_login', 'queue'),
                   ('follower_is_cat', 'proc'), ('pet_owned', 'proc')):
    d = defines(name)
    check(d == ['scripts/npc/scripts/follower.rs2'],
          '%s is defined once, in npc/scripts/follower.rs2: %s' % (name, d or 'nowhere'))

check(not re.search(r'(?m)^\[(?:proc|queue),follower_', CATRS2),
      'the cat quest defines none of them any more - it is a caller like everything else')
check('~follower_spawn(' in code(CATRS2),
      '...and ~cat_spawn claims the slot through ~follower_spawn')

check('queue(follower_login, 0, 0);' in code(LOGIN), 'login.rs2 queues follower_login')
check('~follower_logout;' in code(LOGOUT), 'logout.rs2 calls ~follower_logout')
check('~follower_death;' in code(DEATH), 'death.rs2 calls ~follower_death')

# The one spawn. Every OTHER write of %follower_uid = npc_uid is a changetype follow-up: the cat
# growing up, or Recipe for Disaster's hell-cat - the npc is the same npc, so the slot is only
# being told its new type. A NEW npc_uid in the slot anywhere else is a second spawn path.
spawn = SPEC['spawn_line']
sites = {p: t.count(spawn) for p, t in RS2.items() if spawn in t}
check(sites.get('scripts/npc/scripts/follower.rs2') == 1,
      'the slot is claimed once in npc/scripts/follower.rs2, and is written in %d files: %s'
      % (len(sites), ', '.join(sorted(os.path.basename(p) for p in sites))))
loose = []
for p, t in sorted(RS2.items()):
    if p == 'scripts/npc/scripts/follower.rs2':
        continue
    for m in re.finditer(re.escape(spawn), t):
        if not re.search(r'npc_changetype_keepall\([^;]*\);\s*$', t[:m.start()]):
            loose.append(os.path.basename(p))
check(not loose,
      'every other write of it follows an npc_changetype_keepall on the line before - the same npc '
      'being told its new type, not a second spawn path: %s' % (sorted(set(loose)) or 'none loose'))

check('npc_setmode(playerfollow);' in code(FOLLOWER)
      and code(BOSSRS2).count('npc_setmode(playerfollow)') == 0
      and code(EXCH).count('npc_setmode(playerfollow)') == 0,
      'and the pets and the metamorphosis no longer set follow mode themselves')

print('\n-- 2. no pet gets cat behaviour -----------------------------------------------')

iscat = trigger(FOLLOWER, 'proc,follower_is_cat')
named = set(re.findall(r'oc_category\(\$item\) = (\w+)', iscat or ''))
check(named == set(SPEC['cat_categories']),
      '~follower_is_cat names exactly the cat categories %s: %s'
      % (SPEC['cat_categories'], sorted(named)))

# The categories are not a guess: they are what the cache's own cat items carry.
cat_items = {n: re.search(r'category=(\w+)', b) for n, b in blocks(ALLOBJ).items()
             if 'param=follower_id,' in b}
cats = {(m.group(1) if m else None) for m in cat_items.values()}
check(cats == set(SPEC['cat_categories']),
      'all %d follower items in the 377 cache carry one of them: %s'
      % (len(cat_items), sorted(c or 'none' for c in cats)))

pet_items = {n: b for n, b in blocks(PETOBJ).items() if 'param=follower_id,' in b}
petcats = {re.search(r'category=(\w+)', b).group(1) for b in pet_items.values()}
check(not (petcats & set(SPEC['cat_categories'])),
      '...and not one of the %d pet items carries a cat category: %s'
      % (len(pet_items), sorted(petcats)))
check(len(pet_items) == LOST['pet_items'],
      'there are %d pet items outside the cat system' % len(pet_items))

logn = trigger(FOLLOWER, 'queue,follower_login')
# The say and the timer must be INSIDE the cat branch, which is a claim about order: the guard
# first, both lines after it.
guard = logn.find('~follower_is_cat(')
check(guard != -1 and logn.find('npc_say(') > guard and logn.find('settimer(petcat_growth') > guard,
      'the login respawn puts the miaow and the growth timer behind ~follower_is_cat')
check('~follower_spawn(oc_param(%follower_obj, follower_id))' in logn,
      '...and respawns whatever the slot remembers, through ~follower_spawn')
check('oc_param(%follower_obj, follower_id) = null' in logn,
      '...and empties the slot rather than spawning null when the item is no longer a follower')

settimers = {p: t.count('settimer(petcat_growth') for p, t in RS2.items()
             if 'settimer(petcat_growth' in t}
check(settimers == {'scripts/npc/scripts/follower.rs2': 1,
                    'scripts/quests/quest_fluffs/scripts/pet.rs2': 1},
      'petcat_growth is started in exactly two places, the login cat branch and ~cat_spawn: %s'
      % settimers)

grow = trigger(CATRS2, 'timer,petcat_growth')
cg = grow.find('~follower_is_cat(')
check(cg != -1 and 'cleartimer(petcat_growth)' in grow[cg:cg + 200],
      'the growth timer clears itself for a follower that is not a cat, so an old save stops meowing')
check(cg < grow.find('def_category $cat_cat'),
      '...and it does that BEFORE it reads the cat growth stage, which a pet does not have')

print('\n-- 3. death ------------------------------------------------------------------')

dth = trigger(FOLLOWER, 'proc,follower_death')
i_keep = dth.find('def_namedobj $pet = %follower_obj;')
i_clear = dth.find('%follower_obj = null;')
i_store = dth.find('inv_add(%s, $pet, 1)' % LOST['inv'])
i_cat = dth.find('~follower_is_cat($pet)')
check(i_keep != -1 and i_clear != -1 and i_keep < i_clear,
      'death remembers which pet it was before it empties the slot')
check(i_store != -1 and i_store > i_cat > i_clear,
      '...and puts it in %s, on the far side of the cat test' % LOST['inv'])
check('%cat_growth = 0;' in dth and 'npc_del;' in dth,
      '...while a cat still goes for good, growth and all')
check(re.search(r'mes\("[^"]*Probita', dth) is not None,
      '...and the player is told where the pet went')
check('inv_del(%s' % LOST['inv'] not in code(FOLLOWER),
      'nothing in the lifecycle takes a pet back OUT of the store - only Probita does')

print('\n-- 4. one answer to "owns this pet" ------------------------------------------')

own = trigger(FOLLOWER, 'proc,pet_owned')
for frag, what in (('~obj_gettotal($pet) > 0', 'the pack, the bank and what you are wearing'),
                   ('%follower_obj = $pet', 'what is following you'),
                   ('inv_total(%s, $pet) > 0' % LOST['inv'], "what Probita is holding")):
    check(frag in own, '~pet_owned counts %s' % what)

for src, name in ((BOSSRS2, 'the boss pet roll'), (SKILLRS2, 'the skilling pet roll'),
                  (EXCH, 'the Fight Cave exchange')):
    c = code(src)
    check('~pet_owned(' in c and '%follower_obj = $pet' not in c,
          '%s asks ~pet_owned and nothing else' % name)

print('\n-- 5. Probita ----------------------------------------------------------------')

rec = blocks(PROBNPC).get(PROB['npc'])
check(rec is not None, 'there is a [%s] npc record' % PROB['npc'])
ops = dict(re.findall(r'op(\d)=(.+)', rec or ''))
check(ops == PROB['ops'], "her ops are the cache's own, %s: %s" % (PROB['ops'], ops))
check('vislevel=hide' in rec and 'wanderrange=0' in rec,
      '...she has no combat level and does not wander off')
check('readyanim=human_ready' in rec and 'walkanim=human_walk_f' in rec,
      '...and moves on the 377 human animations, like the estate agent')

pack = {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/model.pack').split('\n') if l)}
npcpack = {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/npc.pack').split('\n') if l)}
check(PROB['npc'] in npcpack, '...and a line in npc.pack')
pid = npcpack.get(PROB['npc'])
named_models = re.findall(r'(?:model|head)\d+=(\S+)', rec or '')
check(len(named_models) == PROB['models'] + PROB['heads'],
      'her record names %d models and %d chatheads' % (PROB['models'], PROB['heads']))
missing = [m for m in named_models if m not in pack
           or not os.path.exists(os.path.join(C, 'models/npc', m + '.ob2'))]
check(not missing, '...every one of them packed and on disk: %s' % (missing or 'all present'))
bad = [m for m in named_models
       if hashlib.sha1(open(os.path.join(C, 'models/npc', m + '.ob2'), 'rb').read()).hexdigest()
       != PROB['model_sha1'].get(m)]
check(not bad, "...and every one is OSRS npc %d's own art, re-encoded: %s"
      % (PROB['osrs'], bad or 'all nine match'))

npcsec = MAP.split('==== NPC ====')[1].split('====')[0]
spawns = re.findall(r'(?m)^(\d) (\d+) (\d+): (\d+)$', npcsec)
mine = [(int(a), int(b), int(c)) for a, b, c, i in spawns if pid is not None and int(i) == pid]
check(mine == [tuple(PROB['tile'])],
      'she is spawned exactly once, at %s in maps/%s.jm2: %s'
      % (PROB['tile'], PROB['map'], mine))
aemad = [(int(a), int(b), int(c)) for a, b, c, i in spawns
         if int(i) == npcpack.get('aemad', -1)]
check(tuple(PROB['aemad_tile']) in aemad,
      "...in the same map square as Aemad's Adventuring Supplies %s" % PROB['aemad_tile'])
lv, x, z = PROB['tile']
alv, ax, az = PROB['aemad_tile']
check(lv == alv and max(abs(x - ax), abs(z - az)) <= PROB['reach'],
      '...and %d tiles from him, which is what "the small building next to Aemad\'s" means'
      % max(abs(x - ax), abs(z - az)))
locsec = MAP.split('==== LOC ====')[1].split('====')[0]
onher = [l for l in locsec.split('\n') if l.startswith('%d %d %d:' % (lv, x, z))]
solid = [l for l in onher if int(re.search(r': (\d+)', l).group(1)) and
         (len(l.split(':')[1].split()) == 1 or int(l.split(':')[1].split()[1]) in (10, 11))]
check(not solid, '...on a tile with nothing standing on it: %s' % (onher or 'bare ground'))

print('\n-- 6. the window -------------------------------------------------------------')

coms = blocks(IFACE)
grid = coms.get('pets')
check(grid is not None and 'type=inv' in grid, 'the window has an inv grid called pets')
gw = int(re.search(r'width=(\d+)', grid).group(1))
gh = int(re.search(r'height=(\d+)', grid).group(1))
# The label quotes the SPEC's numbers, not the measured ones: a label that prints what it just
# measured moves with the mutation and never names the check that caught it.
check((gw, gh) == (LOST['grid_cols'], LOST['grid_rows']),
      '...%d slots across by %d down' % (LOST['grid_cols'], LOST['grid_rows']))
size = int(re.search(r'size=(\d+)', blocks(INV)[LOST['inv']]).group(1))
check(size == gw * gh,
      '...and %s holds exactly as many as the window can show: %d = %d'
      % (LOST['inv'], size, gw * gh))
check(size >= LOST['pet_items'],
      '...which is enough for every pet item in the tree (%d)' % LOST['pet_items'])
check('scope=%s' % LOST['scope'] in blocks(INV)[LOST['inv']]
      and 'stackall' not in blocks(INV)[LOST['inv']],
      '...saved with the character, and nothing stacks in it, so used slots ARE pets')
check('option1=Reclaim' in grid and 'interactable=yes' in grid,
      '...and its one option is Reclaim')

ifpack = [l for l in read('pack/interface.pack').split('\n') if l]
ids = {n: int(i) for i, n in (l.split('=', 1) for l in ifpack)}
order = [int(l) for l in read('pack/interface.order').split('\n') if l.strip()]
check(PROB['iface'] in ids, 'the window itself is in interface.pack')
absent = [n for n in coms if '%s:%s' % (PROB['iface'], n) not in ids]
check(not absent, '...with every one of its %d components: %s'
      % (len(coms), absent or 'all present'))
check(set(order) == set(ids.values()) and len(order) == len(ids),
      'interface.order and interface.pack agree exactly - an id in one and not the other packs a '
      'component with type -1 and the client throws on load')

pc = code(PROBRS2)
check('if_openmain(%s);' % PROB['iface'] in pc, 'Check opens the window')
check('[opnpc3,%s] ~probita_open;' % PROB['npc'] in pc,
      "...off op3, which is the op the cache gives her for it")
check('inv_transmit(%s, %s:pets);' % (LOST['inv'], PROB['iface']) in pc,
      '...transmitting the store to the grid')
check('inv_stoptransmit(%s:pets);' % PROB['iface'] in pc
      and '[if_close,%s]' % PROB['iface'] in pc,
      '...and stopping when it closes')
for com in ('subtitle', 'help'):
    check('if_settext(%s:%s,' % (PROB['iface'], com) in pc and com in coms,
          '...%s is set by the script and exists in the .if' % com)
check('inv_size(%s) - inv_freespace(%s)' % (LOST['inv'], LOST['inv']) in pc,
      '~probita_count is the used slots of the store')

recl = trigger(PROBRS2, 'inv_button1,%s:pets' % PROB['iface'])
check(recl is not None, 'clicking a pet in the grid is handled')
ops_used = sorted(set(re.findall(r'\b(inv_\w+)\(', recl or '')))
check(ops_used == sorted(PROB['free']['reclaim_inv_ops']),
      '...and it touches only %s: %s' % (', '.join(sorted(PROB['free']['reclaim_inv_ops'])), ops_used))
check('inv_freespace(inv) = 0' in (recl or ''),
      '...refusing without a free slot, the same way picking a pet up off the ground does')
bad = [w for w in PROB['free']['forbidden_symbols'] if re.search(r'\b%s\b' % w, pc)]
check(not bad, 'nothing in the bureau names a currency - reclaiming is free: %s'
      % (bad or 'no coins anywhere'))

print('\nALL PASS' if not fails else '\n%d FAILED' % fails)
sys.exit(1 if fails else 0)
