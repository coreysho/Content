#!/usr/bin/env python3
"""Render a .if interface file to a PNG, offline, the way the 377 client would.

WHY THIS EXISTS. Interface geometry is the one part of this project that cannot be
checked by arithmetic: "does it look right" is a question about pixels. Two rounds of
build-panel rework were spent shipping a layout, looking at it in game, and finding
text off the bottom of the panel. This draws the same file the packer reads, using the
same sprite sheets and the same fonts, so the looking can happen here instead.

WHAT IT IS FAITHFUL ABOUT
  - sprite sheets: content/sprites/*.png split row-major into meta/<name>.opt tiles,
    magenta (0xFF00FF) transparent, exactly as tools/pack/PixPack.ts convertImage does.
  - fonts: content/fonts/*.png, 20x20 cells, 16x16 grid. Glyph advance is recomputed
    with PixFont's own rule (cropped width + 2, minus one for a blank first column and
    one for a blank last column, space = advance of 'i', or 'I' for the quill font), so
    stringWid() here agrees with the client to the pixel.
  - layers: children are positioned relative to the layer and clipped to it, and a layer
    with scroll > height gets a scrollbar drawn just outside its right edge, which is
    where Client.drawInterface puts it.
  - text: type 4 draws one line per \\n, left or centre aligned, with the shadow offset.

WHAT IT FAKES
  - type=model draws a labelled box. The model itself is 3D and would need the whole
    renderer; the box is the footprint the client reserves, which is what layout needs.
    NOTE the client does NOT clip model icons to the layer horizontally or at the top -
    only at the bottom (Pix3D's rasterisers clamp to Pix2D.bottom and nothing else) -
    so --modelbleed draws the worst-case overhang a scrolled row would produce.
  - type=inv draws the slot grid, not the items.
  - interface scripts (script1op1=...) are not run, so the inactive colour is used.
"""

import json, os, re, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPRITES = os.path.join(ROOT, 'sprites')
FONTS = os.path.join(ROOT, 'fonts')
MAGENTA = (255, 0, 255)

# --------------------------------------------------------------------------- sprites

_sheet_cache = {}

