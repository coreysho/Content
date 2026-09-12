#!/usr/bin/env python3
"""Re-implement the bank tab arithmetic from bank_tabs.rs2 and beat on it.

WHY. A tab is a RANGE of one ordered list, so every count is load-bearing: get one wrong and
every tab above it shows somebody else's items. Nothing in the build checks that, and it is not
the kind of thing that shows up as a crash - it shows up as a player's bank quietly reshuffling.
So the procs are transcribed here and run against random sequences, asserting the invariants the
rs2 cannot assert for itself.

Transcribed from scripts/interface_bank/scripts/bank_tabs.rs2 - if that changes, change this.
"""
import random, sys

TABS = 8
SIZE = 352

class Bank:
    def __init__(s):
        s.items = []            # the gapless ordered list; each entry is an opaque id
        s.c = [0] * (TABS + 1)  # c[1..8]

    # ---- transcribed procs
    def start(s, tab):
        return sum(s.c[i] for i in range(1, tab))
    def numbered_total(s):
        return s.start(TABS + 1)
    def of_slot(s, slot):
        end = 0
        for i in range(1, TABS + 1):
            end += s.c[i]
            if slot < end:
                return i
        return 0
    def closegap(s, slot):
        if slot < len(s.items):
            s.items.pop(slot)
    def removed(s, slot):
        # called when the slot has been emptied; rs2 checks inv_getobj == null first
        tab = s.of_slot(slot)
        if tab:
            s.c[tab] = max(0, s.c[tab] - 1)
        s.closegap(slot)
    def insert(s, frm, to):
        it = s.items.pop(frm)
        s.items.insert(to, it)
    def move_to(s, slot, tab):
        frm = s.of_slot(slot)
        if frm == tab:
            return
        if frm:
            s.c[frm] -= 1
        dest = s.numbered_total() if tab == 0 else s.start(tab) + s.c[tab]
        if slot < dest:
            dest -= 1
        s.insert(slot, dest)
        if tab:
            s.c[tab] += 1
    def deposit(s, obj, viewing):
        s.items.append(obj)
        if viewing:
            s.move_to(len(s.items) - 1, viewing)
    def validate(s):
        occupied = len(s.items)
        total = s.numbered_total()
        tab = TABS
        while tab > 0 and total > occupied:
            excess = total - occupied
            if s.c[tab] <= excess:
                total -= s.c[tab]; s.c[tab] = 0
            else:
                s.c[tab] -= excess; total = occupied
            tab -= 1

    # ---- invariants
    def check(s, where):
        assert all(x >= 0 for x in s.c), f'{where}: negative count {s.c}'
        assert s.numbered_total() <= len(s.items), \
            f'{where}: tabs claim {s.numbered_total()} of {len(s.items)} items -> a tab points past the end'
        assert len(s.items) == len(set(s.items)), f'{where}: an item was duplicated'
        # every item is in exactly one tab, and the ranges tile the list in order
        seen = 0
        for t in range(1, TABS + 1):
            for i in range(s.start(t), s.start(t) + s.c[t]):
                assert s.of_slot(i) == t, f'{where}: slot {i} should be tab {t}, of_slot says {s.of_slot(i)}'
                seen += 1
        assert seen == s.numbered_total()
        for i in range(s.numbered_total(), len(s.items)):
            assert s.of_slot(i) == 0, f'{where}: slot {i} past the numbered tabs is not tab 0'

def run(seed):
    rnd = random.Random(seed)
    b = Bank(); nxt = 0
    for step in range(400):
        act = rnd.random()
        if act < 0.35 and len(b.items) < SIZE:
            b.deposit(nxt, rnd.choice([0] + list(range(1, TABS + 1)))); nxt += 1
        elif act < 0.6 and b.items:
            b.removed(rnd.randrange(len(b.items)))
        elif act < 0.9 and b.items:
            b.move_to(rnd.randrange(len(b.items)), rnd.randrange(0, TABS + 1))
        else:
            # simulate items vanishing behind the bank's back (death, other scripts),
            # then the guard that runs on open
            for _ in range(rnd.randrange(1, 4)):
                if b.items: b.items.pop(rnd.randrange(len(b.items)))
            b.validate()
        b.check(f'seed {seed} step {step}')
    return b

worst = 0
for seed in range(400):
    b = run(seed)
    worst = max(worst, len(b.items))
print(f'400 seeds x 400 operations: all invariants held (largest bank reached {worst} items)')

# a targeted case: moving rightwards across a boundary is the one the -1 exists for
b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
before = list(b.items)
b.move_to(0, 2)                     # first item of tab 1 -> tab 2
b.check('rightward move')
assert b.c[1] == 2 and b.c[2] == 4, f'counts wrong: {b.c[1:3]}'
assert b.items[:5] == [1, 2, 3, 4, 0], f'item landed wrong: {b.items[:6]}'
print('rightward move across a boundary lands at the end of the destination tab')

