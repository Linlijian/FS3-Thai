"""Merge a translated batch into the master sheet, checking every row.
usage: tr_import.py <master.tsv> <batch.tsv> [--write]
batch rows: member, block, offset, source, thai  (same 5 columns as the master). Without --write only reports.
Checks per row: address exists and its source equals the master's (batch not made from another sheet), control codes (@@..@@, %s %d) are
the same multiset as in the source, thai not empty. Rows with problems are listed and NOT merged; existing translations are kept unless --overwrite."""
import sys, re, collections
master, batch = sys.argv[1:3]; write = '--write' in sys.argv; over = '--overwrite' in sys.argv
rd = lambda p: [ln.rstrip('\n').split('\t') for ln in open(p, encoding='utf-8')]
M = rd(master); idx = {(r[0], r[1], r[2]): i for i, r in enumerate(M) if len(r) == 5 and not r[0].startswith('#')}
codes = lambda s: collections.Counter(re.findall(r'@@[^@]*@@|%[-+ #0-9.]*[a-zA-Z]', s))
ok, bad, kept = 0, [], 0
for n, r in enumerate(rd(batch), 1):
    if not r or r[0].startswith('#'): continue
    if len(r) != 5: bad.append((n, f'{len(r)} columns')); continue
    i = idx.get((r[0], r[1], r[2]))
    if i is None: bad.append((n, 'address not in master')); continue
    if M[i][3] != r[3]: bad.append((n, 'source differs from master')); continue
    if not r[4].strip(): continue                                            # untranslated row of the batch: nothing to merge
    if codes(r[3]) != codes(r[4]): bad.append((n, f'control codes differ: {dict(codes(r[3]) - codes(r[4]))} missing, {dict(codes(r[4]) - codes(r[3]))} extra')); continue
    if M[i][4].strip() and not over: kept += 1; continue
    M[i][4] = r[4]; ok += 1
print(f'{ok} merged, {kept} already translated (kept), {len(bad)} rejected')
for n, why in bad: print(f'  batch line {n}: {why}')
if write and not bad or write and '--force' in sys.argv:
    open(master, 'w', encoding='utf-8', newline='\n').write('\n'.join('\t'.join(r) for r in M) + '\n'); print('written', master)
elif write: print('NOT written: fix the rejected rows first (or --force to merge the good ones)')
