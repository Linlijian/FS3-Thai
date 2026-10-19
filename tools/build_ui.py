"""Thai labels for the image-only UI texts in FS3UI.pak (menu bar, sub tabs, ...).
usage: build_ui.py <game_copy> <labels.tsv> <out_dir>
labels.tsv: texture base (path inside FS3UI.pak without _Nor/_Ove/_Pre/_Dis.dds, e.g. Menu/M_Team) <TAB> thai [<TAB> extra px over the original ink width, default 28 = top-bar pitch]
Every state file of a base is redrawn: the original's glyph box and colours (top / bottom of the ink, for the gradient) are
measured, the Thai label is drawn with a Windows Thai font (GDI shapes vowels / tones), a white glow like the original's is
added, and the texture is written as uncompressed A8R8G8B8 DDS. A hand-edited <out_dir>/../ui_edit/<file>.png (same size)
is used instead when present. Writes <out_dir>/FS3UI.pak and preview PNGs in <out_dir>/ui_preview/."""
import os, sys, ctypes as C, ctypes.wintypes as W
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ujpak, fsdds, fszip
FACE = 'Leelawadee UI'
g, u = C.WinDLL('gdi32'), C.WinDLL('user32')
for f, r, a in ((g.CreateCompatibleDC, C.c_void_p, [C.c_void_p]), (g.CreateFontW, C.c_void_p, None), (g.SelectObject, C.c_void_p, [C.c_void_p, C.c_void_p]),
                (g.CreateDIBSection, C.c_void_p, [C.c_void_p, C.c_void_p, C.c_uint, C.POINTER(C.c_void_p), C.c_void_p, C.c_uint]),
                (g.DeleteObject, C.c_int, [C.c_void_p]), (g.SetTextColor, C.c_uint, [C.c_void_p, C.c_uint]), (g.SetBkMode, C.c_int, [C.c_void_p, C.c_int]),
                (g.DeleteDC, C.c_int, [C.c_void_p]), (u.DrawTextW, C.c_int, [C.c_void_p, C.c_wchar_p, C.c_int, C.POINTER(W.RECT), C.c_uint])):
    f.restype = r
    if a: f.argtypes = a
