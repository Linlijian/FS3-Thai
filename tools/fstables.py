"""Name / help tables outside the dialogue scripts [V 2026-10-13]. Address scheme for translation files: block = record index, offset = 0.
Fixed-record tables (name field at record +0, cp950, NUL-terminated, zero-padded):
  Objects.bin   u32 count | count * 104 B, name[20]            (speaker labels, object names)   live copy in FS3UpdataChs.dat
  FS2_Items.bin name[40] 'FS2ItemData' | u32 count | count * 124 B, name[16]      (item names)  live copy in FS3UpdataChs.dat
  ArrayData.bin name[40] 'FS2ArrayData' | u32 groups | groups * (u32 first record, u32 count) | 282 * 636 B, name[12] at +4
                (battle formations, one record per level)                                     live copy in FS3UpdataChs.dat
Offset table:
  FS2_ItemHelp.bin name[40] 'FS2ItemHelp' | u32 count | count * u32 offset (from blob start) | blob of NUL-terminated strings
  (tiles exactly) -- rewritten with new offsets, so any length fits.
Multi-list tables: name[40] | u32 header values @40 (some are list counts) | the offset lists back to back from `first`
| other records | at EOF one blob = the lists' NUL-terminated strings in list order (each list's offsets start at 0).
  FS2_Fighter.Bin     lists = header[0,2,5,6,7] = 100 (beast-seal) / 288 skills / 16 / 4 categories / 13 targets, first 0x48
  FS2_FighterHelp.bin lists = header[0,1,2] = 65 / 166 / 15 skill help, first 0x34                       (both only in FS3Bin.dat)
  Address: block = list number, offset = index in the list. Patched SAME-LENGTH, padded with spaces (the engine may find the sub-blobs by counting NULs, so their number never changes).
Message table:
  Message.bin 'MSGV2.0' + NUL | u32 records @8 (931) | u32 strings @12 (798) | records * 48 B | strings * (u32 len incl. NUL, bytes)
  to EOF (UI labels, menus, system messages). No record value points into the string area (none in 1000..EOF), so the
  strings are taken by index and rewritten at any length. Address: block = string index, offset = 0.   live copy in FS3UpdataChs.dat
  printf templates ('%d', '%s', '@@W(10)@@' markup): only the Chinese pieces BETWEEN the specifiers are exported, offset =
  piece number 1.. ; the engine's own sprintf still fills in the values. ponytail: Thai keeps the source argument order."""
import struct, re
SPEC = re.compile(r'(@@[A-Za-z]+(?:\([^)]*\))?@@|%[-+ #0-9.]*[a-zA-Z]|%%)')   # kept as-is inside templates
def _pieces(raw):
    """template -> list of str parts; odd indices are specifiers / markup (split on decoded text: Big5 trail bytes can be '@')"""
    return SPEC.split(raw.decode('cp950', 'surrogateescape'))   # keys (Big5 user area FA/FB) are not in Python's cp950
def _tmpl_strs(i, raw):
    out, k = {}, 0
    for j, part in enumerate(_pieces(raw)):
        if j % 2 == 0 and part:
            k += 1
            if any(ord(c) >= 0x80 for c in part): out[(i, k)] = part.encode('cp950', 'surrogateescape')
    return out
FIXED = {'Objects.bin': (0, 4, 104, 20, 0), 'FS2_Items.bin': (40, 44, 124, 16, 0),      # count offset, first record, record size,
         'ArrayData.bin': (None, None, 636, 12, 4)}                                     # name size, name offset in the record
HELP = ('FS2_ItemHelp.bin', 'DefaultString.bin')   # same layout; DefaultString = loose CFG/ file (battle popups, mission goals)
MULTI = {'FS2_Fighter.Bin': ((0, 2, 5, 6, 7), 0x48), 'FS2_FighterHelp.bin': ((0, 1, 2), 0x34)}   # header indices of list counts, first list
MSG = ('Message.bin',)
def kind(member):
    base = member.rsplit('/', 1)[-1]
    return base if base in FIXED or base in HELP or base in MULTI or base in MSG else None
def _msg(data):
    """-> (start of the string area, [raw strings]) ; the length chain must end exactly at EOF"""
    assert data[:8] == b'MSGV2.0\x00', 'not MSGV2.0'
    nrec, nstr = struct.unpack_from('<2I', data, 8); p = start = 16 + 48 * nrec; out = []
    for _ in range(nstr):
        n, = struct.unpack_from('<I', data, p); assert n and data[p + 3 + n] == 0, ('Message.bin chain', p)
        out.append(data[p + 4:p + 3 + n]); p += 4 + n
    assert p == len(data), 'Message.bin: chain does not end at EOF'
    return start, out
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
    """-> (count, offset of record 0's NAME, record size, name size)"""
    co, first, rec, name, noff = FIXED[base]
    if first is None:                        # ArrayData: u32 groups @40, groups * (first record, count), then the records
        first = 44 + 8 * struct.unpack_from('<I', data, 40)[0]; n, r = divmod(len(data) - first, rec); assert not r, base
    else: n, = struct.unpack_from('<I', data, co)
    assert first + n * rec == len(data), f'{base}: size != header + count*{rec}'
    return n, first + noff, rec, name
