"""Bin/Objects.bin: u32 count | count * 104-byte records; record +0 = name[20] (cp950, NUL-terminated, <= 19 bytes) [V 2026-10-13].
Names are what the engine shows as the speaker label above the dialogue box (母雞巧巧 = record 405 etc.).
Address scheme for translation files: block = record index, offset = 0."""
import struct
REC, NAME = 104, 20
def strs(data):
    """-> {(record, 0): raw name bytes} for every non-empty name"""
    n, = struct.unpack_from('<I', data, 0); assert 4 + n * REC == len(data), 'Objects.bin size != 4 + count*104'
    out = {}
    for i in range(n):
        raw = data[4 + i * REC: 4 + i * REC + NAME].split(b'\0')[0]
        if raw: out[(i, 0)] = raw
    return out
def slot_lens(data):
    return {k: NAME - 1 for k in strs(data)}      # the whole field minus the terminating NUL is usable
def patch(data, edits):
    """edits: {(record, 0): new_bytes <= 19}; field is NUL-padded, the rest of the record untouched"""
    b = bytearray(data)
    for (i, _), new in edits.items():
        assert len(new) < NAME, (i, len(new)); o = 4 + i * REC; b[o:o + NAME] = new.ljust(NAME, b'\0')
    return bytes(b)
