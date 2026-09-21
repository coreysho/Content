#!/usr/bin/env python3
"""What Graceful actually buys, in ticks, so the in-game check has numbers to compare against.

WHY THIS EXISTS. The project doc for the first Graceful round said to "confirm the recovery differs
by about a fifth from bare". That is not a check, it is a feeling. This prints the exact tick
counts the engine's own arithmetic produces, so wearing the set and counting is a pass or a fail.

IT DOES NOT HOLD ITS OWN COPY OF THE FORMULAS. Both lines are asserted to be present in the
engine's Player.ts before anything is printed - if updateEnergy() is rewritten, this stops rather
than quietly reporting last month's behaviour. The engine clone is found the same way
tools/objpacked.py finds it: $LOSTCITY_ENGINE, then a sibling named engine or Engine-TS.

    python3 tools/gracefulsim.py
"""
import json, os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOTS = ([os.environ['LOSTCITY_ENGINE']] if os.environ.get('LOSTCITY_ENGINE') else []) \
    + [os.path.join(C, '..', e) for e in ('engine', 'Engine-TS')]
PL = next((os.path.join(r, 'src/engine/entity/Player.ts') for r in ROOTS
           if os.path.exists(os.path.join(r, 'src/engine/entity/Player.ts'))), None)
if PL is None:
    print('no engine clone with src/engine/entity/Player.ts - tried:\n  ' + '\n  '.join(ROOTS))
    sys.exit(2)
SRC = open(PL, encoding='utf-8', newline='').read().replace('\r\n', '\n')

# The two lines this file is a model of. Quoted exactly, so a rewrite of either is a stop.
RECOVER = 'const recovered = natural + (((natural * this.runrestore) / 100) | 0);'
NATURAL = "const natural = ((this.baseLevels[PlayerStat.AGILITY] / 6) | 0) + 8;"
LOSS = 'const loss = (67 + (67 * clampWeight) / 64) | 0;'
CLAMP = 'const clampWeight = Math.min(Math.max(weightKg, 0), 64);'
missing = [n for n, t in (('the natural recovery', NATURAL), ('the restore scale', RECOVER),
                          ('the drain', LOSS), ('the weight clamp', CLAMP)) if t not in SRC]
if missing:
    print('updateEnergy() no longer contains %s - this model is out of date, fix it before '
          'trusting it' % ', '.join(missing))
    sys.exit(1)

FULL = 10000
spec = json.load(open(os.path.join(C, 'tools', 'gracefulspec.json')))
RESTORE = spec['result']['total_pct']
OSRS_RESTORE = spec['osrs']['full_set_total_pct']
GRACE_KG = -sum(spec['osrs']['weight_kg'].values())      # 25, as a saving


def natural(agility):
    return (agility // 6) + 8


def recovered(agility, restore_pct):
    n = natural(agility)
    return n + (n * restore_pct) // 100


def loss(weight_kg):
    clamp = min(max(weight_kg, 0), 64)
    return int(67 + (67 * clamp) / 64)


def ticks_to_full(agility, restore_pct):
    return -(-FULL // recovered(agility, restore_pct))


def ticks_of_running(weight_kg):
    return -(-FULL // loss(weight_kg))


print('Graceful, in ticks. One tick is 0.6s.')
print('Recovery is the standing-still branch of updateEnergy(); the drain is the moving branch.')
print()
print('RESTING FROM EMPTY TO FULL')
print('  %-9s %-22s %-22s %-22s' % ('agility', 'bare', 'OSRS full set (+%d%%)' % OSRS_RESTORE,
                                    'this build (+%d%%)' % RESTORE))
for ag in (1, 20, 40, 60, 80, 99):
    b = ticks_to_full(ag, 0)
    o = ticks_to_full(ag, OSRS_RESTORE)
    m = ticks_to_full(ag, RESTORE)
    print('  %-9d %-22s %-22s %-22s'
          % (ag,
             '%d ticks (%.0fs)' % (b, b * 0.6),
             '%d ticks (%.0fs)' % (o, o * 0.6),
             '%d ticks (%.0fs), %.2fx' % (m, m * 0.6, b / m)))

print()
print('RUNNING FROM FULL TO EMPTY, by what you are carrying')
print('  %-14s %-14s %s' % ('carried', 'with Graceful', 'ticks of running'))
for kg in (0, 5, 10, 15, 25, 40, 64):
    bare = ticks_of_running(kg)
    with_g = ticks_of_running(kg - GRACE_KG)
    print('  %-14s %-14s bare %d (%.0fs) -> %d (%.0fs), %.2fx'
          % ('%d kg' % kg, '%d kg' % (kg - GRACE_KG),
             bare, bare * 0.6, with_g, with_g * 0.6, with_g / bare))

print()
print('WHAT TO CHECK IN GAME')
print('  Stand still at Agility 1 with nothing on: energy should fill in about %d ticks (%.0fs).'
      % (ticks_to_full(1, 0), ticks_to_full(1, 0) * 0.6))
print('  Do it in the full set: about %d ticks (%.0fs).'
      % (ticks_to_full(1, RESTORE), ticks_to_full(1, RESTORE) * 0.6))
print('  A piece is worth its own percent and nothing more - there is no set bonus at all, so')
print('  five of the six should measure between %d%% and %d%% depending on which one is off,'
      % (RESTORE - max(spec['result']['per_piece_pct'].values()),
         RESTORE - min(spec['result']['per_piece_pct'].values())))
print('  never %d%%. That is the difference between this and OSRS, where the sixth piece is worth'
      % RESTORE)
print('  its own percent plus another ten.')
print('  And a piece in the BACKPACK should change the recovery not at all, while still taking')
print('  its weight off - the weight counts what you carry, the recovery counts what you wear.')
