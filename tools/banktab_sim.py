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
