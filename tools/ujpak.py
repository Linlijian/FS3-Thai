"""Reader for the 'UJ  ' nested pak format (FS3Data.pak etc).
Layout (all LE): header 0x80 bytes: magic 'UJ  ', u16 ver, u32 total_size, u32 index_off(rel to pak start),
u32 count (at 0x0e), name[] at 0x12.  Index = count * 128-byte entries at index_off:
name[64] | u32 off @0x40 | u32 size @0x44 | u32 flag @0x48 | 52 bytes (see docs).
Entries whose payload starts with 'UJ  ' are sub-paks (offsets relative to the *sub-pak* start)."""
import struct, sys
def entries(buf, base=0):
    magic, ver, tot, idx, cnt = struct.unpack_from('<4sHIII', buf, base)
    assert magic == b'UJ  ', (base, magic)
    for i in range(cnt):
        e = buf[base+idx+i*128: base+idx+(i+1)*128]
        name = e[:64].split(b'\0')[0].decode('latin1')
        off, size, flag = struct.unpack_from('<III', e, 0x40)
        yield name, base+off, size, flag, e[0x4c:]
def walk(buf, base=0, path=''):
    for name, off, size, flag, rest in entries(buf, base):
        p = f'{path}/{name}'
        if buf[off:off+4] == b'UJ  ':
            yield from walk(buf, off, p)
        else:
            yield p, off, size, flag, rest
if __name__ == '__main__':
    import mmap
    with open(sys.argv[1], 'rb') as f:
        m = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        n = 0
        for p, off, size, flag, rest in walk(m):
            n += 1
            if n <= int(sys.argv[2] if len(sys.argv) > 2 else 15): print(p, off, size, flag, rest.hex()[:40])
        print('leaf files', n)

# ---- tree + writer (round-trip) ----
class Node:
    """dir (children is list) or file (data bytes). hdr = the 0x80-byte header remainder after the 0x12 name field (kept verbatim)."""
    def __init__(s, name, data=None, children=None, pak_name=None, flag=0, ent_rest=b'\0'*52):
        s.name, s.data, s.children, s.pak_name, s.flag, s.ent_rest = name, data, children, pak_name, flag, ent_rest
def read_tree(buf, base=0):
    """returns the list of child Nodes of the pak at `base` plus (pak_name, ver)."""
    magic, ver, tot, idx, cnt = struct.unpack_from('<4sHIII', buf, base)
    pname = bytes(buf[base+0x12:base+0x80]).split(b'\0')[0].decode('latin1')
    kids = []
    for name, off, size, flag, rest in entries(buf, base):
        if buf[off:off+4] == b'UJ  ':
            sub, sname, _ = read_tree(buf, off)
            kids.append(Node(name, children=sub[0], pak_name=sname, flag=flag, ent_rest=bytes(rest)))
        else:
            kids.append(Node(name, data=bytes(buf[off:off+size]), flag=flag, ent_rest=bytes(rest)))
    return (kids, pname, ver), pname, ver
def build(kids, pak_name, ver=1):
    body = bytearray(); ents = []
    for k in kids:
        off = 0x80 + len(body)
        blob = build(k.children, k.pak_name, ver) if k.children is not None else k.data
        body += blob
        ents.append(k.name.encode('latin1').ljust(64, b'\0') + struct.pack('<III', off, len(blob), k.flag) + k.ent_rest)
    idx = 0x80 + len(body)
    hdr = bytearray(0x80); hdr[:4] = b'UJ  '
    struct.pack_into('<HIII', hdr, 4, ver, idx + 128*len(kids), idx, len(kids))
    hdr[0x12:0x12+len(pak_name)] = pak_name.encode('latin1')
    return bytes(hdr) + bytes(body) + b''.join(ents)
def roundtrip(buf):
    (kids, pname, ver), _, _ = read_tree(buf)
    return build(kids, pname, ver)
