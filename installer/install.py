"""FS3 Thai installer (runs on the player's PC, standard library only).
usage: install.py install|uninstall [--game DIR]
Package layout: install.py  tools/*.py  mod/{d3dx9_25.dll, FS3_TH_hook.ini, channel_base.txt, translations.tsv, ui_labels.tsv, source_hashes.txt}
install: checks the player's original files by sha256 -> backs them up (FS3_TH_backup, first time only) -> BUILDS the Thai files from
those originals (no game data is shipped) -> stages *.th_new -> renames into place; any failure restores the backup."""
import os, sys, re, shutil, hashlib, subprocess, tempfile
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass
HERE = os.path.dirname(os.path.abspath(__file__)); MOD = os.path.join(HERE, 'mod'); TOOLS = os.path.join(HERE, 'tools')
REPLACED = ['Pack/FS3Bin.dat', 'Pack/FS3UpdataChs.dat', 'Pack/FS3UI.pak', 'CFG/DefaultString.bin']   # originals backed up, rebuilt
CHECKED = REPLACED + ['FS3.exe']                                                                      # must match source_hashes.txt
PLACED = ['FS3_TH_map.txt', 'FS3_TH_text.txt', 'FS3_TH_exe.txt']                                      # generated, dropped next to FS3.exe
OWN = PLACED + ['FS3_TH_hook.ini', 'FS3_TH_hook.log', 'FS3_TH_installed.txt', 'FS3_TH_hook.ini.old']
class Fail(Exception): pass
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
def is_game(d): return bool(d) and os.path.isfile(os.path.join(d, 'FS3.exe')) and os.path.isfile(os.path.join(d, 'Pack', 'FS3UpdataChs.dat'))
def find_game():
    a = sys.argv[1:]
    if '--game' in a: g = a[a.index('--game') + 1]; assert is_game(g), f'ไม่พบเกมที่ {g}'; return g
    cands = [HERE, os.path.dirname(HERE), os.getcwd()]
    try:
        import winreg
        for hive, key, val in ((winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam', 'SteamPath'), (winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\WOW6432Node\Valve\Steam', 'InstallPath')):
            try:
                with winreg.OpenKey(hive, key) as k: cands.append(winreg.QueryValueEx(k, val)[0])
            except OSError: pass
    except ImportError: pass
    libs = []
    for c in list(cands):
        vdf = os.path.join(c, 'steamapps', 'libraryfolders.vdf')
        if os.path.isfile(vdf): libs += [m.replace('\\\\', '\\') for m in re.findall(r'"path"\s+"([^"]+)"', open(vdf, encoding='utf-8', errors='replace').read())]
    for c in cands + libs:
        for d in (c, os.path.join(c, 'steamapps', 'common', 'FantasiaSango3')):
            if is_game(d): return os.path.abspath(d)
    for _ in range(3):
        d = input('ไม่พบเกมอัตโนมัติ — พิมพ์ที่อยู่โฟลเดอร์เกม (โฟลเดอร์ที่มี FS3.exe): ').strip().strip('"')
        if is_game(d): return os.path.abspath(d)
        print('  ไม่ใช่โฟลเดอร์เกม (ไม่มี FS3.exe / Pack\\FS3UpdataChs.dat)')
    raise Fail('ไม่พบโฟลเดอร์เกม')
def expected():
    rows = [ln.split(None, 1) for ln in open(os.path.join(MOD, 'source_hashes.txt'), encoding='utf-8').read().splitlines() if ln.strip() and ln[0] != '#']
    return {p.strip(): h for h, p in rows}
def put(src, dst):                                                   # copy to dst.th_new (not yet in place)
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst + '.th_new'); return dst
def commit(pairs):
    """pairs: [(dst)] each has dst.th_new -> rename over dst; returns on success, raises Fail after cleaning up"""
    for dst in pairs:
        try: os.replace(dst + '.th_new', dst)
        except OSError as e: raise Fail(f'เขียน {dst} ไม่ได้: {e}\n  ปิดเกม/Steam ที่กำลังรันอยู่ แล้วลองใหม่ (ถ้าเกมอยู่ใน Program Files ให้รันแบบ Administrator)')
def clean(pairs):
    for dst in pairs:
        try: os.remove(dst + '.th_new')
        except OSError: pass
def restore(game, bk):
    for rel in REPLACED:
        if os.path.isfile(os.path.join(bk, rel)):
            commit([put(os.path.join(bk, rel), os.path.join(game, rel))])
    o = os.path.join(game, 'd3dx9_25_orig.dll')
    if os.path.isfile(o): os.replace(o, os.path.join(game, 'd3dx9_25.dll'))
