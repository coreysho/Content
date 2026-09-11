#!/usr/bin/env python3
"""
Render a 377-format .ob2 model the way the client does.

Mirrors javaclient/src/main/java/jagex2:
  dash3d/Model.java      - header/vertex/face decode, method380() transform + projection
  config/ObjType.java    - the inventory-icon call (32x32, zoom/xan/yan/zan/xof/yof)
  graphics/Pix3D.java    - initColourTable() HSL16 palette, gammaCorrect(), sin/cos tables

Purpose: see a model before shipping it. Written after a black mask was built on a model
nobody had looked at, and shipped as an unreadable blob.

  python3 ob2render.py out.png a.ob2 b.ob2 ...          # contact sheet, auto-framed
  python3 ob2render.py out.png a.ob2 --xan 160 --yan 152 --zoom 800
  python3 ob2render.py out.png a.ob2 --recol 2115:1057  # apply a recolour pair first
"""
import sys, os, math, argparse
import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- packet reads
class P:
    def __init__(s, b, pos=0): s.b, s.pos = b, pos
    def g1(s):
        v = s.b[s.pos]; s.pos += 1; return v
    def g2(s):
        v = (s.b[s.pos] << 8) | s.b[s.pos+1]; s.pos += 2; return v
    def gsmart(s):                       # Packet.gsmart()
        return s.g1() - 64 if s.b[s.pos] < 128 else s.g2() - 49152

# ---------------------------------------------------------------- HSL16 palette
def _hue2rgb(p, q, t):
    if t*6.0 < 1.0: return (q-p)*6.0*t + p
    if t*2.0 < 1.0: return q
    if t*3.0 < 2.0: return (q-p)*(2.0/3.0 - t)*6.0 + p
    return p

