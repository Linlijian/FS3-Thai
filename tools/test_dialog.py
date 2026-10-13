"""Run the dialog parser over a set of archives; report coverage, round-trip, markup census, and orig-vs-other diffs.
usage: test_dialog.py <game_copy> [--set original|patched]"""
import os, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fszip, fsdialog, fsset
mode = fsset.parse_set(sys.argv); game = sys.argv[1]; P = f'{game}/Pack'
arch = dict(fsset.archives(game, mode))
z = fszip.open_fszip(arch['FS3Bin.dat']); u = fszip.open_fszip(arch['FS3UpdataChs.dat'])
tot = collections.Counter(); census = collections.Counter(); maxlen = 0; rt_bad = 0
for label, zz, pre in (('FS3Bin', z, 'Bin/'), ('Updata', u, 'BIN/')):
    for i in zz.infolist():
        if not (i.filename.startswith(pre + 'Dialog/') or i.filename.startswith(pre + 'AutoDialog/')) or i.is_dir(): continue
        d = zz.read(i); name, toc = fsdialog.parse(d)
        if fsdialog.rebuild(d) != d: rt_bad += 1
        g, bad = fsdialog.groups(name, d); tot[label, 'files'] += 1; tot[label, 'groups'] += len(g); tot[label, 'unvalidated_runs'] += bad
        for x in g:
            for _, r in x.strs:
                tot[label, 'strings'] += 1; maxlen = max(maxlen, len(r))
                if label == 'FS3Bin':
                    for m in fsdialog.MARK.findall(r.decode(fsdialog.ENC)): census[m if m.startswith('@@') is False else m.split('(')[0]] += 1
for k, v in sorted(tot.items()): print(k, v)
print('rebuild() mismatches:', rt_bad, '| longest string (bytes):', maxlen)
print('markup census (FS3Bin set):', census.most_common(25))
# orig vs Updata: same member -> identical?
same = diff = only = 0; diffs = []
for i in z.infolist():
    if i.is_dir() or not ('/Dialog/' in i.filename or '/AutoDialog/' in i.filename): continue
    try: other = u.read('BIN' + i.filename[3:])
    except KeyError: only += 1; continue
    if other == z.read(i): same += 1
    else: diff += 1; diffs.append(i.filename)
print(f'FS3Bin vs UpdataChs: identical {same}, different {diff}, only-in-FS3Bin {only}', diffs[:8])
