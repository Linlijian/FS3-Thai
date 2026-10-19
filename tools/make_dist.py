"""Assemble the player package FS3_Thai/ (+ zip). Contains NO game files: only our DLL / ini / tables / python scripts and an embedded Python.
usage: make_dist.py <game_copy> <strings_all.tsv> <proxy.dll> <launcher.exe> <out_dir> [python-embed.zip]
  <game_copy>   a game folder whose original files are readable (FS3Bin.dat.bak etc. are used when present): only their sha256 is stored
  <out_dir>     receives FS3_Thai/ and FS3_Thai.zip
Without python-embed.zip the package needs a Python 3.12 on the player's PC (python\\ missing) - for tests only."""
import os, sys, shutil, hashlib, zipfile, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(ROOT, 'tools'))
import fszip
game, strings, dll, exe, out = sys.argv[1:6]; emb = sys.argv[6] if len(sys.argv) > 6 else None
TOOLS = 'build_channel build_keys build_ui fszip ujpak fsdds fsdialog fstables fsexe thaichan thaibreak'.split()
pkg = os.path.join(out, 'FS3_Thai'); shutil.rmtree(pkg, ignore_errors=True)
os.makedirs(f'{pkg}/mod'); os.makedirs(f'{pkg}/tools')
for t in TOOLS: shutil.copy(f'{ROOT}/tools/{t}.py', f'{pkg}/tools/{t}.py')
shutil.copy(f'{ROOT}/installer/install.py', f'{pkg}/install.py')
shutil.copy(exe, f'{pkg}/install.exe'); shutil.copy(exe, f'{pkg}/uninstall.exe')
shutil.copy(dll, f'{pkg}/mod/d3dx9_25.dll'); shutil.copy(f'{ROOT}/proxy/FS3_TH_hook.ini', f'{pkg}/mod/FS3_TH_hook.ini')
shutil.copy(f'{ROOT}/poc/FS3_TH_map.txt', f'{pkg}/mod/channel_base.txt'); shutil.copy(f'{ROOT}/poc/ui_labels.tsv', f'{pkg}/mod/ui_labels.tsv')
subprocess.run([sys.executable, '-I', f'{ROOT}/tools/pack_translations.py', strings, f'{pkg}/mod/translations.tsv'], check=True)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
with open(f'{pkg}/mod/source_hashes.txt', 'w', encoding='ascii', newline='\n') as f:
    f.write('# sha256 of the ORIGINAL files this package builds from (checked by install.py before anything is changed)\n')
    for rel in ['Pack/FS3Bin.dat', 'Pack/FS3UpdataChs.dat', 'Pack/FS3UI.pak', 'CFG/DefaultString.bin', 'FS3.exe']:
        f.write(f'{sha(fszip.orig(game, rel))}  {rel}\n')
open(f'{pkg}/README.txt', 'w', encoding='utf-8', newline='\r\n').write(
    'FS3 Thai (Fantasia Sango 3 ภาษาไทย)\n\n'
    '1. แตก zip ทั้งโฟลเดอร์ไว้ที่ไหนก็ได้ (ไม่ต้องอยู่ในโฟลเดอร์เกม)\n2. ปิดเกมและ Steam ที่กำลังรันเกมอยู่\n'
    '3. ดับเบิลคลิก install.exe — โปรแกรมหาเกมเอง (หรือถามที่อยู่โฟลเดอร์) แล้วสร้างไฟล์ภาษาไทยจากไฟล์เกมของคุณ ใช้เวลาประมาณ 1 นาที\n'
    '4. เปิดเกมจาก Steam ตามปกติ\n\nถอนการติดตั้ง: ดับเบิลคลิก uninstall.exe (คืนไฟล์เดิมทั้งหมด)\n'
    'ถ้าติดตั้งไม่ผ่านเพราะ "ไฟล์ไม่ตรงเวอร์ชัน": Steam > คลิกขวาเกม > Properties > Installed Files > Verify integrity of game files แล้วรัน install.exe ใหม่\n'
    'ต้องใช้ Windows 10 ขึ้นไป (ฟอนต์ Leelawadee UI)\n\nแพ็กเกจนี้ไม่มีไฟล์ของเกม: ไฟล์ภาษาไทยถูกสร้างบนเครื่องคุณจากเกมที่คุณมีอยู่แล้ว\n')
if emb:
    with zipfile.ZipFile(emb) as z: z.extractall(f'{pkg}/python')
zp = os.path.join(out, 'FS3_Thai.zip');
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(pkg):
        for fn in fs: p = os.path.join(d, fn); z.write(p, os.path.relpath(p, out))
print(f'{pkg}\n{zp} {os.path.getsize(zp) >> 10} KiB')
