"""FS3 Thai installer (runs on the player's PC, standard library only). Shipped inside app.zip as __main__.py (run: python -I app.zip install|uninstall [--game DIR] [--yes]).
Package layout: install.exe uninstall.exe app.zip(__main__.py + tools/*.py) mod/{d3dx9_25.dll, FS3_TH_hook.ini, channel_base.txt, translations.tsv, key_ids.tsv, ui_labels.tsv, source_hashes.txt} python/
install: checks the player's original files by sha256 -> backs them up (FS3_TH_backup, first time only) -> BUILDS the Thai files from
those originals (no game data is shipped) -> stages *.th_new -> renames into place; any failure restores the backup.
Console text is English on purpose (cmd.exe cannot show Thai)."""
import os, sys, re, shutil, hashlib, subprocess, tempfile
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception: pass
APP = os.path.abspath(sys.argv[0]); HERE = os.path.dirname(APP); MOD = os.path.join(HERE, 'mod')
REPLACED = ['Pack/FS3Bin.dat', 'Pack/FS3UpdataChs.dat', 'Pack/FS3UI.pak', 'CFG/DefaultString.bin', 'CFG/Mission.bin']   # originals backed up, rebuilt
CHECKED = [r for r in REPLACED if r != 'CFG/Mission.bin'] + ['CFG/Mission.bnk.bin', 'FS3.exe']   # Mission.bin is built from the game's own Mission.bnk.bin                                                                      # must match source_hashes.txt
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
    if '--game' in a:
        g = a[a.index('--game') + 1]
        if not is_game(g): raise Fail(f'Fantasia Sango 3 not found in {g}')
        return os.path.abspath(g)
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
        d = input('Game folder not found automatically. Type the game folder (the one that contains FS3.exe): ').strip().strip('"')
        if is_game(d): return os.path.abspath(d)
        print('  Not a game folder (FS3.exe or Pack\\FS3UpdataChs.dat is missing).')
    raise Fail('Game folder not found.')
def expected():
    rows = [ln.split(None, 1) for ln in open(os.path.join(MOD, 'source_hashes.txt'), encoding='utf-8').read().splitlines() if ln.strip() and ln[0] != '#']
    return {p.strip(): h for h, p in rows}
def put(src, dst):                                                   # copy to dst.th_new (not yet in place)
    os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copyfile(src, dst + '.th_new'); return dst
