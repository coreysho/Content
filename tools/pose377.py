#!/usr/bin/env python3
"""Pose a 377 mesh with a 377 animation set, and render the frames.

THE HALF THAT WAS MISSING. tools/models/posepreview.py (on the laptop, beside the OSRS importers)
poses an OSRS mesh with an OSRS animation - it answers "which OSRS seq is the attack". It cannot
answer the question that matters after a conversion: does the converted animation look right on
the mesh THIS server will animate? Those are different questions whenever the mesh and the
animation come from different caches, which is exactly what an import is.

And they really can differ. OSRS's player skeleton (framemap 0) has 245 transform groups where
377's has 117, and over the 117 they share, the transform TYPES all match but the vertex-label
lists differ in 63 of them. So "the same animation" arriving on the OSRS skeleton is not
self-evidently safe on a 377-labelled mesh, and the client's own guard
(Model.java: "if (!sameSkeleton(...))") only stops the walk-MERGE, not the animation itself.

This reads what the build reads: a .anim set out of models/, which carries both the frames and
the base they play on. No cache, no importer, no laptop.

    python3 tools/pose377.py models/anim_osrs_11654.anim models/npc/npc_2028.ob2 \
        --out /tmp/karil.png --cols 8
    python3 tools/pose377.py models/anim_553.anim models/npc/npc_2028.ob2 --frames 15825,15828 \
        --out /tmp/before.png

Transform semantics are posepreview's, which are the client's: 0 sets the pivot from the listed
vertex groups' centroid plus the frame's delta, 1 translates, 2 rotates about the pivot, 3 scales
about it in 128ths, 5 is alpha (drawn as-is - a preview has no blending). Two traps posepreview
recorded the hard way and this inherits: a scale axis the frame does not mention is 128 and not 0,
and the vertex label byte IS the transform group index (no minus-one; label 0 is a real group).
"""
import argparse, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image
import ob2render

SINE = [int(32768.0 * np.sin(i * 0.0030679615)) for i in range(2048)]
COSINE = [int(32768.0 * np.cos(i * 0.0030679615)) for i in range(2048)]


def parse_377_anim(blob):
    """AnimFrame.method262: the frames in a set, and the base they share.

    -> ([(frameId, groupCount, flags, values, bakedDelay)], baseBlob)

    The baked delay is the fifth field and is the RS2 way of timing an animation: a seq whose
    delay for a frame is 0 falls back to the frame's own, and only then to 1 tick. That is why a
    377 seq can carry no delay lines at all and still play at the right speed.
    """
    n = len(blob)
    g2 = lambda o: (blob[o] << 8) | blob[o + 1]
    head_len, t1, t2, dl = g2(n - 8), g2(n - 6), g2(n - 4), g2(n - 2)
    hp = 0
    pos = head_len + 2
    t1p = pos; pos += t1
    t2p = pos; pos += t2
    dp = pos; pos += dl
    bp = pos
    total = g2(hp); hp += 2
    out = []
    for _ in range(total):
        fid = g2(hp); hp += 2
        cnt = blob[hp]; hp += 1
        flags = blob[t1p:t1p + cnt]; t1p += cnt
        vs = t2p
        for f in flags:
            for bit in (1, 2, 4):
                if f & bit:
                    t2p += 1 if blob[t2p] < 128 else 2
        out.append((fid, cnt, bytes(flags), bytes(blob[vs:t2p]), blob[dp]))
        dp += 1
    return out, blob[bp:n - 8]


def parse_377_base(b):
    """The inverse of animconv474.emit_377_base: size, types[size], then (count, labels...) per
    group. NOT the 474/OSRS framemap layout, which keeps all the counts in one block - reading a
    377 base with that parser walks off the end, which is how this function came to exist."""
    p = 0
    size = b[p]; p += 1
    types = list(b[p:p + size]); p += size
    counts, labels = [], []
    for _ in range(size):
        c = b[p]; p += 1
        counts.append(c)
        labels.append(list(b[p:p + c])); p += c
    if p != len(b):
        raise SystemExit('base walk %d != %d' % (p, len(b)))
    return size, types, counts, labels


