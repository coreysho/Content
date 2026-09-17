#!/usr/bin/env python3
"""The Slayer Rewards window: tools/genslayerui.py writes the interface and the code that fills it.

WHY A WINDOW AND NOT THE CHAT BOX. Slayer points used to be spent through nested p_choice menus -
"Unlock something." then five labels then a confirm - which is not what Old School does and cannot
show a price list. OSRS interface 426 (read out of the cache, 39 components) is a window with a
title, a tab strip, a list, a description panel and a Back / Confirm pair, and it is the flow that
matters most: you SELECT a reward, read what it does, and only then confirm. That is what this
builds. What it does not copy is OSRS's geometry - 480px of modern fonts and custom sprites - so the
window is 377's own smithing backing at 377's proportions, the way the two Construction windows are.
The tab names, the button wording and the orange (0xFF981F) are the cache's.

The frame, title, close and subtitle come from genmenus.window, and the interface ids from
genmenus.repack, so this is the third generator sharing that file and none of them moves the others'
ids (see the note in repack).

    python3 tools/genslayerui.py
"""
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import genmenus as G

ROOT = G.ROOT
def _read(p): return open(os.path.join(ROOT, p), newline='').read().replace('\r\n', '\n')
ENUMS = _read('scripts/skill_slayer/configs/slayer_rewards.enum')
CONST = _read('scripts/skill_slayer/configs/slayer.constant')
ORANGE, WHITE, YELLOW = '0xFF981F', '0xFFFFFF', '0xFFFF00'
# The three browns: a row at rest, a row the pointer is over, and a tab that is not the open one.
# ^slayer_ui_row_on and ^slayer_ui_tab_on are their bright halves, in slayer.constant, because the
# script is what paints them.
ROW_OFF, ROW_HOVER, TAB_OFF = '0x4A3F31', '0x6F6250', '0x3E3529'

# The tab strip. The names are OSRS's own, in OSRS's order.
TABS = ['Unlock', 'Extend', 'Buy', 'Tasks', 'Cosmetics']
TAB_Y, TAB_H, TAB_X, TAB_W, TAB_GAP = 66, 14, 16, 92, 4

# ROWS is the longest list any tab shows - eleven, the extends - so no tab ever needs a page. A
# paged window would spend a fresh redraw per page out of one shared opcode budget; see
# claude/poh-menu-opcount.md for what that cost the Construction window.
ROWS, ROW_Y, ROW_STEP, ROW_H = 11, 90, 15, 14
ROW_X, ROW_W, COST_W = 26, 460, 120

DESC_Y, DESC_STEP, DESC_LINES = 258, 14, 3
BUTTON_Y = 306


def components():
    coms = G.window('Slayer Rewards')
    # Each tab is a fill with the label on top. The fill is what marks the open tab - the same
    # if_setcolour trick the rows use, for the same reason.
    for i, name in enumerate(TABS):
        x = TAB_X + i * (TAB_W + TAB_GAP)
        coms.append(('tab%dfill' % i, dict(type='rect', x=x, y=TAB_Y, width=TAB_W, height=TAB_H,
                                           fill='yes', colour=TAB_OFF)))
        coms.append(('tab%d' % i, dict(type='text', x=x, y=TAB_Y, buttontype='normal',
                                       width=TAB_W, height=TAB_H, center='yes', font='b12_full',
                                       shadowed='yes', text=name, colour=ORANGE,
                                       overcolour=WHITE)))
    for i in range(ROWS):
        coms.append(('row%d' % i, dict(type='layer', x=ROW_X, y=ROW_Y + i * ROW_STEP,
                                       width=ROW_W, height=ROW_H, scroll=0)))
        # The rect is the button and the text sits on top of it: a component carries exactly one
        # option string, and "Select" belongs to the whole row rather than to either label.
        # FILLED, and its colour is how the window shows what is selected. if_sethide only works
        # on layers, and a row is already one - so hiding a highlight inside it is not an option,
        # but if_setcolour on the fill is, and it leaves the name's own green/white/red intact.
        coms.append(('r%dbox' % i, dict(layer='row%d' % i, type='rect', x=0, y=0,
                                        buttontype='normal', width=ROW_W, height=ROW_H,
                                        fill='yes', colour=ROW_OFF, overcolour=ROW_HOVER,
                                        option='Select')))
        coms.append(('r%dname' % i, dict(layer='row%d' % i, type='text', x=6, y=1,
                                         width=ROW_W - COST_W - 12, height=ROW_H - 2,
                                         font='p12_full', shadowed='yes', text='', colour=WHITE)))
        coms.append(('r%dcost' % i, dict(layer='row%d' % i, type='text', x=ROW_W - COST_W - 4, y=1,
                                         width=COST_W, height=ROW_H - 2, center='yes',
                                         font='p12_full', shadowed='yes', text='', colour=WHITE)))
    for i in range(DESC_LINES):
        coms.append(('desc%d' % i, dict(type='text', x=ROW_X + 6, y=DESC_Y + i * DESC_STEP,
                                        width=ROW_W - 12, height=13, font='p12_full',
                                        shadowed='yes', text='', colour=YELLOW)))
    coms.append(('back', dict(type='text', x=ROW_X + 6, y=BUTTON_Y, buttontype='normal',
                              width=88, height=14, center='yes', font='b12_full', shadowed='yes',
                              text='Back', colour=ORANGE, overcolour=WHITE)))
    coms.append(('confirm', dict(type='text', x=ROW_X + ROW_W - 94, y=BUTTON_Y,
                                 buttontype='normal', width=88, height=14, center='yes',
                                 font='b12_full', shadowed='yes', text='Confirm',
                                 colour=ORANGE, overcolour=WHITE)))
    return coms


