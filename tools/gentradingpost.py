#!/usr/bin/env python3
"""Write the Trading Post's four windows, and take their ids in interface.pack.

    python3 tools/gentradingpost.py            # write the .if files and take pack ids
    python3 tools/gentradingpost.py --check     # exit 1 if any of them would change

THE WINDOWS. Three main panels, one side panel, every one of them the same frame the shop and
the boss window use (tradebacking tiles across 12..500, a b12 title, "Close Window" top right):

  tradingpost          the lists: Browse, My listings, My offers, Collection box. One inv grid
                       whose right-click options the script rewrites per tab with if_setinvop.
  tradingpost_listing  one listing: the item, who sells it, the price, the offers on it. The
                       seller can pick an offer, see what is in it, and accept or decline.
  tradingpost_offer    building an offer: coins, plus up to twelve items from the inventory.
  tradingpost_side     the player's inventory beside all three - "List" to sell, or "Offer"
                       while an offer is being built.

WHY THREE MAIN PANELS AND NOT ONE WITH HIDDEN LAYERS. Opening a different main panel is what
fires [if_close] on the one before, and that is the one place the barter window can hand its
items back - on Back, on Close, on walking away and on logout alike. A hidden layer has no close.

The script that drives them is scripts/tradingpost/scripts/tradingpost.rs2, and it is not
generated: nothing in it repeats.
"""
import os, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(C, 'tools'))
from genbosskills import read, take, take_order  # noqa: E402

OUT = os.path.join(C, 'scripts', 'tradingpost', 'interfaces')
IFPACK = os.path.join(C, 'pack', 'interface.pack')
IFORDER = os.path.join(C, 'pack', 'interface.order')

PANEL_X, PANEL_Y, PANEL_W, PANEL_H = 12, 20, 488, 300
TILE_W, TILE_H = 88, 60
ORANGE = '0xFF981F'
WHITE = '0xFFFFFF'
YELLOW = '0xFFFF00'
GREY = '0x808080'


class Panel:
    def __init__(self, name, blurb):
        self.name = name
        self.names = []
        self.out = ['// %s. GENERATED - do not hand-edit.' % blurb,
                    '//   python3 tools/gentradingpost.py', '']

    def com(self, nm, **kv):
        self.names.append(nm)
        self.out.append('[%s]' % nm)
        for k, v in kv.items():
            self.out.append('%s=%s' % (k, v))
        self.out.append('')

    def frame(self):
        n = 0
        x = PANEL_X
        while x < PANEL_X + PANEL_W:
            w = min(TILE_W, PANEL_X + PANEL_W - x)
            y = PANEL_Y
            while y < PANEL_Y + PANEL_H:
                self.com('frame%d' % n, type='graphic', x=x, y=y, width=w,
                         height=min(TILE_H, PANEL_Y + PANEL_H - y), graphic='tradebacking,0')
                n += 1
                y += TILE_H
            x += TILE_W

    def title(self, text):
        self.com('title', type='text', x=PANEL_X, y=PANEL_Y + 8, width=PANEL_W, height=14,
                 font='b12_full', shadowed='yes', center='yes', colour=ORANGE, text=text)
        self.com('close', type='text', x=420, y=29, width=68, height=11, buttontype='close',
                 font='p11_full', shadowed='yes', text='Close Window', colour=GREY, overcolour=WHITE)

    def text(self, nm, x, y, w, text, colour=WHITE, font='p12_full', center=False, h=14):
        kv = dict(type='text', x=x, y=y, width=w, height=h, font=font, shadowed='yes')
        if center:
            kv['center'] = 'yes'
        kv.update(colour=colour, text=text)
        self.com(nm, **kv)

    # A clickable line of text: orange, white under the mouse, one option.
    def button(self, nm, x, y, w, text, option=None, center=False):
        kv = dict(type='text', x=x, y=y, width=w, height=14, buttontype='normal', font='p12_full',
                  shadowed='yes')
        if center:
            kv['center'] = 'yes'
        kv.update(colour=ORANGE, overcolour=WHITE, text=text, option=option or text)
        self.com(nm, **kv)

    def inv(self, nm, x, y, cols, rows, margin, options):
        kv = dict(type='inv', x=x, y=y, width=cols, height=rows, margin=margin)
        for i, o in enumerate(options):
            kv['option%d' % (i + 1)] = o
        self.com(nm, **kv)

    def body(self):
        return '\n'.join(self.out)


