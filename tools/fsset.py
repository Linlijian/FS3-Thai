"""Choose which archive set to read: 'original' (FS3Bin.dat.bak stands in for the patched FS3Bin.dat) or 'patched' (as installed).
Only FS3Bin.dat has a known backup; everything else is identical in both sets. Every tool takes --set original|patched (default original)."""
import os, sys
BACKUP = {'FS3Bin.dat': 'FS3Bin.dat.bak'}
SKIP = ('.bak', '.pk.pak')            # backups / duplicate of SP_FS3.pak (identical sha256)
def parse_set(argv):
    """pops --set X from argv, returns 'original'|'patched'"""
    s = 'original'
    if '--set' in argv:
        i = argv.index('--set'); s = argv[i+1]; del argv[i:i+2]
    assert s in ('original', 'patched'), s
    return s
def archives(game, mode='original'):
    """yield (logical_name, real_path) for every archive in <game>/Pack"""
    for n in sorted(os.listdir(f'{game}/Pack')):
        if n.endswith(SKIP): continue
        real = BACKUP.get(n, n) if mode == 'original' else n
        yield n, f'{game}/Pack/{real}'