def vertex_labels(b):
    """The per-vertex label byte, which ob2render skips because a still does not need it."""
    n = len(b)
    h = ob2render.P(b, n - 18)
    vcount = h.g2(); fcount = h.g2(); h.g1()
    f_tex, f_pri, f_alpha, f_flabel, f_vlabel = h.g1(), h.g1(), h.g1(), h.g1(), h.g1()
    if f_vlabel != 1:
        return None, vcount
    o = vcount + fcount
    if f_pri == 255: o += fcount
    if f_flabel == 1: o += fcount
    if f_tex == 1: o += fcount
    return list(b[o:o + vcount]), vcount


def groups_of(labels):
    out = {}
    for v, l in enumerate(labels or []):
        out.setdefault(l, []).append(v)
    return {g: np.array(v, np.int64) for g, v in out.items()}


def apply_frame(m, groups, base, flags, vals):
    size, types, counts, glabels = base
    ox = oy = oz = 0
    p = 0

    def nxt():
        nonlocal p
        v = vals[p]
        if v < 128:
            p += 1
            return v - 64
        v = ((vals[p] << 8) | vals[p + 1]) & 0x7FFF
        p += 2
        return v - 16384

    def pivot(i, dx, dy, dz):
        nonlocal ox, oy, oz
        hit = [g for g in glabels[i] if g in groups]
        idx = np.concatenate([groups[g] for g in hit]) if hit else None
        if idx is not None and len(idx):
            ox = int(m.vx[idx].mean()) + dx
            oy = int(m.vy[idx].mean()) + dy
            oz = int(m.vz[idx].mean()) + dz
        else:
            ox, oy, oz = dx, dy, dz

    last = -1
    for i, f in enumerate(flags):
        if f == 0:
            continue
        if i >= size:
            raise SystemExit('frame addresses group %d, base has %d' % (i, size))
        t = types[i]
        # THE IMPLIED PIVOT (AnimFrame.unpack): a transform with no pivot of its own since the last
        # one the frame wrote gets the nearest earlier pivot group, at a zero offset. A frame may leave
        # every pivot out - OSRS's Toktz-xil-ul throw and Tzhaar-ket-om swing do - and without this
        # each rotation turned about the feet: arms three times their length, the head on a pole.
        if t != 0:
            for g in range(i - 1, last, -1):
                if types[g] == 0:
                    pivot(g, 0, 0, 0)
                    break
        last = i
        dflt = 128 if t == 3 else 0
        dx = nxt() if f & 1 else dflt
        dy = nxt() if f & 2 else dflt
        dz = nxt() if f & 4 else dflt
        hit = [g for g in glabels[i] if g in groups]
        idx = np.concatenate([groups[g] for g in hit]) if hit else None
        if t == 0:
            pivot(i, dx, dy, dz)
        elif idx is None or not len(idx):
            continue
        elif t == 1:
            m.vx[idx] += dx; m.vy[idx] += dy; m.vz[idx] += dz
        elif t == 2:
            x = m.vx[idx] - ox; y = m.vy[idx] - oy; z = m.vz[idx] - oz
            if dz:
                s, c = SINE[(dz & 0xff) * 8], COSINE[(dz & 0xff) * 8]
                x, y = (y * s + x * c) >> 15, (y * c - x * s) >> 15
            if dx:
                s, c = SINE[(dx & 0xff) * 8], COSINE[(dx & 0xff) * 8]
                y, z = (y * c - z * s) >> 15, (y * s + z * c) >> 15
            if dy:
                s, c = SINE[(dy & 0xff) * 8], COSINE[(dy & 0xff) * 8]
                x, z = (x * c + z * s) >> 15, (z * c - x * s) >> 15
            m.vx[idx] = x + ox; m.vy[idx] = y + oy; m.vz[idx] = z + oz
        elif t == 3:
            x = m.vx[idx] - ox; y = m.vy[idx] - oy; z = m.vz[idx] - oz
            m.vx[idx] = (x * dx) // 128 + ox
            m.vy[idx] = (y * dy) // 128 + oy
            m.vz[idx] = (z * dz) // 128 + oz
    return p


