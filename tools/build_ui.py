"""Thai labels for the image-only UI texts in FS3UI.pak (menu bar, sub tabs, ...).
usage: build_ui.py <game_copy> <labels.tsv> <out_dir>
labels.tsv: texture base (path inside FS3UI.pak without _Nor/_Ove/_Pre/_Dis.dds, e.g. Menu/M_Team) <TAB> thai [<TAB> extra px over the original ink width, default 28 = top-bar pitch]
Every state file of a base is redrawn: the original's glyph box and colours (top / bottom of the ink, for the gradient) are
measured, the Thai label is drawn with a Windows Thai font (GDI shapes vowels / tones), a white glow like the original's is
added, and the texture is written as uncompressed A8R8G8B8 DDS. A hand-edited <out_dir>/../ui_edit/<file>.png (same size)
is used instead when present. Writes <out_dir>/FS3UI.pak and preview PNGs in <out_dir>/ui_preview/."""
import os, sys, ctypes as C, ctypes.wintypes as W
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ujpak, fsdds
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
if __name__ == '__main__':
    game, labels, out = sys.argv[1:4]
    rows = [ln.rstrip('\n').split('\t') for ln in open(labels, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
    want = {r[0]: r[1] for r in rows}; extra = {r[0]: int(r[2]) for r in rows if len(r) > 2}
    buf = open(f'{game}/Pack/FS3UI.pak', 'rb').read(); (kids, pname, ver), _, _ = ujpak.read_tree(buf)
    os.makedirs(f'{out}/ui_preview', exist_ok=True); edit_dir = os.path.join(os.path.dirname(os.path.abspath(out)), 'ui_edit'); done = []
    def visit(nodes, path):
        for n in nodes:
            p = f'{path}/{n.name}' if path else n.name
            if n.children is not None: visit(n.children, p); continue
            base = p.rsplit('_', 1)[0] if p.lower().endswith('.dds') and '_' in p else None
            if base not in want: continue
            tmp = f'{out}/ui_preview/_orig.dds'; open(tmp, 'wb').write(n.data); w, h, px, mips = fsdds.read(tmp)
            ed = os.path.join(edit_dir, p.replace('/', '_')[:-4] + '.png')
            if os.path.exists(ed): ew, eh, new = fsdds.read_png(ed); assert (ew, eh) == (w, h), ed
            else: new = render(px, w, h, want[base], extra.get(base, 28))
            fsdds.write_dds(tmp, w, h, new, mips); n.data = open(tmp, 'rb').read()
            fsdds.write_png(f"{out}/ui_preview/{p.replace('/', '_')[:-4]}.png", w, h, new); done.append(p)
    visit(kids, '')
    os.remove(f'{out}/ui_preview/_orig.dds')
    blob = ujpak.build(kids, pname, ver); open(f'{out}/FS3UI.pak', 'wb').write(blob)
    (k2, _, _), _, _ = ujpak.read_tree(blob)                      # verify: parses, every replaced file is a DDS of the right size
    print(f'{len(done)} textures for {len(want)} labels -> {out}/FS3UI.pak ({len(blob)} B); missing: {sorted(set(want) - {d.rsplit("_", 1)[0] for d in done})}')
