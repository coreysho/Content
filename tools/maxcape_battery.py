"""Battery for the Max cape, the Construction cape and the elder chaos druid robes.

Everything here is PARSED OUT of the delivered files - the item bonuses from the .obj configs, the
requirement and the price from the scripts that compute them, the spawns from the real maps, the
drop rates from the drop table's own arithmetic - so a change to one of them cannot pass a check
still asserting the old value. The numbers on the right-hand side of a comparison are OSRS's, from
oldschool.runescape.wiki (Max_cape, Max_hood, Elder_chaos_druid and the three robe pages).

    python3 tools/maxcape_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def pack(name):
    out = {}
    for line in read('pack/' + name).split('\n'):
        if '=' in line:
            i, n = line.split('=', 1)
            out[n.strip()] = int(i)
    return out

def blocks(txt):
    """A .obj/.npc config into {name: {key: [values]}}."""
    out = {}
    cur = None
    for line in txt.split('\n'):
        line = line.split('//')[0].strip()
        if not line: continue
        if line.startswith('[') and line.endswith(']'):
            cur = {}; out[line[1:-1]] = cur; continue
        if cur is None or '=' not in line: continue
        k, v = line.split('=', 1)
        cur.setdefault(k, []).append(v)
    return out

OBJP, NPCP, MODELP = pack('obj.pack'), pack('npc.pack'), pack('model.pack')
SEQP, SPOTP, ANIMP = pack('seq.pack'), pack('spotanim.pack'), pack('anim.pack')
MAXOBJ = blocks(read('scripts/skillcapes/configs/max_cape.obj'))
CAPES = blocks(read('scripts/skillcapes/configs/skillcapes.obj'))
ELDER = blocks(read('scripts/areas/area_wilderness/configs/elder_chaos.obj'))
ECDNPC = blocks(read('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc'))
MACNPC = blocks(read('scripts/skillcapes/configs/skillcape_npcs.npc'))
EQUIP = read('scripts/skillcapes/scripts/skillcape_equip.rs2')
PERKS = read('scripts/skillcapes/scripts/skillcape_perks.rs2')
SHOP = read('scripts/skillcapes/scripts/skillcape_shop.rs2')
SCENUM = read('scripts/skillcapes/configs/skillcape.enum')
STATENUM = read('scripts/player/configs/stat.enum')
TIER40 = read('scripts/levelrequire/scripts/tier40.rs2')
DROPS = read('scripts/drop_tables/scripts/elder_chaos_druid.rs2')
CONST = read('scripts/skillcapes/configs/skillcape.constant') + '\n' \
      + read('scripts/areas/area_wilderness/configs/elder_chaos.constant')
def const(n):
    return int(re.search(r'\^' + n + r'\s*=\s*(-?\d+)', CONST).group(1))

def enum_rows(txt, name):
    body = txt.split('[' + name + ']', 1)[1].split('\n[', 1)[0]
    return dict(re.findall(r'^val=([^,\n]+),(.*)$', body, re.M))

STATS = enum_rows(STATENUM, 'stats')

# ============================================================================ 1
print('1. the two items are real, and every model they name is in the cache')
check(set(MAXOBJ) == {'max_cape', 'max_hood'}, 'max_cape.obj holds the cape and the hood')
for name in ('max_cape', 'max_hood'):
    check(name in OBJP, '%s has an id in obj.pack (%s)' % (name, OBJP.get(name)))
missing = []
for name, cfg in list(MAXOBJ.items()) + list(ELDER.items()):
    for key in ('model', 'manwear', 'womanwear', 'manwear2', 'womanwear2', 'manhead', 'womanhead'):
        for v in cfg.get(key, []):
            m = v.split(',')[0]
            if m not in MODELP or not os.path.exists(os.path.join(C, 'models', 'obj', m + '.ob2')):
                missing.append((name, m))
check(not missing, 'all %d models of the five new items are in model.pack and on disk: %s'
      % (sum(len(c.get(k, [])) for c in list(MAXOBJ.values()) + list(ELDER.values())
             for k in ('model', 'manwear', 'womanwear', 'manwear2', 'womanwear2', 'manhead', 'womanhead')),
         missing[:3] or 'yes'))

# ============================================================================ 2
print('2. the Max cape wears like a trimmed skillcape, and keeps its Drop option')
prm = {}
for p in MAXOBJ['max_cape'].get('param', []):
    k, v = p.split(',', 1)
    prm[k] = v
check(all(prm.get(k) == '9' for k in ('stabdefence', 'slashdefence', 'crushdefence',
                                      'magicdefence', 'rangedefence')),
      'the +9 all-round defence of a Cape of Accomplishment: %s' % prm)
check(prm.get('prayerbonus') == '4', 'and the +4 prayer a trimmed one gives')
# the same defence a real skill cape carries, read off the Attack cape rather than written twice
acape = {p.split(',')[0]: p.split(',')[1] for p in CAPES['attack_cape'].get('param', [])}
check(all(acape.get(k) == prm.get(k) for k in ('stabdefence', 'magicdefence')),
      'which is the same number the Attack cape carries, not a second opinion')
check(MAXOBJ['max_cape'].get('category') == ['armour_cape'], 'it is an armour_cape like the rest')
check(MAXOBJ['max_cape'].get('tradeable') == ['no'] and MAXOBJ['max_hood'].get('tradeable') == ['no'],
      'neither piece is tradeable')
iops = {k: v[0] for k, v in MAXOBJ['max_cape'].items() if k.startswith('iop')}
check(iops == {'iop2': 'Wear', 'iop3': 'Teleports', 'iop4': 'Features'},
      'the ops are Wear, Teleports and Features: %s' % iops)
check('iop5' not in iops, "and iop5 is left alone, so Drop still works on an untradeable cape")
check(MAXOBJ['max_hood'].get('iop2') == ['Wear'] and len(
      [k for k in MAXOBJ['max_hood'] if k.startswith('iop')]) == 1,
      'the hood only wears, like every other skillcape hood')
check(MAXOBJ['max_hood'].get('param') is None, 'and carries no bonuses at all, as in OSRS')

# ============================================================================ 3
print('3. it needs 99 in every skill there is, and Mac charges by the skill')
gate = EQUIP.split('[opheld2,max_cape]', 1)[1].split('\n[', 1)[0]
check('~skillcape_count_99s < enum_getoutputcount(stats)' in gate,
      'the gate counts 99s against the stats enum rather than naming skills')
check('~equip(last_slot)' in gate, 'and equips when they are all there')
# VALUES AFTER THE CLAIM, NOT INSIDE IT. A mutation's label is the wording of the check it is
# written for, so a number in the middle of a claim changes the wording the moment the number
# changes, and the label stops matching. Three labels in this file were unmatchable for that
# reason; tools/mutate_labels.py is what found them.
check(len(STATS) == 22,
      'the enum holds every skill this build has, Construction in and Hunter out: %d'
      % len(STATS))
check('construction' in STATS.values() and 'hunter' not in STATS.values(),
      'Construction is one of them and Hunter is not, which is what makes the cape reachable')
price = SHOP.split('[proc,maxcape_price]', 1)[1].split('\n[', 1)[0]
check('^skillcape_price * enum_getoutputcount(stats)' in price,
      'the price is the skillcape price times that same count')
check(const('skillcape_price') == 99000, 'a skillcape is 99,000 coins, as in OSRS')
check(const('skillcape_price') * len(STATS) == 2178000,
      'so the Max cape comes to %s coins - 99,000 a skill, the way OSRS prices its own'
      % format(const('skillcape_price') * len(STATS), ','))
check(not re.search(r'\b2178000\b', SHOP), 'and that total is nowhere written down as a literal')
mac = SHOP.split('[opnpc1,skillcape_mac]', 1)[1].split('\n[', 1)[0]
check('~maxcape_ready = false' in mac, 'Mac checks the requirement before he offers anything')
check('%maxcape_bought = 1' in mac, 'remembers that you bought one')
check('~maxcape_give' in mac, 'and replaces a lost piece through the same one proc')
give = SHOP.split('[proc,maxcape_give]', 1)[1].split('\n[', 1)[0]
check('inv_freespace(inv) < $missing' in give, 'which asks for room for the missing pieces only')
check(give.count('~obj_gettotal') == 2,
      'and looks in the inventory, the bank and the worn slots for each piece')

# ============================================================================ 4
print('4. every skill has a cape, and every cape has an emote - the random pick cannot come up empty')
capes = enum_rows(SCENUM, 'skillcape_cape')
capes_t = enum_rows(SCENUM, 'skillcape_cape_t')
hoods = enum_rows(SCENUM, 'skillcape_hood')
for tbl, name in ((capes, 'skillcape_cape'), (capes_t, 'skillcape_cape_t'), (hoods, 'skillcape_hood')):
    missing = sorted(set(STATS.values()) - set(tbl))
    check(not missing, '%s covers all %d skills: %s' % (name, len(STATS), missing or 'yes'))
eseq = enum_rows(SCENUM, 'skillcape_emote_seq')
espot = enum_rows(SCENUM, 'skillcape_emote_spot')
bad = [s for s in STATS.values() if capes[s] not in eseq or capes[s] not in espot]
check(not bad, 'and every one of those capes has both an emote and a graphic: %s' % (bad or 'yes'))
bad = [s for s in STATS.values() if capes_t[s] not in eseq or capes_t[s] not in espot]
check(not bad, 'trimmed included: %s' % (bad or 'yes'))
emote = SHOP.split('[if_button,controls:skillcape]', 1)[1].split('\n[', 1)[0]
check('if ($cape = max_cape)' in emote, 'the emote button knows about the Max cape')
check('enum(int, stat, stats, calc(random(enum_getoutputcount(stats)) + 1))' in emote,
      'and picks one of the 22 skills, 1-based like the enum')
check(sorted(int(k) for k in STATS) == list(range(1, len(STATS) + 1)),
      'the stats enum really is 1..%d with no gap, or that pick could miss' % len(STATS))

# ============================================================================ 5
print('5. it has every perk, through the one proc that answers them all')
worn = PERKS.split('[proc,skillcape_worn]', 1)[1].split('\n[', 1)[0]
check('if ($back = max_cape) {\n    return(true);' in worn,
      '~skillcape_worn answers true for the Max cape whatever the skill asked about')
check(worn.index('max_cape') < worn.index('skillcape_cape'),
      'before it looks the individual capes up, so no table needs a Max cape row')
tele = PERKS.split('[opheld3,max_cape]', 1)[1].split('\n[', 1)[0]
feat = PERKS.split('[opheld4,max_cape]', 1)[1].split('\n[', 1)[0]
check('~p_choice5_header' in tele and tele.count('@skillcape_teleport(') == 3
      and '@skillcape_teleport_house' in tele,
      'Teleports offers the three guild teleports and the house, all through the single capes\' own labels')
check('~p_choice4_header' in feat and '@skillcape_toggle_rol' in feat
      and '@skillcape_agility_boost' in feat and '@skillcape_spellbook' in feat,
      'Features reaches the ring of life, the run-energy boost and the spellbook swap')
# every destination the menu names is a destination a single cape teleports to
single = set(re.findall(r'@skillcape_teleport\((\S+?)\);', PERKS.split('[opheld3,max_cape]', 1)[0]))
menu = set(re.findall(r'@skillcape_teleport\((\S+?)\);', tele))
check(menu <= single, 'and every coordinate in the menu is one a cape already teleports to: %s'
      % (sorted(menu - single) or 'all three'))
for lbl in ('skillcape_teleport', 'skillcape_teleport_house', 'skillcape_toggle_rol',
            'skillcape_agility_boost', 'skillcape_spellbook'):
    check('[label,%s]' % lbl in PERKS, 'the %s label exists' % lbl)
check(PERKS.count('[label,skillcape_teleport_house]') == 1
      and PERKS.count('~poh_enter(false)') == 1,
      'the house teleport is written once and ends in ~poh_enter, the tablet\'s own call')
house = PERKS.split('[label,skillcape_teleport_house]', 1)[1].split('\n[', 1)[0]
check('~wilderness_level(coord) > 20' in house and '~pre_tele_checks(coord) = false' in house,
      'with the wilderness and pre-teleport guards every other cape teleport has')

# ============================================================================ 6
print('6. the Construction cape is wearable now that the skill is')
check('@skillcape_unavailable("Construction")' not in EQUIP,
      'it is no longer refused for a skill that does not exist')
check(EQUIP.count('@skillcape_require(stat_base(construction), "Construction", last_slot)') == 2,
      'both the plain and the trimmed cape gate on 99 Construction')
check('@skillcape_unavailable("Hunter")' in EQUIP, 'Hunter is still the only unavailable one')
check('[opheld3,construction_cape] @skillcape_teleport_house;' in PERKS
      and '[opheld3,construction_cape_t] @skillcape_teleport_house;' in PERKS,
      'and its own op is the teleport home OSRS gives it')
agent = read('scripts/skill_construction/scripts/poh_portal.rs2')
offer = agent.split('[opnpc1,poh_estate_agent]', 1)[1].split('\n[', 1)[0]
check('~skillcape_offer(construction) = true' in offer, 'the estate agent sells it')
check(offer.index('~skillcape_offer') < offer.index('%poh_owned'),
      'from the top of his Talk-to, before his own dialogue')

# ============================================================================ 7
print('7. the Construction cape emote, which was the gap in a block of 24')
SEQ = read('scripts/skillcapes/configs/skillcape_emotes.seq')
SPOT = read('scripts/skillcapes/configs/skillcape_emotes.spotanim')
for name in ('skillcape_construction_emote', 'skillcape_construction'):
    check('[%s]' % name in SEQ, '%s is in the seq file' % name)
check('[skillcape_construction]' in SPOT, 'and the graphic is in the spotanim file')
body = SEQ.split('[skillcape_construction_emote]', 1)[1].split('\n[', 1)[0]
check('// OSRS seq 4953' in body, 'it is OSRS seq 4953 - the one id the 22 imported emotes skipped')
frames = re.findall(r'^frame\d+=(\S+)$', body, re.M)
check(len(frames) == 113, 'all %d frames of it' % len(frames))
check(all(f in ANIMP for f in frames), 'every frame is in anim.pack')
check('replaceheldright=skillcape_prop_crafting_r' in body,
      'and it holds the prop the cache says it holds - obj 9894, the one the Crafting emote also uses')
check('skillcape_prop_crafting_r' in OBJP, 'which is an obj that exists')
sbody = SPOT.split('[skillcape_construction]', 1)[1].split('\n[', 1)[0]
check('// OSRS spotanim 820' in sbody, 'the graphic is OSRS spotanim 820 - the other gap in the block')
check(re.search(r'^model=(\S+)$', sbody, re.M).group(1) in MODELP, 'its model is in model.pack')
check(re.search(r'^anim=(\S+)$', sbody, re.M).group(1) == 'skillcape_construction',
      'and it animates with the seq of the same name')
# the block really is 24 wide with these two filling it
# the player emotes are the odd ids of the block; the even ones beside them are the graphics' own
seqs = sorted(int(m) for m in re.findall(r'// OSRS seq (49\d\d)', SEQ))
player = [n for n in seqs if n % 2]
check(player == list(range(4937, 4982, 2)),
      'the emote seqs are the 23 odd ids from 4937 to 4981 with none missing: %d of them' % len(player))
check(len(seqs) == 2 * len(player), 'each with its graphic\'s animation beside it')

# ============================================================================ 8
print('8. Mac, and where he stands')
check('skillcape_mac' in MACNPC, 'his config is beside the other new masters')
check(MACNPC['skillcape_mac'].get('op1') == ['Talk-to'], 'he talks')
check('op2' not in MACNPC['skillcape_mac'], 'and cannot be attacked, whatever level the cache gave him')
check(MACNPC['skillcape_mac'].get('vislevel') == ['hide'], 'his combat level is hidden, like the other masters')
check('skillcape_mac' in NPCP, 'he has an id in npc.pack (%s)' % NPCP.get('skillcape_mac'))
sec = None; spots = []; solid = set()
for line in read('maps/m44_55.jm2').split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCP['skillcape_mac']: spots.append((lv, x, z))
    if sec == 'LOC' and lv == 0:
        d = data.split()
        if len(d) < 2 or int(d[1]) != 22: solid.add((x, z))
check(len(spots) == 1, 'he is placed exactly once, got %d' % len(spots))
if spots:
    lv, x, z = spots[0]
    ring = [(x + dx, z + dz) for dx in (-1, 0, 1) for dz in (-1, 0, 1) if (x + dx, z + dz) in solid]
    check(lv == 0 and not ring, 'his tile and the eight around it are clear: (%d,%d) %s'
          % (2816 + x, 3520 + z, ring or 'all nine'))
    check(2816 + x < 2837, 'and it is west of the guild wall, as near OSRS\'s island as this map gets')

# ============================================================================ 9
print('9. the elder chaos druid is the cache\'s and the wiki\'s monster')
d = ECDNPC['elder_chaos_druid']
WIKI = {'vislevel': '129', 'hitpoints': '150', 'attack': '98', 'strength': '98',
        'defence': '65', 'magic': '110', 'ranged': '1'}
bad = [(k, d.get(k), v) for k, v in WIKI.items() if d.get(k) != [v]]
check(not bad, 'level 129, 150 hitpoints and the four combat stats OSRS gives it: %s' % (bad or 'all seven'))
check(d.get('op2') == ['Attack'], 'it can be attacked')
check(d.get('huntmode') == ['ranged'] and int(d['huntrange'][0]) >= 8,
      'it hunts at range and from %s tiles away - aggressive, as the wiki says' % d.get('huntrange'))
prm = dict(p.split(',', 1) for p in d.get('param', []))
check(prm.get('attackrate') == '4', 'its attack speed is OSRS\'s 4 ticks')
check(prm.get('damagetype') == '^magic_style', 'and it hits with magic')
check(const('elder_chaos_maxhit') == 17, 'its maximum hit is OSRS\'s 17')
check('param=stabdefence' not in read('scripts/areas/area_wilderness/configs/elder_chaos_druid.npc')
      and 'attackbonus' not in str(prm),
      'it carries no attack or defence bonuses, which is what the wiki\'s block says')
ecd = read('scripts/areas/area_wilderness/scripts/elder_chaos_druid.rs2')
check('[ai_applayer2,elder_chaos_druid]' in ecd and '[ai_opplayer2,elder_chaos_druid]' in ecd,
      'it casts whether you are next to it or not - it has no melee attack in OSRS')
check('~npc_default_attack' not in ecd, 'and it never punches')
check('npc_param(attackrate)' in ecd, 'the cast speed is read from the config, not written twice')
check('~npc_spell_success($spell_data, ^elder_chaos_maxhit, $duration)' in ecd,
      'and the damage is the constant, not the borrowed spell\'s own')

# ============================================================================ 10
print('10. the robes drop at OSRS\'s rate, out of a table that adds up')
thresholds = [int(m) for m in re.findall(r'\$random < (\d+)', DROPS)]
check(thresholds == sorted(thresholds), 'the if-chain\'s thresholds only ever go up: %s' % thresholds[:6])
check(const('elder_chaos_table') == 129, 'the table is rolled out of 129, as OSRS rolls it')
check(max(thresholds) == 128 and 'else if' in DROPS.split('$random < 128')[1],
      'and the last slot is the 129th, so nothing falls off the end')
check(const('elder_chaos_slots') == 11, 'the robe table has 11 slots')
rt = DROPS.split('[proc,elder_chaos_robe_table]', 1)[1]
for piece in ('elder_chaos_hood', 'elder_chaos_robe', 'elder_chaos_top'):
    check(rt.count('obj_add(npc_coord, %s, 1,' % piece) == 1, '%s takes exactly one of them' % piece)
slots = [int(m) for m in re.findall(r'\$slot < (\d+)', rt)]
check(slots == [4, 8, 9, 10], 'four monk tops, four bottoms, then the three pieces: %s' % slots)
rate = const('elder_chaos_table') * const('elder_chaos_slots')
check(rate == 1419, 'which makes each piece 1 in %d - OSRS\'s own figure' % rate)
objs = set(re.findall(r'obj_add\(npc_coord, (\w+),', DROPS))
bad = sorted(o for o in objs if o not in OBJP)
check(not bad, 'every item the table drops is a real obj: %s' % (bad or '%d of them' % len(objs)))
check('npc_param(death_drop)' in DROPS, 'and bones always drop, from the npc\'s own param')

# ============================================================================ 11
print('11. the robes themselves, and the one requirement they have')
WIKISTATS = {'elder_chaos_top': (10, 8), 'elder_chaos_robe': (6, 6), 'elder_chaos_hood': (5, 4)}
for name, (atk, dfc) in WIKISTATS.items():
    prm = dict(p.split(',', 1) for p in ELDER[name].get('param', []))
    check(prm.get('magicattack') == str(atk) and prm.get('magicdefence') == str(dfc),
          '%s: +%d magic attack, +%d magic defence' % (name, atk, dfc))
    check(prm.get('levelrequire') == '40', 'and 40 Magic to wear')
    check(name in OBJP, 'with an id in obj.pack (%s)' % OBJP.get(name))
    check('[opheld2,%s] @levelrequire_magic(40, last_slot);' % name in TIER40,
          'gated on Magic alone in tier40.rs2 - no Defence requirement anywhere')
    body = read('scripts/areas/area_wilderness/configs/elder_chaos.obj')
    check('levelrequire_magic_and_defence' not in TIER40.split(name, 1)[1].split('\n')[0],
          'not on the two-stat gate the splitbark pieces use')
check(ELDER['elder_chaos_top'].get('wearpos') == ['torso']
      and ELDER['elder_chaos_robe'].get('wearpos') == ['legs']
      and ELDER['elder_chaos_hood'].get('wearpos') == ['hat'],
      'the three of them fill the torso, legs and hat slots')

# ============================================================================ 12
print('12. the druids stand around the Chaos altar, on ground they fit on')
LOCP = pack('loc.pack')
altar = [n for n, i in LOCP.items() if n == 'chaos_altar']
sec = None; spots = []; solid = set(); altars = []
alt_ids = {i for n, i in LOCP.items() if 'altar' in n}
for line in read('maps/m50_56.jm2').split('\n'):
    if line.startswith('===='):
        sec = line.strip('= '); continue
    if ':' not in line: continue
    head, data = line.split(':', 1)
    try: lv, x, z = (int(v) for v in head.split())
    except ValueError: continue
    if sec == 'NPC' and int(data) == NPCP['elder_chaos_druid']: spots.append((lv, x, z))
    if sec == 'LOC' and lv == 0:
        d = data.split()
        if int(d[0]) in alt_ids and (x, z) not in altars: altars.append((x, z))
        if len(d) < 2 or int(d[1]) != 22: solid.add((x, z))
check(len(spots) == 8, 'and the spawn count is what it was: %d' % len(spots))
check(len(altars) == 1, 'and one altar on the square (%s)'
      % ', '.join('%d,%d' % (3200 + x, 3584 + z) for x, z in altars))
if altars and spots:
    ax, az = altars[0]
    far = [(3200 + x, 3584 + z) for lv, x, z in spots if max(abs(x - ax), abs(z - az)) > 5]
    check(not far, 'every one is within five tiles of it: %s' % (far or 'all eight'))
    on = [(3200 + x, 3584 + z) for lv, x, z in spots if (x, z) in solid]
    check(not on, 'and none is standing inside a tree or a rock: %s' % (on or 'all eight clear'))
    check(all(lv == 0 for lv, x, z in spots), 'all on ground level')
    wild = [3584 + z for lv, x, z in spots]
    check(min(wild) >= 3520, 'all of them in the Wilderness (z %d-%d)' % (min(wild), max(wild)))
    lvls = sorted({(z - 3520) // 8 + 1 for z in wild})
    check(max(lvls) <= 20, 'in wilderness levels %s - inside the 20 that teleports still work in'
          % '-'.join(str(l) for l in (lvls[0], lvls[-1])))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
