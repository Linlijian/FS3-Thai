"""Analyse a proxy log made with log_mb2wc=2. usage: analyze_mb2wc.py <log> [missing_chars.csv]
Pairs each MultiByteToWideChar input (bytes) with its 'out' UTF-16 line, compares with Python's cp936 decode, and reports chars where they differ."""
import sys, re, csv, collections
log = open(sys.argv[1], encoding='latin1').read().splitlines()
calls = []; cur = None
for ln in log:
    m = re.match(r'MultiByteToWideChar cp=(\d+) flags=(\d+) len=(\d+)(.*)', ln)
    if m: cur = {'cp': int(m[1]), 'bytes': None, 'out': None, 'thai': 'THAI' in m[4]}; calls.append(cur); continue
    if cur is None: continue
    m = re.match(r'\s+bytes len=(\d+) hex=([0-9a-f ]*)\|', ln)
    if m: cur['bytes'] = bytes.fromhex(m[2].replace(' ', '')); continue
    m = re.match(r'\s+out n=(\d+) utf16=([0-9a-f ]*)', ln)
    if m: cur['out'] = [int(x, 16) for x in m[2].split()]
done = [c for c in calls if c['bytes'] is not None and c['out'] is not None]
print('calls', len(calls), '| with out', len(done), '| cps', collections.Counter(c['cp'] for c in calls))
mism = collections.Counter(); ex = {}
for c in done:
    if c['cp'] != 936: continue
    b = c['bytes'].rstrip(b'\0'); exp = [ord(ch) for ch in b.decode('gbk', errors='replace')]
    out = [u for u in c['out'] if u]
    if exp != out and not c['thai']:
        for e, o in zip(exp, out): 
            if e != o: mism[(e, o)] += 1; ex.setdefault((e, o), b.hex(' '))
print('calls whose output != cp936 decode (non-Thai):', sum(mism.values()), 'distinct pairs', len(mism))
for (e, o), n in mism.most_common(15): print(f'  expected U+{e:04X} got U+{o:04X} x{n}  e.g. {ex[(e, o)][:40]}')
# targeted: where do the test chars show up on the wire?
tests = {'雲': 'B6B3', '祕': 'AFA6', '薙': '', '屍': '', '甕': '', '犽': '', '豐': '', '瞭': '', '裡': 'B8CC', '‧': ''}
allout = collections.Counter(u for c in done for u in c['out'])
for ch in tests:
    cands = {ch: allout.get(ord(ch), 0)}
    print(f'{ch} U+{ord(ch):04X}: in output {allout.get(ord(ch),0)}x')
# GBK byte pairs seen on the wire that map to a character absent from the original b2g set?
seen = collections.Counter()
for c in done:
    if c['cp'] != 936: continue
    b = c['bytes']; i = 0
    while i < len(b) - 1:
        if b[i] >= 0x81: seen[b[i:i+2]] += 1; i += 2
        else: i += 1
print('distinct GBK pairs on the wire:', len(seen))
open('work/mb2wc_pairs.txt', 'w', encoding='utf-8').write('\n'.join(f'{k.hex()} {k.decode("gbk","replace")} {v}' for k, v in sorted(seen.items())))
