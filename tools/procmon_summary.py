r"""Summarise a Process Monitor CSV export of FS3.exe file activity: which archive member was read from which archive, in what order.
Procmon filter: Process Name is FS3.exe ; Path contains \Pack\ ; (Operation is CreateFile / ReadFile). Export CSV (Columns: Time of Day, Process Name, PID, Operation, Path, Result, Detail).
usage: procmon_summary.py <game_copy> <procmon.csv> [--set original|patched]"""
import os, sys, csv, re, struct, bisect, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, ujpak, fsset
mode = fsset.parse_set(sys.argv); game, log = sys.argv[1], sys.argv[2]
def intervals(path):
    raw = open(path, 'rb').read(); iv = []
    if raw[:4] == b'UJ  ':
        for p, off, size, *_ in ujpak.walk(raw): iv.append((off, off + size, p))
    else:
        z = fszip.open_fszip_bytes(raw)
        for i in z.infolist():
            nl, xl = struct.unpack_from('<HH', raw, i.header_offset + 26); s = i.header_offset
            iv.append((s, s + 30 + nl + xl + i.compress_size, '/' + i.filename))
    iv.sort(); return iv
arch = {}                                   # lower-case file name -> (logical, intervals, starts)
for name, real in fsset.archives(game, mode):
    iv = intervals(real); arch[os.path.basename(name).lower()] = (name, iv, [x[0] for x in iv])
for real_name in ('FS3Bin.dat.bak',):       # the game may open either; map both names to the right data
    pass
first = collections.OrderedDict(); reads = collections.Counter(); opens = []
with open(log, newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        path = row.get('Path', ''); base = os.path.basename(path).lower()
        if base not in arch or row.get('Result') != 'SUCCESS': continue
        op = row['Operation']
        if op == 'CreateFile': opens.append((row['Time of Day'], base)); continue
        m = re.search(r'Offset:\s*([\d,]+),\s*Length:\s*([\d,]+)', row.get('Detail', ''))
        if op != 'ReadFile' or not m: continue
        off, ln = int(m[1].replace(',', '')), int(m[2].replace(',', '')); name, iv, st = arch[base]
        k = max(0, bisect.bisect_right(st, off) - 1)
        while k < len(iv) and iv[k][0] < off + ln:
            if iv[k][1] > off: key = (name, iv[k][2]); reads[key] += 1; first.setdefault(key, row['Time of Day'])
            k += 1
print('archive open order:', list(dict.fromkeys(b for _, b in opens)))
byname = collections.defaultdict(set)
for (a, member), _ in reads.items(): byname[re.sub(r'^/?(bin|BIN)/', 'Bin/', member, flags=re.I).lower().lstrip('/')].add(a)
both = {m: s for m, s in byname.items() if len(s) > 1}
print('members read:', len(reads), '| members read from MORE than one archive:', len(both)); [print('  ', m, sorted(s)) for m, s in list(both.items())[:20]]
for tag in ('dialog', 'autodialog'):
    rows = [(k, first[k]) for k in reads if tag in k[1].lower() and not (tag == 'dialog' and 'autodialog' in k[1].lower())]
    print(f'{tag}: {len(rows)} members read', [f'{a}:{m.split("/")[-1]}' for (a, m), _ in rows[:12]])
