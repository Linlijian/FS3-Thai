"""Export every translatable string to a TSV for translators:
dialogue slots (Dia*/Auto*) and fstables (Objects, FS2_Items, FS2_ItemHelp). A member comes from FS3UpdataChs.dat when it is there,
else from FS3Bin.dat.bak -- the engine's own lookup order (open-questions Q2).
usage: export_strings.py <game_copy> <out.tsv>
Columns: member <TAB> block <TAB> offset_in_block <TAB> source (cp950 -> UTF-8) <TAB> thai (empty, fill in).
build_keys.py reads this file directly; rows sharing a source reuse the first filled translation.
The output contains game text: keep it on your own disk (work/), never commit it."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, fstables
game, out = sys.argv[1:3]
n = small = 0; uniq = set(); upd = set()
with open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write('# member\tblock\toffset_in_block\tsource\tthai ( | = allowed break, * = forced break; empty = keep original)\n')
    for arc in ('FS3UpdataChs.dat', 'FS3Bin.dat.bak'):
        z = fszip.open_fszip(f'{game}/Pack/{arc}')
        for i in z.infolist():
            if i.is_dir() or i.filename.lower() in upd: continue      # shadowed by FS3UpdataChs.dat
            if arc == 'FS3UpdataChs.dat': upd.add(i.filename.lower())
            if arc == 'FS3UpdataChs.dat' and any(f'/{d}/' in i.filename for d in ('Dialog', 'AutoDialog')):
                d = z.read(i); found = [((x.block, st), raw) for x in fsdialog.groups(fsdialog.parse(d)[0], d)[0] for st, raw in x.strs]
            elif fstables.kind(i.filename):
                found = sorted(fstables.strs(i.filename, z.read(i)).items())
            else: continue
            for (blk, st), raw in found:
                if not any(b >= 0x80 for b in raw): continue          # ASCII-only: labels / code, not text
                src = raw.decode(fsdialog.ENC).replace('\t', ' '); n += 1; uniq.add(src); small += len(raw) < 6 and fstables.kind(i.filename) in (None, *fstables.MULTI)
                f.write(f'{i.filename}\t{blk}\t{st}\t{src}\t\n')
print(f'{n} strings ({len(uniq)} unique), {small} slots < 6 bytes (short keys) -> {out}')
