"""Battery for the bottomless compost bucket.

The item is worth having because a bucket of compost poured in is worth TWO uses, so most of what
is checked here is that doubling, the cap, and the one-type-at-a-time rule that falls out of the
store having a single slot. The rest is the farming side: that a use is spent instead of a bucket,
and that a plain bucket still behaves exactly as it did.

    python3 tools/compost_battery.py
"""
import os, re, sys

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def read(p): return open(os.path.join(C, p), newline='').read().replace('\r\n', '\n')

fails = 0
def check(ok, what):
    global fails
    print(('  ok   ' if ok else '  FAIL ') + what)
    if not ok: fails += 1

def code(txt): return '\n'.join(l.split('//')[0] for l in txt.split('\n'))

BUCKET = read('scripts/skill_farming/scripts/compost_bucket.rs2')
USEITEM = read('scripts/skill_farming/scripts/farming_useitem.rs2')
OBJ = read('scripts/skill_farming/configs/compost_bucket.obj')
INV = read('scripts/skill_farming/configs/compost_bucket.inv')
CONST = read('scripts/skill_farming/configs/compost_bucket.constant')
FCONST = read('scripts/skill_farming/configs/farming.constant')
ALLOBJ = read('scripts/_unpack/377/all.obj')
STORAGE = read('scripts/storage_items/scripts/storage_items.rs2')

def const(txt, n):
    m = re.search(r'\^' + n + r'\s*=\s*(\d+)', txt)
    return int(m.group(1)) if m else None
def block(txt, n):
    return txt.split('[' + n + ']', 1)[1].split('\n[', 1)[0] if '[' + n + ']' in txt else ''
def objblock(n):
    return dict(l.split('=', 1) for l in block(OBJ, n).split('\n')
                if '=' in l and not l.startswith('//'))

# ============================================================================ 1
print('1. the numbers are OSRS\'s, and the doubling is the point')
check(const(CONST, 'compost_bucket_per_bucket') == 2,
      'a bucket poured in is worth two uses, which is why the item is worth having')
check(const(CONST, 'compost_bucket_max') == 10000, 'it holds 10,000 uses')
check(const(CONST, 'compost_bucket_fill_max') == 5000, 'and takes 5,000 buckets in one Fill')
fill = code(block(BUCKET, 'proc,compost_bucket_fill'))
check('$took * ^compost_bucket_per_bucket' in fill,
      'Fill multiplies buckets into uses rather than storing buckets')
check('min($have, ^compost_bucket_fill_max)' in fill, '...caps how many buckets one Fill takes')
check('$room / ^compost_bucket_per_bucket' in fill,
      '...and converts the room left back into buckets, so it cannot overfill')
check('^compost_bucket_max - ~compost_bucket_uses' in fill, 'the room is measured in uses')
# THE ONE DEPARTURE FROM OSRS, and it is deliberate: OSRS hands the empty buckets back in the same
# noted or unnoted form they went in as. Here the buckets go in with the compost. Five thousand
# empty buckets are not a reward, and the whole point of the item is not to handle buckets.
check('bucket_empty' not in fill,
      'the buckets go IN - nothing comes back, which is the one place this differs from OSRS')
check('bucket_empty' not in BUCKET,
      '...and nowhere else in the file hands one back either')
check('$took = ~compost_bucket_take($want, $buckets)' in fill,
      'what is actually stored is what the pack could give up, not what was asked for')
check('if ($took < 1) {' in fill, '...and nothing is stored when it could give up none')

# ============================================================================ 2
print('2. the state is the store\'s one slot: the obj is the tier, the count is the uses')
iv = block(INV, 'compost_bucket_store')
check('size=1' in iv, 'the store has one slot')
check('scope=perm' in iv, 'and survives a logout')
check('stackall=yes' in iv, 'and stacks, so 10,000 uses is one slot')
check('[proc,compost_bucket_tier]' in BUCKET and 'inv_getobj(compost_bucket_store, 0)' in BUCKET,
      'the tier is read off the slot')
check('[proc,compost_bucket_uses]' in BUCKET and 'inv_getnum(compost_bucket_store, 0)' in BUCKET,
      'and the uses are its count')
check(not re.search(r'%compost_bucket', BUCKET),
      'so there is no varp for either: %s' % (re.findall(r'%compost\w+', BUCKET) or 'none'))
check('param=compost' not in OBJ, 'and no param for what is inside')
# one type at a time is a consequence of one slot, but Fill must still refuse the other kind
check('$inside = bucket_supercompost' in fill and '$inside = bucket_compost' in fill,
      'Fill looks at what is already inside before it chooses what to pour')

