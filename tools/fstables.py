"""Name / help tables outside the dialogue scripts [V 2026-10-13]. Address scheme for translation files: block = record index, offset = 0.
Fixed-record tables (name field at record +0, cp950, NUL-terminated, zero-padded):
  Objects.bin   u32 count | count * 104 B, name[20]            (speaker labels, object names)   live copy in FS3UpdataChs.dat
  FS2_Items.bin name[40] 'FS2ItemData' | u32 count | count * 124 B, name[16]      (item names)  only in FS3Bin.dat
Offset table:
  FS2_ItemHelp.bin name[40] 'FS2ItemHelp' | u32 count | count * u32 offset (from blob start) | blob of NUL-terminated strings
  (tiles exactly) -- rewritten with new offsets, so any length fits."""
import struct
FIXED = {'Objects.bin': (0, 4, 104, 20), 'FS2_Items.bin': (40, 44, 124, 16)}   # count offset, first record, record size, name size
HELP = ('FS2_ItemHelp.bin',)
def kind(member):
    base = member.rsplit('/', 1)[-1]
    return base if base in FIXED or base in HELP else None
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
    if base in HELP: return {(i, 0): s for i, s in enumerate(_help(data)) if s}
    n, first, rec, name = _fixed(base, data)
    return {(i, 0): r for i in range(n) if (r := data[first + i * rec: first + i * rec + name].split(b'\0')[0])}
def slot_lens(member, data):
    base = kind(member); room = 10 ** 6 if base in HELP else FIXED[base][3] - 1
    return {k: room for k in strs(member, data)}
def patch(member, data, edits):
    """edits: {(record, 0): new_bytes}; fixed tables: NUL-padded in place; help table: rebuilt with new offsets"""
    base = kind(member)
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
def offset_of(member, data, rec_index, key_len):
    """byte offset of a written string (for verification)"""
    base = kind(member)
    if base in HELP: return 44 + 4 * struct.unpack_from('<I', data, 40)[0] + struct.unpack_from('<I', data, 44 + 4 * rec_index)[0]
    _, first, rec, _ = _fixed(base, data); return first + rec_index * rec
if __name__ == '__main__':                                       # round trip on a game copy: patch nothing -> identical bytes
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import fszip
    for arc, m in (('FS3UpdataChs.dat', 'BIN/Objects.bin'), ('FS3Bin.dat.bak', 'Bin/FS2_Items.bin'), ('FS3Bin.dat.bak', 'Bin/FS2_ItemHelp.bin')):
        d = fszip.open_fszip(f'{sys.argv[1]}/Pack/{arc}').read(m); s = strs(m, d)
        assert patch(m, d, {}) == d and patch(m, d, dict(list(s.items())[:5])) == d, m
        print(m, len(s), 'strings, round trip OK')
