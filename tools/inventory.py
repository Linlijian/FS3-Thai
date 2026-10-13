"""Inventory the game copy: disk files (+sha256) and the contents of every pak/dat archive -> work/inventory/*.csv"""
import os, sys, csv, hashlib, mmap, collections
sys.path.insert(0, os.path.dirname(__file__))
import ujpak, fszip, fsset
mode = fsset.parse_set(sys.argv)
root = sys.argv[1]; out = sys.argv[2]; os.makedirs(out, exist_ok=True)
kinds = {'.pak':'archive','.dat':'archive/data','.bks':'image-stream','.img':'map-image','.map':'map','.bin':'table','.xml':'text','.ini':'text','.mp3':'audio','.wav':'audio','.ani':'cursor','.dll':'code','.exe':'code','.dds':'image','.tga':'image','.cfx':'fx','.bwn':'model','.cfg':'config','.log':'log'}
def kind(n): return kinds.get(os.path.splitext(n)[1].lower(), 'other')
with open(f'{out}/disk.csv','w',newline='',encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['path','size','ext','kind','sha256'])
    for d,_,fs in os.walk(root):
        for n in sorted(fs):
            p = os.path.join(d,n); h = hashlib.sha256()
            with open(p,'rb') as g:
                for c in iter(lambda: g.read(1<<22), b''): h.update(c)
            w.writerow([os.path.relpath(p,root).replace(os.sep,'/'), os.path.getsize(p), os.path.splitext(n)[1].lower(), kind(n), h.hexdigest()])
rows = []
for n, p in fsset.archives(root, mode):
    try:
        with open(p,'rb') as f: head = f.read(4)
        if head == b'UJ  ':
            with open(p,'rb') as f, mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
                for path,off,size,flag,_ in ujpak.walk(m): rows.append((n,path,size,kind(path),'uj'))
        elif head == b'\x03\x05\x03\x04':
            z = fszip.open_fszip(p)
            for i in z.infolist():
                if not i.is_dir(): rows.append((n,'/'+i.filename,i.file_size,kind(i.filename),f'zip-m{i.compress_type}'))
    except Exception as e: print('skip', n, repr(e))
with open(f'{out}/archives.csv','w',newline='',encoding='utf-8') as f:
    w = csv.writer(f); w.writerow(['container','path','size','kind','fmt']); w.writerows(rows)
c = collections.Counter((r[0], r[3]) for r in rows)
for k,v in sorted(c.items()): print(k, v)
print('total archived files', len(rows))
