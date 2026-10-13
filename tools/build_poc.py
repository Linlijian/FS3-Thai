"""Plan A PoC: put one long Thai sentence into the Dia039 line the user has already seen, via the Thai channel.
Writes work/poc/FS3UpdataChs.dat (only Dia039 changed; every other member byte-identical, verified).
usage: build_poc.py <game_copy> <map_file> <out_dir>"""
import os, sys, re, hashlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, thaichan
game, mapf, out = sys.argv[1:4]
MEMBER = 'BIN/Dialog/Dia039.bin'
TARGETS = {(0, 3043), (0, 3715), (0, 3799), (4, 4244), (4, 4916), (4, 5000)}   # (block, offset): Madame Wu's line, both variants (draw_run2)
# longest first; '*' = line break. Covers leading vowels (เ แ โ), upper (ั ิ ี ื), lower (ุ ู), tones (่ ้ ๊), stacked upper+tone, sara am (ำ), thanthakhat (์)
CANDIDATES = [                                                            # first that fits wins: ordered by mark coverage
    'แค่ก แค่ก... แม้ชาวเมืองจะลำบาก*แต่ถ้ามีท่านมหาปราชญ์อยู่ตรงนี้*พวกเราต้องผ่านพ้นไปได้แน่นอน',  # needs ~170 B: shows the budget problem
    'แค่ก เมืองลำบาก*แต่ท่านอยู่ที่นี่*เรารอด',   # เ แ | ื ำ ู ี | ่ | stacked upper vowel + tone (ที่ นี่)
    'แค่ก เมืองลำบาก*แต่มีท่านอาจารย์*เรารอดแน่',
]
t2b, _ = thaichan.load_map(mapf)
z = fszip.open_fszip(f'{game}/Pack/FS3UpdataChs.dat'); raw = open(f'{game}/Pack/FS3UpdataChs.dat', 'rb').read()
d = z.read(MEMBER); name, toc = fsdialog.parse(d); groups, _ = fsdialog.groups(name, d)
edits = {}; report = []
for g in groups:
    for st, r in g.strs:
        if (g.block, st) not in TARGETS: continue
        for th in CANDIDATES:
            enc = thaichan.encode(th, t2b)
            if len(enc) <= len(r) and all(len(thaichan.encode(p, t2b)) <= 42 for p in th.split('*')):   # 42 B = longest designed line
                edits[(g.block, st)] = enc; report.append((g.block, st, len(r), len(enc), th)); break
        else: raise SystemExit(f'no candidate fits {len(r)} B at block {g.block}+{st}')
newd = fsdialog.patch_same_len(d, edits)
assert len(newd) == len(d)
blob = fszip.write_like(z, raw, replace={MEMBER: newd})
os.makedirs(out, exist_ok=True); open(f'{out}/FS3UpdataChs.dat', 'wb').write(blob)
# verify: archive opens, CRCs pass, only Dia039 differs, Thai decodes back exactly
z2 = fszip.open_fszip_bytes(blob); assert z2.testzip() is None
diff = [i.filename for i in z.infolist() if z.read(i.filename) != z2.read(i.filename)]; assert diff == [MEMBER], diff
d2 = z2.read(MEMBER); _, toc2 = fsdialog.parse(d2); g2, _ = fsdialog.groups(name, d2)
for blk, st, old, new, th in report:
    o = toc2[blk][1] + st; got = d2[o:o + new]
    assert thaichan.decode(got, t2b) == th and d2[o + new:o + old] == b'\0' * (old - new)
    print(f'block {blk} +{st}: {old} B slot, {new} B Thai, {old - new} B NUL pad | {th}')
print('lines per * :', [len(thaichan.encode(p, t2b)) for p in report[0][4].split('*')], 'bytes')
print('wrote', f'{out}/FS3UpdataChs.dat', len(blob), 'B sha256', hashlib.sha256(blob).hexdigest()[:16], '| changed members:', diff)