HEAD = '''// The Slayer Rewards window - what fills it and what its clicks do.
//
// GENERATED by tools/genslayerui.py. The rows and the interface are both its work; the rewards
// themselves are data in configs/slayer_rewards.enum and the spending is in slayer_rewards.rs2 and
// slayer_points.rs2, which still hold the one implementation of every effect. Edit the generator or
// the enums, not this file.
//
// THE SHAPE IS OSRS INTERFACE 426's: a tab strip, a list, a description and Back / Confirm. You
// select a row, read what it does, and confirm - the cache's own two-button flow. ~slayer_ui_draw
// repaints every row on every click, so it is deliberately cheap: eleven rows of two if_settexts
// and a handful of enum reads. The engine spends ONE 500,000-opcode budget on a whole window
// session (claude/poh-menu-opcount.md), which is why the click loop is bounded by
// ^slayer_ui_clicks and why the battery measures what a redraw costs.'''


def rs2():
    o = [HEAD, '']
    o.append('// One row: the name on the left, the price or state on the right, hidden when the')
    o.append('// tab has nothing to put in it. if_sethide only works on layers, which is why every')
    o.append('// row is one.')
    for i in range(ROWS):
        o.append('[proc,slayer_ui_row%d](int $tab, int $i, int $sel)' % i)
        o.append('if ($i >= ~slayer_ui_count($tab)) {')
        o.append('    if_sethide(slayer_rewards:row%d, true);' % i)
        o.append('    return;')
        o.append('}')
        o.append('if_sethide(slayer_rewards:row%d, false);' % i)
        o.append('if_settext(slayer_rewards:r%dname, "<~slayer_ui_tint($tab, $i)><~slayer_ui_name($tab, $i)>");' % i)
        o.append('if_settext(slayer_rewards:r%dcost, "<~slayer_ui_tint($tab, $i)><~slayer_ui_cost_text($tab, $i)>");' % i)
        o.append('if_setcolour(slayer_rewards:r%dbox, ~slayer_ui_row_fill($sel, $i));' % i)
        o.append('')
    o.append('// The whole window, repainted. $sel is -1 for nothing selected.')
    o.append('[proc,slayer_ui_draw](int $tab, int $sel)')
    o.append('if_settext(slayer_rewards:subtitle, "<~slayer_ui_points_text>");')
    for i, name in enumerate(TABS):
        o.append('if_settext(slayer_rewards:tab%d, "<~slayer_ui_tabtint($tab, %d)>%s");' % (i, i, name))
        o.append('if_setcolour(slayer_rewards:tab%dfill, ~slayer_ui_tab_fill($tab, %d));' % (i, i))
    for i in range(ROWS):
        o.append('~slayer_ui_row%d($tab, %d, $sel);' % (i, i))
    for i in range(DESC_LINES):
        o.append('if_settext(slayer_rewards:desc%d, "<~slayer_ui_desc($tab, $sel, %d)>");' % (i, i))
    o.append('')
    o.append('// Every button the window can answer with, added after the draw.')
    o.append('[proc,slayer_ui_buttons](int $tab)')
    for i in range(len(TABS)):
        o.append('if_addresumebutton(slayer_rewards:tab%d);' % i)
    o.append('def_int $i = 0;')
    o.append('while ($i < ~slayer_ui_count($tab)) {')
    o.append('    ~slayer_ui_rowbutton($i);')
    o.append('    $i = calc($i + 1);')
    o.append('}')
    o.append('if_addresumebutton(slayer_rewards:back);')
    o.append('if_addresumebutton(slayer_rewards:confirm);')
    o.append('')
    o.append('// A resume button per row, by index. switch_int rather than eleven ifs so an unused')
    o.append('// row costs one comparison.')
    o.append('[proc,slayer_ui_rowbutton](int $i)')
    o.append('switch_int ($i) {')
    for i in range(ROWS):
        o.append('    case %d : if_addresumebutton(slayer_rewards:r%dbox);' % (i, i))
    o.append('}')
    o.append('')
    o.append('// Which row was clicked, or -1. The window reads last_com once and asks this.')
    o.append('[proc,slayer_ui_clicked_row]()(int)')
    o.append('switch_component (last_com) {')
    for i in range(ROWS):
        o.append('    case slayer_rewards:r%dbox : return(%d);' % (i, i))
    o.append('}')
    o.append('return(-1);')
    o.append('')
    o.append('// Which tab was clicked, or -1.')
    o.append('[proc,slayer_ui_clicked_tab]()(int)')
    o.append('switch_component (last_com) {')
    for i in range(len(TABS)):
        o.append('    case slayer_rewards:tab%d : return(%d);' % (i, i))
    o.append('}')
    o.append('return(-1);')
    return o


