"""Thai channel = the user's 87-entry map (FS3_TH_map.txt: 'GBKPAIR UNICODE  # ... via big5 XXXX').
Thai char -> reserved Big5 code (stored in game text) -> b2g.dat entry -> reserved GBK pair -> proxy MB2WC hook -> U+0E.."""
import re
def load_map(path):
    t2b, pair = {}, {}
    for ln in open(path, encoding='latin1'):
        m = re.match(r'([0-9A-Fa-f]{4})\s+([0-9A-Fa-f]{4}).*via big5 ([0-9A-Fa-f]{4})', ln)
        if m: g, u, b = (int(x, 16) for x in m.groups()); t2b[chr(u)] = b; pair[b] = g
    return t2b, pair
def encode(text, t2b):
    out = bytearray()
    for ch in text:
        if ch in t2b: out += t2b[ch].to_bytes(2, 'big')
        elif ord(ch) < 0x80: out += ch.encode('ascii')
        else: raise ValueError(f'no channel code for {ch!r} U+{ord(ch):04X}')
    return bytes(out)
def decode(raw, t2b):
    b2t = {v: k for k, v in t2b.items()}; out = []; i = 0
    while i < len(raw):
        if raw[i] >= 0x80: out.append(b2t.get(int.from_bytes(raw[i:i+2], 'big'), '?')); i += 2
        else: out.append(chr(raw[i])); i += 1
    return ''.join(out)
