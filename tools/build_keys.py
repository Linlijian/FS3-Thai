"""Plan A, budget-free text: each translated string slot gets a 6-byte KEY (marker + 2 base-128 digits, Thai-channel v3 codes);
the proxy looks the key up in FS3_TH_text.txt and draws the full Thai line itself (wrapping at '|' hints / spaces, '*' = forced break).
usage: build_keys.py <game_copy> <map_v3> <translations.tsv> <out_dir> [key_ids.tsv]   (run build_channel.py into the same <out_dir> first)
key_ids.tsv (poc/key_ids.tsv) keeps every slot's text id across builds and is updated in place: saves store keys.
Dialogue keys are followed by pad chars (U+E200) up to the slot's length: the engine types and waits as for the Chinese.
TSV: member <TAB> block <TAB> offset_in_block [<TAB> source] <TAB> thai   (export_strings.py writes the 5-column form)
Members SP/... (FS3_SP.exe) are patched into a rebuilt SP_FS3.pak, CFG_SP/... like CFG/ (docs/sp.md).
Members found in FS3UpdataChs.dat are patched there; the others (e.g. Bin/FS2_ItemHelp.bin) in FS3Bin.dat, rebuilt from
FS3Bin.dat.bak + the channel table BIG2GB.idx of <out_dir>/FS3Bin.dat, so re-running never stacks old edits.
Slots < 6 bytes get a one-char SHORT key (U+E200+id, ids 1..127 reserved for their texts).
Rows with empty thai reuse the translation of another row with the same source, else stay original.
Thai without any '|' is word-broken automatically (tools/thaibreak.py, Windows Uniscribe dictionary).
Dialogue with more than PAGE lines ('*') keeps the engine's paging: the Thai is cut into pages of PAGE lines and the slot becomes
KEY1* * * *KEY2* ...  (one key per page + blank lines, like the originals pad their pages), so each page is its own text."""
import os, sys, hashlib, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, fstables, fsexe, thaichan, thaibreak, ujpak
game, mapf, tsv, out = sys.argv[1:5]; REG = sys.argv[5] if len(sys.argv) > 5 else None
t2b, _ = thaichan.load_map(mapf)
assert chr(0xE000) in t2b and chr(0xE17F) in t2b and chr(0xE27F) in t2b, 'map has no (short) KEY codes - run build_channel.py first'
rows = [ln.rstrip('\n').split('\t') for ln in open(tsv, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
by_src = {r[3]: r[4] for r in reversed(rows) if len(r) == 5 and r[4].strip()}      # first filled row wins
ARC = {'FS3UpdataChs.dat': fszip.orig(game, 'Pack/FS3UpdataChs.dat'), 'FS3Bin.dat': fszip.orig(game, 'Pack/FS3Bin.dat')}
raw = {a: open(p, 'rb').read() for a, p in ARC.items()}; zz = {a: fszip.open_fszip_bytes(b) for a, b in raw.items()}
upd = set(zz['FS3UpdataChs.dat'].namelist())
arc_of = lambda member: 'FS3UpdataChs.dat' if member in upd else 'FS3Bin.dat'
LOOSE = {m: fszip.orig(game, m) for m in ('CFG/DefaultString.bin', 'CFG/Mission.bin', 'CFG_SP/DefaultString.bin', 'CFG_SP/Mission.bin')}   # outside the archives
sp = {}                                                                             # FS3_SP.exe members 'SP/Bin/...' = Pack/SP_FS3.pak mounted as SP\ (docs/sp.md)
if any(r[0].startswith('SP/') for r in rows):
    sp_buf = open(fszip.orig(game, 'Pack/SP_FS3.pak'), 'rb').read(); sp = {'SP' + p: sp_buf[o:o + n] for p, o, n, *_ in ujpak.walk(sp_buf)}
read = lambda member: open(LOOSE[member], 'rb').read() if member in LOOSE else sp[member] if member in sp else zz[arc_of(member)].read(member)
slots = {}                                                                          # member -> {(block, offset): usable bytes}
def slot_len(member, blk, off):
    if member not in slots:
        d = read(member)
        slots[member] = fstables.slot_lens(member, d) if fstables.kind(member) else \
            {(g.block, st): len(r) for g in fsdialog.groups(fsdialog.parse(d)[0], d)[0] for st, r in g.strs}
    return slots[member][(blk, off)]
EXES = ('FS3.exe', 'FS3_SP.exe')
exe_rows = [r for r in rows if r[0] in EXES and r[-1].strip()]; rows = [r for r in rows if r[0] not in EXES]   # drawn-text replacement
PAGE = 4                                                                            # lines per dialogue box page (Chinese originals)
items, seen = [], set()                                                             # (member, (block, offset), text, slot bytes)
for r in rows:
    member, blk, off, thai = r[0], int(r[1]), int(r[2]), r[-1]
    if (member, blk, off) in seen: continue                                         # same address twice: first row wins
    seen.add((member, blk, off))
    if len(r) == 5 and not thai.strip(): thai = by_src.get(r[3], '')
    if not thai.strip(): continue
    if '|' not in thai: thai = thaibreak.breaks(thai)
    thai = thai.replace('|', '​'); n = slot_len(member, blk, off); lines = thai.split('*')
    if not fstables.kind(member) and n >= 6 and len(lines) > PAGE:                   # multi-page dialogue: one text per page
        thai = tuple('*'.join(lines[p:p + PAGE]).rstrip('* ') or ' ' for p in range(0, len(lines), PAGE))
    items.append((member, (blk, off), thai, n))
pages = lambda text: text if isinstance(text, tuple) else (text,)
addr, short = collections.defaultdict(list), set()                                # text -> slot addresses (member, block, offset, page)
for member, at, text, n in items:
    for p, t in enumerate(pages(text)): addr[t].append((member, *at, p))
    if n < 6: short.add(text)
reg = {}                                       # REGISTRY: saves store keys (party names, map / mission names), so an id must keep
if REG and os.path.exists(REG):                # meaning the same slot in every later build; ids are never reused (plana-b4: renumbered
    for ln in open(REG, encoding='utf-8'):     # ids turned saved names into dialogue lines)
        if ln.strip() and not ln.startswith('#'): i, m, b, o, p = ln.rstrip('\n').split('\t'); reg[(m, int(b), int(o), int(p))] = int(i)
top, stop, used, ids, drawn_short = max(reg.values(), default=127), max([i for i in reg.values() if i < 128], default=0), set(), {}, set()
for it in sorted(items, key=lambda it: it[3] >= 6):                                # texts used by a < 6-byte slot need a low id: a SHORT key U+E200+id is one char
    for t in pages(it[2]):
        if t in ids: continue
        old = sorted(i for i in (reg.get(a) for a in addr[t]) if i and i not in used and (i < 128 or t not in short))
        if old: ids[t] = old[0]
        elif t in short and stop >= 127:                                            # all 127 SHORT ids taken (FS3): its short slots see below,
            drawn_short.add(t); old = sorted(i for i in (reg.get(a) for a in addr[t]) if i and i not in used)   # its long slots keep a normal id
            if old: ids[t] = old[0]
            else: top = max(top, 127) + 1; ids[t] = top
        elif t in short: stop += 1; ids[t] = stop
        else: top = max(top, 127) + 1; ids[t] = top
        used.add(ids[t])
assert stop < 128, 'more than 127 distinct texts in short slots'
short_drawn = [it for it in items if it[2] in drawn_short and it[3] < 6]           # (FS3_SP's 2-byte 是 / 否 choices) the slot keeps its Chinese,
items = [it for it in items if not (it[2] in drawn_short and it[3] < 6)]           # FS3_TH_exe.txt replaces it where it is drawn whole
for member, at, t, _ in short_drawn: addr[t].remove((member, *at, 0))
for t in drawn_short:
    if not addr[t]: del addr[t], ids[t]
assert max(ids.values()) < 16256, 'ids reached the proxy dynamic range (DYN0)'
if REG:
    for t, aa in addr.items():
        for a in aa: reg[a] = ids[t]
    with open(REG, 'w', encoding='utf-8', newline='\n') as f:
        f.write('# id\tmember\tblock\toffset\tpage   text ids by slot address: an id is never reused (saves store keys) -- updated by tools/build_keys.py\n')
        for a, i in sorted(reg.items(), key=lambda kv: (kv[1], kv[0])): f.write(f'{i}\t{a[0]}\t{a[1]}\t{a[2]}\t{a[3]}\n')
K = lambda i: chr(0xE000) + chr(0xE100 + i // 128) + chr(0xE100 + i % 128)
PAD = chr(0xE200)                              # typewriter pad after a dialogue key: the engine reveals the slot at its Chinese length (and
padt = {}                                      # waits as long); the proxy shows Thai in step with the pads drawn. text -> fewest pads of its slots
by_member, nshort = collections.defaultdict(dict), 0
for member, at, text, n in items:
    if n >= 6 and not fstables.kind(member):                                        # dialogue: KEY + pads, page after page (KEY + blank lines)
        pp, sep = pages(text), '* ' * (PAGE - 1) + '*'; spare = (n - 6 * len(pp) - len(sep) * (len(pp) - 1)) // 2; tot = sum(map(len, pp))
        pads = [spare * len(t) // tot for t in pp]
        for t, p in zip(pp, pads): padt[t] = min(padt.get(t, p), p)
        key = ''.join(K(ids[t]) + PAD * p + (sep if j < len(pp) - 1 else '') for j, (t, p) in enumerate(zip(pp, pads)))
        by_member[member][at] = thaichan.encode(key, t2b); continue
    i = ids[text]
    if n >= 6: key = K(i)
    else: assert i < 128, f'short slot text got id {i} ({member} {at})'; key = chr(0xE200 + i); nshort += 1
    by_member[member][at] = thaichan.encode(key, t2b)
repl = collections.defaultdict(dict)
for member, edits in by_member.items():
    new = fstables.patch(member, read(member), edits) if fstables.kind(member) else fsdialog.patch_same_len(read(member), edits)
    if member in LOOSE:
        os.makedirs(os.path.dirname(f'{out}/{member}'), exist_ok=True); open(f'{out}/{member}', 'wb').write(new)
        assert set(fstables.strs(member, new)) >= {k for k in edits if k[1] == 0}, member   # still parses, whole-string keys present
    else: repl['SP_FS3.pak' if member in sp else arc_of(member)][member] = new
def verify(member, d2):                                                            # every key sits in its slot of the rebuilt member
    toc = None if fstables.kind(member) else fsdialog.parse(d2)[1]
    for (blk, off), key in by_member[member].items():
        o = fstables.offset_of(member, d2, blk, off) if toc is None else toc[blk][1] + off
        e = d2.index(b'\0', o)                                                      # multi-list tables pad with spaces
        assert (d2[o:o + len(key)] == key and not d2[o + len(key):e].strip(b' ')) or                    (fstables.kind(member) in (*fstables.MSG, *fstables.HELP) and off > 0 and key in d2[o:e]), (member, blk, off)   # template piece
os.makedirs(out, exist_ok=True); report = [f'{m} -> {out}/{m}' for m in by_member if m in LOOSE]
for a in ('FS3UpdataChs.dat', 'FS3Bin.dat'):
    if a == 'FS3Bin.dat':
        if not repl[a]: continue                                                    # nothing for FS3Bin: keep build_channel's file
        repl[a]['Bin/Code/BIG2GB.idx'] = fszip.open_fszip(f'{out}/FS3Bin.dat').read('Bin/Code/BIG2GB.idx')
    blob = fszip.write_like(zz[a], raw[a], replace=repl[a]); open(f'{out}/{a}', 'wb').write(blob)
    z2 = fszip.open_fszip_bytes(blob); assert z2.testzip() is None
    changed = sorted(i.filename for i in zz[a].infolist() if zz[a].read(i.filename) != z2.read(i.filename)); assert changed == sorted(repl[a]), changed
    for member in repl[a]:
        if member in by_member: verify(member, z2.read(member))
    report.append(f'{a} {len(blob)} B sha256 {hashlib.sha256(blob).hexdigest()[:16]} members {changed}')
if repl['SP_FS3.pak']:                                                             # SP_FS3.pak patched in place: no other file may move
    blob = bytearray(sp_buf); ujpak.patch_in_place(blob, {m[2:]: d for m, d in repl['SP_FS3.pak'].items()}); blob = bytes(blob)
    open(f'{out}/SP_FS3.pak', 'wb').write(blob)
    sp2 = {'SP' + p: blob[o:o + n] for p, o, n, *_ in ujpak.walk(blob)}; assert sp2.keys() == sp.keys()
    assert [(p, o) for p, o, *_ in ujpak.walk(blob)] == [(p, o) for p, o, *_ in ujpak.walk(sp_buf)] and len(blob) == len(sp_buf)
    changed = sorted(m for m in sp if sp[m] != sp2[m]); assert changed == sorted(repl['SP_FS3.pak']), changed
    for member in changed: verify(member, sp2[member])
    report.append(f'SP_FS3.pak {len(blob)} B sha256 {hashlib.sha256(blob).hexdigest()[:16]} members {len(changed)}')
exe_strs = {e: fsexe.strs(open(f'{game}/{e}', 'rb').read()) for e in {r[0] for r in exe_rows}}
big2gb = zz['FS3Bin.dat'].read('Bin/Code/BIG2GB.idx')                                  # original table: the channel only adds codes
with open(f'{out}/FS3_TH_exe.txt', 'w', encoding='utf-8', newline='\n') as f:
    f.write('# drawn Chinese pattern<TAB>thai  (%s / %d = values the game inserts, same order) -- generated by tools/build_keys.py\n')
    exe_p = set()
    for r in exe_rows:
        thai = r[-1] if '|' in r[-1] else thaibreak.breaks(r[-1]); pat = fsexe.drawn(exe_strs[r[0]][(int(r[1]), 0)], big2gb)
        if r[0] != 'FS3.exe' and pat in exe_p: continue                             # FS3_SP.exe: a pattern FS3.exe already has
        exe_p.add(pat); f.write(f"{pat}\t{thai.replace('|', chr(0x200b))}\n")
    for member, at, text, _ in short_drawn:
        d = read(member)
        src = fstables.strs(member, d) if fstables.kind(member) else {(g.block, st): r for g in fsdialog.groups(fsdialog.parse(d)[0], d)[0] for st, r in g.strs}
        pat = fsexe.drawn(src[at], big2gb)
        if pat not in exe_p: exe_p.add(pat); f.write(f"{pat}\t{text}\n")
    seen_p = set(); nn = 0                                                          # names / places: old saves and some NPC labels hold
    names = {}                                                                      # the Chinese name itself -> replace it where it is drawn
    for r in rows:                                                                  # (source read from the game file: the player package has no source column)
        if r[0].rsplit('/', 1)[-1] not in ('Objects.bin', 'KINDLE.BIN', 'FS3Maps.BIN'): continue
        if r[0] not in names: names[r[0]] = fstables.strs(r[0], read(r[0]))
        raw = names[r[0]].get((int(r[1]), int(r[2])), b''); thai = r[-1] if len(r) >= 4 else ''
        if len(r) == 5 and not thai.strip(): thai = by_src.get(r[3], '')
        if not thai.strip() or b'%' in raw or len(raw.strip()) < 4: continue
        try: pat = fsexe.drawn(raw, big2gb)
        except (UnicodeError, IndexError): continue
        if pat in seen_p or '\t' in pat: continue
        seen_p.add(pat); nn += 1; f.write(f"{pat}\t{(thai if '|' in thai else thaibreak.breaks(thai)).replace('|', chr(0x200b))}\n")
report.append(f'FS3_TH_exe.txt: {len(exe_rows)} drawn-text replacements + {nn} names / places')
with open(f'{out}/FS3_TH_text.txt', 'w', encoding='utf-8', newline='\n') as f:
    f.write('# id[:pads]<TAB>thai   (U+200B = allowed break, * = forced break, pads = typewriter pads after the key) -- generated by tools/build_keys.py\n')
    for text, i in sorted(ids.items(), key=lambda kv: kv[1]): f.write(f"{i}{':%d' % padt[text] if padt.get(text) else ''}\t{text}\n")
with open(f'{out}/FS3_TH_ids.tsv', 'w', encoding='utf-8', newline='\n') as f:     # addresses only: for overflow_report.py
    f.write('# id\tmember\tblock\toffset_in_block\n')
    for member, at, text, _ in items:
        for t in (text if isinstance(text, tuple) else (text,)): f.write(f'{ids[t]}\t{member}\t{at[0]}\t{at[1]}\n')
print(f'{sum(map(len, by_member.values()))} slots ({nshort} short keys), {len(ids)} texts')
for ln in report: print(ln)
