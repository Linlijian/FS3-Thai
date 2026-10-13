"""Extract every archive in <game>/Pack to <out>/<container>/ and verify each file's sha256 against the source bytes.
usage: extract.py <game_copy> <out_dir> [--set original|patched]"""
import os, sys, mmap, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ujpak, fszip, fsset
mode = fsset.parse_set(sys.argv)
game, out = sys.argv[1], sys.argv[2]
man = {}
for n, p in fsset.archives(game, mode):
    head = open(p,'rb').read(4); d = f'{out}/{n}'; cnt = bad = 0
    def put(rel, data):
        global cnt
        t = os.path.join(d, rel.lstrip('/')); os.makedirs(os.path.dirname(t), exist_ok=True)
        open(t,'wb').write(data); cnt += 1
        return hashlib.sha256(data).hexdigest()
    if head == b'UJ  ':
        with open(p,'rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
            for path,off,size,flag,_ in ujpak.walk(m):
                h = put(path, m[off:off+size])
                if h != hashlib.sha256(m[off:off+size]).hexdigest(): bad += 1   # re-read from source
                man[f'{n}{path}'] = h
    elif head == b'\x03\x05\x03\x04':
        z = fszip.open_fszip(p)
        for i in z.infolist():
            if i.is_dir(): continue
            man[f'{n}/{i.filename}'] = put(i.filename, z.read(i))   # zipfile verifies CRC32 on read
    else: print('skip', n, head); continue
    print(n, cnt, 'files, mismatches:', bad)
json.dump(man, open(f'{out}/manifest.json','w'), indent=0)
