"""Export every dialogue string slot of FS3UpdataChs.dat (Dia*/Auto*) and the names in BIN/Objects.bin (speaker labels) to a TSV.
usage: export_strings.py <game_copy> <out.tsv>
Columns: member <TAB> block <TAB> offset_in_block <TAB> source (cp950 -> UTF-8) <TAB> thai (empty, fill in).
build_keys.py reads this file directly; rows sharing a source reuse the first filled translation.
The output contains game text: keep it on your own disk (work/), never commit it."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, fsobjects
game, out = sys.argv[1:3]
z = fszip.open_fszip(f'{game}/Pack/FS3UpdataChs.dat'); n = small = 0; uniq = set()
with open(out, 'w', encoding='utf-8', newline='\n') as f:
    f.write('# member\tblock\toffset_in_block\tsource\tthai ( | = allowed break, * = forced break; empty = keep original)\n')
    for i in z.infolist():
        if i.is_dir(): continue
        if i.filename.endswith('/Objects.bin'): found = sorted(fsobjects.strs(z.read(i)).items())
        elif any(f'/{d}/' in i.filename for d in ('Dialog', 'AutoDialog')):
            d = z.read(i); found = [((x.block, st), raw) for x in fsdialog.groups(fsdialog.parse(d)[0], d)[0] for st, raw in x.strs]
        else: continue
        for (blk, st), raw in found:
            if not any(b >= 0x80 for b in raw): continue          # ASCII-only: labels / code, not text
            src = raw.decode(fsdialog.ENC).replace('\t', ' '); n += 1; uniq.add(src); small += len(raw) < 6 and not i.filename.endswith('/Objects.bin')
            f.write(f'{i.filename}\t{blk}\t{st}\t{src}\t\n')
print(f'{n} strings ({len(uniq)} unique), {small} slots < 6 bytes (short keys) -> {out}')
