"""Find Chinese text that is not translated yet.
  find_untranslated.py files <game> <master.tsv>   every archive member / CFG file with Big5 text whose sentences are not in the master
                                                    (translated) - lists files the export does not cover yet, and untranslated rows
  find_untranslated.py log <FS3_TH_hook.log>       Chinese the game really DREW (needs log_drawtext=1): one line per screen row, with
                                                    position - what a player sees untranslated, keys excluded
Reads only; game text is printed to the console / your disk, never commit the output."""
import os, re, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BIG5 = re.compile(rb'(?:[\xa1-\xf9][\x40-\x7e\xa1-\xfe]|[\x20-\x7e])*(?:[\xa1-\xf9][\x40-\x7e\xa1-\xfe])(?:[\xa1-\xf9][\x40-\x7e\xa1-\xfe]|[\x20-\x7e])*')
SKIP = re.compile(r'(?i)(/code/|\.ttf$|\.nm|\.fm$|\.sm$|\.ms$|\.nmm$|\.img$|gb2gig5|\.bfl$|chatmenu|objects_back|/autodialog\.bin$|/dialog\.bin$|fs2message|leave\.bin|martialartedit|\.ini$|\.txt$|fs2maps|roleman|sgmessage)')
def text_of(d):
    out = set()
    for m in BIG5.finditer(d):
        s = m.group()
        if not all(0xa140 <= int.from_bytes(s[j:j + 2], 'big') <= 0xc67e for j in range(len(s)) if s[j] >= 0xa1 and j + 1 < len(s) and (j == 0 or s[j - 1] < 0x80 or True)): pass
        try: t = s.decode('cp950').strip()
        except UnicodeDecodeError: continue
        if sum('\u4e00' <= c <= '\u9fff' for c in t) >= 2: out.add(t)
    return out
def files(game, master):
    import fszip
    rows = [l.rstrip('\n').split('\t') for l in open(master, encoding='utf-8') if l.strip() and not l.startswith('#')]
    done = {r[3].strip() for r in rows if len(r) == 5 and r[4].strip()}; known = {r[3].strip() for r in rows if len(r) >= 4}
    covered = {r[0].lower() for r in rows}; res = []; upd = set()
    for arc in ('FS3UpdataChs.dat', 'FS3Bin.dat'):
        z = fszip.open_fszip(fszip.orig(game, f'Pack/{arc}'))
        for i in z.infolist():
            k = i.filename.lower(); key = k[4:] if k.startswith(('bin/', 'BIN/')) else k
            if i.is_dir() or SKIP.search(k) or key in upd: continue
            if arc == 'FS3UpdataChs.dat': upd.add(key)
            t = text_of(z.read(i)); new = {x for x in t if x not in known}; todo = {x for x in t if x in known and x not in done}
            if (new and k not in covered) or todo: res.append((len(new), len(todo), i.filename, 'NOT EXPORTED' if k not in covered else ''))
    for rel in ('CFG/DefaultString.bin', 'CFG/Mission.bin'):
        t = text_of(open(fszip.orig(game, rel), 'rb').read()); todo = {x for x in t if x in known and x not in done}
        if todo: res.append((0, len(todo), rel, ''))
    for n, t, f, note in sorted(res, reverse=True): print(f'{n:6d} new {t:6d} untranslated  {f}  {note}')
    left = [r for r in rows if len(r) == 5 and not r[4].strip()]
    print(f'master: {len(rows)} rows, {len(left)} without Thai:', collections.Counter(r[0].rsplit('/', 1)[-1] for r in left).most_common(10))
def log(path):
    t = open(path, encoding='utf-8', errors='replace').read(); rows = collections.OrderedDict()
    for m in re.finditer(r'DrawTextW .*?rect_in=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\).*?\n\s+wide n=\d+ utf16=([0-9a-f ]+)', t):
        l, tp, r, b = map(int, m.groups()[:4]); s = ''.join(chr(int(x, 16)) for x in m.group(5).split())
        if any(0xE000 <= ord(c) < 0xE300 for c in s) or not any('\u4e00' <= c <= '\u9fff' for c in s): continue
        rows.setdefault((b - tp, tp), {})[l] = s
    seen = set()
    for (h, y), cells in rows.items():
        line = ''.join(cells[x] for x in sorted(cells))
        if line not in seen: seen.add(line); print(f'h={h:2d} y={y:4d} x={min(cells):4d}  {line}')
    print(f'# {len(seen)} distinct Chinese lines drawn')
if __name__ == '__main__':
    if sys.argv[1] == 'files': files(sys.argv[2], sys.argv[3])
    elif sys.argv[1] == 'log': log(sys.argv[2])
