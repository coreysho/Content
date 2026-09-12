"""Run the packing, rotation and join rules the way poh.rs2 does, straight off the shipped file.

The arithmetic is the part a compile check cannot see: bit packing that loses a rotation, a door
mask that rotates the wrong way, a join rule that lets a room seal itself off. Every constant and
every table below is PARSED OUT of the delivered files rather than retyped, so a change to one of
them cannot pass a test still asserting the old value."""
import os, re, sys

CONTENT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
rs2 = open(CONTENT + '/scripts/skill_construction/scripts/poh.rs2', newline='').read().replace('\r\n', '\n')
const = open(CONTENT + '/scripts/skill_construction/configs/construction.constant', newline='').read().replace('\r\n', '\n')
enums = open(CONTENT + '/scripts/skill_construction/configs/poh_rooms.enum', newline='').read().replace('\r\n', '\n')

C = {m.group(1): int(m.group(2)) for m in re.finditer(r'\^(\w+)\s*=\s*(-?\d+)', const)}
GRID = C['poh_grid']
N, E, S, W = C['poh_door_n'], C['poh_door_e'], C['poh_door_s'], C['poh_door_w']

def enum_block(name):
    body = enums.split('[' + name + ']', 1)[1].split('\n[', 1)[0]
    out = {}
    for k, v in re.findall(r'^val=(\d+),(.+)$', body, re.M):
        out[int(k)] = v.strip()
    return out

ZONE = {k: int(v) for k, v in enum_block('poh_room_zone').items()}
DOORS = {k: int(v) for k, v in enum_block('poh_room_doors').items()}
NAME = enum_block('poh_room_name')

# ---- the same arithmetic poh.rs2 does -------------------------------------------------------
words = [0] * 16

def word_get(i): return words[i]
def word_set(i, v): words[i] = v

def setbit_range_toint(num, value, start, end):      # engine NumberOps
    mask = (1 << (end - start + 1)) - 1
    cleared = num & ~(mask << start)
    return cleared | (min(value, mask) << start)

def getbit_range(num, start, end):                   # (num << (31-end)) >>> (start + 31-end)
    a = 31 - end
    return ((num << a) & 0xFFFFFFFF) >> (start + a)

