"""Chinese strings hardcoded in FS3.exe (readable .rdata/.data only; the .text section is DRM-encrypted and FS3.exe is never
modified). They are translated at draw time by the proxy: build_keys.py writes FS3_TH_exe.txt = <drawn pattern> TAB <thai>,
where the pattern is the string as the engine draws it (Big5 -> BIG2GB.idx -> GBK -> UTF-16) and %s / %d stay wildcards.
Address in translation files: member FS3.exe, block = file offset, offset 0."""
import re, struct
def strs(exe):
    pe, = struct.unpack_from('<I', exe, 0x3c); n, = struct.unpack_from('<H', exe, pe + 6); opt, = struct.unpack_from('<H', exe, pe + 20)
    out = {}
    for k in range(n):
        name, _, _, size, raw = struct.unpack_from('<8sIIII', exe, pe + 24 + opt + 40 * k)
        if name.rstrip(b'\0') not in (b'.rdata', b'.data'): continue
        for m in re.finditer(rb'(?:[\x09\x0a\x0d\x20-\x7e]|[\xa1-\xf9][\x40-\x7e\xa1-\xfe])+\x00', exe[raw:raw + size]):
            s = m.group()[:-1]; pairs = re.findall(rb'[\xa1-\xf9][\x40-\x7e\xa1-\xfe]', s)
            if len(pairs) >= 2 and all(0xa140 <= int.from_bytes(p, 'big') <= 0xc67e for p in pairs): out[(raw + m.start(), 0)] = s
    return out
def drawn(raw, big2gb):
    """Big5 bytes -> the UTF-16 text the engine draws (its own Big5 -> GBK table, then GBK)"""
    out, i = bytearray(), 0
    while i < len(raw):
        if raw[i] >= 0x80: w = raw[i] | raw[i + 1] << 8; out += big2gb[w * 2:w * 2 + 2]; i += 2
        else: out.append(raw[i]); i += 1
    return out.decode('gbk')
