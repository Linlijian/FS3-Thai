"""Analyse DrawTextA/W lines from the proxy log (log_drawtext=1). usage: analyze_drawtext.py <log>
Reports: format flags in use, CALCRECT measurements (px per char), box widths, callers (module+RVA) with sample text."""
import sys, re, collections
FLAGS = {0x0: 'TOP', 0x1: 'CENTER', 0x2: 'RIGHT', 0x4: 'VCENTER', 0x8: 'BOTTOM', 0x10: 'WORDBREAK', 0x20: 'SINGLELINE', 0x40: 'EXPANDTABS',
         0x100: 'NOCLIP', 0x400: 'CALCRECT', 0x800: 'NOPREFIX', 0x10000: 'RTLREADING', 0x8000: 'EDITCONTROL', 0x8000: 'PATH_ELLIPSIS?'}
def names(f): return '|'.join(n for b, n in sorted(FLAGS.items()) if b and f & b) or 'LEFT|TOP'
lines = open(sys.argv[1], encoding='latin1').read().splitlines(); ev = []
for i, ln in enumerate(lines):
    m = re.match(r'DrawText([AW]) ret=(-?\d+) cnt=(-?\d+) fmt=0x([0-9a-f]+) col=([0-9a-f]+) rect_in=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) rect_out=\((-?\d+),(-?\d+),(-?\d+),(-?\d+)\) caller=(\S+)', ln)
    if not m: continue
    txt = ''
    for nxt in lines[i+1:i+3]:
        h = re.match(r'\s+bytes len=\d+ hex=([0-9a-f ]*)\|', nxt); w = re.match(r'\s+wide n=\d+ utf16=([0-9a-f ]*)', nxt)
        if h and m[1] == 'A': txt = bytes.fromhex(h[1].replace(' ', '')).decode('gbk', 'replace').rstrip(chr(0)); break
        if w and m[1] == 'W': txt = ''.join(chr(int(x, 16)) for x in w[1].split()); break
    v = list(map(int, m.group(6, 7, 8, 9, 10, 11, 12, 13)))
    ev.append(dict(api=m[1], ret=int(m[2]), fmt=int(m[4], 16), rin=v[:4], rout=v[4:], caller=m[14], txt=txt))
print('DrawText events (deduped by proxy):', len(ev), collections.Counter(e['api'] for e in ev))
print('\nformat flags:'); [print(f'  0x{f:x} {names(f):38s} {n}') for f, n in collections.Counter(e['fmt'] for e in ev).most_common(12)]
calc = [e for e in ev if e['fmt'] & 0x400 and e['txt']]
print(f'\nCALCRECT (measure) calls: {len(calc)}')
for e in calc[:12]:
    w = e['rout'][2] - e['rout'][0]; h = e['rout'][3] - e['rout'][1]; t = e['txt']
    print(f'  {len(t):3d} chars  w={w:4d}px h={h:3d}px  ({w / max(1, len(t)):.1f} px/char)  {t[:30]!r}  from {e["caller"]}')
boxes = collections.Counter((e['rin'][2] - e['rin'][0]) for e in ev if not e['fmt'] & 0x400 and e['rin'][2] > e['rin'][0])
print('\ncommon box widths (rect_in, non-measure):', boxes.most_common(8))
print('lines containing * (engine passes the break marker to D3DX?):', sum(1 for e in ev if '*' in e['txt']), '| containing newline:', sum(1 for e in ev if '\n' in e['txt']))
print('\ncallers:')
by = collections.defaultdict(list)
for e in ev: by[e['caller']].append(e)
for c, l in sorted(by.items(), key=lambda kv: -len(kv[1]))[:14]:
    print(f'  {c:28s} x{len(l):5d} fmt={sorted({hex(x["fmt"]) for x in l})[:3]} e.g. {l[0]["txt"][:24]!r}')
