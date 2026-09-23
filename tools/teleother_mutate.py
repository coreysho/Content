#!/usr/bin/env python3
"""Mutation test for tools/teleother_battery.py. Same runner as enchant_mutate.py.

Every entry breaks Teleother, its panel, or the Accept aid setting it reads, in one specific way,
and expects the battery to go red with the check that is named. A GREEN line is a hole.

Anchors are counted for uniqueness by the runner before they are used, because replace(..., 1)
takes the FIRST match and this round edits three near-identical dbrows, two near-identical options
tabs and a panel with 116 blocks in it. The Barrows round shipped a check that could not tell two
identical calls apart for exactly this reason.

    python3 tools/teleother_mutate.py
    python3 tools/teleother_mutate.py "Accept aid"   # just the ones whose name contains that
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'teleother_mutate_work')

DBROW = 'scripts/skill_magic/configs/magic_spells.dbrow'
MAGICIF = 'scripts/skill_magic/interfaces/magic.if'
PANEL = 'scripts/skill_magic/interfaces/teleother.if'
RS2 = 'scripts/skill_magic/scripts/spells/teleother.rs2'
VARP = 'scripts/skill_magic/configs/teleother.varp'
TOCONST = 'scripts/skill_magic/configs/teleother.constant'
AIDCONST = 'scripts/interface_options/configs/game_options.constant'
OPTRS = 'scripts/interface_options/scripts/game_options.rs2'
OPTLDRS = 'scripts/interface_options/scripts/game_options_ld.rs2'
OPTIF = 'scripts/interface_options/interfaces/options.if'
OPTLDIF = 'scripts/interface_options/interfaces/options_ld.if'
IFPACK = 'pack/interface.pack'
VARPPACK = 'pack/varp.pack'
SPEC = 'tools/unwiredspells.json'
ADOPT = 'tools/adoptspec.json'

MUTS = [
 # ---- 1, the numbers, with the cache's own button as the second opinion
 (DBROW, 'data=spell,^teleother_lumbridge\ndata=spellcom,magic:teleother_lumbridge\n'
         'data=members,true\ndata=levelrequired,74',
         'data=spell,^teleother_lumbridge\ndata=spellcom,magic:teleother_lumbridge\n'
         'data=members,true\ndata=levelrequired,75',
  "1 Lumbridge: the row's level requirement is the button's own threshold plus one"),
 (MAGICIF, 'script4=gt,73', 'script4=gt,74',
  "1 Lumbridge: the row's level requirement is the button's own threshold plus one"),
 (DBROW, 'data=runesrequired,earthrune,1,soulrune,1,lawrune,1',
         'data=runesrequired,earthrune,1,soulrune,1,lawrune,2',
  '1 Lumbridge: the row costs exactly the runes the button counts'),
 (MAGICIF, 'script4=gt,81', 'script4=gt,82',
  "1 Falador: the row's level requirement is the button's own threshold plus one"),
 (DBROW, 'data=runesrequired,waterrune,1,soulrune,1,lawrune,1',
         'data=runesrequired,waterrune,2,soulrune,1,lawrune,1',
  '1 Falador: the row costs exactly the runes the button counts'),
 (DBROW, 'data=levelrequired,90\ndata=runesrequired,soulrune,2,lawrune,1,null,null',
         'data=levelrequired,91\ndata=runesrequired,soulrune,2,lawrune,1,null,null',
  "1 Camelot: the row's level requirement is the button's own threshold plus one"),
 (DBROW, 'data=runesrequired,soulrune,2,lawrune,1,null,null',
         'data=runesrequired,soulrune,1,lawrune,1,null,null',
  '1 Camelot: the row costs exactly the runes the button counts'),
 (MAGICIF, 'script1=gt,1\nscript2=gt,0\nscript3=gt,89',
           'script1=gt,0\nscript2=gt,0\nscript3=gt,89',
  '1 Camelot: the row costs exactly the runes the button counts'),
 (DBROW, '[magic_spell_teleother_camelot]', '[magic_spell_teleother_camelot_disabled]',
  '1 Camelot: the row and the button both exist'),

 # ---- 2, the destination and the word the panel shows
 (DBROW, 'data=experience,840\ndata=tele_coord,0_50_50_21_18',
         'data=experience,840\ndata=tele_coord,0_50_50_21_19',
  '2 Lumbridge: Teleother lands exactly where the plain teleport to that town lands'),
 (DBROW, 'data=experience,1000\ndata=tele_coord,0_43_54_5_22',
         'data=experience,1000\ndata=tele_coord,0_41_51_37_37',
  '2 Camelot: Teleother lands exactly where the plain teleport to that town lands'),
 (MAGICIF, 'action=Teleother Falador', 'action=Teleother Port Sarim',
  "2 Falador: the panel's word is the tail of the button's own action text"),
 (RS2, '@teleother_cast(^teleother_camelot, "Camelot");\n[applayert',
       '@teleother_cast(^teleother_camelot, "Camelot!");\n[applayert',
  '2 Camelot: and BOTH of its triggers pass that literal'),
 (DBROW, 'data=spellcom,magic:teleother_falador\ndata=members,true\n'
         'data=levelrequired,82\ndata=runesrequired,waterrune,1,soulrune,1,lawrune,1\n'
         'data=experience,920\n',
         'data=spellcom,magic:teleother_falador\ndata=members,true\n'
         'data=levelrequired,82\ndata=runesrequired,waterrune,1,soulrune,1,lawrune,1\n',
  '2 Falador: the row carries an experience value'),

 # ---- 3, the panel is Jagex's screen
 (PANEL, 'text=...wants to teleport you to...', 'text=is teleporting you to',
  "3 the cache's own 'text=...wants to teleport you to...' survived the rename"),
 (PANEL, 'text=Do you accept?', 'text=Accept this?',
  "3 the cache's own 'text=Do you accept?' survived the rename"),
 (PANEL, 'option=Decline', 'option=No thanks',
  "3 the cache's own 'option=Decline' survived the rename"),
 (PANEL, '[caster]', '[com_89]', '3 [caster] is the block that used to hold \'%1\''),
 (PANEL, '[accept]\nlayer=com_95', '[accept]\nlayer=com_96',
  '3 both buttons still sit in the layers the cache put them in'),
 (PANEL, '// GENERATED by tools/genadopt.py', '// hand-renamed, sorry',
  '3 the panel is genadopt output and says what it was - the adoption is a rerunnable tool, '
  'not a hand rename, and the cache file moved rather than being copied'),
 (ADOPT, '"name": "destination"', '"name": "dest"',
  '3 four rules, one match each, so a panel that is not this one fails the count rather than '
  'renaming the wrong components'),
 (ADOPT, '"dst": "scripts/skill_magic/interfaces/teleother.if"',
         '"dst": "scripts/interfaces/teleother.if"',
  '3 and tools/adoptspec.json is where the rename lives, beside the six panels the windows '
  'round adopted - one tool, not two ways of doing this'),
 (ADOPT, '"field": "text",\n          "pattern": "^%1$"',
         '"field": "name",\n          "pattern": "^%1$"',
  "3 ...and every rule joins on the panel's OWN text rather than a com_<n> somebody typed"),

 # ---- 4, the ids
 (IFPACK, '=teleother:accept', '=teleother:accept_button',
  '4 every component in the .if has a pack id and nothing else does'),
 (IFPACK, '=magic:teleother_camelot', '=magic:com_541',
  '4 magic:teleother_camelot took the id its com_5NN name had'),
 (PANEL, '[destination]\ntype=text\nx=164\ny=168', '[destination]\ntype=text\nx=164\ny=68',
  '4 the caster slot really is above the "...wants to teleport you to..." line and the '
  'destination below it, which is the only thing that tells %1 from %2'),

 # ---- 5, no dead clicks
 (RS2, '[opnpct,magic:teleother_falador] @teleother_on_npc;\n', '',
  '5 Falador: [opnpct] is handled too - the button offers "Cast on" over every npc in the game'),
 (RS2, '[applayert,magic:teleother_lumbridge] @teleother_cast(^teleother_lumbridge, '
       '"Lumbridge");\n', '',
  '5 Lumbridge: [applayert] is handled'),
 (RS2, 'mes("You can only cast this spell on other players.");',
       'mes("Nothing interesting happens.");',
  '5 ...and casting one at an npc says so rather than doing nothing'),
 (MAGICIF, 'actiontarget=npc,player\naction=Teleother Lumbridge',
           'actiontarget=player\naction=Teleother Lumbridge',
  '5 Lumbridge: the button is a target button aimed at npcs AND players'),

 # ---- 6, the cast pays last
 (RS2, 'if (.%option_aid = ^aid_no) {\n    mes("<.displayname> is not accepting aid.");\n'
       '    return;\n}\n', '',
  '6 Accept aid is checked before the runes are taken'),
 (RS2, 'if (.busy = true) {\n    mes("<.displayname> is busy at the moment.");\n'
       '    return;\n}\n', '',
  '6 the target being busy is checked before the runes are taken'),
 (RS2, 'if (.%teleother_expires > map_clock) {\n'
       '    mes("<.displayname> already has a teleport offer to answer.");\n    return;\n}\n',
       '',
  '6 an offer already standing is checked before the runes are taken'),
 (RS2, '~delete_spell_runes($spell_data);\n~give_spell_xp($spell_data);\np_stopaction;',
       'p_stopaction;',
  '6 and the cost is paid before the panel opens - Corey\'s call: on cast, win or lose'),
 (RS2, 'if (.uid = uid) {', 'if (.uid = null) {', '6 you cannot cast it on yourself'),
 (RS2, 'if (~wilderness_level(.coord) > 20 | ~wilderness_level(coord) > 20) {',
       'if (~wilderness_level(coord) > 20) {',
  "6 the wilderness rule is asked of the TARGET's coord and the caster's, not just one of them"),
 (RS2, '.clearsofttimer(teleother_expire);\n.softtimer(teleother_expire',
       '.softtimer(teleother_expire',
  '6 and the timer is cleared before it is armed, so a second offer cannot leave two running'),
 (TOCONST, '^teleother_offer_ticks = 17', '^teleother_offer_ticks = 170',
  '6 the timeout is 17 ticks - 10.2 seconds - and lives in one constant, not in two places'),
 (RS2, '.%teleother_expires = add(map_clock, ^teleother_offer_ticks);', '',
  '6 the offer is stamped on the target, expiry included'),

 # ---- 7, the answer, and the order that stops the close eating the accept
 (RS2, '~teleother_answer_caster("<displayname> accepts your teleport offer.");\n'
       '~teleother_clear;\nif_close;',
       'if_close;\n~teleother_answer_caster("<displayname> accepts your teleport offer.");\n'
       '~teleother_clear;',
  '7 ACCEPT reads the offer, then clears it, then closes - in that order, or [if_close] wipes '
  'the offer out from under the accept still reading it'),
 (RS2, 'if (%teleother_expires <= map_clock) {\n    if_close;\n'
       '    mes("That teleport offer has expired.");\n    return;\n}\n', '',
  '7 ...and it checks expiry itself rather than trusting the timer to have fired'),
 (RS2, 'if (p_finduid(uid) = true) {', 'if (true = true) {',
  '7 and it re-acquires p_active_player before any protected op - an if_button is not handed '
  'one, which the XP lock round paid two deploys to learn'),
 (RS2, '    if (~pre_tele_checks(coord) = false) {\n        return;\n    }\n', '',
  '7 the destination checks are re-run at accept, ten seconds after the cast'),
 (RS2, '[if_button,teleother:decline]\nif_close;',
       '[if_button,teleother:decline]\nif_close;\n~teleother_clear;',
  '7 DECLINE is nothing but a close, so the X, the Decline button and being attacked are one '
  'path rather than three'),
 (RS2, '~teleother_answer_caster("<displayname> declines your teleport offer.");', '',
  '7 CLOSE is the decline, and it says nothing when the offer has already been answered'),
 (RS2, 'if (%teleother_expires > map_clock) {\n    // Somebody offered again',
       'if (%teleother_expires > 0) {\n    // Somebody offered again',
  '7 the TIMER refuses to fire on an offer that has been re-armed underneath it'),
 (RS2, 'clearsofttimer(teleother_expire);\n\n// Say something', '\n// Say something',
  '7 one clear, and it clears the timer as well as the three varps'),
 (RS2, '~teleother_answer_caster("<displayname> accepts your teleport offer.");',
       '',
  '7 ...and the caster is told before the uid it is read from is nulled'),

 # ---- 8, the varps
 (VARP, '[teleother_expires]\ntype=int\nprotect=no',
        '[teleother_expires]\ntype=int',
  '8 teleother_expires is protect=no - the caster writes it through the secondary pointer from '
  'inside [opplayert]'),
 (VARP, '[teleother_caster]\ntype=player_uid', '[teleother_caster]\ntype=int',
  '8 the caster is a player_uid, not an int, so ~finduid can get back to them'),
 (VARP, '[teleother_spell]\ntype=int\nprotect=no',
        '[teleother_spell]\ntype=int\nprotect=no\nscope=perm',
  '8 teleother_spell is temp, so a pending offer cannot survive a logout'),
 (VARPPACK, '=teleother_caster', '=teleother_caster_uid',
  '8 teleother_caster is in varp.pack'),

 # ---- 9, Accept aid
 (AIDCONST, '^aid_no = 2', '^aid_no = 0', '9 the tri-state is 0 unset / 1 yes / 2 no'),
 (OPTRS, '%option_aid = ^aid_yes;', '%option_pm = 1;',
  "9 options:accept_aid sets %option_aid both ways - the 377 tab's Yes/No pair once set %option_pm, "
  'which belongs to Split Private-chat, so Accept Aid silently moved your private chat setting'),
 (OPTLDRS, '%option_aid = ^aid_no;', '%option_aid = 0;',
  '9 the low-detail tab - which had it right all along - uses the same constants'),
 (OPTIF, 'script1op1=pushvar,option_aid\nscript1=lt,2',
         'script1op1=pushvar,option_aid\nscript1=eq,1',
  '9 options: Yes lights below 2, so an account that has never opened this tab shows Yes - '
  'a varp has no default and 0 is what every existing save holds'),
 (OPTLDIF, 'script1op1=pushvar,option_aid\nscript1=eq,2',
           'script1op1=pushvar,option_aid\nscript1=eq,0',
  '9 options_ld: No lights on 2'),
 (RS2, '.%option_aid = ^aid_no', '.%teleother_spell = ^aid_no',
  '9 and Teleother is the first thing in the build that reads the setting at all'),

 # ---- 10, the rule and the art
 (SPEC, '"magic:com_531"', '"magic:com_511"',
  '10 Tele Block stays: it needs a mechanism, not a panel'),
 (RS2, 'anim(human_teleport_other_impact, 0);', 'anim(human_castteleport, 0);',
  '10 human_teleport_other_impact is in seq.pack and the script uses it'),
 (RS2, 'spotanim_pl(teleport_other_casting, 92, 0);', 'spotanim_pl(teleport_casting, 92, 0);',
  '10 teleport_other_casting is in spotanim.pack and the script uses it'),

 # ---- 11, the idioms
 (RS2, '[proc,teleother_answer_caster](string $message)',
       '[proc,teleother_answer_caster](string $message)(string)',
  '11 none of the four idioms with no precedent in this repo'),
]


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
            print('  SKIP (pattern not found) %-34s %s' % (os.path.basename(path), why))
            fails += 1
            continue
        if raw.count(f) != 1:
            print('  SKIP (pattern is not unique - %d hits) %-20s %s'
                  % (raw.count(f), os.path.basename(path), why))
            fails += 1
            continue
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'teleother_battery.py')],
                           capture_output=True, text=True, cwd=W)
        open(p, 'wb').write(original)
        ok = r.returncode != 0
        named = why.split(' ', 1)[1] if why[:1].isdigit() else why
        fired = [l.strip()[5:].strip() for l in r.stdout.split('\n') if l.strip().startswith('FAIL')]
        onpoint = any(named in x for x in fired)
        if not ok:
            state, note = 'GREEN', 'NOT CAUGHT'; fails += 1
        elif onpoint:
            state, note = 'red', 'caught by its own check'
        else:
            state, note = 'red', 'caught, but by: %s' % (fired[0][:52] if fired else 'a non-zero exit')
            loose += 1
        print('  %-5s %-64s %s' % (state, why, note))
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