def commit(pairs):
    """pairs: [(dst)] each has dst.th_new -> rename over dst"""
    for dst in pairs:
        try: os.replace(dst + '.th_new', dst)
        except OSError as e: raise Fail(f'Cannot write {dst}: {e}\n  Close the game and Steam\'s game window, then run again (if the game is under Program Files, run as Administrator).')
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
    print(f'Game folder: {game}\n[1/5] Checking your original game files (sha256)')
    for rel in CHECKED:                                              # the backup (if any) is the authority, else the file in the game
        p = os.path.join(bk, rel) if os.path.isfile(os.path.join(bk, rel)) else os.path.join(game, rel)
        if not os.path.isfile(p): raise Fail(f'File not found: {rel}')
        if sha(p) != want[rel]:
            raise Fail(f'{rel} is not the version this mod supports (already modified, or the game was updated).\n'
                       '  Fix: in Steam right-click the game > Properties > Installed Files > Verify integrity of game files, then run install.exe again.\n'
                       '  Nothing in your game was changed.')
    if shutil.disk_usage(game).free < 400 << 20: raise Fail('Less than 400 MB free on the game drive.')
    print('[2/5] Backing up the original files ->', bk)
    for rel in REPLACED:
        d = os.path.join(bk, rel)
        if not os.path.isfile(d): os.makedirs(os.path.dirname(d), exist_ok=True); shutil.copyfile(os.path.join(game, rel), d + '.part'); os.replace(d + '.part', d)
    tmp = tempfile.mkdtemp(prefix='fs3th_'); out = os.path.join(tmp, 'out'); py = sys.executable
    env = dict(os.environ, FS3_ORIG=bk, PYTHONUTF8='1')
    def run(tool, *a):
        r = subprocess.run([py, '-I', APP, '--tool', tool, *a], env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
        if r.returncode: raise Fail(f'{tool} failed (your game was not modified):\n{r.stdout[-800:]}{r.stderr[-1500:]}')
    try:
        print('[3/5] Building the Thai files from your game (about 1 minute)')
        run('build_channel', game, os.path.join(MOD, 'channel_base.txt'), out)
        run('build_keys', game, os.path.join(out, 'FS3_TH_map.txt'), os.path.join(MOD, 'translations.tsv'), out, os.path.join(MOD, 'key_ids.tsv'))
        run('build_ui', game, os.path.join(MOD, 'ui_labels.tsv'), out)
        print('[4/5] Checking the built files')
        import fszip, ujpak
        for a in ('FS3Bin.dat', 'FS3UpdataChs.dat'): assert fszip.open_fszip(os.path.join(out, a)).testzip() is None, a
        ujpak.read_tree(open(os.path.join(out, 'FS3UI.pak'), 'rb').read())
        for f in PLACED + ['CFG/DefaultString.bin', 'CFG/Mission.bin']: assert os.path.getsize(os.path.join(out, f)) > 0, f
        print('[5/5] Installing')
        dll, orig, ours = (os.path.join(game, 'd3dx9_25.dll'), os.path.join(game, 'd3dx9_25_orig.dll'), os.path.join(MOD, 'd3dx9_25.dll'))
        if not os.path.isfile(orig):
            if not os.path.isfile(dll): raise Fail('d3dx9_25.dll not found in the game folder.')
            if sha(dll) == sha(ours): raise Fail('d3dx9_25.dll is already the mod\'s but d3dx9_25_orig.dll is missing - Verify integrity in Steam, then run again.')
        ini = os.path.join(game, 'FS3_TH_hook.ini')
        if os.path.isfile(ini) and sha(ini) != sha(os.path.join(MOD, 'FS3_TH_hook.ini')): shutil.copyfile(ini, ini + '.old')
        todo = [put(os.path.join(out, 'FS3Bin.dat'), os.path.join(game, 'Pack', 'FS3Bin.dat')), put(os.path.join(out, 'FS3UpdataChs.dat'), os.path.join(game, 'Pack', 'FS3UpdataChs.dat')),
                put(os.path.join(out, 'FS3UI.pak'), os.path.join(game, 'Pack', 'FS3UI.pak')), put(os.path.join(out, 'CFG', 'DefaultString.bin'), os.path.join(game, 'CFG', 'DefaultString.bin')),
                put(os.path.join(out, 'CFG', 'Mission.bin'), os.path.join(game, 'CFG', 'Mission.bin'))]
        todo += [put(os.path.join(out, f), os.path.join(game, f)) for f in PLACED] + [put(os.path.join(MOD, 'FS3_TH_hook.ini'), ini)]
        swap = not os.path.isfile(orig); dll_new = put(ours, dll) and dll
        try:
            commit(todo)
            if swap:
                try: os.replace(dll, orig)
                except OSError as e: raise Fail(f'Cannot rename d3dx9_25.dll: {e}\n  Close the game and run again.')
            commit([dll])
        except Fail:
            clean(todo + [dll_new]); restore(game, bk); raise
        with open(os.path.join(game, 'FS3_TH_installed.txt'), 'w', encoding='utf-8') as f:
            f.write('FS3 Thai mod installed\n' + ''.join(f'{sha(os.path.join(game, p))}  {p}\n' for p in REPLACED + PLACED + ['FS3_TH_hook.ini', 'd3dx9_25.dll']))
    finally: shutil.rmtree(tmp, ignore_errors=True)
    print('\nDone. Start the game from Steam as usual.\nTo remove the mod: run uninstall.exe (restores your original files).')
def uninstall(game):
    bk = os.path.join(game, 'FS3_TH_backup')
    if not os.path.isdir(bk): raise Fail('FS3_TH_backup not found - nothing to restore (if the game misbehaves: Steam > Verify integrity of game files).')
    print('Restoring the original files...'); restore(game, bk)
    for f in OWN:
        try: os.remove(os.path.join(game, f))
        except OSError: pass
    shutil.rmtree(bk, ignore_errors=True)
    print('Done. Your game files are back to the original.')
def confirm(cmd, game):
    if '--yes' in sys.argv or not (sys.stdin and sys.stdin.isatty()): return
    what = 'INSTALL the Thai mod into' if cmd == 'install' else 'REMOVE the Thai mod from'
    try: input(f'\nThis will {what}:\n  {game}\nPress Enter to continue, or close this window to cancel. ')
    except EOFError: raise Fail('Cancelled.')
if __name__ == '__main__':
    if len(sys.argv) > 2 and sys.argv[1] == '--tool':              # build tools run from inside app.zip as separate processes
        import runpy; name = sys.argv[2]; sys.argv = [name + '.py', *sys.argv[3:]]; runpy.run_module(name, run_name='__main__'); sys.exit(0)
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'install'; code = 0
    try:
        if cmd not in ('install', 'uninstall'): raise Fail('usage: install|uninstall [--game DIR] [--yes]')
        game = find_game(); confirm(cmd, game); {'install': install, 'uninstall': uninstall}[cmd](game)
    except Fail as e: print('\nERROR:', e); code = 1
    except Exception as e: print('\nUNEXPECTED ERROR:', repr(e)); code = 2
    if '--yes' not in sys.argv and sys.stdin and sys.stdin.isatty():
        try: input('\nPress Enter to close. ')
        except EOFError: pass
    sys.exit(code)