def install(game):
    bk = os.path.join(game, 'FS3_TH_backup'); want = expected()
    print(f'โฟลเดอร์เกม: {game}\n[1/5] ตรวจไฟล์ต้นฉบับ (sha256)')
    for rel in CHECKED:                                              # the backup (if any) is the authority, else the file in the game
        p = os.path.join(bk, rel) if os.path.isfile(os.path.join(bk, rel)) else os.path.join(game, rel)
        if not os.path.isfile(p): raise Fail(f'ไม่พบไฟล์ {rel}')
        if sha(p) != want[rel]:
            raise Fail(f'ไฟล์ {rel} ไม่ตรงกับเวอร์ชันที่ mod นี้รองรับ (อาจถูกแก้ไขแล้ว หรือเกมอัปเดต)\n'
                       '  วิธีแก้: Steam > คลิกขวาเกม > Properties > Installed Files > Verify integrity of game files แล้วรันใหม่\n'
                       '  (ยังไม่ได้แก้ไขอะไรในเกมของคุณ)')
    if shutil.disk_usage(game).free < 400 << 20: raise Fail('พื้นที่ว่างในไดรฟ์เกมน้อยกว่า 400 MB')
    print('[2/5] สำรองไฟล์ต้นฉบับ ->', bk)
    for rel in REPLACED:
        d = os.path.join(bk, rel)
        if not os.path.isfile(d): os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copyfile(os.path.join(game, rel), d + '.part'); os.replace(d + '.part', d)
    tmp = tempfile.mkdtemp(prefix='fs3th_'); out = os.path.join(tmp, 'out'); py = sys.executable
    env = dict(os.environ, FS3_ORIG=bk, PYTHONUTF8='1')
    def run(tool, *a):
        r = subprocess.run([py, '-I', os.path.join(TOOLS, tool), *a], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode: raise Fail(f'{tool} ล้มเหลว (เกมยังไม่ถูกแก้ไข):\n{r.stdout[-800:]}{r.stderr[-1500:]}')
    try:
        print('[3/5] สร้างไฟล์ภาษาไทยจากเกมของคุณ (ใช้เวลา ~1 นาที)')
        run('build_channel.py', game, os.path.join(MOD, 'channel_base.txt'), out)
        run('build_keys.py', game, os.path.join(out, 'FS3_TH_map.txt'), os.path.join(MOD, 'translations.tsv'), out)
        run('build_ui.py', game, os.path.join(MOD, 'ui_labels.tsv'), out)
        print('[4/5] ตรวจไฟล์ที่สร้าง')
        sys.path.insert(0, TOOLS); import fszip, ujpak
        for a in ('FS3Bin.dat', 'FS3UpdataChs.dat'): assert fszip.open_fszip(os.path.join(out, a)).testzip() is None, a
        ujpak.read_tree(open(os.path.join(out, 'FS3UI.pak'), 'rb').read())
        for f in PLACED + ['CFG/DefaultString.bin']: assert os.path.getsize(os.path.join(out, f)) > 0, f
        print('[5/5] ติดตั้ง')
        dll, orig, ours = (os.path.join(game, 'd3dx9_25.dll'), os.path.join(game, 'd3dx9_25_orig.dll'), os.path.join(MOD, 'd3dx9_25.dll'))
        if not os.path.isfile(orig):
            if not os.path.isfile(dll): raise Fail('ไม่พบ d3dx9_25.dll ในโฟลเดอร์เกม')
            if sha(dll) == sha(ours): raise Fail('d3dx9_25.dll เป็นของ mod อยู่แล้วแต่ไม่มี d3dx9_25_orig.dll — Verify integrity ใน Steam แล้วลองใหม่')
        ini = os.path.join(game, 'FS3_TH_hook.ini')
        if os.path.isfile(ini) and sha(ini) != sha(os.path.join(MOD, 'FS3_TH_hook.ini')): shutil.copyfile(ini, ini + '.old')
        todo = [put(os.path.join(out, 'FS3Bin.dat'), os.path.join(game, 'Pack', 'FS3Bin.dat')), put(os.path.join(out, 'FS3UpdataChs.dat'), os.path.join(game, 'Pack', 'FS3UpdataChs.dat')),
                put(os.path.join(out, 'FS3UI.pak'), os.path.join(game, 'Pack', 'FS3UI.pak')), put(os.path.join(out, 'CFG', 'DefaultString.bin'), os.path.join(game, 'CFG', 'DefaultString.bin'))]
        todo += [put(os.path.join(out, f), os.path.join(game, f)) for f in PLACED] + [put(os.path.join(MOD, 'FS3_TH_hook.ini'), ini)]
        swap = not os.path.isfile(orig); dll_new = put(ours, dll) and dll
        try:
            commit(todo)
            if swap:
                try: os.replace(dll, orig)
                except OSError as e: raise Fail(f'เปลี่ยนชื่อ d3dx9_25.dll ไม่ได้: {e}\n  ปิดเกมที่กำลังรันอยู่แล้วลองใหม่')
            commit([dll])
        except Fail:
            clean(todo + [dll_new]); restore(game, bk); raise
        with open(os.path.join(game, 'FS3_TH_installed.txt'), 'w', encoding='utf-8') as f:
            f.write('FS3 Thai mod installed\n' + ''.join(f'{sha(os.path.join(game, p))}  {p}\n' for p in REPLACED + PLACED + ['FS3_TH_hook.ini', 'd3dx9_25.dll']))
    finally: shutil.rmtree(tmp, ignore_errors=True)
    print('\nติดตั้งเสร็จแล้ว — เปิดเกมได้เลย\nถ้ามีปัญหา: รัน uninstall เพื่อคืนไฟล์เดิม')
def uninstall(game):
    bk = os.path.join(game, 'FS3_TH_backup')
    if not os.path.isdir(bk): raise Fail('ไม่พบ FS3_TH_backup — ไม่มีอะไรให้คืน (ถ้าเกมมีปัญหา ใช้ Steam > Verify integrity)')
    print('คืนไฟล์ต้นฉบับ...'); restore(game, bk)
    for f in OWN:
        try: os.remove(os.path.join(game, f))
        except OSError: pass
    shutil.rmtree(bk, ignore_errors=True)
    print('ถอนการติดตั้งเรียบร้อย — ไฟล์เกมกลับเป็นต้นฉบับ')
if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'install'; code = 0
    try:
        {'install': install, 'uninstall': uninstall}[cmd](find_game())
    except Fail as e: print('\nผิดพลาด:', e); code = 1
    except Exception as e: print('\nผิดพลาดที่ไม่คาดคิด:', repr(e)); code = 2
    if sys.stdin and sys.stdin.isatty():
        try: input('\nกด Enter เพื่อปิด')
        except EOFError: pass
    sys.exit(code)