class Merged:
    """The client merges an npc's models into one before it animates them; so does this."""
    def __init__(s, parts):
        s.vx = np.concatenate([p.vx for p in parts])
        s.vy = np.concatenate([p.vy for p in parts])
        s.vz = np.concatenate([p.vz for p in parts])
        off = np.cumsum([0] + [p.vcount for p in parts[:-1]])
        s.fa = np.concatenate([p.fa + o for p, o in zip(parts, off)])
        s.fb = np.concatenate([p.fb + o for p, o in zip(parts, off)])
        s.fc = np.concatenate([p.fc + o for p, o in zip(parts, off)])
        s.colour = np.concatenate([p.colour for p in parts])
        s.finfo = None
        if any(p.finfo is not None for p in parts):
            s.finfo = np.concatenate([p.finfo if p.finfo is not None
                                      else np.zeros(p.fcount, np.int32) for p in parts])
        s.vcount = int(sum(p.vcount for p in parts))
        s.fcount = int(len(s.fa))
        s.tcount = 0

    def height(s):
        return int(max(0, -int(s.vy.min())))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('anim', help='a .anim set under models/')
    ap.add_argument('mesh', nargs='+', help='one or more .ob2 meshes, merged as the client merges them')
    ap.add_argument('--frames', default=None, help='comma-separated FRAME IDS (default: spread over the set)')
    ap.add_argument('--count', type=int, default=8)
    ap.add_argument('--cols', type=int, default=8)
    ap.add_argument('--size', type=int, default=180)
    ap.add_argument('--yan', type=int, default=512)
    ap.add_argument('--xan', type=int, default=0)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()

    frames, baseblob = parse_377_anim(open(a.anim, 'rb').read())
    base = parse_377_base(baseblob)
    print('%s: %d frame(s) on a base of %d transform groups'
          % (os.path.basename(a.anim), len(frames), base[0]))
    print('   frame ids %s, baked delays %s'
          % ([f[0] for f in frames], [f[4] for f in frames]))

    labels = []
    for p in a.mesh:
        lbl, vc = vertex_labels(open(p, 'rb').read())
        if lbl is None:
            print('   %s has NO vertex labels - nothing can animate it' % os.path.basename(p))
        labels += (lbl if lbl is not None else [0] * vc)
    addressed = set().union(*[set(x) for x in base[3]]) if base[3] else set()
    have = set(labels)
    print('   mesh: %d vertices, %d distinct labels, %d of them addressed by this base'
          % (len(labels), len(have), len(have & addressed)))

    byid = {f[0]: f for f in frames}
    if a.frames:
        want = [int(x) for x in a.frames.split(',')]
    else:
        ids = [f[0] for f in frames]
        n = min(a.count, len(ids))
        want = [ids[int(i * (len(ids) - 1) / max(1, n - 1))] for i in range(n)]

    tiles = []
    for fid in want:
        if fid not in byid:
            raise SystemExit('frame %d is not in this set (%s)' % (fid, sorted(byid)))
        _, cnt, flg, vls, delay = byid[fid]
        mm = Merged([ob2render.Model(p) for p in a.mesh])
        used = apply_frame(mm, groups_of(labels), base, flg, vls)
        if used != len(vls):
            print('   frame %d: WARNING read %d of %d value bytes' % (fid, used, len(vls)))
        tiles.append((fid, ob2render.render(mm, size=a.size, yan=a.yan, xan=a.xan)))
        print('   frame %-6d %d group(s), delay %d: posed' % (fid, cnt, delay))

    cols = min(a.cols, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * a.size, rows * a.size), (24, 24, 27))
    for i, (fid, img) in enumerate(tiles):
        sheet.paste(img, ((i % cols) * a.size, (i // cols) * a.size))
    sheet.save(a.out)
    print('wrote', a.out)


main()
