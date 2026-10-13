"""FS3 *.dat archives are ZIPs whose 'PK' signatures were replaced by 03 05.
Patch the 4-byte signatures at the exact offsets (EOCD -> central dir -> local headers) and open with zipfile."""
import struct, io, zipfile
SIG = {b'\x03\x05\x03\x04': b'PK\x03\x04', b'\x03\x05\x01\x02': b'PK\x01\x02', b'\x03\x05\x05\x06': b'PK\x05\x06'}
def open_fszip(path):
    return open_fszip_bytes(open(path, 'rb').read())
def open_fszip_bytes(data):
    b = bytearray(data)
    e = b.rfind(b'\x03\x05\x05\x06'); assert e >= 0, 'no EOCD'
    n, = struct.unpack_from('<H', b, e+10); cd, = struct.unpack_from('<I', b, e+16)
    b[e:e+4] = b'PK\x05\x06'; p = cd
    for _ in range(n):
        assert b[p:p+4] == b'\x03\x05\x01\x02', (p, bytes(b[p:p+4]))
        nl, xl, cl = struct.unpack_from('<HHH', b, p+28); lo, = struct.unpack_from('<I', b, p+42)
        b[p:p+4] = b'PK\x01\x02'
        assert b[lo:lo+4] == b'\x03\x05\x03\x04', (lo, bytes(b[lo:lo+4])); b[lo:lo+4] = b'PK\x03\x04'
        p += 46 + nl + xl + cl
    return zipfile.ZipFile(io.BytesIO(bytes(b)))
def obfuscate(zbytes):
    """standard ZIP bytes -> FS-ZIP (PK -> 03 05) using the same EOCD/central-dir walk."""
    b = bytearray(zbytes); e = b.rfind(b'PK'); n, = struct.unpack_from('<H', b, e+10); cd, = struct.unpack_from('<I', b, e+16)
    b[e:e+2] = b''; p = cd
    for _ in range(n):
        nl, xl, cl = struct.unpack_from('<HHH', b, p+28); lo, = struct.unpack_from('<I', b, p+42)
        b[p:p+2] = b''; b[lo:lo+2] = b''; p += 46 + nl + xl + cl
    return bytes(b)
if __name__ == '__main__':
    import sys
    z = open_fszip(sys.argv[1]); il = z.infolist(); print(len(il), 'entries')
    for i in il[:int(sys.argv[2]) if len(sys.argv) > 2 else 10]: print(i.filename, i.file_size, i.compress_type)
    print('testzip:', z.testzip())

# ---- faithful writer (round-trip) ----
import zlib
def _dos(dt):
    y, mo, d, h, mi, s = dt
    return ((h << 11) | (mi << 5) | (s // 2)) & 0xFFFF, (((y - 1980) << 9) | (mo << 5) | d) & 0xFFFF
def _best_level(data, stored):
    for lv in (6, 9, 5, 7, 8, 4, 3, 2, 1):
        co = zlib.compressobj(lv, zlib.DEFLATED, -15, 8)
        if co.compress(data) + co.flush() == stored: return lv
    return None
def write_like(src_zip, src_raw, replace=None, level=6):
    """Rebuild FS-ZIP from `src_zip` (ZipFile from open_fszip) keeping every header field of the source.
    replace: {filename: new_bytes}. Unchanged entries reuse a deflate level that reproduces the original stream (fallback `level`).
    Returns obfuscated bytes. Entries with unreproducible streams are listed in write_like.unreproducible."""
    replace = replace or {}; write_like.unreproducible = []
    out = bytearray(); cd = bytearray(); infos = src_zip.infolist()
    for i in infos:
        data = replace.get(i.filename, src_zip.read(i))
        if i.compress_type == 0: comp = data
        else:
            stored = None
            if i.filename not in replace:
                lo = i.header_offset; nl, xl = struct.unpack_from('<HH', src_raw, lo+26)   # src_raw is the obfuscated original
                stored = bytes(src_raw[lo+30+nl+xl: lo+30+nl+xl+i.compress_size]); lv = _best_level(data, stored)
                if lv is None: write_like.unreproducible.append(i.filename); comp = stored
                else:
                    co = zlib.compressobj(lv, zlib.DEFLATED, -15, 8); comp = co.compress(data) + co.flush()
            else:
                co = zlib.compressobj(level, zlib.DEFLATED, -15, 8); comp = co.compress(data) + co.flush()
        t, dd = _dos(i.date_time); name = i.filename.encode('cp437'); crc = zlib.crc32(data)
        off = len(out)
        out += struct.pack('<4sHHHHHIIIHH', b'\x03\x05\x03\x04', i.extract_version, i.flag_bits, i.compress_type, t, dd, crc, len(comp), len(data), len(name), 0) + name + comp
        cd += struct.pack('<4sHHHHHHIIIHHHHHII', b'\x03\x05\x01\x02', i.create_version | (i.create_system << 8), i.extract_version, i.flag_bits, i.compress_type,
                          t, dd, crc, len(comp), len(data), len(name), 0, 0, 0, i.internal_attr, i.external_attr, off) + name
    cdo = len(out); out += cd
    out += struct.pack('<4sHHHHIIH', b'\x03\x05\x05\x06', 0, 0, len(infos), len(infos), len(cd), cdo, 0)
    return bytes(out)
