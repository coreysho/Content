#!/usr/bin/env python3
"""Pick the interface zoom for a model icon, and render it, the way the client would.

The 377 client draws a type=model component like this (Client.drawInterface, comType 6):

    Pix3D.centerX = width / 2 + x;   Pix3D.centerY = height / 2 + y;
    model.method380(0, yan, 0, xan, 0, sin[xan]*zoom>>16, cos[xan]*zoom>>16);

Two consequences drive everything here.

ZOOM IS INVERSE. The projection divides by a depth that is zoom plus the rotated vertex,
so a BIGGER zoom draws a SMALLER icon. 560 - the value the first build panel used - puts a
loc model about nine times over the edge of its box.

THE MODEL HANGS UPWARD FROM THE CENTRE. A loc model's origin is the middle of its floor
tile, and the component has no vertical offset, so the icon sits in the TOP half of its
box with a little of the base below the middle. The fix is not a zoom: it is to give the
component twice the height of the icon you want and top-align it, so the box's centre
lands on the icon's bottom edge. fit() returns that geometry with the zoom.

Used to generate the zoom tables in poh_roommenu / poh_furnmenu, so every icon is framed
from its own geometry instead of one guessed number shared by 78 different models.
"""

import os, sys, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ob2render as R

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def modelpack():
    out = {}
    for l in open(os.path.join(ROOT, 'pack/model.pack')).read().split('\n'):
        if '=' in l:
            i, n = l.split('=', 1)
            out[n] = int(i)
    return out

def ob2path(name):
    for sub in ['loc', 'obj', 'npc', 'com', 'spot', 'idk', '_unpack', '']:
        p = os.path.join(ROOT, 'models', sub, name + '.ob2')
        if os.path.exists(p):
            return p
    return None

def extent(m, w, h, xan, yan, zoom):
    """(half-width in px, rise above centre, drop below centre) at this zoom."""
    sx, sy, sz = m.vx.astype(np.int64), m.vy.astype(np.int64), m.vz.astype(np.int64)
    s_y, c_y = R.SIN[yan & 2047], R.COS[yan & 2047]
    s_x, c_x = R.SIN[xan & 2047], R.COS[xan & 2047]
    if yan:
        t = (s_y * sz + c_y * sx) >> 16
        sz = (c_y * sz - s_y * sx) >> 16
        sx = t
    a5 = (s_x * zoom) >> 16
    a6 = (c_x * zoom) >> 16
    Y = a5 + sy
    Z = a6 + sz
    dep = (s_x * Y + c_x * Z) >> 16
    dep = np.where(dep <= 0, 1, dep)
    vy = (c_x * Y - s_x * Z) >> 16
    px = (sx * 512.0) / dep
    py = (vy * 512.0) / dep
    return abs(px).max(), max(0.0, -py.min()), max(0.0, py.max())

def fit(path, iconw, iconh, below, xan=150, yan=40, fill=0.92):
    """Zoom that fits this model into an iconw x iconh box whose CENTRE line sits
    `below` pixels above the icon's bottom edge.

    The component that holds it is then:  y = icontop - (iconh - below) + iconh/... no -
    simply: height = 2 * (iconh - below), y = icontop, which puts the centre at
    icontop + iconh - below. Everything above that centre is `rise`, everything under it
    `drop`, so the model lands inside the icon exactly when rise <= iconh - below and
    drop <= below. Those are the two constraints solved here, plus the width.
    """
    m = R.Model(path)
    lo, hi = 200, 60000
    for _ in range(44):
        z = (lo + hi) // 2
        hw, rise, drop = extent(m, iconw, iconh, xan, yan, z)
        if hw > iconw * fill / 2 or rise > (iconh - below) * fill or drop > below * fill:
            lo = z + 1
        else:
            hi = z
    hw, rise, drop = extent(m, iconw, iconh, xan, yan, hi)
    return hi, hw, rise, drop

if __name__ == '__main__':
    mp = modelpack()
    spec = json.load(open(sys.argv[1]))
    iconw, iconh, below = int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4])
    for row in spec:
        p = ob2path(row['model'])
        z, hw, rise, drop = fit(p, iconw, iconh, below)
        row.update(id=mp[row['model']], zoom=z, hw=round(hw, 1), rise=round(rise, 1), drop=round(drop, 1))
        print(f"{row.get('label', row['model']):28} id={mp[row['model']]:6} zoom={z:6} hw={hw:5.1f} rise={rise:5.1f} drop={drop:5.1f}")
    json.dump(spec, open(sys.argv[1], 'w'), indent=1)
