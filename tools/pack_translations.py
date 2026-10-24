"""Distribution form of a translation sheet: no source column (= no game text), every row resolved.
usage: pack_translations.py <strings_all.tsv> <out translations.tsv>
- rows with an empty thai reuse the translation of the same source (build_keys' by_src), rows without one are dropped
- word breaks ('|') are added here (thaibreak, Windows' Thai dictionary), so the player's Windows build cannot change the result
Output: member <TAB> block <TAB> offset_in_block <TAB> thai   (build_keys.py reads the 4-column form)"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import thaibreak
src, dst = sys.argv[1:3]
rows = [ln.rstrip('\n').split('\t') for ln in open(src, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
by_src = {r[3]: r[4] for r in reversed(rows) if len(r) == 5 and r[4].strip()}
brk = lambda t: t if '|' in t else thaibreak.breaks(t)
out, seen = [], set()
for r in rows:
    thai = r[-1]
    if r[0] in ('FS3.exe', 'FS3_SP.exe'):                                   # drawn-text replacement: block = string index, no dedupe (as in build_keys)
        if thai.strip(): out.append((r[0], r[1], r[2], brk(thai)))
        continue
    at = (r[0], int(r[1]), int(r[2]))
    if at in seen: continue                                 # same address twice: first row wins
    seen.add(at)
    if len(r) == 5 and not thai.strip(): thai = by_src.get(r[3], '')
    if thai.strip(): out.append((r[0], r[1], r[2], brk(thai)))
with open(dst, 'w', encoding='utf-8', newline='\n') as f:
    f.write('# member\tblock\toffset_in_block\tthai ( | = allowed line break, * = forced line break )\n')
    for o in out: f.write('\t'.join(o) + '\n')
print(f'{len(out)} rows -> {dst}')
