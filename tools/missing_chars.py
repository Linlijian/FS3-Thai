"""List Big5 chars used in game text but absent from the ORIGINAL b2g.dat.
Strings = maximal NUL-delimited runs that decode fully as Big5 (>=3 bytes, contain a lead byte). Heuristic until the Dia*.bin
layout is solved (docs/open-questions Q1) - not a structural parse. usage: missing_chars.py <game_copy> <out.csv>"""
import os, sys, re, csv, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip
game, out = sys.argv[1], sys.argv[2]; P = f'{game}/Pack'
orig = fszip.open_fszip(f'{P}/FS3Bin.dat.bak'); upd = fszip.open_fszip(f'{P}/FS3UpdataChs.dat')
b = orig.read('Bin/Code/b2g.dat'); mapped = {c for c in range(0x10000) if b[c*2:c*2+2] != b'\0\0'}
files = {}                                                   # logical name -> bytes ; updata overrides bin (override order = Q2)
for i in orig.infolist():
    if re.match(r'Bin/(Dialog|AutoDialog)/|Bin/(FS2_Items|FS2_ItemHelp|KINDLE|Message|FS2Message|SGmessage|DIALOG|AutoDialog|Objects|NPC|RoleInf|MartialArt)', i.filename, re.I) and not i.is_dir(): files[i.filename.upper()] = (f'FS3Bin:{i.filename}', orig.read(i))
for i in upd.infolist():
    if i.filename.upper().startswith('BIN/') and not i.is_dir() and i.filename.upper() in files: files[i.filename.upper()] = (f'Updata:{i.filename}', upd.read(i))
seg = re.compile(rb'(?<=\x00)[\x20-\x7e\xa1-\xf9][\x20-\x7e\x40-\xfe]{2,}(?=\x00)')
use = collections.defaultdict(list)
for key, (name, data) in files.items():
    for m in seg.finditer(data):
        s = m.group()
        try: s.decode('big5')
        except UnicodeDecodeError: continue
        k = 0
        while k < len(s):
            if s[k] >= 0xa1 and k + 1 < len(s):
                c = s[k] << 8 | s[k+1]
                if c not in mapped: use[c].append((name, m.start(), s.decode('big5')))
                k += 2
            else: k += 1
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f); w.writerow(['big5_hex', 'char', 'count', 'files', 'first_file', 'first_offset', 'first_string'])
    for c, v in sorted(use.items(), key=lambda kv: -len(kv[1])):
        w.writerow([f'{c:04X}', bytes([c >> 8, c & 255]).decode('big5'), len(v), len({x[0] for x in v}), v[0][0], v[0][1], v[0][2]])
print(len(use), 'distinct missing chars;', sum(len(v) for v in use.values()), 'occurrences')
for c, v in sorted(use.items(), key=lambda kv: -len(kv[1]))[:12]: print(f'{c:04X}', bytes([c>>8,c&255]).decode('big5'), len(v), v[0][0], v[0][2][:30])
