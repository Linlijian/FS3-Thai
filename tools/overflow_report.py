"""List the translations that do not fit the dialogue box, from a proxy log made with box_lines=3.
usage: overflow_report.py <FS3_TH_hook.log> <FS3_TH_ids.tsv from build_keys.py>
Prints member <TAB> block <TAB> offset <TAB> lines  -- the same addresses as the translation TSV."""
import re, sys, collections
log, idsf = sys.argv[1:3]
over = {int(m[1]): int(m[2]) for m in re.finditer(r'overflow: key (\d+) needs (\d+) lines', open(log, encoding='utf-8', errors='replace').read())}
rows = collections.defaultdict(list)
for ln in open(idsf, encoding='utf-8'):
    if not ln.startswith('#'): i, *addr = ln.rstrip('\n').split('\t'); rows[int(i)].append(addr)
for i, n in sorted(over.items()):
    for addr in rows.get(i, [['?', '?', '?']]): print(*addr, n, sep='\t')
print(f'# {len(over)} text(s), {sum(len(rows.get(i, [1])) for i in over)} slot(s) too long', file=sys.stderr)