def mask(text, w, h, px_h, cx, cy):
    """-> alpha bytes (w*h) of `text` drawn at font height px_h, centred on (cx, cy)"""
    dc = g.CreateCompatibleDC(None); bits = C.c_void_p()
    bmi = (C.c_byte * 44)(); C.memmove(bmi, (C.c_int * 4)(40, w, -h, 1 | (32 << 16)), 16)
    bmp = g.CreateDIBSection(dc, bmi, 0, C.byref(bits), None, 0); g.SelectObject(dc, bmp)
    font = g.CreateFontW(-px_h, 0, 0, 0, 700, 0, 0, 0, 0, 0, 0, 4, 0, FACE); g.SelectObject(dc, font)   # 4 = ANTIALIASED_QUALITY
    g.SetTextColor(dc, 0xFFFFFF); g.SetBkMode(dc, 1)
    m = W.RECT(0, 0, 0, 0); u.DrawTextW(dc, text, -1, C.byref(m), 0x400 | 0x20)                      # DT_CALCRECT | DT_SINGLELINE
    tw, th = m.right, m.bottom; rc = W.RECT(cx - tw // 2, cy - th // 2, cx - tw // 2 + tw, cy - th // 2 + th)
    u.DrawTextW(dc, text, -1, C.byref(rc), 0x20 | 0x100)                                           # DT_SINGLELINE | DT_NOCLIP
    raw = C.string_at(bits, w * h * 4); out = bytes(raw[i + 1] for i in range(0, len(raw), 4))
    g.DeleteObject(font); g.DeleteObject(bmp); g.DeleteDC(dc)
    return out, tw
def render(px, w, h, text, extra=28):
    ink = [(x, y) for y in range(h) for x in range(w) if px[(y * w + x) * 4 + 3] > 200 and sum(px[(y * w + x) * 4:(y * w + x) * 4 + 3]) < 600]
    if not ink: ink = [(x, y) for y in range(h) for x in range(w) if px[(y * w + x) * 4 + 3] > 128]
    x0, x1 = min(p[0] for p in ink), max(p[0] for p in ink); y0, y1 = min(p[1] for p in ink), max(p[1] for p in ink)
    col = lambda ys: [sum(px[(y * w + x) * 4 + k] for x, y in ink if y in ys) // max(1, sum(1 for x, y in ink if y in ys)) for k in range(3)]
    mid = (y0 + y1) // 2; top, bot = col(range(y0, mid + 1)), col(range(mid, y1 + 1))
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2; size = int((y1 - y0 + 1) * 1.4)          # Thai x-height is small next to a CJK glyph box
    while True:                                           # shrink until it fits the texture with room for the glow
        a, tw = mask(text, w, h, size, cx, cy)
        if tw <= min(w - 8, x1 - x0 + 1 + extra) or size <= 8: break   # buttons sit close: stay near the original ink width
        size -= 1
    if cx - tw // 2 < 4 or cx + tw // 2 > w - 4: cx = w // 2; a, tw = mask(text, w, h, size, cx, cy)
    glow = bytearray(w * h)
    for y in range(h):                                    # 2 px glow: max of the neighbourhood, softened
        for x in range(w):
            m = max(a[yy * w + xx] for yy in range(max(0, y - 2), min(h, y + 3)) for xx in range(max(0, x - 2), min(w, x + 3)))
            glow[y * w + x] = m * 3 // 4
    out = bytearray(w * h * 4)
    for y in range(h):
        t = min(1.0, max(0.0, (y - y0) / max(1, y1 - y0))); c = [int(top[k] + (bot[k] - top[k]) * t) for k in range(3)]
        for x in range(w):
            ta, ga = a[y * w + x], glow[y * w + x]; fa = max(ta, ga)
            if not fa: continue
            out[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes([(c[k] * ta + 255 * (fa - ta)) // fa for k in range(3)] + [fa])
    return bytes(out)
def render_region(px, w, h, rect, text):
    """atlas mode: rebuild the background inside rect (x,y,w,h) from its border (Coons patch, all 4 channels), then draw the
    Thai label there with the original's fill colour and, when the original has one, its outline colour."""
    rx, ry, rw, rh = rect; out = bytearray(px)
    P = lambda x, y: px[(min(h - 1, max(0, y)) * w + min(w - 1, max(0, x))) * 4:(min(h - 1, max(0, y)) * w + min(w - 1, max(0, x))) * 4 + 4]
    L = [P(rx - 1, y) for y in range(ry, ry + rh)]; R = [P(rx + rw, y) for y in range(ry, ry + rh)]
    T = [P(x, ry - 1) for x in range(rx, rx + rw)]; B = [P(x, ry + rh) for x in range(rx, rx + rw)]
    c00, c10, c01, c11 = P(rx - 1, ry - 1), P(rx + rw, ry - 1), P(rx - 1, ry + rh), P(rx + rw, ry + rh)
    bg = {}
    for j in range(rh):
        v = (j + 1) / (rh + 1)
        for i in range(rw):
            u = (i + 1) / (rw + 1)
            bg[i, j] = [max(0, min(255, round((1 - u) * L[j][k] + u * R[j][k] + (1 - v) * T[i][k] + v * B[i][k]
                        - ((1 - u) * (1 - v) * c00[k] + u * (1 - v) * c10[k] + (1 - u) * v * c01[k] + u * v * c11[k])))) for k in range(4)]
    ink, hit = [], set()                                  # original pixels that differ from the smooth background estimate
    for (i, j), b in bg.items():
        o = P(rx + i, ry + j)
        if sum(abs(o[k] * o[3] - b[k] * b[3]) for k in range(3)) // 255 + abs(o[3] - b[3]) > 90:
            hit.add((rx + i, ry + j))
            if o[3] > 128: ink.append(o)
    lum = lambda c: c[0] * 3 + c[1] * 6 + c[2]
    ink.sort(key=lum); half = len(ink) // 2
    dark, light = ink[:max(1, len(ink) // 4)], ink[-max(1, len(ink) // 4):]
    avg = lambda cs: [sum(c[k] for c in cs) // len(cs) for k in range(3)]
    bgl = sum(lum(b) for b in bg.values()) / max(1, len(bg))
    nd = sum(1 for c in ink if abs(lum(c) - lum(dark[0])) < abs(lum(c) - lum(light[-1])))
    fill, line = (avg(dark), avg(light)) if nd >= len(ink) - nd else (avg(light), avg(dark))
    outline = abs(lum(line) - bgl) > 600                  # the outline colour stands out from the background
    size = int(rh * 0.95)
    while True:
        a, tw = mask(text, w, h, size, rx + rw // 2, ry + rh // 2)
        if tw <= rw - 2 or size <= 7: break
        size -= 1
    hole = {(x + dx, y + dy) for x, y in hit for dx in (-2, -1, 0, 1, 2) for dy in (-2, -1, 0, 1, 2)
            if rx <= x + dx < rx + rw and ry <= y + dy < ry + rh}         # ink + its glow, kept inside the rect
    while hole:                                           # onion-peel inpainting: fill from known neighbours inward
        ring = {}
        for x, y in hole:
            nb = [out[(yy * w + xx) * 4:(yy * w + xx) * 4 + 4] for xx in (x - 1, x, x + 1) for yy in (y - 1, y, y + 1)
                  if 0 <= xx < w and 0 <= yy < h and (xx, yy) not in hole]
            if nb:
                al = sum(c[3] for c in nb)
                ring[x, y] = bytes([sum(c[k] * c[3] for c in nb) // al if al else 0 for k in range(3)] + [al // len(nb)])
        if not ring: break
        for (x, y), c in ring.items(): out[(y * w + x) * 4:(y * w + x) * 4 + 4] = c
        hole -= set(ring)
    for y in range(max(0, ry - 1), min(h, ry + rh + 1)):
        for x in range(max(0, rx - 1), min(w, rx + rw + 1)):
            ta = a[y * w + x]; ga = 0
            if outline: ga = max(a[yy * w + xx] for yy in range(max(0, y - 1), min(h, y + 2)) for xx in range(max(0, x - 1), min(w, x + 2)))
            o = list(out[(y * w + x) * 4:(y * w + x) * 4 + 4])
            for col, al in ((line, ga), (fill, ta)):
                if not al: continue
                na = al + o[3] * (255 - al) // 255
                o = [(col[k] * al + o[k] * o[3] * (255 - al) // 255) // max(1, na) for k in range(3)] + [na]
            out[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes(o)
    return bytes(out)
if __name__ == '__main__':
    game, labels, out = sys.argv[1:4]
    rows = [ln.rstrip('\n').split('\t') for ln in open(labels, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
    want = {r[0]: r[1] for r in rows if '@' not in r[0]}; extra = {r[0]: int(r[2]) for r in rows if len(r) > 2}
    regions = {}                                          # 'Dir/File.dds@x,y,w,h' rows: atlas regions, several per file
    for r in rows:
        if '@' in r[0]: f, rc = r[0].split('@'); regions.setdefault(f, []).append((tuple(map(int, rc.split(','))), r[1]))
    buf = open(fszip.orig(game, 'Pack/FS3UI.pak'), 'rb').read(); (kids, pname, ver), _, _ = ujpak.read_tree(buf)
    os.makedirs(f'{out}/ui_preview', exist_ok=True); edit_dir = os.path.join(os.path.dirname(os.path.abspath(out)), 'ui_edit'); done = []
    def visit(nodes, path):
        for n in nodes:
            p = f'{path}/{n.name}' if path else n.name
            if n.children is not None: visit(n.children, p); continue
            base = p.rsplit('_', 1)[0] if p.lower().endswith('.dds') and '_' in p else None
            if base not in want and p not in regions: continue
            tmp = f'{out}/ui_preview/_orig.dds'; open(tmp, 'wb').write(n.data); w, h, px, mips = fsdds.read(tmp)
            ed = os.path.join(edit_dir, p.replace('/', '_')[:-4] + '.png')
            if os.path.exists(ed): ew, eh, new = fsdds.read_png(ed); assert (ew, eh) == (w, h), ed
            elif p in regions:
                new = px
                for rc, t in regions[p]: new = render_region(new, w, h, rc, t)
            else: new = render(px, w, h, want[base], extra.get(base, 28))
            fsdds.write_dds(tmp, w, h, new, mips); n.data = open(tmp, 'rb').read()
            fsdds.write_png(f"{out}/ui_preview/{p.replace('/', '_')[:-4]}.png", w, h, new); done.append(p)
    visit(kids, '')
    os.remove(f'{out}/ui_preview/_orig.dds')
    blob = ujpak.build(kids, pname, ver); open(f'{out}/FS3UI.pak', 'wb').write(blob)
    (k2, _, _), _, _ = ujpak.read_tree(blob)                      # verify: parses, every replaced file is a DDS of the right size
    print(f'{len(done)} textures for {len(want)} labels -> {out}/FS3UI.pak ({len(blob)} B); missing: {sorted((set(want) - {d.rsplit("_", 1)[0] for d in done}) | (set(regions) - set(done)))}')
