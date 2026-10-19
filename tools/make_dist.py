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
os.makedirs(f'{pkg}/mod')
with zipfile.ZipFile(f'{pkg}/app.zip', 'w', zipfile.ZIP_DEFLATED) as z:               # one file: __main__.py (installer) + the build tools, plain .py (readable)
    z.write(f'{ROOT}/installer/install.py', '__main__.py')
    for t in TOOLS: z.write(f'{ROOT}/tools/{t}.py', f'{t}.py')
shutil.copy(exe, f'{pkg}/install.exe'); shutil.copy(exe, f'{pkg}/uninstall.exe')
shutil.copy(dll, f'{pkg}/mod/d3dx9_25.dll'); shutil.copy(f'{ROOT}/proxy/FS3_TH_hook.ini', f'{pkg}/mod/FS3_TH_hook.ini')
shutil.copy(f'{ROOT}/poc/FS3_TH_map.txt', f'{pkg}/mod/channel_base.txt'); shutil.copy(f'{ROOT}/poc/ui_labels.tsv', f'{pkg}/mod/ui_labels.tsv')
subprocess.run([sys.executable, '-I', f'{ROOT}/tools/pack_translations.py', strings, f'{pkg}/mod/translations.tsv'], check=True)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
with open(f'{pkg}/mod/source_hashes.txt', 'w', encoding='ascii', newline='\n') as f:
    f.write('# sha256 of the ORIGINAL files this package builds from (checked by install.py before anything is changed)\n')
    for rel in ['Pack/FS3Bin.dat', 'Pack/FS3UpdataChs.dat', 'Pack/FS3UI.pak', 'CFG/DefaultString.bin', 'FS3.exe']:
        f.write(f'{sha(fszip.orig(game, rel))}  {rel}\n')
README = """FS3 Thai - Thai text for Fantasia Sango 3 (Steam)

1. Unzip the WHOLE folder anywhere (it does not have to be inside the game folder). Do not move files out of it.
2. Close the game.
3. Double-click install.exe. It finds your game, asks you to confirm, then builds the Thai files from YOUR copy of the game (about 1 minute).
4. Start the game from Steam as usual.

Uninstall: double-click uninstall.exe (restores every original file).
If install says "not the version this mod supports": Steam > right-click the game > Properties > Installed Files > Verify integrity of game files, then run install.exe again.
Needs Windows 10 or newer (font Leelawadee UI). Nothing from the game is included in this package; the Thai files are generated on your PC.

--- ภาษาไทย ---
1. แตก zip ทั้งโฟลเดอร์ไว้ที่ไหนก็ได้ ห้ามย้ายไฟล์ออกจากโฟลเดอร์  2. ปิดเกม
3. ดับเบิลคลิก install.exe  (หาเกมเอง ถามยืนยัน แล้วสร้างไฟล์ไทยจากเกมของคุณ ~1 นาที)  4. เปิดเกมจาก Steam ตามปกติ
ถอนการติดตั้ง: uninstall.exe   ถ้าขึ้นว่าไฟล์ไม่ตรงเวอร์ชัน: Steam > Properties > Installed Files > Verify integrity แล้วรันใหม่
ข้อความในหน้าต่างติดตั้งเป็นภาษาอังกฤษ เพราะ cmd แสดงภาษาไทยไม่ได้
"""
open(f'{pkg}/README.txt', 'w', encoding='utf-8-sig', newline='\r\n').write(README)
if emb:
    with zipfile.ZipFile(emb) as z: z.extractall(f'{pkg}/python')
zp = os.path.join(out, 'FS3_Thai.zip');
with zipfile.ZipFile(zp, 'w', zipfile.ZIP_DEFLATED) as z:
    for d, _, fs in os.walk(pkg):
        for fn in fs: p = os.path.join(d, fn); z.write(p, os.path.relpath(p, out))
print(f'{pkg}\n{zp} {os.path.getsize(zp) >> 10} KiB')
