"""Predict what the engine sends to MultiByteToWideChar for Big5 chars absent from the original b2g.dat:
b2u.dat (Big5 -> Unicode, value big-endian) -> Windows LCMapStringW(LCMAP_SIMPLIFIED_CHINESE) -> GBK.  [hypothesis, checked on 3 chars in the step-D log]
usage: predict_missing.py <game_copy> <missing_chars.csv> <out.csv>"""
import sys, os, csv, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip
z = fszip.open_fszip(f'{sys.argv[1]}/Pack/FS3Bin.dat.bak'); b2u = z.read('Bin/Code/b2u.dat')
def simp(ch, lcid=0x0804):
    out = ctypes.create_unicode_buffer(8)
    n = ctypes.windll.kernel32.LCMapStringW(lcid, 0x02000000, ch, len(ch), out, 8)
    return out.value[:n]
rows = []
for r in csv.DictReader(open(sys.argv[2], encoding='utf-8-sig')):
    c = int(r['big5_hex'], 16); u = int.from_bytes(b2u[c*2:c*2+2], 'big'); uni = chr(u) if u else ''
    s = simp(uni) if uni else ''
    try: gbk = s.encode('gbk').hex() if s else ''
    except UnicodeEncodeError: gbk = 'NOT-IN-GBK'
    rows.append([r['big5_hex'], r['char'], r['count'], f'U+{u:04X}' if u else '', s, gbk, 'changed' if s != uni else 'same'])
with open(sys.argv[3], 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['big5', 'char', 'count', 'b2u', 'simplified', 'gbk', 'lcmap']); w.writerows(rows)
bad = [r for r in rows if r[5] in ('', 'NOT-IN-GBK')]
print(len(rows), 'chars;', sum(1 for r in rows if r[6] == 'changed'), 'simplified by LCMap;', len(bad), 'not representable in GBK:', ' '.join(r[1] for r in bad))
for r in rows[:12]: print(r)
