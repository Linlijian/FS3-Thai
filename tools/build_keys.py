"""Plan A, budget-free text: each translated string slot gets a 6-byte KEY (marker + 2 base-128 digits, Thai-channel v3 codes);
the proxy looks the key up in FS3_TH_text.txt and draws the full Thai line itself (wrapping at '|' hints / spaces, '*' = forced break).
usage: build_keys.py <game_copy> <map_v3> <translations.tsv> <out_dir>     (run build_channel.py into the same <out_dir> first)
TSV: member <TAB> block <TAB> offset_in_block [<TAB> source] <TAB> thai   (export_strings.py writes the 5-column form)
Members found in FS3UpdataChs.dat are patched there; the others (e.g. Bin/FS2_ItemHelp.bin) in FS3Bin.dat, rebuilt from
FS3Bin.dat.bak + the channel table BIG2GB.idx of <out_dir>/FS3Bin.dat, so re-running never stacks old edits.
Slots < 6 bytes get a one-char SHORT key (U+E200+id, ids 1..127 reserved for their texts).
Rows with empty thai reuse the translation of another row with the same source, else stay original.
Thai without any '|' is word-broken automatically (tools/thaibreak.py, Windows Uniscribe dictionary)."""
import os, sys, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, fstables, thaichan, thaibreak
game, mapf, tsv, out = sys.argv[1:5]
t2b, _ = thaichan.load_map(mapf)
assert chr(0xE000) in t2b and chr(0xE17F) in t2b and chr(0xE27F) in t2b, 'map has no (short) KEY codes - run build_channel.py first'
rows = [ln.rstrip('\n').split('\t') for ln in open(tsv, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
by_src = {r[3]: r[4] for r in reversed(rows) if len(r) == 5 and r[4].strip()}      # first filled row wins
ARC = {'FS3UpdataChs.dat': f'{game}/Pack/FS3UpdataChs.dat', 'FS3Bin.dat': f'{game}/Pack/FS3Bin.dat.bak'}
raw = {a: open(p, 'rb').read() for a, p in ARC.items()}; zz = {a: fszip.open_fszip_bytes(b) for a, b in raw.items()}
upd = set(zz['FS3UpdataChs.dat'].namelist())
arc_of = lambda member: 'FS3UpdataChs.dat' if member in upd else 'FS3Bin.dat'
slots = {}                                                                          # member -> {(block, offset): usable bytes}
def slot_len(member, blk, off):
    if member not in slots:
        d = zz[arc_of(member)].read(member)
        slots[member] = fstables.slot_lens(member, d) if fstables.kind(member) else \
            {(g.block, st): len(r) for g in fsdialog.groups(fsdialog.parse(d)[0], d)[0] for st, r in g.strs}
    return slots[member][(blk, off)]
items, seen = [], set()                                                             # (member, (block, offset), text, slot bytes)
for r in rows:
    member, blk, off, thai = r[0], int(r[1]), int(r[2]), r[-1]
    if (member, blk, off) in seen: continue                                         # same address twice: first row wins
    seen.add((member, blk, off))
    if len(r) == 5 and not thai.strip(): thai = by_src.get(r[3], '')
    if not thai.strip(): continue
    if '|' not in thai: thai = thaibreak.breaks(thai)
    items.append((member, (blk, off), thai.replace('|', '​'), slot_len(member, blk, off)))
ids = {}                                       # texts used by a < 6-byte slot get the low ids: a SHORT key U+E200+id is one char
for it in sorted(items, key=lambda it: it[3] >= 6): ids.setdefault(it[2], len(ids) + 1)
assert len(ids) < 128 * 128
by_member, nshort = collections.defaultdict(dict), 0
for member, at, text, n in items:
    i = ids[text]
    if n >= 6: key = chr(0xE000) + chr(0xE100 + i // 128) + chr(0xE100 + i % 128)
    else: assert i < 128, f'more than 127 distinct texts in short slots ({member} {at})'; key = chr(0xE200 + i); nshort += 1
    by_member[member][at] = thaichan.encode(key, t2b)
repl = collections.defaultdict(dict)
for member, edits in by_member.items():
    d = zz[arc_of(member)].read(member)
    repl[arc_of(member)][member] = fstables.patch(member, d, edits) if fstables.kind(member) else fsdialog.patch_same_len(d, edits)
os.makedirs(out, exist_ok=True); report = []
for a in ('FS3UpdataChs.dat', 'FS3Bin.dat'):
    if a == 'FS3Bin.dat':
        if not repl[a]: continue                                                    # nothing for FS3Bin: keep build_channel's file
        repl[a]['Bin/Code/BIG2GB.idx'] = fszip.open_fszip(f'{out}/FS3Bin.dat').read('Bin/Code/BIG2GB.idx')
    blob = fszip.write_like(zz[a], raw[a], replace=repl[a]); open(f'{out}/{a}', 'wb').write(blob)
    z2 = fszip.open_fszip_bytes(blob); assert z2.testzip() is None
    changed = sorted(i.filename for i in zz[a].infolist() if zz[a].read(i.filename) != z2.read(i.filename)); assert changed == sorted(repl[a]), changed
    for member in repl[a]:
        if member not in by_member: continue
        d2 = z2.read(member); toc = None if fstables.kind(member) else fsdialog.parse(d2)[1]
        for (blk, off), key in by_member[member].items():
            o = fstables.offset_of(member, d2, blk, off) if toc is None else toc[blk][1] + off
            e = d2.index(b'\0', o)                                                  # multi-list tables pad with spaces
            assert (d2[o:o + len(key)] == key and not d2[o + len(key):e].strip(b' ')) or                    (fstables.kind(member) == 'Message.bin' and off > 0 and key in d2[o:e]), (member, blk, off)   # template piece
    report.append(f'{a} {len(blob)} B sha256 {hashlib.sha256(blob).hexdigest()[:16]} members {changed}')
with open(f'{out}/FS3_TH_text.txt', 'w', encoding='utf-8', newline='\n') as f:
    f.write('# id<TAB>thai   (U+200B = allowed break, * = forced break) -- generated by tools/build_keys.py\n')
    for text, i in sorted(ids.items(), key=lambda kv: kv[1]): f.write(f'{i}\t{text}\n')
with open(f'{out}/FS3_TH_ids.tsv', 'w', encoding='utf-8', newline='\n') as f:     # addresses only: for overflow_report.py
    f.write('# id\tmember\tblock\toffset_in_block\n')
    for member, at, text, _ in items: f.write(f'{ids[text]}\t{member}\t{at[0]}\t{at[1]}\n')
print(f'{sum(map(len, by_member.values()))} slots ({nshort} short keys), {len(ids)} texts')
for ln in report: print(ln)