b = Bank(); b.items = list(range(10)); b.c[1] = 3; b.c[2] = 3
b.move_to(5, 1)                     # last item of tab 2 -> tab 1
b.check('leftward move')
assert b.c[1] == 4 and b.c[2] == 2, f'counts wrong: {b.c[1:3]}'
assert b.items[:5] == [0, 1, 2, 5, 3], f'item landed wrong: {b.items[:6]}'
print('leftward move across a boundary lands at the end of the destination tab')
print('ALL PASS')

# ===================================================================================================
# The "all items" cell map
# ===================================================================================================
# Transcribed from Component.rebuildCellMap in the client. This is the half that can silently HIDE
# an item: the breaks push everything down, and if the map ran off the end of the grid an item would
# simply stop being drawn with nothing to say so.
# 51 rows, not 44: the breaks need room for up to 56 padding cells on top of the 352 real slots.
WIDTH, ROWS = 8, 51
CELLS = WIDTH * ROWS
SLOTS = 352

def cellmap(first, count, breaks):
    broken = any(b > 0 for b in breaks)
    if count < 0 and not broken:
        return None
    m = [-1] * CELLS
    first = first if count >= 0 else 0
    count = count if count >= 0 else CELLS
    cell = 0
    slot = first
    while slot < first + count and cell < CELLS:
        if broken:
            for b in breaks:
                if b == slot and cell % WIDTH != 0:
                    cell += WIDTH - cell % WIDTH
        if cell >= CELLS:
            break
        m[cell] = slot
        cell += 1
        slot += 1
    return m

def all_view(b):
    breaks = [b.start(t) for t in range(2, TABS + 1)] + [b.numbered_total()]
    m = cellmap(0, -1, breaks)
    # None is the client's "identity mapping" case - every break is 0, i.e. no tab is in use, so
    # the all-items view is just the plain contiguous list. Spell it out rather than special-case
    # it at every call site.
    return (m if m is not None else list(range(CELLS))), breaks

fail = 0
for seed in range(400):
    b = run(seed)
    m, breaks = all_view(b)
    shown = [s for s in m if s >= 0]
    # every real item is reachable, in order. shown is slot NUMBERS, so the test is that the
    # first len(items) of them are 0..n-1 - i.e. no item was skipped or reordered by the padding.
    if shown[:len(b.items)] != list(range(len(b.items))):
        print(f'seed {seed}: all-view order wrong'); fail += 1
    # each tab starts on a fresh row
    for t in range(1, TABS + 1):
        if b.c[t] == 0:
            continue
        cell = m.index(b.start(t))
        if cell % WIDTH != 0 and b.start(t) != 0:
            print(f'seed {seed}: tab {t} starts mid-row at cell {cell}'); fail += 1
    # nothing is dropped off the bottom at realistic sizes
    if len(shown) < len(b.items):
        print(f'seed {seed}: {len(b.items) - len(shown)} items pushed off the grid '
              f'({len(b.items)} items, 8 tabs)'); fail += 1
assert fail == 0, f'{fail} all-view failures'
print('400 seeds: the all-items view shows every item, in order, each tab starting on a fresh row')

# the worst case: eight tabs each holding one item wastes seven cells per tab
b = Bank()
b.items = list(range(16))
for t in range(1, 9):
    b.c[t] = 1
m, breaks = all_view(b)
shown = [s for s in m if s >= 0]
assert shown[:16] == list(range(16)), 'worst case lost an item'
for t in range(1, 9):
    assert m.index(b.start(t)) % WIDTH == 0 or b.start(t) == 0
print('worst case (8 tabs x 1 item): 8 rows of one, remainder starts on row 9, nothing lost')

# and the capacity cost of the breaks at full tilt
# the capacity question the extra rows exist to answer: a FULL bank, eight tabs each ragged
# enough to waste the maximum 7 cells. Every one of the 352 slots must still be reachable.
b = Bank(); b.items = list(range(SLOTS))
for t in range(1, 9):
    b.c[t] = 9          # 9 items = 2 rows, 7 cells wasted per tab, 56 wasted in total
m, _ = all_view(b)
shown = [s for s in m if s >= 0]
assert shown[:SLOTS] == list(range(SLOTS)), \
    f'full bank + worst-case padding loses items: only {len(shown)} of {SLOTS} reachable'
print(f'full bank (352) with 8 maximally ragged tabs: all 352 reachable in {CELLS} cells '
      f'({CELLS - SLOTS} spare)')
print('ALL PASS')