def cost_text():
    """Every price the window can show, written the way OSRS writes it.

    The 377 engine has no command that groups digits, so "1,000 points" has to be a table. Same
    trick as poh_room_cost_text and for the same reason - a menu that says 1000 reads as noise.
    Keyed BY THE PRICE rather than by the row, so the four tables that hold prices (and the three
    constants that hold the rest) all share one set of strings and no lookup can miss: battery
    group 9 fails if a price anywhere has no row here.
    """
    costs = set()
    for tbl in ('slayer_unlock_cost', 'slayer_extend_cost', 'slayer_buy_cost', 'slayer_cosmetic_cost'):
        body = ENUMS.split('[' + tbl + ']', 1)[1].split('\n[', 1)[0]
        costs |= {int(v) for v in re.findall(r'^val=\d+,(-?\d+)$', body, re.M)}
    for c in ('slayer_cancel_cost', 'slayer_block_cost'):
        costs.add(int(re.search(r'\^' + c + r'\s*=\s*(\d+)', CONST).group(1)))
    return sorted(costs)


def main():
    G.add_enum(os.path.join(ROOT, 'scripts/skill_slayer/configs/slayer_rewards.enum'),
               'slayer_cost_text',
               G.enum_block('slayer_cost_text', [(c, G.group(c)) for c in cost_text()], 'string',
                            '// Every price the Slayer Rewards window can show, grouped. The engine\n'
                            '// has no command that formats a number and a row that says 1000 reads\n'
                            '// as noise. GENERATED by tools/genslayerui.py from the four cost tables\n'
                            '// and the three cost constants, so a new price cannot arrive ungrouped.'))
    print('slayer_cost_text    %3d prices' % len(cost_text()))
    coms = components()
    names = [n for n, _ in coms]
    if len(names) != len(set(names)):
        raise SystemExit('duplicate component name')
    path = os.path.join(ROOT, 'scripts/skill_slayer/interfaces/slayer_rewards.if')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    text = G.emit(coms)
    if G._crlf(os.path.join(ROOT, 'scripts/interfaces/skill_guide.if')):
        text = text.replace('\r\n', '\n').replace('\n', '\r\n')
    open(path, 'wb').write(text.encode('utf-8'))
    print('slayer_rewards.if   %3d components' % len(coms))

    src = rs2()
    path = os.path.join(ROOT, 'scripts/skill_slayer/scripts/slayer_ui.rs2')
    nl = '\r\n' if G._crlf(os.path.join(ROOT, 'scripts/skill_slayer/scripts/slayer_rewards.rs2')) else '\n'
    # Join on \n and convert once - HEAD is one entry holding many lines. See genmenus.
    body = nl.join(src).replace('\r\n', '\n').rstrip('\n')
    if nl == '\r\n':
        body = body.replace('\n', '\r\n')
    open(path, 'wb').write((body + nl).encode('utf-8'))
    print('slayer_ui.rs2       %3d lines' % len(src))

    G.repack({'slayer_rewards': names}, [])


if __name__ == '__main__':
    main()
