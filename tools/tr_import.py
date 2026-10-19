"""Merge a translated batch into the master sheet, checking every row.
usage: tr_import.py <master.tsv> <batch.tsv> [--write] [--overwrite] [--force]
batch rows: member, block, offset, source, thai  (same 5 columns as the master). Without --write only reports.
Checks per row: address exists and its source equals the master's (batch not made from another sheet), control codes (@@..@@, %s %d) are
the same multiset as in the source. Rows with problems are listed and NOT merged; existing translations are kept unless --overwrite.
Also used by tr.py (import of a whole export folder)."""
import sys, re, collections
codes = lambda s: collections.Counter(re.findall(r'@@[^@]*@@|%[-+ #0-9.]*[a-zA-Z]', s))
def load(p): return [ln.rstrip('\n').split('\t') for ln in open(p, encoding='utf-8')]
def save(p, M): open(p, 'w', encoding='utf-8', newline='\n').write('\n'.join('\t'.join(r) for r in M) + '\n')
def index(M): return {(r[0], r[1], r[2]): i for i, r in enumerate(M) if len(r) == 5 and not r[0].startswith('#')}
def merge(M, idx, rows, over=False, where=''):
    """rows -> (merged, kept, bad[(where+line, reason)]); modifies M"""
    ok, kept, bad = 0, 0, []
    for n, r in enumerate(rows, 1):
        if not r or not r[0] or r[0].startswith('#'): continue
        if len(r) != 5: bad.append((f'{where}{n}', f'{len(r)} columns')); continue
        i = idx.get((r[0], r[1], r[2]))
        if i is None: bad.append((f'{where}{n}', 'address not in master')); continue
        if M[i][3] != r[3]: bad.append((f'{where}{n}', 'source differs from master')); continue
        if not r[4].strip() or r[4] == M[i][4]: continue                          # untranslated, or unchanged
        if codes(r[3]) != codes(r[4]): bad.append((f'{where}{n}', f'control codes differ: {dict(codes(r[3]) - codes(r[4]))} missing, {dict(codes(r[4]) - codes(r[3]))} extra')); continue
        if M[i][4].strip() and not over: kept += 1; continue
        M[i][4] = r[4]; ok += 1
    return ok, kept, bad
if __name__ == '__main__':
    master, batch = sys.argv[1:3]; write = '--write' in sys.argv
    M = load(master); ok, kept, bad = merge(M, index(M), load(batch), '--overwrite' in sys.argv)
    print(f'{ok} merged, {kept} already translated (kept), {len(bad)} rejected')
    for w, why in bad: print(f'  batch line {w}: {why}')
    if write and (not bad or '--force' in sys.argv): save(master, M); print('written', master)
    elif write: print('NOT written: fix the rejected rows first (or --force to merge the good ones)')
