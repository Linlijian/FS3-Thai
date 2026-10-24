"""Export every translatable string to a TSV for translators:
dialogue slots (Dia*/Auto*), fstables (Objects, Items, ItemHelp, Fighter(Help), ArrayData, Message) and the loose CFG/DefaultString.bin. A member comes from FS3UpdataChs.dat when it is there,
else from FS3Bin.dat.bak -- the engine's own lookup order (open-questions Q2).
usage: export_strings.py <game_copy> <out.tsv> [--sp]   (originals via fszip.orig: $FS3_ORIG > .bak > plain, so a game with the mod installed works too)
--sp: the FS3_SP.exe expansion instead (docs/sp.md): members of Pack/SP_FS3.pak as the engine names them (SP/Bin/...), CFG_SP/ loose files
(their pristine .bnk.bin copies) and FS3_SP.exe.
Columns: member <TAB> block <TAB> offset_in_block <TAB> source (cp950 -> UTF-8) <TAB> thai (empty, fill in).
build_keys.py reads this file directly; rows sharing a source reuse the first filled translation.
The output contains game text: keep it on your own disk (work/), never commit it."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, fstables, fsexe, ujpak
sp = '--sp' in sys.argv
if sp: sys.argv.remove('--sp')
game, out = sys.argv[1:3]
n = small = 0; uniq = set(); upd = set()
def emit(f, name, d, dialog):
    global n, small
    if dialog and any(f'/{x}/' in name for x in ('Dialog', 'AutoDialog')):
        found = [((x.block, st), raw) for x in fsdialog.groups(fsdialog.parse(d)[0], d)[0] for st, raw in x.strs]
    elif fstables.kind(name) and d:                                   # SP's BlessTable.bin is empty
        found = sorted(fstables.strs(name, d).items())
    else: return
    for (blk, st), raw in found:
        if not any(b >= 0x80 for b in raw): continue          # ASCII-only: labels / code, not text
        src = raw.decode(fsdialog.ENC).replace('\t', ' '); n += 1; uniq.add(src); small += len(raw) < 6 and fstables.kind(name) in (None, *fstables.MULTI)
        f.write(f'{name}\t{blk}\t{st}\t{src}\t\n')
with open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write('# member\tblock\toffset_in_block\tsource\tthai ( | = allowed break, * = forced break; empty = keep original)\n')
    if sp:                                                            # SP_FS3.pak is never modified by the mod yet: read it as is
        raw = open(f'{game}/Pack/SP_FS3.pak', 'rb').read()
        for p, off, size, *_ in ujpak.walk(raw): emit(f, 'SP' + p, raw[off:off + size], True)
    else:
        for arc in ('FS3UpdataChs.dat', 'FS3Bin.dat'):
            z = fszip.open_fszip(fszip.orig(game, f'Pack/{arc}'))
            for i in z.infolist():
                if i.is_dir() or i.filename.lower() in upd: continue      # shadowed by FS3UpdataChs.dat
                if arc == 'FS3UpdataChs.dat': upd.add(i.filename.lower())
                emit(f, i.filename, z.read(i), arc == 'FS3UpdataChs.dat')
    cfg = 'CFG_SP' if sp else 'CFG'
    for m in (f'{cfg}/DefaultString.bin', f'{cfg}/Mission.bin'):                             # loose file outside the archives; .bak = original
        src = f'{game}/{m[:-4]}.bnk.bin' if sp and os.path.exists(f'{game}/{m[:-4]}.bnk.bin') else fszip.orig(game, m)
        for (blk, st), raw in sorted(fstables.strs(m, open(src, 'rb').read()).items()):
            if not any(b >= 0x80 for b in raw): continue
            src_txt = raw.decode(fsdialog.ENC).replace('\t', ' '); n += 1; uniq.add(src_txt)
            f.write(f'{m}\t{blk}\t{st}\t{src_txt}\t\n')
    exe = 'FS3_SP.exe' if sp else 'FS3.exe'
    for (blk, st), raw in sorted(fsexe.strs(open(f'{game}/{exe}', 'rb').read()).items()):   # drawn-text replacement (proxy)
        src_txt = raw.decode(fsdialog.ENC).replace('\t', ' ').replace('\n', ' '); n += 1; uniq.add(src_txt)
        f.write(f'{exe}\t{blk}\t{st}\t{src_txt}\t\n')
print(f'{n} strings ({len(uniq)} unique), {small} slots < 6 bytes (short keys) -> {out}')
