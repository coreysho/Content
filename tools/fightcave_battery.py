"""Battery for the TzHaar Fight Cave.

The cave is 63 waves of monsters that the cache already had the art for and no content at all.
What can break silently here is not the fighting - that is the engine's own combat - it is the
ARITHMETIC and the ADDRESSING: a wave table off by one tier, a spawn point where a five-tile Jad
does not fit, a monster counted from the instance next door, an npc_add duration the engine's own
validator rejects at runtime while compiling perfectly.

So nothing here is compared against itself. The monsters' numbers come from tools/fightcavespec.json,
which records the OSRS cache's records; the wave table is GENERATED from the enum's own thresholds
and checked against thirteen cells of the wiki's table; and the arena's geometry is re-measured off
maps/m37_79.jm2 every run rather than trusted from the spec.

    python3 tools/fightcave_battery.py
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def read(p): return open(os.path.join(C, p), newline='', errors='replace').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

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

def consts(txt):
    return {m.group(1): m.group(2).strip()
            for m in re.finditer(r'(?m)^\^(\w+)\s*=\s*(.+?)\s*$', txt)}

def param(d, key):
    for pv in d.get('param', []):
        k, _, v = pv.partition(',')
        if k == key: return v
    return None

SPEC = json.loads(read('tools/fightcavespec.json'))
MON = SPEC['monsters']
CONST = consts(read('scripts/minigames/game_fightcave/configs/fightcave.constant'))
ENUM = read('scripts/minigames/game_fightcave/configs/fightcave.enum')
RS2 = read('scripts/minigames/game_fightcave/scripts/fightcave.rs2')
MRS2 = read('scripts/minigames/game_fightcave/scripts/fightcave_monsters.rs2')
REW = read('scripts/minigames/game_fightcave/scripts/fightcave_reward.rs2')
ALLNPC = blocks(read('scripts/_unpack/377/all.npc'))
ALLOBJ = blocks(read('scripts/_unpack/377/all.obj'))
ALLSEQ = blocks(read('scripts/_unpack/377/all.seq'))
DEATH = read('scripts/player/scripts/death.rs2')
MELEE = read('scripts/skill_combat/scripts/npc/npc_combat_melee.rs2')

def enumrows(name):
    b = ENUM.split('[' + name + ']', 1)[-1].split('\n[', 1)[0]
    return dict(m.groups() for m in re.finditer(r'(?m)^val=([^,]+),(.+)$', b))

# ============================================================================ the arena, measured
BLOCK_SHAPES = {0, 1, 2, 3, 9, 10, 11}

def entry_const():
    """The entry tile as ^fightcave_entry states it. NOT as the spec states it: a check that reads
    the spec and then floods from the spec compares the spec with itself, and the mutation run is
    what said so - moving ^fightcave_entry onto the clipped tile under the exit loc went unnoticed."""
    m = re.fullmatch(r'0_%s_(\d+)_(\d+)' % SPEC['arena']['square'], CONST['fightcave_entry'])
    return (int(m.group(1)), int(m.group(2))) if m else (-1, -1)

def pack(name):
    return {n: int(i) for i, n in (l.split('=', 1) for l in read('pack/' + name).split('\n') if '=' in l)}

def npc_spawns(sq, name):
    """Where one npc is spawned in a square. The .jm2 stores npc IDS, not names - grepping the name
    finds nothing and reads as "no spawns anywhere"."""
    want = pack('npc.pack').get(name)
    out = []
    t = read('maps/m%s.jm2' % sq)
    if '==== NPC ====' not in t: return out
    for l in t.split('==== NPC ====', 1)[1].split('\n====', 1)[0].split('\n'):
        m = re.match(r'^\s*(\d+)\s+(\d+)\s+(\d+):\s*(\d+)', l)
        if m and int(m.group(4)) == want:
            out.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    return out

def fits1(x, z):
    """Walkable in its own right, rather than merely being the tile the flood was seeded on - a
    flood counts its seed whether anything can stand there or not."""
    return any((0, x + dx, z + dz) in REACH for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)))

def arena():
    """(reachable tiles, blocked tiles) of m37_79 level 0, flooded from the entry tile."""
    t = read('maps/m%s.jm2' % SPEC['arena']['square'])
    blocked = set()
    for l in t.split('==== MAP ====', 1)[1].split('\n====', 1)[0].split('\n'):
        m = re.match(r'^\s*(\d) (\d+) (\d+): ?(.*)', l)
        if not m: continue
        fl = re.search(r'\bf(\d+)', m.group(4))
        if fl and int(fl.group(1)) & 1:
            blocked.add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
    locs = []
    for l in t.split('==== LOC ====', 1)[1].split('\n', 1)[1].split('\n'):
        m = re.match(r'^\s*(\d) (\d+) (\d+): (\d+) (\d+)', l)
        if not m: continue
        lv, x, z, oid, sh = (int(m.group(k)) for k in (1, 2, 3, 4, 5))
        locs.append((oid, lv, x, z))
        if sh in BLOCK_SHAPES: blocked.add((lv, x, z))
    ex, ez = entry_const()
    start = (0, ex, ez)
    seen = {start}; q = [start]
    while q:
        lv, x, z = q.pop()
        for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (lv, x + dx, z + dz)
            if 0 <= n[1] < 64 and 0 <= n[2] < 64 and n not in seen and n not in blocked:
                seen.add(n); q.append(n)
    return seen, locs

print('1. the arena is a place a player can be put, and a five-tile monster can stand in it')
REACH, LOCS = arena()
ex, ez = entry_const()
check(list((ex, ez)) == SPEC['arena']['entry'] and (0, ex, ez) in REACH and fits1(ex, ez),
      '^fightcave_entry is the tile the spec measured from, and a tile a player can stand on: %d,%d'
      % (ex, ez))
check(len(REACH) == SPEC['arena']['reachable_tiles'],
      'the reachable arena is the size the spec measured: %d' % len(REACH))
def fits5(x, z):
    return all((0, x + dx, z + dz) in REACH for dx in range(5) for dz in range(5))
five = [(x, z) for (lv, x, z) in REACH if fits5(x, z)]
check(len(five) == SPEC['arena']['tiles_fitting_size5'],
      '...of which the spec\'s count have a 5x5 clear block: %d' % len(five))
for k, (x, z) in sorted(SPEC['arena']['spawns'].items()):
    check((x, z) in five, 'the %s spawn is a tile a five-tile monster fits on' % k.upper())
    want = '0_%s_%d_%d' % (SPEC['arena']['square'], x, z)
    check(CONST.get('fightcave_spawn_' + k) == want,
          '...and ^fightcave_spawn_%s is that tile: %s' % (k, CONST.get('fightcave_spawn_' + k)))
pts = list(SPEC['arena']['spawns'].values())
closest = min(abs(a[0]-b[0]) + abs(a[1]-b[1]) for i, a in enumerate(pts) for b in pts[i+1:])
check(closest == SPEC['arena']['closest_two_spawns'],
      'no two spawn points are closer than the spec measured: %d tiles' % closest)
# the two doors, and that something answers them
for key, lbl in (('city_loc', 'fightcave_enter'), ('exit_loc', 'fightcave_leave')):
    nm = SPEC['arena'][key]
    check('[oploc1,%s] @%s;' % (nm, lbl) in RS2, '%s has a handler' % nm)
    check(param(ALLNPC.get(nm, {}), 'x') is None, '...(and %s is a loc, not an npc)' % nm)
check('0_%s' % SPEC['arena']['square'] in CONST.get('fightcave_template', ''),
      'the template square is the arena itself: %s' % CONST.get('fightcave_template'))
check(int(CONST['fightcave_zones']) * 8 == 64,
      'and the instance copies all 64 tiles of it: %s zones a side' % CONST['fightcave_zones'])

# ============================================================================ 2
print('2. every monster carries the cache\'s numbers, its tier and a death that ends the wave')
for name, s in sorted(MON.items(), key=lambda kv: kv[1]['tier']):
    d = ALLNPC.get(name, {})
    check(bool(d), '%s has a config block' % name)
    check(d.get('vislevel', [None])[0] == str(s['level']), '...level %d' % s['level'])
    got = [d.get(k, ['1'])[0] for k in ('attack', 'defence', 'strength', 'hitpoints', 'ranged', 'magic')]
    check(got == [str(v) for v in s['stats']], '...with the cache\'s stats %s' % ','.join(got))
    check(d.get('size', ['1'])[0] == str(s['size']),
          '...and the size the art record already had: %d' % s['size'])
    check(param(d, 'fightcave_tier') == str(s['tier']), '...tagged tier %d' % s['tier'])
    for k in ('attack_anim', 'defend_anim', 'death_anim'):
        a = param(d, k)
        check(a is not None and a in ALLSEQ, '...%s is a real seq: %s' % (k, a))
    check(param(d, 'damagetype') is not None, '...and it has a damage type at all')
    check('[ai_queue3,%s]' % name in MRS2, '...and its death is hooked')
# the five b duplicates the cache carries and the wave builder does not use
for b in ('_1b', '_2b', '_3b', '_4b', '_5b'):
    nm = 'tzhaar_fightcave_swarm' + b
    if nm not in ALLNPC: continue
    check(param(ALLNPC[nm], 'fightcave_tier') is None,
          '%s is left as the cache left it, so it cannot turn up in a wave' % nm)

# ============================================================================ 3
print('3. the wave table, generated from the enum and checked against the wiki')
TH = {int(k): int(CONST[v.lstrip('^')]) for k, v in enumrows('fightcave_tier_threshold').items()}
NPCOF = {int(k): v for k, v in enumrows('fightcave_tier_npc').items()}
check(sorted(TH) == [1, 2, 3, 4, 5], 'five tiers have a threshold')
check([TH[t] for t in sorted(TH)] == [1, 3, 7, 15, 31],
      '...and they are the 2^k-1 series: %s' % [TH[t] for t in sorted(TH)])
check(all(NPCOF[t] in ALLNPC for t in sorted(NPCOF)), 'each tier names an npc that exists')
check(sorted(int(t) for t in NPCOF) == [1, 2, 3, 4, 5], '...one per tier, 1 to 5')
def wave(n):
    out = []; m = n
    while m > 0:
        for t in sorted(TH, reverse=True):
            if m >= TH[t]:
                out.append(t); m -= TH[t]; break
        else:
            return None                      # no tier fits: the table would loop for ever
    return out
bad = [n for n in range(1, SPEC['wave_boundaries']['last_wave'] + 1) if wave(n) is None]
check(not bad, 'every wave from 1 to 62 terminates: %s' % (bad[:5] or 'yes'))
for n, want in sorted((int(k), v) for k, v in SPEC['wave_anchors'].items()):
    got = wave(n)
    check(got == want, 'wave %d is the wiki\'s: %s' % (n, got))
B = SPEC['wave_boundaries']
for tier, key in ((3, 'tokxil_first_heads'), (4, 'mejkot_first_heads'), (5, 'ketzek_first_heads')):
    n = B[key]
    check(wave(n) == [tier] and max(wave(n - 1)) < tier,
          'tier %d first heads a wave at %d and not before' % (tier, n))
check(wave(B['last_wave']) == [5, 5], 'the last ordinary wave is two of the top tier')
check(int(CONST['fightcave_jad_wave']) == B['jad_wave'] == int(CONST['fightcave_waves']),
      'and wave %d is TzTok-Jad, alone' % B['jad_wave'])
check('if ($wave >= ^fightcave_jad_wave) {' in RS2 and 'tzhaar_fightcave_swarm_boss)' in RS2,
      '...which the wave builder spawns instead of composing anything')
cyc = enumrows('fightcave_cycle_spawn')
check(len(cyc) == int(CONST['fightcave_cycle']) == 15,
      'the spawn cycle is 15 steps long: %d' % len(cyc))
check([int(cyc[str(i)]) for i in range(15)] == [0, 1, 2, 3, 1, 0, 4, 3, 2, 0, 1, 4, 3, 2, 4],
      '...in the order the wiki gives: SE SW C NW SW SE S NW C SE SW S NW C S')

# ============================================================================ 4
print('4. the instance is addressed, counted and freed correctly')
check('npc_add($at, $type, ^fightcave_npc_life);' in RS2,
      'a spawned monster is given a real lifetime')
check(int(CONST['fightcave_npc_life']) >= 1,
      '...which is not 0, because DurationValid rejects that at RUNTIME: %s' % CONST['fightcave_npc_life'])
for f, src in (('fightcave.rs2', RS2), ('fightcave_monsters.rs2', MRS2)):
    bad = re.findall(r'npc_add\([^;]*,\s*0\)', src)
    check(not bad, '%s adds no npc with a 0 duration: %s' % (f, bad[:2] or 'none'))
ALIVE = RS2.split('[proc,fightcave_alive]', 1)[-1].split('\n[', 1)[0]
check('npc_param(fightcave_tier) ! null' in ALIVE, 'the alive count tests the tier param')
check('instance_find(npc_coord) = %fightcave_instance' in ALIVE,
      '...AND the instance, so the cave next door cannot hold this wave open')
END = RS2.split('[proc,fightcave_end]', 1)[-1].split('\n[', 1)[0]
check(END.index('p_teleport(^fightcave_outside);') < END.index('instance_delete($inst);'),
      'the player is teleported out before the instance is deleted, not after')
check('%fightcave_instance = null;' in END, '...and the pointer is cleared with it')
BUILD = RS2.split('[proc,fightcave_build]', 1)[-1].split('\n[', 1)[0]
check('instance_delete($base);' in BUILD,
      'a half-built cave is deleted rather than entered')
check('queue*(fightcave_died, 0)(npc_uid);' in MRS2,
      'a monster\'s death reaches the player through a queue, which is where the protected pointer is')
check('[queue,fightcave_died]' in RS2, '...and that is what fightcave_died is')

# ============================================================================ 5
print('5. the rewards, and that they are the only source either of them has')
def tok(n): return n * (n + 1) if n > 0 else 0
check(tok(int(CONST['fightcave_waves'])) + int(CONST['fightcave_tokkul_jad'])
      == int(CONST['fightcave_full_run_tokkul']) == SPEC['tokkul']['full_run'],
      'a full run pays %d Tokkul, which is the figure the wiki quotes on its own'
      % SPEC['tokkul']['full_run'])
check('multiply($waves, add($waves, 1))' in REW,
      'and the formula in the script is the wiki\'s N * (N + 1)')
check('~obj_giveorbank(tzhaar_cape_fire, 1);' in REW, 'killing Jad hands over the Fire cape')
check('inv_add(bank, $obj, $count);' in REW,
      '...and nothing is dropped on the floor of an instance that is about to be deleted')
def givers(obj):
    hits = []
    for root, _, fs in os.walk(os.path.join(C, 'scripts')):
        for f in sorted(fs):
            if not f.endswith('.rs2'): continue
            src = open(os.path.join(root, f), newline='', errors='replace').read()
            if re.search(r'(inv_add|obj_add|~obj_giveorbank)\([^;]*\b%s\b' % obj, src):
                hits.append(f)
    return sorted(hits)
check('tzhaar_cape_fire' in ALLOBJ and 'tzhaar_token' in ALLOBJ, 'both rewards are real objs')
check(givers('tzhaar_cape_fire') == ['fightcave_reward.rs2'],
      'the cave is the ONLY source of a Fire cape: %s' % (', '.join(givers('tzhaar_cape_fire')) or 'nothing'))
# Tokkul is a different case and the check says so rather than pretending otherwise: the four
# TzHaar city monsters already dropped it, so the cave is a new source and not the first one.
check(givers('tzhaar_token') == ['fightcave_reward.rs2', 'tzhaar_hur.rs2', 'tzhaar_ket.rs2',
                                 'tzhaar_mej.rs2', 'tzhaar_xil.rs2'],
      'and Tokkul comes from the cave and the four city drop tables that already had it: %s'
      % ', '.join(givers('tzhaar_token')))

# ============================================================================ 6
print('6. the mechanics that make it the Fight Cave rather than 63 waves of furniture')
KIH = ALLNPC['tzhaar_fightcave_swarm_1a']
check(param(KIH, 'prayer_drain') == '1', 'Tz-Kih drains a prayer point')
check('queue(fightcave_prayer_drain, 0, npc_param(prayer_drain));' in MELEE,
      '...and it is param-driven, not keyed on the npc type')
check(MRS2.count('tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);') == 2,
      'Tz-Kek splits into exactly two')
check(param(ALLNPC['tzhaar_fightcave_swarm_2spawn'], 'fightcave_tier') is not None,
      '...and the halves count towards the wave, so it cannot end with them alive')
MEJ = MRS2.split('[proc,mejkot_attack]', 1)[-1].split('\n[', 1)[0]
check('multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)' in MEJ,
      'Yt-MejKot only heals once it is below half health')
check(MEJ.index('~fightcave_melee(') < MEJ.index('~fightcave_heal_others;')
      and MEJ.split('~fightcave_heal_others;', 1)[1].strip() == '}',
      '...and the heal is the last thing it does, because it walks the npc pointer')
check(MRS2.count('.npc_queue(9, ^fightcave_heal_amount, 0);') == 2,
      'both healers heal through a queue on the target, since there is no .npc_statheal: %d of 2'
      % MRS2.count('.npc_queue(9, ^fightcave_heal_amount, 0);'))
JAD = ALLNPC['tzhaar_fightcave_swarm_boss']
anims = {param(JAD, k) for k in ('crushattack_anim', 'rangeattack_anim', 'magicattack_anim')}
check(len(anims) == 3 and all(a in ALLSEQ for a in anims),
      'TzTok-Jad has three distinct attack animations: %s' % ', '.join(sorted(anims)))
check(param(JAD, 'magicattack_anim') == 'lordmagmus_fire',
      '...the 31-frame breath is the magic one')
check(param(JAD, 'rangeattack_anim') == 'lordmagmus_smash',
      '...the rear-and-slam with the splash on the ground is the ranged one')
JA = MRS2.split('[proc,jad_attack]', 1)[-1].split('\n[', 1)[0]
check('%fightcave_jad_called = 0 & npc_stat(hitpoints) <= ^fightcave_jad_heal_hp' in JA,
      'the healers come at %s hitpoints, once' % CONST['fightcave_jad_heal_hp'])
check(int(CONST['fightcave_jad_heal_hp']) < MON['tzhaar_fightcave_swarm_boss']['stats'][3],
      '...which is below his %d, or they would come the moment he spawned'
      % MON['tzhaar_fightcave_swarm_boss']['stats'][3])
check(MRS2.count('tzhaar_fightcave_swarm_boss_cleric, ^fightcave_npc_life);') == 1
      and 'while ($i < ^fightcave_jad_healers)' in MRS2,
      'and there are %s of them, from one loop' % CONST['fightcave_jad_healers'])
HUR = MRS2.split('[proc,hurkot_heal_jad]', 1)[-1].split('\n[', 1)[0]
check('.npc_type = tzhaar_fightcave_swarm_boss' in HUR, 'a Yt-HurKot heals Jad and only Jad')
check('~fightcave_adjacent(1) = true' in MRS2.split('[proc,hurkot_attack]', 1)[-1].split('\n[', 1)[0],
      '...and fights back instead when something is next to it')
check('if (~in_fightcave(coord) = true) {' in DEATH and '@fightcave_death;' in DEATH,
      'dying in the cave is caught before the ordinary death')
FD = RS2.split('[label,fightcave_death]', 1)[-1].split('\n[', 1)[0]
check('~player_death_lose_items' not in FD and '~pvp_death_lose_items' not in FD,
      '...and keeps the player\'s items, because the cave is safe')
check('~fightcave_end(sub(%fightcave_wave, 1));' in FD,
      '...and pays for the waves that were survived, not the one they died on')

# ============================================================================ 7
print('7. Tokkul is worth having, and the pet exists')
INV727 = blocks(read('scripts/_unpack/727/all.inv'))
TRADERS = blocks(read('scripts/areas/area_karamja/configs/tzhaar_traders.npc'))
SHOP = read('scripts/shop/scripts/shop.rs2')
SHOPPARAM = read('scripts/shop/configs/shopkeeper.param')
PETNPC = blocks(read('scripts/npc/configs/boss_pets.npc'))
PETOBJ = blocks(read('scripts/npc/configs/boss_pets.obj'))
PETSEQ = blocks(read('scripts/npc/configs/boss_pets.seq'))

# --- the currency, which said "coins" in six places
for what, needle in (('the till it counts', 'inv_total(inv, %shop_currency)'),
                     ('what it takes', 'inv_del(inv, %shop_currency, $added_amt)'),
                     ('what it pays', 'inv_add(inv, %shop_currency, $total_value)'),
                     ('the space it checks', 'inv_itemspace(inv, %shop_currency,'),
                     ('what it refuses to buy', '$item = %shop_currency'),
                     ('what it says you are short of, in both places it prints it', None)):
    if needle is None:
        # TWICE, not once: the currency's name is printed in the price quote AND in "you don't have
        # enough", and testing for presence let the second be replaced by the word coins unnoticed.
        check(SHOP.count('oc_name(%shop_currency)') == 2,
              'the shop reads its currency for %s: %d' % (what, SHOP.count('oc_name(%shop_currency)')))
    else:
        check(needle in SHOP, 'the shop reads its currency for %s' % what)
check(SHOP.count('%shop_currency =') == 2,
      '...and the currency is set in exactly those two places and nowhere else: %d'
      % SHOP.count('%shop_currency ='))
check('%shop_currency = coins;' in SHOP.split('[proc,openshop]', 1)[-1].split('\n[', 1)[0],
      '~openshop still sets coins, so its 38 callers did not have to change')
check('%shop_currency = npc_param(shop_currency);' in SHOP,
      '...and a shopkeeper\'s own shop reads the param')
cp = SHOPPARAM.split('[shop_currency]', 1)[-1].split('\n[', 1)[0]
check('default=coins' in cp,
      '...whose default is coins, so every shopkeeper that predates this keeps its till')

# --- the three traders and the three shops that had nobody to open them
WANT = {'tzhaar_shopkeeper_equipment': 'tzhaar_shop_equipment',
        'tzhaar_shopkeeper_oreandgem': 'tzhaar_shop_oreandgem',
        'tzhaar_shopkeeper_rune': 'tzhaar_shop_rune'}
check(sorted(TRADERS) == sorted(WANT), 'there are three TzHaar traders and no strangers')
for npc, shop in sorted(WANT.items()):
    d = TRADERS.get(npc, {})
    check(param(d, 'owned_shop') == shop, '%s owns %s' % (npc, shop))
    check(param(d, 'shop_currency') == 'tzhaar_token', '...and trades in Tokkul')
    check(d.get('category', [None])[0] == 'shop_keeper',
          '...on the category the shop triggers hang off')
    check(d.get('op3', [None])[0] == 'Trade' and d.get('op1', [None])[0] == 'Talk-to',
          '...with Trade and Talk-to')
    check('op2' not in d and d.get('vislevel', [None])[0] == 'hide',
          '...and cannot be attacked, so you can stand beside it')
    s = INV727.get(shop, {})
    stock = sorted(int(k[5:]) for k in s if re.fullmatch(r'stock\d+', k))
    check(stock == list(range(1, len(stock) + 1)),
          '%s stock numbering has no gaps or duplicates: %d entries' % (shop, len(stock)))
    check(len(stock) > 0, '...and it is not empty')
    check(all(len(v[0].split(',')) == 3 for k, v in s.items() if re.fullmatch(r'stock\d+', k)),
          '...and every line has its count and restock rate')
# the rune shop was the one with every line commented out
RUNE = INV727['tzhaar_shop_rune']
check(len(RUNE) and sorted(v[0].split(',')[0] for k, v in RUNE.items() if k.startswith('stock'))
      == ['airrune', 'bodyrune', 'chaosrune', 'deathrune', 'earthrune', 'firerune', 'mindrune', 'waterrune'],
      'the rune shop sells the eight runes its own commented-out lines listed')
# and the equipment shop still sells the whole obsidian set
EQUIP = {v[0].split(',')[0] for k, v in INV727['tzhaar_shop_equipment'].items() if k.startswith('stock')}
check(EQUIP == {'tzhaar_throwingring', 'tzhaar_splitsword', 'tzhaar_spikeshield', 'tzhaar_knife',
                'tzhaar_staff', 'tzhaar_mace', 'tzhaar_maul', 'tzhaar_cape_obsidian'},
      '...and the equipment shop the whole obsidian set: %d items' % len(EQUIP))
# spawned, and somewhere a player can reach
CITY = '38_80'
for npc in sorted(WANT):
    at = npc_spawns(CITY, npc)
    check(len(at) == 1, '%s is spawned once in m%s' % (npc, CITY))

# --- TzRek-Jad
PET, ITEM = 'bosspet_tzrek_jad', 'bosspet_tzrek_jad_item'
check(PET in PETNPC and ITEM in PETOBJ, 'TzRek-Jad exists as both an npc and an item')
check(param(PETNPC[PET], 'pet_item_id') == ITEM, '...and the npc names the item')
check(param(PETOBJ[ITEM], 'follower_id') == PET, '...and the item names the npc')
check(PETNPC[PET].get('category', [None])[0] == 'bosspet'
      and PETOBJ[ITEM].get('category', [None])[0] == 'bosspet',
      '...both on the category the four follower triggers hang off')
petseqs = [PETNPC[PET].get('readyanim', [''])[0], PETNPC[PET].get('walkanim', [''])[0]]
check(all(s.startswith('osrs_seq_') for s in petseqs),
      'both its animations are converted from OSRS, so they share a base and still walk-merge: %s'
      % ', '.join(petseqs))
check(all(s in PETSEQ for s in petseqs), '...and both are present in boss_pets.seq')
check(PETNPC[PET].get('resizeh', [None])[0] == '20',
      'and it is rendered at the cache\'s own 20, which is the joke')
ROLL = REW.split('[proc,fightcave_pet_roll]', 1)[-1].split('\n[', 1)[0]
check('random(^fightcave_pet_rate) ! 0' in ROLL, 'the pet rolls at ^fightcave_pet_rate')
check(int(CONST['fightcave_pet_rate']) == 200, '...which is 200, the rate for a plain kill')
check('~obj_gettotal(%s) > 0' % ITEM in ROLL and ('%%follower_obj = %s' % ITEM) in ROLL,
      '...and never gives a second one, counting pack, bank, worn and the one out following you')
check('~obj_giveorbank(%s, 1);' % ITEM in ROLL and 'obj_add' not in ROLL,
      '...and hands it over rather than dropping it in an instance about to be deleted')
check('~fightcave_pet_roll;' in REW.split('[proc,fightcave_reward]', 1)[-1].split('\n[', 1)[0],
      'and killing Jad is what rolls it')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