def build_palette(gamma=0.8):
    """Pix3D.initColourTable(): 512 hue/sat combos x 128 lightness, then gammaCorrect()."""
    pal = np.zeros((65536, 3), dtype=np.uint8)
    for i in range(512):
        hue = (i // 8) / 64.0 + 0.0078125
        sat = (i & 7) / 8.0 + 0.0625
        for l in range(128):
            lum = l / 128.0
            r = g = b = lum
            if sat != 0.0:
                q = (sat + 1.0) * lum if lum < 0.5 else sat + lum - sat * lum
                p = lum * 2.0 - q
                tr = hue + 1.0/3.0
                if tr > 1.0: tr -= 1.0
                tb = hue - 1.0/3.0
                if tb < 0.0: tb += 1.0
                r, g, b = _hue2rgb(p, q, tr), _hue2rgb(p, q, hue), _hue2rgb(p, q, tb)
            # gammaCorrect
            rr = int((min(r, 0.999999) ** gamma) * 256.0)
            gg = int((min(g, 0.999999) ** gamma) * 256.0)
            bb = int((min(b, 0.999999) ** gamma) * 256.0)
            pal[i*128 + l] = (min(rr,255), min(gg,255), min(bb,255))
    return pal

def _hsl24to16(h, sa, li):
    if li > 243:   sa >>= 4
    elif li > 217: sa >>= 3
    elif li > 192: sa >>= 2
    elif li > 179: sa >>= 1
    return (((h & 0xff) >> 2) << 10) + ((sa >> 5) << 7) + (li >> 1)

def rgb15_to_hsl16(v):
    """ColorConversion.rgb15toHsl16 - config colours are RGB555, models store HSL16."""
    r, g, b = ((v >> 10) & 31)/31.0, ((v >> 5) & 31)/31.0, (v & 31)/31.0
    mn, mx = min(r, g, b), max(r, g, b)
    h = sN = 0.0; l = (mn + mx)/2.0
    if mn != mx:
        sN = (mx-mn)/(mx+mn) if l < 0.5 else (mx-mn)/(2.0-mx-mn)
        if r == mx:   h = (g-b)/(mx-mn)
        elif g == mx: h = (b-r)/(mx-mn) + 2.0
        else:         h = (r-g)/(mx-mn) + 4.0
    h /= 6.0
    return _hsl24to16(int(h*256.0), max(0, min(255, int(sN*256.0))), max(0, min(255, int(l*256.0))))

PALETTE = None
SIN = [int(math.sin(i * 0.0030679615) * 65536.0) for i in range(2048)]
COS = [int(math.cos(i * 0.0030679615) * 65536.0) for i in range(2048)]

# ---------------------------------------------------------------- model decode
class Model:
    def __init__(s, path):
        b = open(path, 'rb').read()
        h = P(b, len(b) - 18)
        s.vcount = h.g2(); s.fcount = h.g2(); s.tcount = h.g1()
        f_tex, f_pri, f_alpha, f_flabel, f_vlabel = h.g1(), h.g1(), h.g1(), h.g1(), h.g1()
        xlen, ylen, zlen, flen = h.g2(), h.g2(), h.g2(), h.g2()

        # Section order is NOT the order the flag bytes are read in. Model.java consumes
        # var6..var10 in order, then walks offsets as var7, var9, var6, var10, var8.
        o = 0
        vflag_o = o;  o += s.vcount
        ftype_o = o;  o += s.fcount
        if f_pri == 255:  o += s.fcount          # var7 face render priority
        if f_flabel == 1: o += s.fcount          # var9 face labels
        finfo_o = o
        if f_tex == 1:    o += s.fcount          # var6 face info (texture/shading)
        if f_vlabel == 1: o += s.vcount          # var10 vertex labels
        if f_alpha == 1:  o += s.fcount          # var8 face alpha
        fdata_o = o;  o += flen
        colour_o = o; o += s.fcount * 2
        o += s.tcount * 6
        x_o = o;      o += xlen
        y_o = o;      o += ylen
        z_o = o;      o += zlen
        # Self-check: a wrong section order still yields plausible numbers, so reconcile
        # the walk against the real file length and refuse to render garbage.
        if o != len(b) - 18:
            raise ValueError(f'{path}: section walk {o} != body {len(b)-18}')

        vf, xs, ys, zs = P(b, vflag_o), P(b, x_o), P(b, y_o), P(b, z_o)
        s.vx = np.zeros(s.vcount, np.int32); s.vy = np.zeros(s.vcount, np.int32)
        s.vz = np.zeros(s.vcount, np.int32)
        px = py = pz = 0
        for i in range(s.vcount):
            fl = vf.g1()
            dx = xs.gsmart() if fl & 1 else 0
            dy = ys.gsmart() if fl & 2 else 0
            dz = zs.gsmart() if fl & 4 else 0
            px += dx; py += dy; pz += dz
            s.vx[i], s.vy[i], s.vz[i] = px, py, pz

        cp = P(b, colour_o)
        s.colour = np.array([cp.g2() for _ in range(s.fcount)], np.int32)
        s.finfo = None
        if f_tex == 1:
            ip = P(b, finfo_o); s.finfo = np.array([ip.g1() for _ in range(s.fcount)], np.int32)

        fd, ft = P(b, fdata_o), P(b, ftype_o)
        s.fa = np.zeros(s.fcount, np.int32); s.fb = np.zeros(s.fcount, np.int32)
        s.fc = np.zeros(s.fcount, np.int32)
        a = bb = c = trip = 0
        for i in range(s.fcount):
            t = ft.g1()
            if t == 1:
                a = fd.gsmart() + trip; bb = fd.gsmart() + a; c = fd.gsmart() + bb; trip = c
            elif t == 2:
                bb = c; c = fd.gsmart() + trip; trip = c
            elif t == 3:
                a = c; c = fd.gsmart() + trip; trip = c
            elif t == 4:
                a, bb = bb, a; c = fd.gsmart() + trip; trip = c
            s.fa[i], s.fb[i], s.fc[i] = a, bb, c

    def recolour(s, pairs):
        """pairs: [(src_rgb15, dst_rgb15)] exactly as a .obj config's recolNs/recolNd.
        ObjConfig.ts converts each through ColorConversion.rgb15toHsl16 when >= 100,
        so do the same before matching against the model's stored HSL16 colours."""
        for src, dst in pairs:
            sh = rgb15_to_hsl16(src) if src >= 100 else src
            dh = rgb15_to_hsl16(dst) if dst >= 100 else dst
            hit = int((s.colour == sh).sum())
            if hit == 0:
                print(f'  warning: recol source {src} matches no face on this model', file=sys.stderr)
            s.colour[s.colour == sh] = dh

    def height(s):
        return int(max(0, -int(s.vy.min())))

# ---------------------------------------------------------------- lighting
def face_lightness(m, ambient=64, contrast=768, lx=-50, ly=-10, lz=-50):
    """Model.calculateNormals() reduced to a per-face lightness."""
    mag = int(math.sqrt(lx*lx + ly*ly + lz*lz))
    atten = (contrast * mag) >> 8
    vn = np.zeros((m.vcount, 4), np.float64)
    flat = np.zeros(m.fcount, np.float64); flat_set = np.zeros(m.fcount, bool)
    for i in range(m.fcount):
        a, b, c = m.fa[i], m.fb[i], m.fc[i]
        ax, ay, az = m.vx[b]-m.vx[a], m.vy[b]-m.vy[a], m.vz[b]-m.vz[a]
        bx, by, bz = m.vx[c]-m.vx[a], m.vy[c]-m.vy[a], m.vz[c]-m.vz[a]
        nx = ay*bz - az*by; ny = az*bx - ax*bz; nz = ax*by - ay*bx
        while abs(nx) > 8192 or abs(ny) > 8192 or abs(nz) > 8192:
            nx >>= 1; ny >>= 1; nz >>= 1
        ln = int(math.sqrt(nx*nx + ny*ny + nz*nz)) or 1
        nx = nx*256//ln; ny = ny*256//ln; nz = nz*256//ln
        if m.finfo is None or (m.finfo[i] & 1) == 0:
            for v in (a, b, c):
                vn[v, 0] += nx; vn[v, 1] += ny; vn[v, 2] += nz; vn[v, 3] += 1
        else:
            flat[i] = ambient + (lx*nx + ly*ny + lz*nz) / (atten/2 + atten)
            flat_set[i] = True
    out = np.zeros(m.fcount, np.float64)
    for i in range(m.fcount):
        if flat_set[i]:
            out[i] = flat[i]; continue
        tot = 0.0
        for v in (m.fa[i], m.fb[i], m.fc[i]):
            w = vn[v, 3] or 1
            tot += ambient + (lx*vn[v,0] + ly*vn[v,1] + lz*vn[v,2]) / (atten * w)
        out[i] = tot / 3.0
    return out

def adjust_lightness(hsl, light):
    l = int((hsl & 127) * light) >> 7
    l = 2 if l < 2 else (126 if l > 126 else l)
    return (hsl & 0xff80) + l

# ---------------------------------------------------------------- render
def render(m, size=192, xan=0, yan=0, zan=0, zoom=None, xof=0, yof=0, bg=(24,24,27)):
    """ObjType's icon call: method380(0, yan, zan, xan, xof, h/2+sin*zoom+yof, yof+cos*zoom)."""
    sx, sy, sz = m.vx.astype(np.int64), m.vy.astype(np.int64), m.vz.astype(np.int64)
    s_z, c_z = SIN[zan & 2047], COS[zan & 2047]
    s_y, c_y = SIN[yan & 2047], COS[yan & 2047]
    s_x, c_x = SIN[xan & 2047], COS[xan & 2047]
    if zan:
        t = (s_z*sy + c_z*sx) >> 16; sy = (c_z*sy - s_z*sx) >> 16; sx = t
    if yan:
        t = (s_y*sz + c_y*sx) >> 16; sz = (c_y*sz - s_y*sx) >> 16; sx = t

    auto_zoom = zoom is None
    if auto_zoom: zoom = 1000

    def project(zoom_):
        a5 = m.height()//2 + ((s_x*zoom_) >> 16) + yof
        a6 = yof + ((c_x*zoom_) >> 16)
        v18 = (a5*s_x + a6*c_x) >> 16
        X = xof + sx; Y = a5 + sy; Z = a6 + sz
        dep = ((s_x*Y + c_x*Z) >> 16)
        dep = np.where(dep <= 0, 1, dep)
        vy_ = ((c_x*Y - s_x*Z) >> 16)
        sc = size / 32.0
        return ((X*512.0)/dep)*sc + size/2, ((vy_*512.0)/dep)*sc + size/2, dep - v18

    if auto_zoom:
        z = 1000
        for _ in range(24):                      # px extent scales ~1/zoom; converge on a fit
            ax, ay, _ = project(z)
            ext = max(abs(ax - size/2).max(), abs(ay - size/2).max())
            if ext < 1: break
            z = max(32, int(z * ext / (size*0.44)))
        zoom = z
    px, py, pz = project(zoom)

    global PALETTE
    if PALETTE is None: PALETTE = build_palette()
    light = face_lightness(m)

    img = np.zeros((size, size, 3), np.uint8); img[:] = bg
    zbuf = np.full((size, size), 1 << 30, np.float64)
    order = np.argsort(-((pz[m.fa] + pz[m.fb] + pz[m.fc]) / 3.0))
    for i in order:
        if m.finfo is not None and (m.finfo[i] & 2) != 0:
            continue                                   # textured face, no texture here
        ia, ib, ic = m.fa[i], m.fb[i], m.fc[i]
        x0, y0, x1, y1, x2, y2 = px[ia], py[ia], px[ib], py[ib], px[ic], py[ic]
        area = (x1-x0)*(y2-y0) - (x2-x0)*(y1-y0)
        if area == 0: continue
        rgb = PALETTE[adjust_lightness(int(m.colour[i]), light[i])]
        z = (pz[ia] + pz[ib] + pz[ic]) / 3.0
        minx, maxx = int(max(0, min(x0,x1,x2))), int(min(size-1, max(x0,x1,x2)))
        miny, maxy = int(max(0, min(y0,y1,y2))), int(min(size-1, max(y0,y1,y2)))
        if minx > maxx or miny > maxy: continue
        xs_ = np.arange(minx, maxx+1); ys_ = np.arange(miny, maxy+1)
        gx, gy = np.meshgrid(xs_ + 0.5, ys_ + 0.5)
        w0 = (x1-x0)*(gy-y0) - (gx-x0)*(y1-y0)
        w1 = (x2-x1)*(gy-y1) - (gx-x1)*(y2-y1)
        w2 = (x0-x2)*(gy-y2) - (gx-x2)*(y0-y2)
        inside = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
        if not inside.any(): continue
        sub = zbuf[miny:maxy+1, minx:maxx+1]
        hit = inside & (z < sub)
        sub[hit] = z
        img[miny:maxy+1, minx:maxx+1][hit] = rgb
    return Image.fromarray(img)

# ---------------------------------------------------------------- interface model draw
def render_interface(m, w, h, xan=0, yan=0, zoom=560, bg=None):
    """Client.drawInterface's comType==6 branch, not ObjType's icon call.

        Pix3D.centerX = width / 2 + x;  Pix3D.centerY = height / 2 + y;
        pitchSin = sinTable[xan] * zoom >> 16;  pitchCos = cosTable[xan] * zoom >> 16;
        model.method380(0, yan, 0, xan, 0, pitchSin, pitchCos);

    The differences from render() matter: no model.height()/2 vertical centring (a loc
    model's origin is its FLOOR, so it hangs upward from the middle of the component),
    no xof/yof, and the 512 focal length is not rescaled - the component's own width and
    height are the viewport. Returns RGBA with the background transparent.
    """
    sx, sy, sz = m.vx.astype(np.int64), m.vy.astype(np.int64), m.vz.astype(np.int64)
    s_y, c_y = SIN[yan & 2047], COS[yan & 2047]
    s_x, c_x = SIN[xan & 2047], COS[xan & 2047]
    if yan:
        t = (s_y*sz + c_y*sx) >> 16; sz = (c_y*sz - s_y*sx) >> 16; sx = t
    a5 = (s_x*zoom) >> 16
    a6 = (c_x*zoom) >> 16
    v18 = (a5*s_x + a6*c_x) >> 16
    X = sx; Y = a5 + sy; Z = a6 + sz
    dep = ((s_x*Y + c_x*Z) >> 16)
    dep = np.where(dep <= 0, 1, dep)
    vy_ = ((c_x*Y - s_x*Z) >> 16)
    px = (X*512.0)/dep + w/2.0
    py = (vy_*512.0)/dep + h/2.0
    pz = dep - v18

    global PALETTE
    if PALETTE is None: PALETTE = build_palette()
    light = face_lightness(m)

    img = np.zeros((h, w, 4), np.uint8)
    zbuf = np.full((h, w), 1 << 30, np.float64)
    order = np.argsort(-((pz[m.fa] + pz[m.fb] + pz[m.fc]) / 3.0))
    for i in order:
        # A TEXTURED face carries a texture id where its colour would be, so there is no colour to
        # look up - but SKIPPING it hides the whole model when the model is a painting, which is
        # exactly the case this preview exists to judge. Draw it in a flat grey shaded by the same
        # lightness instead: the silhouette is real even though the pattern on it is not.
        textured = m.finfo is not None and (m.finfo[i] & 2) != 0
        ia, ib, ic = m.fa[i], m.fb[i], m.fc[i]
        x0, y0, x1, y1, x2, y2 = px[ia], py[ia], px[ib], py[ib], px[ic], py[ic]
        if (x1-x0)*(y2-y0) - (x2-x0)*(y1-y0) == 0: continue
        if textured:
            g = max(70, min(210, 70 + int(light[i])))
            rgb = np.array([g, g, g], np.uint8)
        else:
            rgb = PALETTE[adjust_lightness(int(m.colour[i]), light[i])]
        z = (pz[ia] + pz[ib] + pz[ic]) / 3.0
        minx, maxx = int(max(0, min(x0,x1,x2))), int(min(w-1, max(x0,x1,x2)))
        miny, maxy = int(max(0, min(y0,y1,y2))), int(min(h-1, max(y0,y1,y2)))
        if minx > maxx or miny > maxy: continue
        xs_ = np.arange(minx, maxx+1); ys_ = np.arange(miny, maxy+1)
        gx, gy = np.meshgrid(xs_ + 0.5, ys_ + 0.5)
        w0 = (x1-x0)*(gy-y0) - (gx-x0)*(y1-y0)
        w1 = (x2-x1)*(gy-y1) - (gx-x1)*(y2-y1)
        w2 = (x0-x2)*(gy-y2) - (gx-x2)*(y0-y2)
        inside = ((w0 >= 0) & (w1 >= 0) & (w2 >= 0)) | ((w0 <= 0) & (w1 <= 0) & (w2 <= 0))
        if not inside.any(): continue
        sub = zbuf[miny:maxy+1, minx:maxx+1]
        hit = inside & (z < sub)
        sub[hit] = z
        tile = img[miny:maxy+1, minx:maxx+1]
        tile[hit, 0:3] = rgb
        tile[hit, 3] = 255
    return Image.fromarray(img, 'RGBA')

# ---------------------------------------------------------------- sheet
def sheet(paths, out, size=192, cols=4, recol=None, **kw):
    tiles = []
    for p in paths:
        name = os.path.basename(p).replace('.ob2', '')
        try:
            m = Model(p)
            if recol: m.recolour(recol)
            im = render(m, size=size, **kw)
            label = f'{name}  {m.vcount}v/{m.fcount}f'
        except Exception as e:
            im = Image.new('RGB', (size, size), (60, 20, 20))
            label = f'{name}  FAILED: {e}'[:60]
        tiles.append((im, label))
    rows = (len(tiles) + cols - 1) // cols
    pad, lab = 8, 16
    W = cols*(size+pad) + pad
    H = rows*(size+pad+lab) + pad
    out_im = Image.new('RGB', (W, H), (18, 18, 20))
    d = ImageDraw.Draw(out_im)
    for i, (im, label) in enumerate(tiles):
        r, c = divmod(i, cols)
        x = pad + c*(size+pad); y = pad + r*(size+pad+lab)
        out_im.paste(im, (x, y))
        d.text((x+2, y+size+3), label, fill=(190,190,195))
    out_im.save(out)
    return out

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('out'); ap.add_argument('models', nargs='+')
    ap.add_argument('--xan', type=int, default=160); ap.add_argument('--yan', type=int, default=152)
    ap.add_argument('--zan', type=int, default=0);   ap.add_argument('--zoom', type=int, default=None)
    ap.add_argument('--size', type=int, default=192); ap.add_argument('--cols', type=int, default=4)
    ap.add_argument('--xof', type=int, default=0);    ap.add_argument('--yof', type=int, default=0)
    ap.add_argument('--recol', action='append', default=[],
                    help='src:dst in RGB555, repeatable, same values a .obj config uses')
    a = ap.parse_args()
    recol = [tuple(int(x) for x in r.split(':')) for r in a.recol]
    print(sheet(a.models, a.out, size=a.size, cols=a.cols, recol=recol,
                xan=a.xan, yan=a.yan, zan=a.zan, zoom=a.zoom, xof=a.xof, yof=a.yof))
