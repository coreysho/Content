#!/usr/bin/env python3
"""The rune pouch window: three interfaces and the rs2 that drives them.

WHY THERE ARE THREE.

  rune_pouch_main    the window - the pouch's four slots, a Fill and an Empty button
  rune_pouch_side    the sidebar while it is open - your pack, click a rune to put it in
  rune_pouch_mirror  NEVER OPENED, and the whole reason spells work

THE MIRROR IS THE POINT. Every spell button in magic.if greys itself with a client-side script:

    script1op1=inv_count,inventory:inv,airrune
    script1op2=inv_count,inventory:inv,smokerune
    script1=gt,0

The client sums those ops and only lights the spell - and only lets a buttontype=target spell be
clicked - when the comparison passes. It counts inventory:inv and nothing else, so a rune in the
pouch could never satisfy one: the server-side ~rune_total was already correct and the cast was
being refused before a packet was ever sent. tools/genpouchruneops.py adds a second count against
rune_pouch_mirror:runes beside every inventory rune count, and login.rs2 transmits the store to it
for the whole session.

It has to be an interface of its own. Player.clearComListeners drops every inv transmit whose
component belongs to a root when that root closes, and it is called for modalMain, modalChat,
modalSide and the main overlay - so a component in the window itself would stop being transmitted
the first time the player closed the window, and one in an existing tab would be at the mercy of
whatever else opens there. An interface that is never opened is never any of those four.

The frame, title, close and subtitle come from genmenus.window and the ids from genmenus.repack,
so this is the fourth generator sharing that file.

    python3 tools/genrunepouch.py
"""
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genmenus as G

ROOT = G.ROOT
ORANGE, WHITE, YELLOW, RED = '0xFF981F', '0xFFFFFF', '0xFFFF00', '0xC00000'

# The pouch's slots, centred. width/height on an inv component are in SLOTS; margin is the gap
# added to each 32x32 cell. Four cells of 32+26 is 232, which centres at x=140 in a 512 window.
SLOTS, MARGIN = 4, 26
CELL = 32 + MARGIN
SLOT_X, SLOT_Y = 140, 112
NAME_Y = 152          # the rune's name under its slot: four 32px icons are hard to tell apart
LOCK_Y = 170
BTN_Y = 224
HINT_Y = 262


def main_if():
    coms = G.window('Rune pouch')
    coms.append(('help', dict(type='text', x=12, y=88, width=488, height=13, center='yes',
                              font='p12_full', shadowed='yes',
                              text='Click a rune to take it out.', colour=WHITE)))
    # The store itself. Remove 1/5/10/All are the bank's four, worded for a pouch; there is no
    # Remove X because the chatbox count prompt is a modal and this window is already one.
    coms.append(('pouch', dict(type='inv', x=SLOT_X, y=SLOT_Y, width=SLOTS, height=1,
                               interactable='yes', margin='%d,0' % MARGIN,
                               option1='Remove 1', option2='Remove 5', option3='Remove 10',
                               option4='Remove All')))
    # A name under each slot. The client draws the count on the icon but never the name, and at
    # 32px an air rune and a mind rune are the same pale blob - which is the whole problem with
    # reading a pouch off four icons.
    for i in range(SLOTS):
        coms.append(('name%d' % i, dict(type='text', x=SLOT_X + i * CELL - 11, y=NAME_Y,
                                        width=54, height=12, center='yes', font='p11_full',
                                        shadowed='yes', text='', colour=ORANGE)))
    # Slot four is only reachable with the divine pouch. hide only works on a LAYER in this client
    # (see genmenus' note), so the marker is a layer with a text inside it.
    coms.append(('locked', dict(type='layer', x=SLOT_X + 3 * CELL - 11, y=LOCK_Y,
                                width=54, height=12, scroll=0, hide='yes')))
    coms.append(('lockedtext', dict(layer='locked', type='text', x=0, y=0, width=54, height=12,
                                    center='yes', font='p11_full', shadowed='yes',
                                    text='locked', colour=RED)))
    coms.append(('fill', dict(type='text', x=96, y=BTN_Y, buttontype='normal', width=140,
                              height=14, center='yes', font='b12_full', shadowed='yes',
                              text='Fill from pack', colour='0xFF9040', overcolour=WHITE)))
    coms.append(('empty', dict(type='text', x=276, y=BTN_Y, buttontype='normal', width=140,
                               height=14, center='yes', font='b12_full', shadowed='yes',
                               text='Empty into pack', colour='0xFF9040', overcolour=WHITE)))
    coms.append(('hint', dict(type='text', x=12, y=HINT_Y, width=488, height=26, center='yes',
                              font='p11_full', shadowed='yes',
                              text='Spells cast straight out of the pouch.' + chr(92) + 'n'
                                   + 'Click a rune in your pack to put it in.',
                              colour=ORANGE)))
    return coms


def side_if():
    # The bank's sidebar, worded for the pouch. Four options, no Store X for the same reason.
    return [('inv', dict(type='inv', x=16, y=8, width=4, height=7, draggable='yes',
                         interactable='yes', usable='yes', margin='10,4',
                         option1='Store 1', option2='Store 5', option3='Store 10',
                         option4='Store All'))]


def mirror_if():
    # Never opened, never drawn, no options: the only thing this component is for is to give the
    # client an inv it can count in a spell's greying script. See the module docstring.
    return [('runes', dict(type='inv', x=0, y=0, width=SLOTS, height=1, margin='0,0'))]


def write(rel, coms):
    path = os.path.join(ROOT, rel)
    nl = '\r\n' if os.path.exists(path) and G._crlf(path) else '\n'
    body = G.emit(coms)
    open(path, 'wb').write(body.replace('\n', nl).encode('utf-8'))
    print('%-58s %d components' % (rel, len(coms)))
    return [n for n, _ in coms]


def run():
    names = {}
    names['rune_pouch_main'] = write('scripts/storage_items/interfaces/rune_pouch_main.if', main_if())
    names['rune_pouch_side'] = write('scripts/storage_items/interfaces/rune_pouch_side.if', side_if())
    names['rune_pouch_mirror'] = write('scripts/storage_items/interfaces/rune_pouch_mirror.if', mirror_if())
    G.repack(names, [])


if __name__ == '__main__':
    run()
