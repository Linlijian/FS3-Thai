"""Translator CLI: export every game string to one TSV per game file, translate, import back.
  tr.py export <game> <outdir> [--master M]   write <outdir>/<member>.tsv for all files + INDEX.tsv + README.txt; rows already translated in M are prefilled
  tr.py status <outdir>                       progress per file (from the files themselves)
  tr.py import <outdir> <master> [--force]    check every edited row and merge into the master sheet (your edits overwrite; master.prev = backup)
<game> = a game folder (originals are found via fszip.orig: FS3_TH_backup > .bak > plain, so it also works with the mod installed).
Default master: work/strings_master.tsv (created by `export` if missing). build_keys.py / pack_translations.py read the master.
The exported files contain game text: keep them on your disk, never commit them."""
import os, sys, subprocess, tempfile, collections, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tr_import
HERE = os.path.dirname(os.path.abspath(__file__)); HEAD = '# member\tblock\toffset_in_block\tsource\tthai ( | = allowed break, * = forced break; empty = keep original)\n'
README = """Each file = one game file; rows are in game order. Edit ONLY the last column (thai). Empty = not translated yet (the game keeps the original).
  *        forced line break      |  allowed break (not needed: word breaks are added automatically)
  @@W(2)@@ @@w(1)@@ @@rw@@ ...    control codes: keep them exactly as in the source (colour / pause / name highlight), move them with the words they wrap
  %s %d    values the game inserts: keep all of them, same order
  The same Chinese sentence anywhere in the game reuses one translation (first filled row wins) - translate it once.
After editing: python -I tools/tr.py import <this folder> <master>.   Rows with wrong codes are rejected with their line number; nothing else is lost.
"""
def rows_of(p): return [ln.rstrip('\n').split('\t') for ln in open(p, encoding='utf-8') if ln.strip() and not ln.startswith('#')]
def files(d): return sorted(os.path.join(r, f) for r, _, fs in os.walk(d) for f in fs if f.endswith('.tsv') and f != 'INDEX.tsv')
def stats(rows):
    done = [r for r in rows if len(r) == 5 and r[4].strip()]; left = {r[3] for r in rows if len(r) == 5 and not r[4].strip()}
    return len(rows), len(done), len(left), sum(map(len, left))
def export(game, out, master):
    tmp = os.path.join(tempfile.mkdtemp(), 'all.tsv')
    r = subprocess.run([sys.executable, '-I', os.path.join(HERE, 'export_strings.py'), game, tmp], capture_output=True, text=True, encoding='utf-8')
    if r.returncode: sys.exit(r.stdout + r.stderr)
    print(r.stdout.strip()); allrows = [r for r in tr_import.load(tmp) if r and not r[0].startswith('#')]
    if not os.path.exists(master): os.makedirs(os.path.dirname(os.path.abspath(master)), exist_ok=True); shutil.copy(tmp, master); print('new master', master)
    have = {(r[0], r[1], r[2]): r for r in tr_import.load(master) if len(r) == 5}
    by = collections.OrderedDict()
    for r in allrows:
        m = have.get((r[0], r[1], r[2]))
        if m and m[3] == r[3]: r[4] = m[4]
        by.setdefault(r[0], []).append(r)
    index = []
    for member, rows in by.items():
        p = os.path.join(out, member + '.tsv'); os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', encoding='utf-8', newline='\n') as f: f.write(HEAD); f.writelines('\t'.join(r) + '\n' for r in rows)
        n, d, u, c = stats(rows); index.append((member, n, d, u, c, rows[0][3][:24]))
    with open(os.path.join(out, 'INDEX.tsv'), 'w', encoding='utf-8', newline='\n') as f:
        f.write('file\trows\ttranslated\tunique_left\tchars_left\tfirst_line\n'); f.writelines('\t'.join(map(str, x)) + '\n' for x in index)
    open(os.path.join(out, 'README.txt'), 'w', encoding='utf-8', newline='\n').write(README)
    print(f'{len(by)} files -> {out}  (see INDEX.tsv and README.txt)')
def status(out):
    tot = [0, 0, 0, 0]; lines = []
    for p in files(out):
        s = stats(rows_of(p)); tot = [a + b for a, b in zip(tot, s)]; lines.append((os.path.relpath(p, out)[:-4], *s))
    for l in lines:
        if l[2]: print(f'{l[0]:42} {l[2]:5}/{l[1]:<5} translated, {l[3]:5} unique left')
    print(f'TOTAL {tot[1]}/{tot[0]} rows translated; {tot[2]} unique sentences left ({tot[3]} chars; shared sentences counted per file)')
def imp(out, master, force):
    M = tr_import.load(master); idx = tr_import.index(M); tot, allbad = 0, []
    for p in files(out):
        ok, _, bad = tr_import.merge(M, idx, tr_import.load(p), over=True, where=os.path.relpath(p, out) + ':'); tot += ok; allbad += bad
    print(f'{tot} rows changed, {len(allbad)} rejected')
    for w, why in allbad: print(f'  {w}: {why}')
    if allbad and not force: sys.exit('NOT written: fix the rejected rows (or --force to merge the good ones)')
    shutil.copy(master, master + '.prev'); tr_import.save(master, M); print('written', master, '(backup: .prev)')
if __name__ == '__main__':
    a = [x for x in sys.argv[1:] if not x.startswith('--')]; opt = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
    if len(a) >= 3 and a[0] == 'export': export(a[1], a[2], opt('--master', 'work/strings_master.tsv'))
    elif len(a) >= 2 and a[0] == 'status': status(a[1])
    elif len(a) >= 3 and a[0] == 'import': imp(a[1], a[2], '--force' in sys.argv)
    else: sys.exit(__doc__)
