# FS3 Thai — Thai text for Fantasia Sango 3 (幻想三國誌3)

Research tools, file-format specs and a working proof of concept for showing **Thai text inside the original
Fantasia Sango 3** (UserJoy, Steam build), without modifying or unpacking `FS3.exe`.

> โปรเจกต์ศึกษาไฟล์เกม Fantasia Sango 3 เพื่อทำ Thai mod สำหรับใช้ส่วนตัว/ชุมชน
> ไม่มีไฟล์ของเกมอยู่ใน repo นี้ ผู้ใช้ต้องมีเกมของตัวเอง เครื่องมือทั้งหมดอ่านจากสำเนาของผู้ใช้

**Status (v0.1):** Thai renders correctly in a real in-game dialogue box (vowel/tone stacking, word-wrapped long lines),
with no byte-length limit on translations. Only dialogue files are covered so far; see [docs/open-questions.md](docs/open-questions.md).

## Legal / scope
* No game assets (text, images, audio, models, binaries) are in this repository, and none must be added. Translation files
  address strings by **file / block / offset**, never by quoting the original text.
* `FS3.exe` is wrapped by Steam DRM. It is **not** unpacked, dumped or patched; the engine is studied black-box
  through a `d3dx9_25.dll` proxy and its data files.
* You need your own copy of the game. Always work on a copy (`work/fs3-copy`), never on the installed files.

## How it works (Plan A)
```
FS3UpdataChs.dat  dialogue slot holds a 6-byte KEY  (Big5 user-defined codes FA41..)
  -> Bin/Code/BIG2GB.idx (in FS3Bin.dat; the engine's real Big5->GBK table) maps them to GBK user-defined pairs AAA1..
  -> proxy MultiByteToWideChar hook turns those pairs into PUA key chars / Thai letters
  -> proxy ID3DXFont::DrawTextW wrapper looks the key up in FS3_TH_text.txt and draws the full Thai line,
     wrapping at word hints and drawing each consonant+vowel/tone cluster once with the game's own font
```
Details and evidence: [docs/text-pipeline.md](docs/text-pipeline.md), [docs/patch-points.md](docs/patch-points.md).

## Requirements
* Windows, Python 3.12 (standard library only; run scripts with `python -I`).
* For the proxy DLL: Visual Studio / Build Tools with the **x86** C compiler (the game is 32-bit).

## Quick start
```bat
:: 1. copy the game (never work on the installed folder)
robocopy "<Steam>\steamapps\common\FantasiaSango3" work\fs3-copy /E

:: 2. study the data
python -I tools/inventory.py      work/fs3-copy work/inventory     &:: file list + sha256
python -I tools/extract.py        work/fs3-copy work/extracted     &:: unpack every Pack/* archive (hash-verified)
python -I tools/test_roundtrip.py work/fs3-copy                    &:: UJ pak + ZIP rebuild byte-identical
python -I tools/test_dialog.py    work/fs3-copy                    &:: parse all Dia*/Auto*.bin

:: 3. export every dialogue string to a translation sheet (stays on your disk: it contains game text)
python -I tools/export_strings.py work/fs3-copy work/strings_all.tsv
::    fill the last column (thai). Word breaks are added automatically (Windows' Thai dictionary);
::    type | yourself only to override. Translate a repeated line once: rows with the same source reuse it.

:: 4. build the Thai mod data (channel table + translations)
python -I tools/build_channel.py  work/fs3-copy poc/FS3_TH_map.txt work/out
python -I tools/build_keys.py     work/fs3-copy work/out/FS3_TH_map.txt work/strings_all.tsv work/out

:: 5. build the proxy (x86 Native Tools prompt)
cd proxy && build_msvc.bat
```
Install (back up the originals first): `work/out/FS3Bin.dat` and `work/out/FS3UpdataChs.dat` -> `Pack\`;
`work/out/FS3_TH_map.txt`, `work/out/FS3_TH_text.txt`, `proxy/d3dx9_25.dll`, `proxy/FS3_TH_hook.ini` -> game folder
(rename the game's own `d3dx9_25.dll` to `d3dx9_25_orig.dll` first). Step-by-step test procedures: [docs/runtime-tests.md](docs/runtime-tests.md).

Tools take `--set original|patched` where it matters (`original` = use `Pack/FS3Bin.dat.bak` as the clean reference).

## Repository layout
| Path | Contents |
|---|---|
| `tools/ujpak.py`, `tools/fszip.py` | readers + byte-identical writers for the `UJ  ` pak and the obfuscated-ZIP `.dat` archives |
| `tools/fsdialog.py` | parser / same-length writer for `FS2Dialog` / `FS2AutoDialog` script files |
| `tools/export_strings.py` | dialogue strings -> translation TSV (member, block, offset, source, thai) |
| `tools/build_channel.py`, `tools/build_keys.py`, `tools/thaichan.py`, `tools/thaibreak.py` | Thai channel + key-expansion data builders; automatic Thai word breaks via Uniscribe |
| `tools/build_poc.py` | first PoC: Thai written directly into a slot (shows the byte-budget limit) |
| `tools/analyze_*.py`, `tools/procmon_summary.py` | analysers for proxy logs and Process Monitor exports |
| `tools/inventory.py`, `extract.py`, `baseline.py`, `scan_text.py`, `missing_chars.py`, `predict_missing.py` | data survey |
| `proxy/` | `d3dx9_25.dll` proxy source (MSVC, x86) + default ini |
| `poc/translations_poc.tsv` | example translations (2 NPCs) |
| `docs/` | specs: file formats, text pipeline, patch points, open questions, baseline hashes, runtime test log, [Plan B (Godot) feasibility](docs/plan-b-godot.md) |

## Credits
Builds on the user's earlier prototype work (obfuscated-ZIP discovery, dialogue container format, first proxy DLL).
Analysis tooling: Ghidra 12.1.4 via REA was installed but static analysis was not possible because of the DRM wrapper.

Licensed under the MIT License (code and docs only) — see [LICENSE](LICENSE).