def room_packed(rx, rz):
    if rx < 0 or rx >= GRID or rz < 0 or rz >= GRID: return 0
    slot = rz * GRID + rx
    lo = (slot % 4) * 8
    return getbit_range(word_get(slot // 4), lo, lo + 7)

def room_type(rx, rz): return room_packed(rx, rz) & 63
def room_rot(rx, rz): return room_packed(rx, rz) // 64

def room_set(rx, rz, t, rot):
    if rx < 0 or rx >= GRID or rz < 0 or rz >= GRID: return
    slot = rz * GRID + rx
    i, lo = slot // 4, (slot % 4) * 8
    packed = (t & 63) + (rot % 4) * 64
    word_set(i, setbit_range_toint(word_get(i), packed, lo, lo + 7))

def rot_doors(doors, rot):
    r = rot % 4
    if r == 1: return (doors * 2 + doors // 8) & 15
    if r == 2: return (doors * 4 + doors // 4) & 15
    if r == 3: return (doors * 8 + doors // 2) & 15
    return doors

def doors_at(rx, rz):
    t = room_type(rx, rz)
    return 0 if t == 0 else rot_doors(DOORS[t], room_rot(rx, rz))

def door_on(rx, rz, side): return (doors_at(rx, rz) & side) != 0

def room_total():
    return sum(1 for rz in range(GRID) for rx in range(GRID) if room_type(rx, rz))

def can_place(rx, rz, t, rot):
    if rx < 0 or rx >= GRID or rz < 0 or rz >= GRID: return False
    if t == 0: return True
    if room_total() == 0: return True
    d = rot_doors(DOORS[t], rot)
    if d & N and door_on(rx, rz + 1, S): return True
    if d & E and door_on(rx + 1, rz, W): return True
    if d & S and door_on(rx, rz - 1, N): return True
    if d & W and door_on(rx - 1, rz, E): return True
    return False

# ---- checks ----------------------------------------------------------------------------------
fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

print('the tables parsed out of the shipped files')
check(GRID == 8, 'grid is %d' % GRID)
check((N, E, S, W) == (1, 2, 4, 8), 'door bits in rotation order, got %s' % ((N, E, S, W),))
COUNT = C['poh_room_count']
check(len(ZONE) == len(DOORS) == len(NAME) == COUNT,
      '^poh_room_count (%d) room types in all three enums' % COUNT)
check(set(ZONE) == set(DOORS) == set(NAME), 'the same ids in all three')
check(0 not in ZONE, 'type 0 is never a room')
check(all(0 <= v < 64 for v in ZONE.values()), 'every zone packs into six bits')
check(all(0 < v < 16 for v in DOORS.values()), 'every room has at least one door and no bit above W')
check(all(z // 8 < 8 and z % 8 < 8 for z in ZONE.values()), 'every template zone is inside its square')
check(len(set(ZONE.values())) == len(ZONE), 'no two room types share a template zone')

print('packing survives every slot, type and rotation')
bad = None
for rz in range(GRID):
    for rx in range(GRID):
        for t in list(ZONE) + [0]:
            for rot in range(4):
                room_set(rx, rz, t, rot)
                got = (room_type(rx, rz), room_rot(rx, rz) if t else room_rot(rx, rz))
                want = (t, rot)
                if got != want and not (t == 0 and got[0] == 0):
                    bad = (rx, rz, t, rot, got)
check(bad is None, 'type and rotation read back for all %d slots x 16 types x 4 rotations%s'
      % (GRID * GRID, '' if bad is None else ', first bad ' + str(bad)))

words[:] = [0] * 16
room_set(0, 0, 15, 3)
room_set(1, 0, 1, 0)
room_set(2, 0, 7, 2)
room_set(3, 0, 9, 1)
check([room_type(x, 0) for x in range(4)] == [15, 1, 7, 9], 'four rooms share one word without treading on each other')
check([room_rot(x, 0) for x in range(4)] == [3, 0, 2, 1], 'and so do their rotations')
room_set(1, 0, 0, 0)
check([room_type(x, 0) for x in range(4)] == [15, 0, 7, 9], 'clearing one leaves its neighbours alone')

print('a slot off the grid is empty, not a wrapped neighbour')
words[:] = [0] * 16
room_set(0, 0, 1, 0)
check(room_type(-1, 0) == 0 and room_type(GRID, 0) == 0 and room_type(0, -1) == 0, 'reads off the edge are empty')
room_set(-1, 0, 5, 0)
room_set(GRID, 0, 5, 0)
check(room_total() == 1, 'and writes off the edge are dropped, got %d rooms' % room_total())

print('rotating a door mask')
check(rot_doors(W, 1) == N and rot_doors(N, 1) == E and rot_doors(E, 1) == S and rot_doors(S, 1) == W,
      'one step turns W->N->E->S->W')
check(all(rot_doors(rot_doors(d, 1), 3) == d for d in range(16)), 'one step then three is the identity')
check(all(rot_doors(d, 4) == d for d in range(16)), 'four steps is the identity')
check(all(rot_doors(d, 2) == rot_doors(rot_doors(d, 1), 1) for d in range(16)), 'two steps is one step twice')
check(rot_doors(15, 2) == 15 and rot_doors(0, 3) == 0, 'all-doors and no-doors are unchanged')

print('the join rule')
words[:] = [0] * 16
G = [k for k, v in NAME.items() if v == 'Garden'][0]
P = [k for k, v in NAME.items() if v == 'Parlour'][0]
K = [k for k, v in NAME.items() if v == 'Kitchen'][0]
check(can_place(4, 4, G, 0), 'the first room may go anywhere')
room_set(4, 4, G, 0)
check(can_place(5, 4, P, 0), 'a parlour east of the garden joins: its W door meets the garden E door')
check(not can_place(6, 4, P, 0), 'but not two tiles away with nothing between')
check(can_place(4, 5, P, 0), 'and north of it too - the parlour SOUTH door meets the garden north one')
check(not can_place(4, 5, P, 2), 'but rotated 180 that south door faces away, so it does not')
# The trap that made the bedroom unreachable in the instancing round: the parlour has no north door,
# so nothing can ever attach to its north side however it is rotated.
words[:] = [0] * 16
room_set(5, 4, P, 0)
check(not any(can_place(5, 5, t, r) for t in ZONE for r in range(4)),
      'nothing at all can attach to the north of a lone parlour - it has no north door')
words[:] = [0] * 16
room_set(4, 4, G, 0)
check(can_place(4, 4, 0, 0), 'clearing a slot is always allowed')
check(not can_place(-1, 4, G, 0) and not can_place(0, GRID, G, 0), 'off the grid is refused')

print('the starter house the code actually hands out')
words[:] = [0] * 16
mid = GRID // 2
room_set(mid, mid, G, 0)
room_set(mid + 1, mid, P, 0)
check(room_total() == 2, 'two rooms')
check(doors_at(mid, mid) & E and doors_at(mid + 1, mid) & W, 'garden E meets parlour W - they join')
check(can_place(mid + 2, mid, K, 0),
      'and a third room attaches east of the parlour: kitchen W door meets parlour E door')
check(not can_place(mid + 1, mid + 1, K, 1),
      'but nothing goes north of the parlour, which is the shape of the bug that made the first '
      'test house bedroom unreachable')

print('every room type can be joined to a garden somehow')
for t in sorted(ZONE):
    words[:] = [0] * 16
    room_set(4, 4, G, 0)
    ok = any(can_place(x, z, t, r)
             for (x, z) in ((5, 4), (3, 4), (4, 5), (4, 3)) for r in range(4))
    check(ok, 'type %d %s' % (t, NAME[t]))

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