def sheet(name):
    if name in _sheet_cache:
        return _sheet_cache[name]
    img = Image.open(os.path.join(SPRITES, name + '.png')).convert('RGBA')
    opt = os.path.join(SPRITES, 'meta', name + '.opt')
    if os.path.exists(opt):
        tw, th = [int(v) for v in open(opt).read().split('\n')[0].strip().split('x')]
    else:
        tw, th = img.size
    tiles = []
    for y in range(img.height // th):
        for x in range(img.width // tw):
            t = img.crop((x * tw, y * th, x * tw + tw, y * th + th))
            px = t.load()
            for j in range(t.height):
                for i in range(t.width):
                    if px[i, j][:3] == MAGENTA:
                        px[i, j] = (0, 0, 0, 0)
            tiles.append(t)
    _sheet_cache[name] = tiles
    return tiles

# --------------------------------------------------------------------------- fonts

class Font:
    def __init__(self, name):
        img = Image.open(os.path.join(FONTS, name + '.png')).convert('RGB')
        opt = os.path.join(FONTS, 'meta', name + '.opt')
        tw, th = [int(v) for v in open(opt).read().split('\n')[0].strip().split('x')]
        self.mask = [None] * 256
        self.w = [0] * 256
        self.h = [0] * 256
        self.offx = [0] * 256
        self.offy = [0] * 256
        self.adv = [0] * 256
        self.height = 0
        cols = img.width // tw
        for c in range(256):
            gx, gy = (c % cols) * tw, (c // cols) * th
            cell = img.crop((gx, gy, gx + tw, gy + th))
            px = cell.load()
            left, top, right, bottom = tw, th, -1, -1
            for j in range(th):
                for i in range(tw):
                    if px[i, j] != MAGENTA:
                        left = min(left, i); top = min(top, j)
                        right = max(right, i); bottom = max(bottom, j)
            if right == -1:
                left = top = 0; wi, hi = tw, th
            else:
                wi, hi = right - left + 1, bottom - top + 1
            self.w[c], self.h[c] = wi, hi
            self.offy[c] = top
            m = [[0] * wi for _ in range(hi)]
            for j in range(hi):
                for i in range(wi):
                    m[j][i] = 0 if px[left + i, top + j] == MAGENTA else 1
            self.mask[c] = m
            if hi > self.height and c < 128:
                self.height = hi
            # PixFont's advance rule, verbatim
            self.offx[c] = 1
            self.adv[c] = wi + 2
            if sum(m[y][0] for y in range(hi // 7, hi)) <= hi // 7:
                self.adv[c] -= 1
                self.offx[c] = 0
            if sum(m[y][wi - 1] for y in range(hi // 7, hi)) <= hi // 7:
                self.adv[c] -= 1
        quill = name.startswith('q')
        self.adv[32] = self.adv[73] if quill else self.adv[105]

    def width(self, s):
        n = 0
        i = 0
        while i < len(s):
            if s[i] == '@' and i + 4 < len(s) and s[i + 4] == '@':
                i += 5
                continue
            n += self.adv[ord(s[i]) & 0xFF]
            i += 1
        return n

    def draw(self, dst, x, y, s, colour, shadowed):
        """y is the BASELINE, as Client.drawInterface passes font.height + top."""
        px = dst.load()
        i = 0
        cx = x
        cur = colour
        while i < len(s):
            if s[i] == '@' and i + 4 < len(s) and s[i + 4] == '@':
                cur = TAGS.get(s[i + 1:i + 4], cur)
                i += 5
                continue
            c = ord(s[i]) & 0xFF
            if c == 32:            # PixFont.drawStringTag skips spaces: the blank glyph
                cx += self.adv[c]  # carries a marker pixel that would otherwise be drawn
                i += 1
                continue
            m = self.mask[c]
            gx, gy = cx + self.offx[c], y - self.height + self.offy[c]
            for j in range(self.h[c]):
                for k in range(self.w[c]):
                    if not m[j][k]:
                        continue
                    if shadowed:
                        _put(px, dst, gx + k + 1, gy + j + 1, (0, 0, 0))
                    _put(px, dst, gx + k, gy + j, cur)
            cx += self.adv[c]
            i += 1

TAGS = {'red': (255, 0, 0), 'gre': (0, 255, 0), 'blu': (0, 0, 255), 'yel': (255, 255, 0),
        'cya': (0, 255, 255), 'mag': (255, 0, 255), 'whi': (255, 255, 255),
        'lre': (255, 153, 153), 'dre': (128, 0, 0), 'bla': (0, 0, 0), 'or1': (255, 176, 0),
        'or2': (255, 144, 64), 'or3': (255, 112, 0), 'gr1': (0, 255, 0), 'gr2': (0, 176, 0),
        'gr3': (0, 128, 0)}

def _put(px, dst, x, y, rgb):
    if 0 <= x < dst.width and 0 <= y < dst.height:
        px[x, y] = rgb + (255,)

_font_cache = {}
def font(name):
    if name not in _font_cache:
        _font_cache[name] = Font(name)
    return _font_cache[name]

# --------------------------------------------------------------------------- .if parsing

def parse_if(path):
    """-> (order, dict name -> dict of key/value). Order is file order."""
    coms = {}
    order = []
    cur = None
    for raw in open(path, 'rb').read().decode('utf-8').replace('\r\n', '\n').split('\n'):
        line = raw.strip()
        if not line or line.startswith('//'):
            continue
        if line.startswith('['):
            cur = line[1:line.index(']')]
            coms[cur] = {}
            order.append(cur)
            continue
        if '=' not in line or cur is None:
            continue
        k, v = line.split('=', 1)
        coms[cur][k] = v
    return order, coms

def tree(order, coms):
    """-> children lists, root first, mirroring PackShared's layer= handling."""
    kids = {n: [] for n in order}
    root = []
    for n in order:
        p = coms[n].get('layer')
        (kids[p] if p else root).append(n)
    return root, kids

def rgb(v):
    if v is None:
        return (0, 0, 0)
    n = int(v, 16) if v.lower().startswith('0x') else int(v)
    return ((n >> 16) & 255, (n >> 8) & 255, n & 255)

# --------------------------------------------------------------------------- rendering

def render(path, out, modelbleed=False, bg=(0, 0, 0), fill=None):
    """fill: {component: {"text": "...", "model": <raw model.pack id>, "hide": "yes",
    "recol": "src:dst,..."}} -
    what a script would have pushed with if_settext / if_setmodel / if_sethide, so the
    preview shows a populated window rather than an empty template."""
    order, coms = parse_if(path)
    for n, over in (fill or {}).items():
        if n not in coms:
            raise SystemExit('fill names a component that is not in the file: %s' % n)
        coms[n].update({k: str(v) for k, v in over.items()})
    root, kids = tree(order, coms)
    img = Image.new('RGBA', (512, 334), bg + (255,))
    _draw_layer(img, coms, kids, root, 0, 0, 0, (0, 0, 512, 334), modelbleed)
    img.convert('RGB').save(out)
    return img

def _draw_layer(img, coms, kids, names, ox, oy, scroll, clip, modelbleed):
    d = ImageDraw.Draw(img)
    for n in names:
        c = coms[n]
        t = c.get('type')
        x = ox + int(c.get('x', 0))
        y = oy + int(c.get('y', 0)) - scroll
        w = int(c.get('width', 0))
        h = int(c.get('height', 0))
        if c.get('hide') == 'yes':
            continue
        if t == 'layer' or t == 'overlay':
            sc = int(c.get('scroll', 0))
            sub = (max(clip[0], x), max(clip[1], y), min(clip[2], x + w), min(clip[3], y + h))
            _draw_layer(img, coms, kids, kids[n], x, y, 0, sub, modelbleed)
            if sc > h:
                d.rectangle([x + w, y, x + w + 15, y + h], fill=(75, 61, 45))
                d.rectangle([x + w, y, x + w + 15, y + 15], fill=(120, 100, 78))
                d.rectangle([x + w, y + h - 15, x + w + 15, y + h], fill=(120, 100, 78))
                bar = max(10, h * h // sc)
                d.rectangle([x + w, y + 16, x + w + 15, y + 16 + bar], fill=(120, 100, 78))
        elif t == 'graphic':
            g = c.get('graphic')
            if not g:
                continue
            nm, idx = g.split(',') if ',' in g else (g, '0')
            tile = sheet(nm)[int(idx)]
            img.alpha_composite(_clipped(tile, x, y, clip), (max(x, clip[0]), max(y, clip[1])))
        elif t == 'rect':
            col = rgb(c.get('colour'))
            if c.get('fill') == 'yes':
                d.rectangle([x, y, x + w - 1, y + h - 1], fill=col)
            else:
                d.rectangle([x, y, x + w - 1, y + h - 1], outline=col)
        elif t == 'text':
            f = font(c.get('font', 'p12_full'))
            col = rgb(c.get('colour'))
            shadow = c.get('shadowed') == 'yes'
            by = y + f.height
            for line in c.get('text', '').split('\\n'):
                if c.get('center') == 'yes':
                    f.draw(img, x + w // 2 - f.width(line) // 2, by, line, col, shadow)
                else:
                    f.draw(img, x, by, line, col, shadow)
                by += f.height
        elif t == 'model':
            tile = _model_tile(c, w, h)
            if tile is None:
                col = (90, 90, 140)
                d.rectangle([x, y, x + w - 1, y + h - 1], outline=col)
                d.line([x, y, x + w - 1, y + h - 1], fill=col)
                d.line([x + w - 1, y, x, y + h - 1], fill=col)
            else:
                # Pix3D's rasterisers clamp to Pix2D.bottom and to nothing else, so a model
                # is cut off at the bottom of its layer and overhangs every other edge.
                cut = max(0, (y + h) - clip[3])
                if cut < h:
                    img.alpha_composite(tile.crop((0, 0, w, h - cut)), (x, y))
        elif t == 'inv':
            for j in range(h):
                for i in range(w):
                    sx = x + i * (int(c.get('margin', '0,0').split(',')[0]) + 32)
                    sy = y + j * (int(c.get('margin', '0,0').split(',')[1]) + 32)
                    d.rectangle([sx, sy, sx + 31, sy + 31], outline=(70, 70, 70))

def _clipped(tile, x, y, clip):
    l = max(0, clip[0] - x); t = max(0, clip[1] - y)
    r = min(tile.width, clip[2] - x); b = min(tile.height, clip[3] - y)
    if r <= l or b <= t:
        return Image.new('RGBA', (1, 1), (0, 0, 0, 0))
    return tile.crop((l, t, r, b))

_model_cache = {}

def _model_tile(c, w, h):
    """Render the component's model the way Client.drawInterface's comType 6 branch does.
    `model` is a raw model.pack id when a fill supplied one, or a model.pack NAME when it
    came from the .if file - the packer accepts only the name, if_setmodel only the id."""
    spec = c.get('model')
    if spec is None:
        return None
    key = (spec, w, h, c.get('xan', 0), c.get('yan', 0), c.get('zoom', 0), c.get('recol', ''))
    if key in _model_cache:
        return _model_cache[key]
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import ifmodels
    name = spec
    if str(spec).isdigit():
        byid = {v: k for k, v in ifmodels.modelpack().items()}
        name = byid.get(int(spec))
    path = ifmodels.ob2path(name) if name else None
    if path is None:
        _model_cache[key] = None
        return None
    import ob2render
    m = ob2render.Model(path)
    # `recol` is how a fill spells if_setobject: the client builds an obj's model with the obj
    # config's recolNs/recolNd applied, so a preview that skipped them would show fourteen
    # identical grey slabs. "src:dst,src:dst", exactly the config's numbers.
    if c.get('recol'):
        m.recolour([tuple(int(x) for x in pair.split(':')) for pair in str(c['recol']).split(',')])
    tile = ob2render.render_interface(m, w, h, xan=int(c.get('xan', 0)),
                                      yan=int(c.get('yan', 0)), zoom=int(c.get('zoom', 1)))
    _model_cache[key] = tile
    return tile

if __name__ == '__main__':
    src = sys.argv[1]
    dst = sys.argv[2] if len(sys.argv) > 2 else '/tmp/if.png'
    fill = json.load(open(sys.argv[3])) if len(sys.argv) > 3 else None
    render(src, dst, fill=fill)
    print(dst)
