"""Assemble the player package: ONE file, <out_dir>/FS3_Thai_Setup.exe = launcher.exe + zip(app.zip, mod/, python/) + u32 size + "FS3THPK1"
(installer/launcher.c unpacks it to a temp folder and shows install / uninstall). Contains NO game files: only our DLL (it carries
the settings, no ini), tables, python scripts and an embedded Python. <out_dir>/FS3_Thai/ is the same package as a folder (tests:
its install.exe runs without unpacking); <out_dir>/README.txt is the text for the download page.
usage: make_dist.py <game_copy> <strings_all.tsv> <proxy.dll> <launcher.exe> <out_dir> [python-embed.zip]
  <game_copy>   a game folder whose original files are readable (FS3Bin.dat.bak etc. are used when present): only their sha256 is stored
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
shutil.copy(exe, f'{pkg}/install.exe')                                           # folder mode, tests only
shutil.copy(dll, f'{pkg}/mod/d3dx9_25.dll')
shutil.copy(f'{ROOT}/poc/FS3_TH_map.txt', f'{pkg}/mod/channel_base.txt'); shutil.copy(f'{ROOT}/poc/ui_labels.tsv', f'{pkg}/mod/ui_labels.tsv')
shutil.copy(f'{ROOT}/poc/key_ids.tsv', f'{pkg}/mod/key_ids.tsv')                       # text ids stay the same as in our builds: saves store keys
subprocess.run([sys.executable, '-I', f'{ROOT}/tools/pack_translations.py', strings, f'{pkg}/mod/translations.tsv'], check=True)
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
with open(f'{pkg}/mod/source_hashes.txt', 'w', encoding='ascii', newline='\n') as f:
    f.write('# sha256 of the ORIGINAL files this package builds from (checked by install.py before anything is changed)\n')
    for rel in ['Pack/FS3Bin.dat', 'Pack/FS3UpdataChs.dat', 'Pack/FS3UI.pak', 'CFG/DefaultString.bin', 'CFG/Mission.bnk.bin', 'FS3.exe']:
        f.write(f'{sha(fszip.orig(game, rel))}  {rel}\n')
README = """FS3 Thai - Thai text for Fantasia Sango 3 (Steam)

1. Close the game.
2. Double-click FS3_Thai_Setup.exe and choose 1 (install). It finds your game, asks you to confirm, then builds the Thai files
   from YOUR copy of the game (about 1 minute).
3. Start the game from Steam as usual.

Uninstall: double-click FS3_Thai_Setup.exe again and choose 2 (restores every original file).
If it says "not the version this mod supports": Steam > right-click the game > Properties > Installed Files > Verify integrity of
game files, then run FS3_Thai_Setup.exe again. Needs Windows 10 or newer. Nothing from the game is included; the Thai files are
generated on your PC.
Dialogue typing speed (optional): create FS3_TH_hook.ini in the game folder with the two lines
  [hook]
  typewriter_pct=50
(% of the game's speed; default 70, 100 = faster; typewriter=0 = whole text at once).

--- ภาษาไทย ---
1. ปิดเกม  2. ดับเบิลคลิก FS3_Thai_Setup.exe แล้วเลือก 1 (ติดตั้ง) โปรแกรมหาเกมเอง ถามยืนยัน แล้วสร้างไฟล์ไทยจากเกมของคุณ (~1 นาที)
3. เปิดเกมจาก Steam ตามปกติ
ถอนการติดตั้ง: ดับเบิลคลิก FS3_Thai_Setup.exe อีกครั้งแล้วเลือก 2
ถ้าขึ้นว่าไฟล์ไม่ตรงเวอร์ชัน: Steam > Properties > Installed Files > Verify integrity แล้วรันใหม่
ข้อความในหน้าต่างติดตั้งเป็นภาษาอังกฤษ เพราะ cmd แสดงภาษาไทยไม่ได้
ปรับความเร็วการพิมพ์บทสนทนา (ไม่จำเป็น): สร้างไฟล์ FS3_TH_hook.ini ในโฟลเดอร์เกม ใส่สองบรรทัด
  [hook]
  typewriter_pct=50
(ค่าเริ่มต้น 70, 100 = เร็วขึ้น, typewriter=0 = แสดงทั้งข้อความทันที)
"""
open(f'{out}/README.txt', 'w', encoding='utf-8-sig', newline='\r\n').write(README)
if emb:
    with zipfile.ZipFile(emb) as z: z.extractall(f'{pkg}/python')
import io, struct
payload = io.BytesIO()
with zipfile.ZipFile(payload, 'w', zipfile.ZIP_DEFLATED) as z:                      # what the setup exe unpacks: app.zip, mod/, python/
    for d, _, fs in os.walk(pkg):
        for fn in fs:
            p = os.path.join(d, fn); rel = os.path.relpath(p, pkg).replace(os.sep, '/')
            if rel != 'install.exe': z.write(p, rel)
data = payload.getvalue(); setup = os.path.join(out, 'FS3_Thai_Setup.exe')
open(setup, 'wb').write(open(exe, 'rb').read() + data + struct.pack('<I', len(data)) + b'FS3THPK1')
for old in ('FS3_Thai.zip',):                                                       # the folder zip of earlier versions
    if os.path.exists(os.path.join(out, old)): os.remove(os.path.join(out, old))
print(f'{setup} {os.path.getsize(setup) >> 10} KiB')