# ============================================================================ 3
print('3. a use is spent instead of a bucket, and only when the caller says so')
check('[proc,farming_apply_compost](int $patch, namedobj $bucket, int $tier, boolean $bottomless)'
      in USEITEM, 'the farming proc is told where the compost comes from')
ap = code(block(USEITEM, 'proc,farming_apply_compost'))
check('if ($bottomless = true) {' in ap and 'inv_del(compost_bucket_store, $bucket, 1);' in ap,
      'a use out of the store when it is the bottomless one...')
check('inv_del(inv, $bucket, 1);' in ap and 'inv_add(inv, bucket_empty, 1);' in ap,
      '...and a bucket out of the inventory when it is not')
calls = re.findall(r'~farming_apply_compost\(([^)]*)\)', code(USEITEM) + code(BUCKET))
check(len(calls) == 4, 'there are four call sites: %d' % len(calls))
check(all(c.strip().endswith(('true', 'false')) for c in calls),
      'and every one of them names a source rather than leaving it to a default')
plain = [c for c in calls if c.strip().endswith('false')]
check(len(plain) == 2 and all('bucket_' in c for c in plain),
      'the two plain buckets still pass false, so nothing changed for them')
check('case bottomless_bucket : ~compost_bucket_apply($patch);' in USEITEM
      and 'case bottomless_bucket_filled : ~compost_bucket_apply($patch);' in USEITEM,
      'both bucket items reach the patch through the same proc')
apply = code(block(BUCKET, 'proc,compost_bucket_apply'))
check('~compost_bucket_uses < 1' in apply, 'an empty bucket does nothing to a patch')
check('bucket_supercompost, ^farming_compost_super' in apply
      and 'bucket_compost, ^farming_compost_normal' in apply,
      'and the tier it applies is the one inside, at the farming constants')
check('inv_getobj' not in apply.split('~farming_apply_compost')[0].split('$inside')[-1]
      or 'bucket_supercompost,' in apply,
      'the namedobj is passed as a literal - inv_getobj answers an obj, which would not compile')

# ============================================================================ 4
print('4. the icon follows the contents')
check('[proc,compost_bucket_restyle]' in BUCKET, 'there is one proc that fixes the icon')
re_ = code(block(BUCKET, 'proc,compost_bucket_restyle'))
check('~compost_bucket_uses > 0' in re_, 'it swaps on whether anything is inside')
check('inv_add(inv, bottomless_bucket_filled, 1);' in re_
      and 'inv_add(inv, bottomless_bucket, 1);' in re_, 'and swaps both ways')
for where in ('proc,compost_bucket_fill', 'proc,compost_bucket_apply'):
    check('~compost_bucket_restyle' in code(block(BUCKET, where)),
          '...called after %s, which can change them' % where.split(',')[1])
check(objblock('bottomless_bucket')['model'] != objblock('bottomless_bucket_filled')['model'],
      'the two items really do draw different models')
check('recol' not in ''.join(objblock('bottomless_bucket_filled').keys()),
      'and the filled one carries no recolour pair, the one that matched no face being dropped')

# ============================================================================ 5
print('5. Fill and Check on both, Destroy only where there is something to lose')
for item in ('bottomless_bucket', 'bottomless_bucket_filled'):
    b = objblock(item)
    check(b.get('iop1') == 'Fill' and '[opheld1,%s]' % item in BUCKET, '%s fills' % item)
    check(b.get('iop2') == 'Check' and '[opheld2,%s]' % item in BUCKET, '...and checks')
    check('[opheldu,%s]' % item in BUCKET, '...and takes a bucket of compost used on it')
check(objblock('bottomless_bucket_filled').get('iop5') == 'Destroy',
      'the filled one can be destroyed')
check('iop5' not in objblock('bottomless_bucket'),
      'and the empty one has nothing to lose, so it keeps the ordinary Drop')
check('@storage_destroy(bottomless_bucket_filled, compost_bucket_store' in BUCKET,
      'Destroy reuses the shared helper, which already warns first')
check('[label,storage_destroy]' in STORAGE, '...which still exists')
check(objblock('bottomless_bucket_filled').get('tradeable') == 'no',
      'a full one is untradeable, since the compost cannot be got back out')
check('tradeable' not in objblock('bottomless_bucket'),
      'and an empty one trades, as in OSRS')