def _help(data):
    n, = struct.unpack_from('<I', data, 40); off = struct.unpack_from(f'<{n}I', data, 44); blob = 44 + 4 * n
    strs = [data[blob + o: data.index(b'\0', blob + o)] for o in off]
    assert blob + sum(len(s) + 1 for s in strs) == len(data) and all(o == sum(len(s) + 1 for s in strs[:i]) for i, o in enumerate(off[:3])), 'help blob does not tile'
    return strs
def strs(member, data):
    """-> {(record, 0): raw bytes} for every non-empty string"""
    base = kind(member)
    if base in MULTI: return {(li, k): r for li, k, _, r in _multi(base, data) if r}
    if base in MSG or base in HELP:
        out = {}
        for i, r in enumerate(_msg(data)[1] if base in MSG else _help(data)):
            if b'%' in r: out.update(_tmpl_strs(i, r))                       # printf template: pieces between specifiers
            elif r: out[(i, 0)] = r
        return out
    n, first, rec, name = _fixed(base, data)
    return {(i, 0): r for i in range(n) if (r := data[first + i * rec: first + i * rec + name].split(b'\0')[0])}
def slot_lens(member, data):
    base = kind(member)
    if base in MULTI: return {(li, k): len(r) for li, k, _, r in _multi(base, data) if r}
    room = 10 ** 6 if base in HELP or base in MSG else FIXED[base][3] - 1      # whole name field minus the NUL
    return {k: room for k in strs(member, data)}
def patch(member, data, edits):
    """edits: {(record, 0): new_bytes}; fixed tables: NUL-padded in place; help table: rebuilt with new offsets"""
    base = kind(member)
    if base in MULTI:
        b = bytearray(data); at = {(li, k): (pos, len(r)) for li, k, pos, r in _multi(base, data)}
        for key, new in edits.items():
            pos, n = at[key]; assert len(new) <= n, (member, key, len(new), n); b[pos:pos + n] = new.ljust(n, b' ')   # spaces, not NULs: the blob keeps its exact NUL layout
        return bytes(b)
    if base in MSG or base in HELP:
        start, s = _msg(data) if base in MSG else (None, _help(data)); by = {}
        for (i, k), new in edits.items(): by.setdefault(i, {})[k] = new
        for i, e in by.items():
            if 0 in e: s[i] = e[0]; continue
            parts, k, out = _pieces(s[i]), 0, b''
            for j, part in enumerate(parts):
                if j % 2 == 0 and part: k += 1; out += e.get(k, part.encode('cp950', 'surrogateescape'))
                else: out += part.encode('cp950', 'surrogateescape')
            s[i] = out
        if base in MSG: return data[:start] + b''.join(struct.pack('<I', len(x) + 1) + x + bytes(1) for x in s)
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
    if base in MSG:
        start, s = _msg(data); return start + sum(4 + len(x) + 1 for x in s[:blk]) + 4
    if base in HELP: return 44 + 4 * struct.unpack_from('<I', data, 40)[0] + struct.unpack_from('<I', data, 44 + 4 * blk)[0]
    _, first, rec, _ = _fixed(base, data); return first + blk * rec
if __name__ == '__main__':                                       # round trip on a game copy: patch nothing -> identical bytes
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import fszip
    for arc, m in (('FS3UpdataChs.dat', 'BIN/Objects.bin'), ('FS3UpdataChs.dat', 'BIN/ArrayData.bin'), ('FS3UpdataChs.dat', 'BIN/Message.bin'), ('FS3Bin.dat.bak', 'Bin/FS2_Items.bin'), ('FS3Bin.dat.bak', 'Bin/FS2_ItemHelp.bin'),
                   ('FS3Bin.dat.bak', 'Bin/FS2_Fighter.Bin'), ('FS3Bin.dat.bak', 'Bin/FS2_FighterHelp.bin')):
        d = fszip.open_fszip(f'{sys.argv[1]}/Pack/{arc}').read(m); s = strs(m, d)
        assert patch(m, d, {}) == d and patch(m, d, dict(list(s.items())[:5])) == d, m
        print(m, len(s), 'strings, round trip OK')
