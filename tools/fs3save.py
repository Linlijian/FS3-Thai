"""Fill the item bag of an FS3 save (Save/Uj_FS*.sav) with weapons / armor / medicine for testing.

Save format [V 2026-10-22, 7 saves compared]: raw struct dump, size and section offsets fixed. The bag is
    u32 count N | N * 140 B { u32 item id (= record index in FS2_Items.bin), u32 qty, 128 zero bytes }
at a fixed-capacity block (everything after it is zero up to the next section), so adding records in place
and raising N keeps the file size. The 8 bytes at 0x58 are not a content checksum (three different saves
share them). The bag capacity is NOT known; a real ending save holds 407 records, hence --limit 400.

    python tools/fs3save.py Save/Uj_FS05.sav [--types 2,3,4,5,6,14,7,10,8] [--limit 400] [--out FILE]
    python tools/fs3save.py Save/Uj_FS05.sav --names      party names saved as Thai-mod KEYS -> the original Chinese names
Without --out the save is replaced in place after a copy goes to work/save_backup/.

Party table in the header: name[20] at 0x94 + k * 0x2c, u32 character id just before it (id = Objects.bin record + 1).
A character's name is copied from Objects.bin when they join; under the mod that copy is a key, which pointed at another
text once build_keys renumbered ids (plana-b4). Chinese names are drawn in Thai by the proxy (FS3_TH_exe.txt), so they
are safe in any build.
"""
import argparse
import shutil
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import fszip
import fstables

ROOT = Path(__file__).resolve().parent.parent
REC = 140
KEY = bytes.fromhex('fa41')  # Big5 code of the Thai-mod key marker U+E000
CONSUMABLE = {13, 14, 19}  # darts, medicine, materials: stack to 99; equipment gets 1


def item_table():
    """-> [(name, type)] for every FS2_Items record (original Chinese table, so junk names can be skipped)."""
    z = fszip.open_fszip(ROOT / 'Pack' / 'FS3UpdataChs.dat.orig')
    d = z.read(next(n for n in z.namelist() if n.lower() == 'bin/fs2_items.bin'))
    n, = struct.unpack_from('<I', d, 40)
    return [(d[44 + i * 124:60 + i * 124].split(b'\0')[0].decode('cp950', 'replace'),
             struct.unpack_from('<I', d, 60 + i * 124)[0]) for i in range(n)]


def fix_names(d):
    """-> (save with every party-name KEY replaced by the Chinese name, {key: name})."""
    z = fszip.open_fszip(fszip.orig(str(ROOT), 'Pack/FS3UpdataChs.dat'))
    names = fstables.strs('BIN/Objects.bin', z.read('BIN/Objects.bin'))
    d, fixed = bytearray(d), {}
    for k in range(8):
        o = 0x94 + k * 0x2c
        cid, = struct.unpack_from('<I', d, o - 4)
        if d[o:o + 2] == KEY and (cid - 1, 0) in names:
            fixed[bytes(d[o:o + 6])] = names[(cid - 1, 0)]
    for key, name in fixed.items():  # every copy (header + character records), only where the field is key + zeros
        i = d.find(key)
        while i >= 0:
            if not any(d[i + 6:i + len(name) + 1]):
                d[i:i + 6] = bytes(6)
                d[i:i + len(name)] = name
            i = d.find(key, i + 1)
    return bytes(d), fixed


def find_bag(d, n_items):
    """-> offset of the count word: N followed by exactly N plausible 140-byte records."""
    for o in range(0x100, len(d) - 4, 4):
        n, = struct.unpack_from('<I', d, o)
        if not 10 <= n <= 1000 or o + 4 + n * REC > len(d):
            continue
        recs = [o + 4 + k * REC for k in range(n)]
        if all(struct.unpack_from('<I', d, r)[0] < n_items and 0 < struct.unpack_from('<I', d, r + 4)[0] < 1000
               and not any(d[r + 8:r + REC]) for r in recs):
            return o
    raise SystemExit('item bag not found in this save')


def fill(d, items, types, limit):
    d = bytearray(d)
    o = find_bag(d, len(items))
    n, = struct.unpack_from('<I', d, o)
    have = {struct.unpack_from('<I', d, o + 4 + k * REC)[0]: o + 4 + k * REC for k in range(n)}
    want = [i for t in types for i, (nm, ty) in enumerate(items)
            if ty == t and nm not in ('', '保留') and not nm.lower().startswith('uj')]
    added = 0
    for i in want:
        qty = 99 if items[i][1] in CONSUMABLE else 1
        if i in have:  # already owned: only top up consumables
            r = have[i]
            if items[i][1] in CONSUMABLE:
                struct.pack_into('<I', d, r + 4, max(qty, struct.unpack_from('<I', d, r + 4)[0]))
        elif n < limit:
            r = o + 4 + n * REC
            d[r:r + REC] = struct.pack('<II', i, qty) + bytes(REC - 8)
            n += 1
            added += 1
    struct.pack_into('<I', d, o, n)
    return bytes(d), o, added, n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('save')
    ap.add_argument('--types', default='2,3,4,5,6,14,7,10,8', help='item types in priority order')
    ap.add_argument('--limit', type=int, default=400, help='max bag records')
    ap.add_argument('--out')
    ap.add_argument('--names', action='store_true', help='replace party-name keys by the Chinese names')
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    src = Path(a.save)
    old = src.read_bytes()
    if a.names:
        new, fixed = fix_names(old)
        assert len(new) == len(old) and not any(new[0x94 + k * 0x2c:0x96 + k * 0x2c] == KEY for k in range(8)), 'a party name is still a key'
        msg = ', '.join(f'{k.hex()} -> {v.decode("cp950")}' for k, v in fixed.items()) or 'no keys in the party table'
    else:
        new, o, added, n = fill(old, item_table(), [int(t) for t in a.types.split(',')], a.limit)
        # self-check: same size, and only the bag block changed
        assert len(new) == len(old)
        diff = [i for i in range(len(old)) if old[i] != new[i]]
        assert not diff or (o <= diff[0] and diff[-1] < o + 4 + n * REC), 'edit escaped the bag block'
        msg = f'bag @ {o:#x}: +{added} records, now {n} (limit {a.limit})'
    out = Path(a.out) if a.out else src
    if new != old:
        if out == src:
            bak = ROOT / 'work' / 'save_backup'
            bak.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, bak / f'{src.stem}.{time.strftime("%Y%m%d_%H%M%S")}.sav')
        out.write_bytes(new)
    print(f'{msg}; {"wrote " + str(out) if new != old else "unchanged"}')


if __name__ == '__main__':
    main()
