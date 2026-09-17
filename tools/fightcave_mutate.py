#!/usr/bin/env python3
"""Mutation test for tools/fightcave_battery.py. Same runner as pet_mutate.py, including its
"caught by its own check" reporting: a mutation that trips some OTHER check proves only that
something noticed.

    python3 tools/fightcave_mutate.py [filter]
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'fightcave_mutate_work')

CONST = 'scripts/minigames/game_fightcave/configs/fightcave.constant'
ENUM = 'scripts/minigames/game_fightcave/configs/fightcave.enum'
RS2 = 'scripts/minigames/game_fightcave/scripts/fightcave.rs2'
MRS2 = 'scripts/minigames/game_fightcave/scripts/fightcave_monsters.rs2'
REW = 'scripts/minigames/game_fightcave/scripts/fightcave_reward.rs2'
ALLNPC = 'scripts/_unpack/377/all.npc'
SPEC = 'tools/fightcavespec.json'
DEATH = 'scripts/player/scripts/death.rs2'
MELEE = 'scripts/skill_combat/scripts/npc/npc_combat_melee.rs2'

MUTS = [
 # 1 - the arena, and a spawn a five-tile monster cannot stand on
 (CONST, '^fightcave_entry = 0_37_79_44_61', '^fightcave_entry = 0_37_79_44_62',
  '1 ^fightcave_entry is the tile the spec measured from, and a tile a player can stand on'),
 (SPEC, '"c": [26, 31]', '"c": [2, 21]',
  '1 the C spawn is a tile a five-tile monster fits on'),
 (CONST, '^fightcave_spawn_nw = 0_37_79_4_56', '^fightcave_spawn_nw = 0_37_79_4_57',
  '1 ...and ^fightcave_spawn_nw is that tile'),
 (CONST, '^fightcave_zones = 8', '^fightcave_zones = 4',
  '1 and the instance copies all 64 tiles of it'),
 (RS2, '[oploc1,loc_9356] @fightcave_enter;\n', '',
  '1 loc_9356 has a handler'),
 # 2 - a monster whose numbers have drifted off the cache
 (ALLNPC, 'strength=960\nhitpoints=250', 'strength=960\nhitpoints=255',
  '2 ...with the cache\'s stats'),
 (ALLNPC, 'param=fightcave_tier,6', 'param=fightcave_tier,5',
  '2 ...tagged tier 6'),
 (ALLNPC, 'param=attack_anim,lordmagmus_attack', 'param=attack_anim,lordmagmus_attackk',
  '2 ...attack_anim is a real seq'),
 (MRS2, '[ai_queue3,tzhaar_fightcave_swarm_5a] @fightcave_monster_death;\n', '',
  '2 ...and its death is hooked'),
 # a b duplicate quietly given a tier, which would let it into a wave
 (ALLNPC, '[tzhaar_fightcave_swarm_1b]', '[tzhaar_fightcave_swarm_1b]\nparam=fightcave_tier,1',
  '2 tzhaar_fightcave_swarm_1b is left as the cache left it, so it cannot turn up in a wave'),
 # 3 - the wave table
 (CONST, '^fightcave_tier_tokxil = 7', '^fightcave_tier_tokxil = 8',
  '3 ...and they are the 2^k-1 series'),
 (CONST, '^fightcave_tier_tzkih = 1', '^fightcave_tier_tzkih = 2',
  '3 every wave from 1 to 62 terminates'),
 (SPEC, '"15": [4]', '"15": [3]',
  '3 wave 15 is the wiki\'s: [4]'),
 (ENUM, 'val=3,tzhaar_fightcave_swarm_3a', 'val=3,tzhaar_fightcave_swarm_3aa',
  '3 each tier names an npc that exists'),
 (CONST, '^fightcave_waves = 63', '^fightcave_waves = 64',
  '3 and wave 63 is TzTok-Jad, alone'),
 (ENUM, 'val=6,4\nval=7,3', 'val=6,3\nval=7,3',
  '3 ...in the order the wiki gives: SE SW C NW SW SE S NW C SE SW S NW C S'),
 (CONST, '^fightcave_cycle = 15', '^fightcave_cycle = 14',
  '3 the spawn cycle is 15 steps long: 15'),
 # 4 - the instance
 (CONST, '^fightcave_npc_life = 30000', '^fightcave_npc_life = 0',
  '4 ...which is not 0, because DurationValid rejects that at RUNTIME'),
 (MRS2, 'tzhaar_fightcave_swarm_boss_cleric, ^fightcave_npc_life);',
        'tzhaar_fightcave_swarm_boss_cleric, 0);',
  '4 fightcave_monsters.rs2 adds no npc with a 0 duration'),
 (RS2, ' & instance_find(npc_coord) = %fightcave_instance', '',
  '4 ...AND the instance, so the cave next door cannot hold this wave open'),
 (RS2, '''p_teleport(^fightcave_outside);
// The player is out before the instance goes: anyone still inside is standing on unallocated
// collision, which blocks every step they try to take.
instance_delete($inst);''', '''instance_delete($inst);
p_teleport(^fightcave_outside);''',
  '4 the player is teleported out before the instance is deleted, not after'),
 (RS2, '''            instance_delete($base);
''', '',
  '4 a half-built cave is deleted rather than entered'),
 (MRS2, 'queue*(fightcave_died, 0)(npc_uid);', 'npc_setmode(none);',
  '4 a monster\'s death reaches the player through a queue, which is where the protected pointer is'),
 # 5 - the rewards
 (CONST, '^fightcave_tokkul_jad = 4000', '^fightcave_tokkul_jad = 3000',
  '5 a full run pays 8032 Tokkul, which is the figure the wiki quotes on its own'),
 (REW, 'return(multiply($waves, add($waves, 1)));', 'return(multiply($waves, $waves));',
  '5 and the formula in the script is the wiki\'s N * (N + 1)'),
 (MRS2, '[proc,hurkot_heal_jad]', 'inv_add(inv, tzhaar_cape_fire, 1);\n\n[proc,hurkot_heal_jad]',
  '5 the cave is the ONLY source of a Fire cape'),
 (REW, 'inv_add(bank, $obj, $count);', 'obj_add(coord, $obj, $count, 100);',
  '5 ...and nothing is dropped on the floor of an instance that is about to be deleted'),
 # 6 - the mechanics
 (ALLNPC, 'param=prayer_drain,1\n', '',
  '6 Tz-Kih drains a prayer point'),
 (MELEE, 'queue(fightcave_prayer_drain, 0, npc_param(prayer_drain));',
         'queue(fightcave_prayer_drain, 0, 1);',
  '6 ...and it is param-driven, not keyed on the npc type'),
 (MRS2, '''npc_add(map_findsquare($home, 1, 2, ^map_findsquare_lineofwalk), tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);
npc_setmode(opplayer2);
npc_add(map_findsquare($home, 1, 2, ^map_findsquare_lineofwalk), tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);
npc_setmode(opplayer2);''',
        '''npc_add(map_findsquare($home, 1, 2, ^map_findsquare_lineofwalk), tzhaar_fightcave_swarm_2spawn, ^fightcave_npc_life);
npc_setmode(opplayer2);''',
  '6 Tz-Kek splits into exactly two'),
 (ALLNPC, 'param=fightcave_tier,2\n\n[tzhaar_fightcave_swarm_3a]', '\n[tzhaar_fightcave_swarm_3a]',
  '6 ...and the halves count towards the wave, so it cannot end with them alive'),
 (MRS2, 'if (multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)) {', 'if (random(2) = 0) {',
  '6 Yt-MejKot only heals once it is below half health'),
 (MRS2, '''~fightcave_melee(npc_param(attack_anim));
// Last, because the heal walks the secondary npc pointer: nothing below may need this npc.
if (multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)) {
    ~fightcave_heal_others;
}''', '''if (multiply(npc_stat(hitpoints), 2) <= npc_basestat(hitpoints)) {
    ~fightcave_heal_others;
}
~fightcave_melee(npc_param(attack_anim));''',
  '6 ...and the heal is the last thing it does, because it walks the npc pointer'),
 (MRS2, '.npc_queue(9, ^fightcave_heal_amount, 0);\n    }\n}\n\n// The far end', 'npc_say("heal");\n    }\n}\n\n// The far end',
  '6 both healers heal through a queue on the target, since there is no .npc_statheal'),
 (ALLNPC, 'param=magicattack_anim,lordmagmus_fire', 'param=magicattack_anim,lordmagmus_smash',
  '6 TzTok-Jad has three distinct attack animations'),
 (CONST, '^fightcave_jad_heal_hp = 150', '^fightcave_jad_heal_hp = 250',
  '6 ...which is below his 250, or they would come the moment he spawned'),
 (MRS2, 'if (%fightcave_jad_called = 0 & npc_stat(hitpoints) <= ^fightcave_jad_heal_hp) {',
        'if (npc_stat(hitpoints) <= ^fightcave_jad_heal_hp) {',
  '6 the healers come at 150 hitpoints, once'),
 (CONST, '^fightcave_jad_healers = 4', '^fightcave_jad_healers = 4\n^fightcave_unused = 1'),
 (MRS2, '.npc_type = tzhaar_fightcave_swarm_boss)', '.npc_type = tzhaar_fightcave_swarm_5a)',
  '6 a Yt-HurKot heals Jad and only Jad'),
 (DEATH, 'if (~in_fightcave(coord) = true) {\n    @fightcave_death;\n}\n', '',
  '6 dying in the cave is caught before the ordinary death'),
 (RS2, '''~prayer_deactivate_all;
~fightcave_end(sub(%fightcave_wave, 1));''', '''~prayer_deactivate_all;
~player_death_lose_items;
~fightcave_end(sub(%fightcave_wave, 1));''',
  '6 ...and keeps the player\'s items, because the cave is safe'),
 (RS2, '~fightcave_end(sub(%fightcave_wave, 1));\n~stat_reset_all;',
        '~fightcave_end(%fightcave_wave);\n~stat_reset_all;',
  '6 ...and pays for the waves that were survived, not the one they died on'),
]
MUTS = [m for m in MUTS if len(m) == 4]

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
            print('  SKIP (pattern not found) %-40s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'fightcave_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state = 'red'
            note = 'caught by its own check' + ('' if len(fired) == 1 else ' (and %d others)' % (len(fired) - 1))
        else:
            state, note = 'red', 'caught, but by: %s' % (
                fired[0][:56] if fired else 'a non-zero exit with no check named, which is a crash and not a catch')
            loose += 1
        print('  %-5s %-66s %s' % (state, why, note))
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
