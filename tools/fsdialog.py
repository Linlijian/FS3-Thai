r"""Parser / writer for FS2Dialog (Bin/Dialog/DiaNNN.bin) and FS2AutoDialog (Bin/AutoDialog/AutoNNN.bin).
Layout (matches D:\FS3_TH_mod spec, re-verified here): name[40] | u32 count | count*(u32 f0,u32 abs_off,u32 len) | blocks (tile the file).
A block is compiled bytecode; text = groups of k NUL-terminated cp950 strings preceded by k descriptors
(stride 84 / rel_offset@+16 for FS2Dialog, 16 / @+12 for FS2AutoDialog; rel_offset = running sum of previous string lengths incl. NUL).
Writer modes: rebuild() = lossless re-serialise (identical bytes if untouched); patch_same_len() = safe in-place edit;
resize is NOT implemented because blocks contain block-relative jump targets that would need the opcode layer (Q1)."""
import struct, re
ENC = 'cp950'
LAYOUT = {'FS2Dialog': (84, 16), 'FS2AutoDialog': (16, 12)}
class Group:
    def __init__(s, block, start, strs): s.block, s.start, s.strs = block, start, strs   # strs: list of (abs_start_in_block, raw bytes)
def parse(data):
    name = data[:40].rstrip(b'\0').decode('ascii'); count, = struct.unpack_from('<I', data, 40)
    toc = [struct.unpack_from('<III', data, 44 + 12*i) for i in range(count)]
    cur = 44 + 12*count
    for f0, off, ln in toc:
        assert off == cur, 'TOC does not tile file'; cur = off + ln
    assert cur == len(data) or count == 0, 'TOC end != EOF'
    return name, toc
def _tokens(blk):
    out, i = [], 0
    while i < len(blk):
        j = blk.find(b'\0', i)
        if j < 0: break
        raw = blk[i:j]
        if not any(c < 0x20 for c in raw):
            try: raw.decode(ENC); out.append((i, raw))
            except UnicodeDecodeError: pass
        i = j + 1
    return out
def _cum(g):
    c = [0]
    for _, r in g[:-1]: c.append(c[-1] + len(r) + 1)
    return c
def _ok(blk, g, stride, fld):
    da = g[0][0] - len(g) * stride
    if da < 0: return False
    try: got = [struct.unpack_from('<I', blk, da + m*stride + fld)[0] for m in range(len(g))]
    except struct.error: return False
    return got == _cum(g)
def _by_desc(blk, run, stride, fld):
    """fallback for NUL-padded (same-length-edited) groups: trust the descriptor offsets instead of string lengths.
    Group = k descriptors right before a text token; offsets start at 0, increase, and each points just after a NUL."""
    for st, raw in run:
        if not any(b >= 0x80 for b in raw): continue
        best = None
        for k in range(1, 64):
            da = st - k * stride
            if da < 0: break
            try: offs = [struct.unpack_from('<I', blk, da + m*stride + fld)[0] for m in range(k)]
            except struct.error: break
            if offs[0] != 0 or any(b <= a for a, b in zip(offs, offs[1:])) or any(blk[st + o - 1] != 0 for o in offs[1:] if st + o < len(blk)): continue
            if st + offs[-1] >= len(blk): continue
            strs = [(st + o, blk[st + o: blk.find(b'\x00', st + o)]) for o in offs]
            try: [r.decode(ENC) for _, r in strs]
            except UnicodeDecodeError: continue
            best = strs
        if best: return best
    return None
def groups(name, data):
    """validated string groups only (descriptor offsets must match) -> list[Group]; also returns count of unvalidated text runs"""
    stride, fld = LAYOUT[name]; _, toc = parse(data); res, bad = [], 0
    for bi, (f0, off, ln) in enumerate(toc):
        blk = data[off:off+ln]; runs, cur = [], []
        for t in _tokens(blk):
            if cur and t[0] == cur[-1][0] + len(cur[-1][1]) + 1: cur.append(t)
            else: runs.append(cur); cur = [t]
        runs.append(cur)
        for run in runs:
            if not any(b >= 0x80 for _, r in run for b in r): continue
            hit = None
            for span in range(len(run), 0, -1):
                for st in range(len(run) - span + 1):
                    sub = run[st:st+span]
                    if any(b >= 0x80 for _, r in sub for b in r) and _ok(blk, sub, stride, fld): hit = sub; break
                if hit: break
            if not hit: hit = _by_desc(blk, run, stride, fld)
            if hit: res.append(Group(bi, hit[0][0], hit))
            else: bad += 1
    return res, bad
def rebuild(data):
    """parse -> serialise again from (name, count, toc, blocks). Identical to input by construction of the TOC rule; used by tests."""
    name, toc = parse(data)
    blocks = [data[o:o+l] for _, o, l in toc]; pos = 44 + 12*len(toc); out = bytearray(data[:40]) + struct.pack('<I', len(toc))
    for (f0, _, _), b in zip(toc, blocks): out += struct.pack('<III', f0, pos, len(b)); pos += len(b)
    return bytes(out) + b''.join(blocks)
def patch_same_len(data, edits):
    """edits: {(block, abs_start_in_block): new_bytes}; new must be <= old length, NUL-padded. Everything else untouched."""
    name, toc = parse(data); b = bytearray(data)
    g, _ = groups(name, data); index = {(x.block, s): r for x in g for s, r in x.strs}
    for (bi, st), new in edits.items():
        old = index[(bi, st)]; assert len(new) <= len(old), f'string at block {bi}+{st}: {len(new)} > {len(old)} bytes'
        o = toc[bi][1] + st; b[o:o+len(old)] = new.ljust(len(old), b'\0')
    return bytes(b)
MARK = re.compile(r'@@[A-Za-z]+(?:\([^)]*\))?@@|%[0-9]*[a-z]|\[A-Za-z0-9]|[<>{}\[\]|^~#$&]|\*')
