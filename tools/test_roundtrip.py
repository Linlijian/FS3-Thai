"""Round-trip tests. UJ pak: parse -> rebuild -> compare bytes. FS-ZIP: de-obfuscate -> rebuild -> compare bytes/content.
usage: test_roundtrip.py <game_copy> [--set original|patched]. Exit 1 on any UJ mismatch."""
import os, sys, hashlib, mmap, zipfile, io
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ujpak, fszip, fsset
mode = fsset.parse_set(sys.argv); game = sys.argv[1]; fail = 0
def first_diff(a, b):
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]: return i
    return n if len(a) != len(b) else -1
for n, p in fsset.archives(game, mode):
    raw = open(p, 'rb').read()
    if raw[:4] == b'UJ  ':
        out = ujpak.roundtrip(raw)
        d = first_diff(raw, out)
        print(f'{n:22s} UJ  {"IDENTICAL" if d < 0 else f"DIFF at 0x{d:x} (src {len(raw)} B, rebuilt {len(out)} B)"}  sha256 {hashlib.sha256(out).hexdigest()[:16]}')
        fail |= d >= 0
    elif raw[:4] == b'\x03\x05\x03\x04':
        z = fszip.open_fszip(p)
        out = fszip.write_like(z, raw)
        z2 = fszip.open_fszip_bytes(out)
        same = [i.filename for i in z.infolist()] == [i.filename for i in z2.infolist()] and all(z.read(i) == z2.read(i.filename) for i in z.infolist())
        d = first_diff(raw, out); un = fszip.write_like.unreproducible
        print(f'{n:22s} ZIP content {"IDENTICAL" if same else "DIFFERS"}; bytes {"IDENTICAL" if d < 0 else f"DIFFER at 0x{d:x} (src {len(raw)} B, rebuilt {len(out)} B)"}; streams not reproducible by zlib: {len(un)} {un[:3]}')
        fail |= (not same) or d >= 0
sys.exit(1 if fail else 0)