# ============================================================================ 6
print('6. it is not obtainable yet, and that is recorded rather than forgotten')
import json, subprocess
spec = json.loads(read('tools/nosourcespec.json'))['objs']
check('bottomless_bucket' in spec, 'the bucket is declared sourceless in tools/nosourcespec.json')
entry = spec.get('bottomless_bucket', {})
check('bottomless_bucket_filled' in entry.get('also', []), '...and so is its filled half')
check('Hespori' in entry.get('osrs_source', ''), '...with what OSRS uses written down')
ign = entry.get('ignore', [])
check(ign == ['compost_bucket.rs2:proc,compost_bucket_restyle'],
      'the only add excused is the icon swap, named by its script: %s' % ign)
check(all(':' in i for i in ign),
      'the exemption is script-grained, not a whole file - a real source added to '
      'compost_bucket.rs2 later must still be caught')

r = subprocess.run([sys.executable, os.path.join(C, 'tools/obtainable.py')],
                   capture_output=True, text=True, cwd=C)
check(r.returncode == 0, 'tools/obtainable.py runs clean')
bydesign = r.stdout.split('BUILT WITH NO SOURCE ON PURPOSE', 1)[-1] \
                   .split('NOTHING ANYWHERE MENTIONS', 1)[0]
check('bottomless_bucket ' in bydesign and 'bottomless_bucket_filled ' in bydesign,
      'the sweep lists both halves as unobtainable by design - OSRS drops it from the Hespori, '
      'which this server has no content for, and no source has been invented')
check('WARNING' not in r.stdout,
      'and it does not disagree with the spec: %s'
      % ('; '.join(l.strip() for l in r.stdout.split(chr(10)) if 'WARNING' in l) or 'no warnings'))

# The icon swap is only allowed to stop counting because it IS a swap. If either half of it were
# an add without the matching delete, the item would be duplicable - so check the pairing here
# rather than trusting the exemption.
re2 = code(block(BUCKET, 'proc,compost_bucket_restyle'))
check(re2.count('inv_add(inv, bottomless_bucket') == re2.count('inv_del(inv, bottomless_bucket'),
      'every add in the swap has its delete, so nothing is created out of nothing')

# ============================================================================ 7
print('7. noted compost, which is the only way the capacity is reachable')
# 10,000 uses is 5,000 buckets and a pack holds 28. Without notes the cap is decoration.
held = code(block(BUCKET, 'proc,compost_bucket_held'))
check('oc_cert($bucket)' in held, 'the count asks for the obj\'s noted form')
check('inv_total(inv, $bucket) + inv_total(inv, $note)' in held,
      '...and counts loose buckets and the noted stack together')
check('if ($note = $bucket) {' in held,
      '...falling back to loose only when the obj has no note, which is what oc_cert answers then')
take = code(block(BUCKET, 'proc,compost_bucket_take'))
check('min(inv_total(inv, $bucket), $count)' in take, 'and spending takes the loose ones first')
check('$rest = calc($count - $loose)' in take, '...then the remainder out of the notes')
check('inv_del(inv, $note, $fromnote);' in take, '...by deleting from the noted stack')
check('return(calc($loose + $fromnote));' in take, '...and answers what it really got')
check('~compost_bucket_held(bucket_supercompost) > 0' in fill
      and '~compost_bucket_held(bucket_compost) > 0' in fill,
      'choosing the tier looks at the noted stack too, so a noted-only pack still fills')
check('def_int $have = ~compost_bucket_held($want);' in fill,
      '...and so does how much there is to pour')
isc = code(block(BUCKET, 'proc,compost_bucket_is_compost'))
check('oc_cert(bucket_compost)' in isc and 'oc_cert(bucket_supercompost)' in isc,
      'a noted bucket used on it fills it, as in OSRS')
check(BUCKET.count('~compost_bucket_is_compost(last_useitem) = true') == 2,
      '...on both the empty and the filled item: %d'
      % BUCKET.count('~compost_bucket_is_compost(last_useitem) = true'))

# The forward link is the part that was missing from the whole cache: oc_cert and
# inv_moveitem_cert both read certlink off the BASE obj (certtemplate == -1 && certlink >= 0), and
# not one obj in this 377 cache carried it - only the notes carried the backward link. So noted
# compost could not exist at all, and neither could a noted anything.
for base in ('bucket_compost', 'bucket_supercompost'):
    blk = block(ALLOBJ, base)
    check('certlink=cert_%s' % base in blk,
          '%s names its note, which is what makes oc_cert answer' % base)
    check('certtemplate' not in blk,
          '...and is not itself a note, which is the other half of the engine\'s test')
    note = block(ALLOBJ, 'cert_' + base)
    check('certlink=%s' % base in note and 'certtemplate=template_for_cert' in note,
          '...and its note still points back at it')

print()
print('ALL PASS' if fails == 0 else '%d FAILED' % fails)
sys.exit(1 if fails else 0)
