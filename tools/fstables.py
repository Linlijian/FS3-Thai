"""Name / help tables outside the dialogue scripts [V 2026-10-13]. Address scheme for translation files: block = record index, offset = 0.
Fixed-record tables (name field at record +0, cp950, NUL-terminated, zero-padded):
  Objects.bin   u32 count | count * 104 B, name[20]            (speaker labels, object names)   live copy in FS3UpdataChs.dat
  FS2_Items.bin name[40] 'FS2ItemData' | u32 count | count * 124 B, name[16]      (item names)  only in FS3Bin.dat
Offset table:
  FS2_ItemHelp.bin name[40] 'FS2ItemHelp' | u32 count | count * u32 offset (from blob start) | blob of NUL-terminated strings
  (tiles exactly) -- rewritten with new offsets, so any length fits.
Multi-list tables: name[40] | u32 header values @40 (some are list counts) | the offset lists back to back from `first`
| other records | at EOF one blob = the lists' NUL-terminated strings in list order (each list's offsets start at 0).
  FS2_Fighter.Bin     lists = header[0,2,5,6,7] = 100 (beast-seal) / 288 skills / 16 / 4 categories / 13 targets, first 0x48
  FS2_FighterHelp.bin lists = header[0,1,2] = 65 / 166 / 15 skill help, first 0x34                       (both only in FS3Bin.dat)
  Address: block = list number, offset = index in the list. Patched SAME-LENGTH, padded with spaces (the engine may find the sub-blobs by counting NULs, so their number never changes)."""
import struct
FIXED = {'Objects.bin': (0, 4, 104, 20), 'FS2_Items.bin': (40, 44, 124, 16)}   # count offset, first record, record size, name size
HELP = ('FS2_ItemHelp.bin',)
MULTI = {'FS2_Fighter.Bin': ((0, 2, 5, 6, 7), 0x48), 'FS2_FighterHelp.bin': ((0, 1, 2), 0x34)}   # header indices of list counts, first list
def kind(member):
    base = member.rsplit('/', 1)[-1]
    return base if base in FIXED or base in HELP or base in MULTI else None
def _multi(base, data):
    """-> [(list, index, abs_offset, raw)] ; blob start found by counting the strings back from EOF, then every offset checked"""
    which, first = MULTI[base]; hv = struct.unpack_from(f'<{max(which) + 1}I', data, 40); counts = [hv[i] for i in which]
    assert first == 40 + 4 * (max(which) + 1), base
    total, p = sum(counts), len(data) - 1; assert data[p] == 0
    for _ in range(total): p = data.rindex(b'\0', 0, p)
    pos, out, lp = p + 1, [], first
    for li, n in enumerate(counts):
        offs = struct.unpack_from(f'<{n}I', data, lp); lp += 4 * n; start = pos
        for k, o in enumerate(offs):
            assert start + o == pos, f'{base}: list {li} entry {k} offset mismatch'
            raw = data[pos:data.index(b'\0', pos)]; out.append((li, k, pos, raw)); pos += len(raw) + 1
    assert pos == len(data), base
    return out
def _fixed(base, data):
    co, first, rec, name = FIXED[base]; n, = struct.unpack_from('<I', data, co)
    assert first + n * rec == len(data), f'{base}: size != header + count*{rec}'
    return n, first, rec, name
def _help(data):
    n, = struct.unpack_from('<I', data, 40); off = struct.unpack_from(f'<{n}I', data, 44); blob = 44 + 4 * n
    strs = [data[blob + o: data.index(b'\0', blob + o)] for o in off]
    assert blob + sum(len(s) + 1 for s in strs) == len(data) and all(o == sum(len(s) + 1 for s in strs[:i]) for i, o in enumerate(off[:3])), 'help blob does not tile'
    return strs
def strs(member, data):
    """-> {(record, 0): raw bytes} for every non-empty string"""
    base = kind(member)
    if base in MULTI: return {(li, k): r for li, k, _, r in _multi(base, data) if r}
    if base in HELP: return {(i, 0): s for i, s in enumerate(_help(data)) if s}
    n, first, rec, name = _fixed(base, data)
    return {(i, 0): r for i in range(n) if (r := data[first + i * rec: first + i * rec + name].split(b'\0')[0])}
def slot_lens(member, data):
    base = kind(member)
    if base in MULTI: return {(li, k): len(r) for li, k, _, r in _multi(base, data) if r}
    room = 10 ** 6 if base in HELP else FIXED[base][3] - 1
    return {k: room for k in strs(member, data)}
def patch(member, data, edits):
    """edits: {(record, 0): new_bytes}; fixed tables: NUL-padded in place; help table: rebuilt with new offsets"""
    base = kind(member)
    if base in MULTI:
        b = bytearray(data); at = {(li, k): (pos, len(r)) for li, k, pos, r in _multi(base, data)}
        for key, new in edits.items():
            pos, n = at[key]; assert len(new) <= n, (member, key, len(new), n); b[pos:pos + n] = new.ljust(n, b' ')   # spaces, not NULs: the blob keeps its exact NUL layout
        return bytes(b)
    if base in HELP:
        s = _help(data)
        for (i, _), new in edits.items(): s[i] = new
        off, o = [], 0
        for x in s: off.append(o); o += len(x) + 1
        return data[:44] + struct.pack(f'<{len(s)}I', *off) + b''.join(x + b'\0' for x in s)
    n, first, rec, name = _fixed(base, data); b = bytearray(data)
    for (i, _), new in edits.items():
        assert len(new) < name, (i, len(new)); o = first + i * rec; b[o:o + name] = new.ljust(name, b'\0')
    return bytes(b)
def offset_of(member, data, blk, off):
    """byte offset of a written string (for verification)"""
    base = kind(member)
    if base in MULTI: return {(li, k): pos for li, k, pos, _ in _multi(base, data)}[(blk, off)]
    if base in HELP: return 44 + 4 * struct.unpack_from('<I', data, 40)[0] + struct.unpack_from('<I', data, 44 + 4 * blk)[0]
    _, first, rec, _ = _fixed(base, data); return first + blk * rec
if __name__ == '__main__':                                       # round trip on a game copy: patch nothing -> identical bytes
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import fszip
    for arc, m in (('FS3UpdataChs.dat', 'BIN/Objects.bin'), ('FS3Bin.dat.bak', 'Bin/FS2_Items.bin'), ('FS3Bin.dat.bak', 'Bin/FS2_ItemHelp.bin'),
                   ('FS3Bin.dat.bak', 'Bin/FS2_Fighter.Bin'), ('FS3Bin.dat.bak', 'Bin/FS2_FighterHelp.bin')):
        d = fszip.open_fszip(f'{sys.argv[1]}/Pack/{arc}').read(m); s = strs(m, d)
        assert patch(m, d, {}) == d and patch(m, d, dict(list(s.items())[:5])) == d, m
        print(m, len(s), 'strings, round trip OK')
