#!/usr/bin/env python3
"""Mutation test for tools/compost_battery.py. Same runner as pouch_mutate.py.

Every entry breaks the bottomless compost bucket in one specific way and expects the battery to go
red with the check that is named. A GREEN line is a hole in the battery.

    python3 tools/compost_mutate.py            # all of them
    python3 tools/compost_mutate.py "doubling" # just the ones whose name contains that
"""
import os, shutil, subprocess, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W = os.path.join(os.environ.get('TMPDIR', '/tmp'), 'compost_mutate_work')

BUCKET = 'scripts/skill_farming/scripts/compost_bucket.rs2'
USEITEM = 'scripts/skill_farming/scripts/farming_useitem.rs2'
OBJ = 'scripts/skill_farming/configs/compost_bucket.obj'
INV = 'scripts/skill_farming/configs/compost_bucket.inv'
CONST = 'scripts/skill_farming/configs/compost_bucket.constant'
SPEC = 'tools/nosourcespec.json'
ALLOBJ = 'scripts/_unpack/377/all.obj'

FARM = 'scripts/skill_farming/scripts/farming_actions.rs2'

MUTS = [
 # ---- 6, where it comes from now that it comes from somewhere
 (FARM, '~compost_bucket_roll($amount);\n', '',
  '6 the roll rides ~farming_xp, the one proc every Farming award already goes through'),
 (FARM, '~compost_bucket_roll($amount);\nstat_advance(farming, calc($amount + $extra));',
        'stat_advance(farming, calc($amount + $extra));\n~compost_bucket_roll(calc($amount + $extra));',
  "6 on the PRE-BONUS amount, so the farmer's outfit does not make its own successor arrive sooner"),
 (BUCKET, 'if (random(^bottomless_roll_xp) >= $xp) {', 'if (random(3000) = 0) {',
  '6 the chance is proportional to what the action was worth, not flat per action'),
 (BUCKET, 'if (stat_base(farming) < ^bottomless_roll_level) {\n    return;\n}\n', '',
  '6 and it is gated on a Farming level rather than open from level 1'),
 (BUCKET, 'if (~obj_gettotal(bottomless_bucket) > 0 | ~obj_gettotal(bottomless_bucket_filled) > 0) {',
          'if (inv_total(inv, bottomless_bucket) > 0) {',
  '6 a player holding either half anywhere - pack, worn or bank - never rolls a second one'),
 (BUCKET, 'obj_add(coord, bottomless_bucket, 1, ^lootdrop_duration);', 'return;',
  '6 and full hands put it on the floor rather than losing it'),
 (SPEC, '"compost_bucket.rs2:proc,compost_bucket_restyle"', '"compost_bucket.rs2"',
  '6 the icon swap is still named as not-a-source, at script grain'), # ---- 7, noted compost and the buckets that do not come back
 (BUCKET, 'inv_add(compost_bucket_store, $want, calc($took * ^compost_bucket_per_bucket));',
          'inv_add(compost_bucket_store, $want, calc($took * ^compost_bucket_per_bucket));\n'
          'inv_add(inv, bucket_empty, $took);',
  '7 the buckets go IN - nothing comes back'),
 (BUCKET, 'return(calc(inv_total(inv, $bucket) + inv_total(inv, $note)));',
          'return(inv_total(inv, $bucket));',
  '7 ...and counts loose buckets and the noted stack together'),
 (BUCKET, 'def_int $loose = min(inv_total(inv, $bucket), $count);', 'def_int $loose = 0;',
  '7 and spending takes the loose ones first'),
 (BUCKET, 'inv_del(inv, $note, $fromnote);', 'inv_del(inv, $bucket, $fromnote);',
  '7 ...by deleting from the noted stack'),
 (BUCKET, 'return(calc($loose + $fromnote));', 'return($count);',
  '7 ...and answers what it really got'),
 (BUCKET, 'def_int $have = ~compost_bucket_held($want);',
          'def_int $have = inv_total(inv, $want);',
  '7 ...and so does how much there is to pour'),
 (BUCKET, '} else if (~compost_bucket_held(bucket_supercompost) > 0) {',
          '} else if (inv_total(inv, bucket_supercompost) > 0) {',
  '7 choosing the tier looks at the noted stack too'),
 (BUCKET, 'if ($obj = oc_cert(bucket_compost) | $obj = oc_cert(bucket_supercompost)) {',
          'if ($obj = bucket_compost | $obj = bucket_supercompost) {',
  '7 a noted bucket used on it fills it, as in OSRS'),
 # The forward certlink. Without it oc_cert answers the base obj, noted compost cannot exist, and
 # nothing above works - so it is the one line the whole group rests on.
 (ALLOBJ, '[cert_bucket_compost]\ncertlink=bucket_compost',
          '[cert_bucket_compost]\ncertlink=bucket_water',
  '7 while cert_bucket_compost is a real note pointing back at it'),
 (ALLOBJ, '[cert_bucket_supercompost]\ncertlink=bucket_supercompost\ncerttemplate=template_for_cert',
          '[cert_bucket_supercompost]\ncertlink=bucket_supercompost',
  '7 while cert_bucket_supercompost is a real note pointing back at it'),
 (ALLOBJ, '[bucket_compost]\nname=Compost',
          '[bucket_compost]\ncertlink=cert_bucket_compost\nname=Compost',
  '7 bucket_compost does not hand-write a forward link - the packer derives it'),
 ('pack/obj.pack', '6033=cert_bucket_compost\n', '',
  '7 ...and is registered in pack/obj.pack, or the packer would never see it'),
 (BUCKET, 'def_int $took = ~compost_bucket_take($want, $buckets);\nif ($took < 1) {',
          'def_int $took = $buckets;\nif ($took < 1) {',
  '7 what is actually stored is what the pack could give up'),

 # 1 - the numbers, and the doubling that is the whole point of the item
 (CONST, '^compost_bucket_per_bucket = 2', '^compost_bucket_per_bucket = 1',
  '1 a bucket poured in is worth two uses'),
 (BUCKET, 'calc($took * ^compost_bucket_per_bucket)', 'calc($took + $took)',
  '1 Fill multiplies buckets into uses rather than storing buckets'),
 (CONST, '^compost_bucket_max = 10000', '^compost_bucket_max = 1000',
  '1 it holds 10,000 uses'),
 (CONST, '^compost_bucket_fill_max = 5000', '^compost_bucket_fill_max = 50',
  '1 and takes 5,000 buckets in one Fill'),
 # Storing the buckets instead of the uses. The item still works, holds the same number of things,
 # and is worth exactly half what it should be - the failure this doubling is for.
 (BUCKET, 'def_int $buckets = min($have, ^compost_bucket_fill_max);',
          'def_int $buckets = $have;',
  '1 ...caps how many buckets one Fill takes'),
 # Capping the buckets at the room in USES rather than in buckets: one bucket short of full then
 # takes a bucket and stores two, over the maximum.
 (BUCKET, '$buckets = min($buckets, calc($room / ^compost_bucket_per_bucket));',
          '$buckets = min($buckets, $room);',
  '1 ...and converts the room left back into buckets'),
 (BUCKET, 'def_int $room = calc(^compost_bucket_max - ~compost_bucket_uses);',
          'def_int $room = ^compost_bucket_max;',
  '1 the room is measured in uses'),

 # 2 - the state is the store's one slot and nothing else
 (INV, 'size=1', 'size=2', '2 the store has one slot'),
 (INV, 'scope=perm', 'scope=temp', '2 and survives a logout'),
 (INV, 'stackall=yes', 'stackall=no', '2 and stacks, so 10,000 uses is one slot'),
 (BUCKET, 'return(inv_getnum(compost_bucket_store, 0));',
          'return(inv_total(compost_bucket_store, ~compost_bucket_tier));',
  '2 and the uses are its count'),
 # A second copy of the same state in a varp is the bug that makes a store item drift out of sync
 # with its own contents.
 (BUCKET, 'def_obj $inside = ~compost_bucket_tier;\n// With something inside',
          'def_obj $inside = %compost_bucket_tier;\n// With something inside',
  '2 so there is no varp for either'),
 (OBJ, 'iop2=Check\n\n// Same item', 'iop2=Check\nparam=compost_tier,bucket_compost\n\n// Same item',
  '2 and no param for what is inside'),
 (BUCKET, 'if ($inside = bucket_supercompost) {\n    $want = bucket_supercompost;\n'
          '} else if ($inside = bucket_compost) {\n    $want = bucket_compost;\n'
          '} else if (~compost_bucket_held(bucket_supercompost) > 0) {',
          'if (~compost_bucket_held(bucket_supercompost) > 0) {',
  '2 Fill looks at what is already inside before it chooses what to pour'),

 # 3 - a use is spent instead of a bucket, and only when the caller says so
 (USEITEM, '[proc,farming_apply_compost](int $patch, namedobj $bucket, int $tier, boolean $bottomless)',
           '[proc,farming_apply_compost](int $patch, namedobj $bucket, int $tier)',
  '3 the farming proc is told where the compost comes from'),
 (USEITEM, 'inv_del(compost_bucket_store, $bucket, 1);', 'inv_del(inv, $bucket, 1);',
  '3 a use out of the store when it is the bottomless one'),
 (USEITEM, '    inv_del(inv, $bucket, 1);\n    inv_add(inv, bucket_empty, 1);',
           '    inv_del(inv, $bucket, 1);',
  '3 ...and a bucket out of the inventory when it is not'),
 # A call site left to a default is how a plain bucket quietly starts spending out of the store.
 (USEITEM, 'case bucket_compost : ~farming_apply_compost($patch, bucket_compost, ^farming_compost_normal, false);',
           'case bucket_compost : ~farming_apply_compost($patch, bucket_compost, ^farming_compost_normal);',
  '3 and every one of them names a source'),
 (USEITEM, 'case bucket_supercompost : ~farming_apply_compost($patch, bucket_supercompost, ^farming_compost_super, false);',
           'case bucket_supercompost : ~farming_apply_compost($patch, bucket_supercompost, ^farming_compost_super, true);',
  '3 the two plain buckets still pass false'),
 (USEITEM, '    case bottomless_bucket_filled : ~compost_bucket_apply($patch);\n', '',
  '3 both bucket items reach the patch through the same proc'),
 (BUCKET, 'if ($inside = null | ~compost_bucket_uses < 1) {', 'if ($inside = null) {',
  '3 an empty bucket does nothing to a patch'),
 (BUCKET, '~farming_apply_compost($patch, bucket_supercompost, ^farming_compost_super, true);',
          '~farming_apply_compost($patch, bucket_supercompost, ^farming_compost_normal, true);',
  '3 and the tier it applies is the one inside'),

 # 4 - the icon
 (BUCKET, 'inv_add(compost_bucket_store, $want, calc($took * ^compost_bucket_per_bucket));\n'
          '~compost_bucket_restyle;\n',
          'inv_add(compost_bucket_store, $want, calc($took * ^compost_bucket_per_bucket));\n',
  '4 ...called after compost_bucket_fill'),
 (BUCKET, '} else if ($have = bottomless_bucket_filled) {\n'
          '    inv_del(inv, bottomless_bucket_filled, 1);\n'
          '    inv_add(inv, bottomless_bucket, 1);\n}', '}',
  '4 and swaps both ways'),
 # An add without its delete: the swap becomes a duplicator, and the bucket really is a source.
 (BUCKET, '        inv_del(inv, bottomless_bucket, 1);\n'
          '        inv_add(inv, bottomless_bucket_filled, 1);',
          '        inv_add(inv, bottomless_bucket_filled, 1);',
  '6 every add in the swap has its delete'),
 (OBJ, 'model=obj_bottomless_bucket_filled', 'model=obj_bottomless_bucket',
  '4 the two items really do draw different models'),
 (OBJ, 'model=obj_bottomless_bucket_filled\n2dzoom=1020',
       'model=obj_bottomless_bucket_filled\nrecol1s=1\nrecol1d=2\n2dzoom=1020',
  '4 and the filled one carries no recolour pair'),

 # 5 - the ops
 (OBJ, 'model=obj_bottomless_bucket\n2dzoom=1020',
       'model=obj_bottomless_bucket\niop5=Destroy\n2dzoom=1020',
  '5 and the empty one has nothing to lose'),
 (BUCKET, '@storage_destroy(bottomless_bucket_filled, compost_bucket_store, "bottomless compost bucket");',
          'inv_del(inv, bottomless_bucket_filled, 1);',
  '5 Destroy reuses the shared helper'),
 (OBJ, 'tradeable=no\niop1=Fill\niop2=Check\niop5=Destroy',
       'iop1=Fill\niop2=Check\niop5=Destroy',
  '5 a full one is untradeable'),
 (OBJ, 'model=obj_bottomless_bucket\n2dzoom',
       'model=obj_bottomless_bucket\ntradeable=no\n2dzoom',
  '5 and an empty one trades, as in OSRS'),

 # 6 - the sourcelessness, and the one exemption that makes it work
 # The point of the whole exemption: an add OUTSIDE the swap is a real source and must be reported
 # even though the file it lives in is named in the spec.
 # A DISAGREEMENT IS THE SPEC AND THE GAME CONTRADICTING EACH OTHER: an obj the spec calls
 # sourceless that something hands out. This used to be made by deleting the bucket's op, back
 # when the spec called the bucket sourceless; the bucket has a source now, so the mistake to
 # simulate is the spec claiming otherwise.
 (BUCKET, '[proc,compost_bucket_tier]()(obj)',
          '[proc,compost_bucket_never_called]\ninv_add(inv, macro_mime_mask, 1);\n\n'
          '[proc,compost_bucket_tier]()(obj)',
  '6 and the sweep does not disagree with the spec'),
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
        open(p, 'w', newline='').write(raw.replace(f, r2, 1))
        r = subprocess.run([sys.executable, os.path.join(W, 'tools', 'compost_battery.py')],
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
        print('  %-5s %-62s %s' % (state, why, note))
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
