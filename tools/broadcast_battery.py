"""Battery for the server-wide announcements - rare drops, pets, capes and ::yell.

    python3 tools/broadcast_battery.py

What it holds in place, and why each is a thing that has already gone wrong once:

  ONE PLACE BUILDS A BROADCAST. There were fourteen hand-written copies of the rare-drop line in
  fourteen files; restyling them meant finding every one, and a copy that was missed would have
  gone on printing plain black text. broadcast_mes is called from general/scripts/broadcast.rs2
  and nowhere else.
  EVERY PET ANNOUNCES. Only the Jad pet did; boss pets, skill pets and the Kraken's did not.
  THE ICON SHEET HAS ALL EIGHT ICONS, keyed on magenta. The packer takes 0xff00ff as transparent and
  ignores alpha, so an icon drawn with alpha-transparent corners ships with black ones.
  THE CROWN RULE IS THE ENGINE'S. ~broadcast_name must give the crown engine ChatCrown gives the
  same player's chat lines - 1 silver, 2 and 3 gold, 4 purple, 5 red, 6 and up blue and gold - or a moderator's yell and
  their chat show different ranks, which is exactly what ::yell used to do.
"""
import os
import re
import sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
fails = 0


def check(cond, what):
    global fails
    print(('  ok   ' if cond else '  FAIL ') + what)
    if not cond:
        fails += 1


def read(p):
    return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')


def nocomment(s):
    return '\n'.join(l.split('//', 1)[0] for l in s.split('\n'))


SCRIPTS = []
for root, _, files in os.walk(os.path.join(C, 'scripts')):
    for f in files:
        if f.endswith('.rs2'):
            p = os.path.relpath(os.path.join(root, f), C).replace(os.sep, '/')
            SCRIPTS.append((p, nocomment(read(p))))
BC = nocomment(read('scripts/general/scripts/broadcast.rs2'))

print('one place builds a broadcast')
outside = [p for p, s in SCRIPTS if 'broadcast_mes(' in s and p not in ('scripts/engine.rs2', 'scripts/general/scripts/broadcast.rs2')]
check(not outside, 'broadcast_mes is called only from broadcast.rs2%s' % (': also ' + ', '.join(outside) if outside else ''))
for proc in ('broadcast_name', 'broadcast_news', 'broadcast_drop', 'broadcast_pet', 'broadcast_staff', 'yell'):
    check('[proc,%s]' % proc in BC, '[proc,%s] exists' % proc)
drops = sum(s.count('~broadcast_drop(') for p, s in SCRIPTS)
check(drops >= 12, 'the rare-drop tables call ~broadcast_drop (%d calls)' % drops)

print('every pet announces')
for p, want in (('scripts/npc/scripts/boss_pets.rs2', '~broadcast_pet($pet)'),
                ('scripts/npc/scripts/skill_pets.rs2', '~broadcast_pet($pet)'),
                ('scripts/areas/area_kraken_cove/scripts/kraken_drops.rs2', '~broadcast_pet(bosspet_kraken_item)'),
                ('scripts/minigames/game_fightcave/scripts/fightcave_reward.rs2', '~broadcast_pet(bosspet_tzrek_jad_item)'),
                ('scripts/minigames/game_fightcave/scripts/fightcave_exchange.rs2', '~broadcast_pet(bosspet_tzrek_jad_item)')):
    check(want in nocomment(read(p)), '%s announces its pet' % p.split('/')[-1])
# a skill pet that lands on the floor for a full pack is still a pet
sp = nocomment(read('scripts/npc/scripts/skill_pets.rs2'))
check(sp.count('~broadcast_pet($pet)') == 2, '...skill pets announce whether they go in the pack or on the floor')
check('would have been followed' not in ''.join(s for _, s in SCRIPTS),
      'no pet is announced as one the player "would have" had - by then they have it')

print('the icon sheet')
try:
    from PIL import Image
    im = Image.open(os.path.join(C, 'sprites/mod_icons.png')).convert('RGBA')
    opt = read('sprites/meta/mod_icons.opt').split('\n')[0].strip()
    tw, th = (int(n) for n in opt.split('x'))
    check((tw, th) == (13, 13), 'tiles are 13x13 (%s)' % opt)
    check(im.size == (8 * tw, th), 'eight tiles - two crowns, three XP-mode badges, the developer crown and both owner crowns (%dx%d)' % im.size)
    alpha = sum(1 for y in range(im.height) for x in range(im.width) if im.getpixel((x, y))[3] < 255)
    check(alpha == 0, 'transparency is magenta, not alpha - the packer ignores alpha (%d alpha pixels)' % alpha)
    for t in range(im.width // tw):
        corner = im.getpixel((t * tw, 0))[:3]
        check(corner == (255, 0, 255), '...tile %d has a transparent corner' % t)
except ImportError:
    print('  skip the icon sheet needs Pillow (pip install pillow)')

print('the crown rule')
m = re.search(r'\[proc,broadcast_name\]\(\)\(string\)(.*?)\n\[', BC + '\n[', re.S)
body = m.group(1) if m else ''
rule = re.findall(r'staffmodlevel >= (\d)\) \{\s*\$icons = "(@cr\d@)"', body)
check(rule == [('6', '@cr8@'), ('5', '@cr7@'), ('4', '@cr6@'), ('2', '@cr2@'), ('1', '@cr1@')],
      '6+ blue and gold, 5 red, 4 purple, 2+ gold, 1+ silver - engine ChatCrown\'s rule (%s)' % rule)
badges = dict(re.findall(r'case (\^xprate_\w+|default) : \$icons = append\(\$icons, "(@cr\d@)"\)', body))
check(badges.get('^xprate_10x') == '@cr5@' and badges.get('^xprate_5x') == '@cr4@' and badges.get('default') == '@cr3@',
      '10x, 5x, and Realism for everything else, unset included (%s)' % badges)
check('~xprate_current' in body and '%xp_rate' not in body and 'displayname' in body,
      '...read through ~xprate_current, never %xp_rate itself, around the player\'s own display name')

print(fails == 0 and '\nALL PASS' or '\n%d FAILED' % fails)
raise SystemExit(1 if fails else 0)