def lists():
    p = Panel('tradingpost', 'THE TRADING POST - the lists')
    p.frame()
    p.title('Trading Post')
    # four tabs across the top; the script colours the open one white
    for i, (nm, label) in enumerate([('tab_browse', 'Browse'), ('tab_mine', 'My listings'),
                                     ('tab_offers', 'My offers'), ('tab_box', 'Collection box')]):
        p.button(nm, 44 + i * 108, 46, 100, label, center=True)
    p.text('status', PANEL_X, 64, PANEL_W, '', colour=YELLOW, font='p11_full', center=True)
    # 8 x 4: an item is 32 wide and the margin 15, so 8*47-15 = 361 wide, centred
    p.inv('grid', 76, 84, 8, 4, '15,15', ['Inspect', 'Buy-now'])
    p.text('empty', PANEL_X, 160, PANEL_W, '', colour=GREY, center=True)
    # the bottom row; the script hides whichever do not apply to the open tab
    p.button('search', 30, 268, 80, 'Search', 'Search by name')
    p.button('showall', 112, 268, 80, 'Show all')
    p.button('prev', 300, 268, 80, '< Previous', 'Previous page', center=True)
    p.button('next', 390, 268, 80, 'Next >', 'Next page', center=True)
    p.button('collectall', 30, 268, 120, 'Collect all')
    p.text('hint', PANEL_X, 292, PANEL_W, '', colour=ORANGE, font='p11_full', center=True)
    return p


OFFER_ROWS = 8


def listing():
    p = Panel('tradingpost_listing', 'THE TRADING POST - one listing')
    p.frame()
    p.title('')
    p.inv('item', 30, 54, 1, 1, '0,0', [])
    for i in range(5):
        p.text('info%d' % i, 76, 50 + i * 14, 240, '', colour=WHITE if i else YELLOW)
    # what the viewer can do, right-hand column. They share rows because they never show together:
    # a seller sees only Take down, and a buyer sees Make an offer or Withdraw, never both.
    p.button('buynow', 320, 50, 170, 'Buy now')
    p.button('cancel', 320, 50, 170, 'Take down this listing')
    p.button('makeoffer', 320, 66, 170, 'Make an offer')
    p.button('withdraw', 320, 66, 170, 'Withdraw my offer')
    # the offers, public: anyone can see who has bid what, only the seller can open one
    p.text('offers_title', 24, 124, 280, 'Offers', colour=ORANGE, font='b12_full')
    for i in range(OFFER_ROWS):
        p.button('row%d' % i, 24, 142 + i * 16, 284, '', 'Select')
    p.text('offers_none', 24, 142, 284, 'No offers yet.', colour=GREY)
    # the chosen offer, seller only
    p.text('sel_title', 320, 124, 170, '', colour=ORANGE, font='b12_full')
    p.inv('offer_items', 320, 142, 4, 3, '10,8', [])
    p.button('accept', 320, 268, 80, 'Accept', 'Accept offer')
    p.button('decline', 410, 268, 80, 'Decline', 'Decline offer')
    p.button('back', 24, 292, 80, '< Back', 'Back')
    p.text('hint', 110, 292, 380, '', colour=ORANGE, font='p11_full', center=True)
    return p


def offer():
    p = Panel('tradingpost_offer', 'THE TRADING POST - making an offer')
    p.frame()
    p.title('')
    p.text('info', PANEL_X, 48, PANEL_W, '', colour=WHITE, center=True)
    p.text('coins', PANEL_X, 70, PANEL_W, '', colour=YELLOW, font='b12_full', center=True)
    p.button('setcoins', 196, 88, 120, 'Set coins', center=True)
    # 6 x 2: 6*47-15 = 267 wide, centred
    p.inv('barter', 122, 116, 6, 2, '15,15', ['Remove', 'Remove-5', 'Remove-All', 'Remove-X'])
    p.text('hint', PANEL_X, 206, PANEL_W, 'Click items in your inventory to add them to your offer.',
           colour=ORANGE, font='p11_full', center=True)
    p.button('submit', 176, 236, 160, 'Make this offer', center=True)
    p.button('back', 24, 292, 80, '< Back', 'Back')
    return p


def side():
    p = Panel('tradingpost_side', 'THE TRADING POST - the inventory beside it')
    # the same grid shop_template_side uses; the options are rewritten per window
    p.inv('inv', 16, 8, 4, 7, '10,4', ['List'])
    return p


PANELS = [lists, listing, offer, side]


def main():
    check = '--check' in sys.argv
    panels = [f() for f in PANELS]
    want = {os.path.join(OUT, p.name + '.if'): p.body() for p in panels}
    names = []
    for p in panels:
        names += [p.name] + ['%s:%s' % (p.name, n) for n in p.names]

    if check:
        bad = [os.path.relpath(path, C) for path, body in want.items()
               if not os.path.exists(path) or read(path) != body]
        _, added = take(IFPACK, names, True)
        if added:
            bad.append('interface.pack is missing %d ids' % len(added))
        if bad:
            print('gentradingpost --check: ' + '; '.join(bad))
            return 1
        print('gentradingpost --check: all four windows and their ids are already what this writes')
        return 0

    os.makedirs(OUT, exist_ok=True)
    for path, body in want.items():
        open(path, 'w', newline='').write(body)
        print('wrote %s' % os.path.relpath(path, C))
    ids, added = take(IFPACK, names, False)
    take_order(IFORDER, [ids[n] for n in names], False)
    print('%d components across %d windows, %d new interface ids' % (len(names), len(panels), len(added)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
