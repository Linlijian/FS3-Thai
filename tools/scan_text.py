"""Rank files by amount of Big5 / GBK double-byte text. usage: scan_text.py <dir> [topN]"""
import os, re, sys
b5 = re.compile(rb'(?:[\xa4-\xc6\xc9-\xf9][\x40-\x7e\xa1-\xfe]){3,}')
gb = re.compile(rb'(?:[\xb0-\xf7][\xa1-\xfe]){3,}')
def ok(rx, data, enc):
    n = 0
    for m in rx.finditer(data):
        try: m.group().decode(enc); n += len(m.group())
        except UnicodeDecodeError: pass
    return n
res = []
for d,_,fs in os.walk(sys.argv[1]):
    for f in fs:
        p = os.path.join(d,f); data = open(p,'rb').read()
        if f.lower().endswith(('.dds','.tga','.mp3','.wav','.bwn','.cfx','.png')) or len(data) > 30_000_000: continue
        if data[:5] == b'<?xml' or f.lower().endswith(('.xml','.ini','.txt')):
            try: data.decode('utf-8'); res.append((len(data), 0, 0, 'UTF8-TEXT', p)); continue
            except UnicodeDecodeError: pass
        res.append((len(data), ok(b5,data,'big5'), ok(gb,data,'gbk'), '', p))
res.sort(key=lambda r: -(r[1]+r[2]))
for r in res[:int(sys.argv[2]) if len(sys.argv)>2 else 40]: print(r[0], 'big5', r[1], 'gbk', r[2], r[3], os.path.relpath(r[4], sys.argv[1]).replace(os.sep,'/'))
