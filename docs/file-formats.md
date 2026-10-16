# File formats (Fantasia Sango 3, Steam build)  — step 1 findings

Confidence: **[V]** verified by running code on the files, **[I]** inferred, **[?]** unknown.

## Layout of the install  [V]
873 files / 2.5 GB. `FS3.exe` (PE32, x86, 5.5 MB), `FS3_SP.exe`, `Pack/` (11 archives), `IMAGE/*.Bks` (stage streams, magic `FS3_StageBink_1`),
`Map/*.map|*.img` (330 maps), `Sound/*.bin`, `Music/*.mp3`, `CFG/` (UI XML, plain UTF-8), `CFG_SP/`.
`d3dx9_25.dll` / `_orig` / `_hook` and `FS3_TH_*` are the user's earlier Thai-hook prototype, not part of the game.

## A. "UJ  " pak (`FS3Data.pak, FS3UI.pak, FS3MergeImage.pak, Patch.pak, SP_FS3.pak`)  [V] — `tools/ujpak.py`
Nested, **uncompressed, unencrypted**. All LE.
```
0x00 "UJ  "   0x04 u16 ver=1   0x06 u32 total_size   0x0A u32 index_off (relative to this pak's start)
0x0E u32 entry_count          0x12 char name[]  (header is 0x80 bytes, payload starts at 0x80)
index @ index_off: entry_count * 128 B:  name[64] | u32 off @0x40 | u32 size @0x44 | u32 flag @0x48 (1=dir/sub-pak, 0=file) | pad
```
Offsets inside a sub-pak are relative to the sub-pak's own `UJ  ` header; a payload that starts with `UJ  ` is a sub-pak. Example (Patch.pak):
`55 4A 20 20 01 00 | 47 08 0F 00 | 47 07 0F 00 | 02 00 00 00 | "Data"`, entry0 `CombatScenes` off=0x80 size=0xBB99A flag=1.
Leaf files are raw DDS/TGA/BWN(model)/CFX(fx)/BIN. 8,424 files in FS3Data.pak. `SP_FS3.pk.pak` is byte-identical size to `SP_FS3.pak` (duplicate).

## B. "*.dat" = ZIP with obfuscated signatures (`FS3Bin.dat, FS3Man.dat, FS3UpdataChs.dat, SP_FS3Updata.dat`)  [V] — `tools/fszip.py`
Standard ZIP (stored/deflate, CRC32 valid — `testzip()` passes on all) but every `PK` signature is `03 05`:
`03 05 03 04` local header, `03 05 01 02` central dir, `03 05 05 06` EOCD. Patch those 4 bytes at the offsets found via EOCD → central dir → local headers, then use `zipfile`.
Do not blind-replace: random hits occur inside deflate data. Filenames are ASCII (2 non-ASCII names in FS3UpdataChs, GBK/CP437 bytes).
`FS3Bin.dat` = game tables (`Bin/*.bin`), codepage tables (`Bin/Code/*`), dialogs (`Bin/Dialog`, `Bin/AutoDialog`, `Bin/Schedule`, ~308 each), menus. `FS3Man.dat` = `Man/*.PS2` character models.
**`FS3UpdataChs.dat` (936 files) overrides `FS3Bin.dat`** (same `Bin/Dialog/DiaNNN.bin`, `FS2_Items.bin`, `Message.bin`, `KINDLE.BIN`...). **Override [V, step C runtime log]:** the engine reads `FS3UpdataChs.dat` first and takes a member from it when present; `FS3Bin.dat` supplies the rest (see open-questions Q2).
`FS3Bin.dat.bak` is the user's pre-patch backup: differs from `.dat` in ~300 dialog bins, `Message/FS2Message/SGmessage.bin` and `Bin/Code/b2g.dat` (87 entries). Not original-vs-patched Thai; the dialog diffs are **[?]**.

## C. Text  [V unless noted]
* On-disk encoding of dialog/item/help text is **Big5 (Traditional)** — e.g. `Dia250.bin`: 506/506 candidate runs decode as Big5, 1 as GBK. `CFG/*.XML` are plain UTF-8 UI layout files (no story text).
* Strings are **NUL-terminated, packed back to back** inside binary table files (`FS2Dialog` header magic, 0x20-byte name field). Example `Dia250.bin @0xA04`:
  `a5 bb a8 d3 a4 a3 b7 51 b0 ca ... 00` (second string of the first text group). Per-record length fields / pointer tables **[?]**, not yet decoded.
* In-text control chars seen: `*` = line break (also `* * *`), `∼` (A1 5C?) as tilde, `%02d`-style printf in `Message.bin`; `<` `>` `\` `@` `#` `$` `^` `{}` `|` `&` occur at high counts but many are binary noise — **[?]** need per-file parse.
* Corpus (dialogs, items, KINDLE, Message): 243,278 chars, **2,927 distinct Big5 chars**; 170 of them are *not* in the original `b2g.dat` **[V]** (e.g. 並 雲 幾 欸 — behavior in engine **[?]**).
* Dialog/item file counts: 308 `Dia*.bin`, 308 `Auto*.bin`, 307 schedule files, `FS2_ItemHelp.bin` (1,125 Big5 strings, 74 KB, sequential NUL strings).

## D. Code-conversion tables `Bin/Code/` (inside FS3Bin.dat)  [V]
| file | size | notes |
|---|---|---|
| `BIG2GB.idx` | 131,072 | **The table the engine actually uses [V]** (FS3.exe `.rdata` names `Bin\Code\BIG2GB.idx` and `GB2BIG.idx`, never `b2g.dat`; in-game garbage from the PoC equals this table's output). Index = the two text bytes read as a little-endian WORD (`lead | trail<<8`); stored 2 bytes = GBK bytes in order. Converts all 13,973 Big5 grid codes (traditional -> simplified GBK). |
| `b2g.dat` | 131,072 | Big5→GBK, **not loaded by the engine** (agrees with BIG2GB.idx on 6,696 of its 6,727 entries). Array of 65,536 × 2 bytes indexed by the Big5 code `(lead<<8)|trail`; the 2 stored bytes are **GBK lead, GBK trail in order** (A4A4 中 → `D6 D0`). 6,727 non-zero entries, lead A1–F9; stored GBK values span 0x8141–0xFDC9. |
| `b2j,j2b,b2u,u2b,g2b` | 131,072 each | other directions (JIS/Unicode/GBK→Big5), same shape **[I]** |
| `BIG5table.dat / GBtable.dat` | 29,516 / 47,880 | glyph/char lists **[?]** |
| `BIG2GB.idx / GB2BIG.idx` | 131,072 | index tables **[?]** |

* Of the 6,727 original entries, 4,490 map to the same character under Python's big5/gbk codecs; 2,227 differ (punctuation/box-drawing and variant chars) — the engine's table, not a codec, is authoritative.
* **`b2u.dat` [V]**: same shape (65,536 x 2 B), index = Big5 code, value = Unicode **big-endian** (劉 BC42 -> 5289, 裡 B8CC -> 88E1, 雲 B6B3 -> 96F2); 65,154 non-zero entries, so it covers almost all Big5 codes while `b2g.dat` covers 6,727.
* **Wire format [V, runtime]:** the text that reaches `MultiByteToWideChar` (cp 936) is simplified GBK (character names and UI words arrive in simplified form). `b2g.dat` therefore stores the traditional->simplified GBK conversion. Chars without a `b2g` entry still arrive simplified (里 几 云 游 observed) [I: via b2u + LCMapStringW].
* **Free Big5 grid slots** (lead A1–F9, valid trail, zero entry): **7,246**, mostly in C6–F9 (~120–157 per lead). These are the candidate "channel" codes.
* The working copy's `b2g.dat` already carries the user's 87 patched entries (GBK `8141…` pairs → Thai, see `FS3_TH_map.txt`); the original is in `FS3Bin.dat.bak`.

## E. Not yet analysed
`Map/*.map` (starts `E4 F4 87 00 | 27 78 01 00 | 78 DA…` = zlib after 8-byte header **[I]**), `Map/*.img` (u32 id/offset/size triples **[I]**), `IMAGE/*.Bks`, `Sound/*.bin` (offset/size pairs **[I]**), `*.BFL/.FAI/.NM` UI/combat tables, `CFG/*.bin` (named header + u32 tables, e.g. `DefaultString`).

## F. Dialog files `Bin/Dialog/DiaNNN.bin` (FS2Dialog), `Bin/AutoDialog/AutoNNN.bin` (FS2AutoDialog)  — parser: `tools/fsdialog.py`
Layout matches the earlier spec in `D:\FS3_TH_mod\FS3_FORMAT_SPEC.md`; re-verified here on all 614 files of the original set (my first notes in this section were wrong: the `(1,3,0x890)` "triplets" are bytecode, the block is `abs_off=56, len=76486`).
```
name[40] "FS2Dialog"/"FS2AutoDialog" | u32 count @40 | count x { u32 f0, u32 abs_offset, u32 length } @44 | blocks back to back   [V: TOC tiles file, 614/614]
```
* A block is compiled **bytecode**. Text = *groups* of k NUL-terminated cp950 strings preceded by k descriptors; stride/offset field: FS2Dialog 84 B / +16, FS2AutoDialog 16 B / +12; field = running sum of previous string lengths incl. NUL (first = 0). **[V]** 2,574 groups, 10,244 strings validated (original set); `tools/fsdialog.py` rebuild() re-serialises all 614 files byte-identically.
* Encoding **cp950** (not Python's `big5`, e.g. `F9 D8`). Longest string 229 B.
* Markup census over validated strings **[V]**: `*` = line break (9,196), `@@w(n)@@`/`@@W(n)@@` = start styled run (914), `@@rw@@`/`@@RW@@` = end (659), one `~`. No other control syntax occurs in these strings (the `< > \ # $ ...` seen in my first raw scans were binary noise). Bytes < 0x20 inside a string would have excluded it from the parse - none was found among validated groups, but strings rejected for that reason are not counted **[?]**.
* **Resizing is unsafe [V by prior analysis, not re-measured]:** blocks hold block-relative jump targets; changing a string's length requires relocating them (opcode layer unknown, Q1). Writer therefore offers `patch_same_len()` only (new <= old bytes, NUL-padded; engine tolerance of NUL padding **[?]**, the prototype did the same).
* Interesting: `FS3UpdataChs.dat` Dia006 is 43 B longer than the `FS3Bin.dat.bak` version, so the developers' own tool does relocate.
* **Why `.dat` differs from `.bak` [V]:** 306 members: 134 `Dia`, 166 `Auto`, `DIALOG.BIN`, `AutoDialog.BIN`, `Message/FS2Message/SGmessage.bin` and `b2g.dat`. Same sizes; the patched dialogs have their text overwritten in place with Thai-channel Big5 codes (your prototype). No offset table changed.
* **`FS3Bin` (original) vs `FS3UpdataChs`:** 604 of 614 dialog files identical, 10 differ (Updata is the later revision: line-break `*` moved, wording fixed, Dia006 gains a line). Load order unknown (Q2, runtime test C).

## Bin/Objects.bin (speaker / object names) [V 2026-10-13]
`u32 count` (4300) + `count` x 104-byte records. Record +0 = name[20], cp950, NUL-terminated (longest 19 B), zero-padded; the other 84 bytes are not decoded. Size check: 4 + 4300*104 = 447,204. The name is the label drawn above the dialogue box. Parser/writer: `tools/fstables.py` (address = record index, offset 0). `FS3UpdataChs.dat` holds the live copy (differs from `FS3Bin.dat` at byte 102,445).

## Bin/FS2_Items.bin, Bin/FS2_ItemHelp.bin (item names / descriptions) [V 2026-10-13]
* `FS2_Items.bin`: name[40] `FS2ItemData`, `u32 count` @40 (1860), records of 124 B from @44; name[16] at record +0 (longest 14 B). Live copy in `FS3UpdataChs.dat` (`BIN/`).
* `FS2_ItemHelp.bin`: name[40] `FS2ItemHelp`, `u32 count` @40 (1860, same index as FS2_Items), `count` x u32 offsets @44 relative to the blob at 44+4*count, blob = NUL-terminated cp950 strings that tile it exactly (14 empty). Only in `FS3Bin.dat` (`Bin/`), so the mod rebuilds `FS3Bin.dat` for it. Rewritten with new offsets, so strings may change length.

## Bin/FS2_Fighter.Bin, Bin/FS2_FighterHelp.bin (skills) [V structure 2026-10-13]
name[40] + u32 header values @40 + offset lists back to back + other records + one string blob at EOF holding every list's NUL-terminated strings in list order (each list's offsets start at 0 for its own sub-blob).
* `FS2_Fighter.Bin` header (100, 520, 288, 1106, 20, 16, 4, 13): lists are header[0,2,5,6,7] = 100 (beast-seal / passive entries) @0x48, 288 skill names @0x1D8, 16 @0x658, 4 categories @0x698, 13 target types @0x6A8; records 0x6DC..0x2686C (520/1106/20 not decoded); blob 2,165 B.
* `FS2_FighterHelp.bin` header (65, 166, 15): lists @0x34; help list 1 index = skill list 1 index (checked on 2 skills), list 0 = list 0 entries.
* Only in `FS3Bin.dat`. Written same-length and padded with spaces, so the blob keeps its NUL count (the engine might find sub-blobs by counting strings). Address: block = list, offset = index. `tools/fstables.py`.

## Bin/ArrayData.bin (battle formations) [V structure 2026-10-13]
name[40] `FS2ArrayData`, `u32 groups` @40 (226), groups x (u32 first record, u32 record count) @44, then 282 records x 636 B (1,852 + 282*636 = 181,204). Record +4 = name[12] cp950 (longest 10 B); one record per formation level (蟠龍陣 x8). 18 distinct names incl. placeholders 保留 / 無. Live copy in `FS3UpdataChs.dat`. `tools/fstables.py` (address = record, 0).

## BIN/Message.bin (UI labels, menus, system messages) [V structure 2026-10-14]
`MSGV2.0` + NUL, `u32` records @8 (931), `u32` strings @12 (798), 931 x 48-byte records from 16, then 798 x (`u32` length incl. NUL, cp950 bytes) ending exactly at EOF (string area @0xAEA0). No u32 in the record area lies between 1,000 and the end of the string area, so records do not point at string byte offsets; strings are addressed by index and rewritten at any length (`tools/fstables.py`). 147 strings are printf templates (`%d`, `%s`, `@@W(10)@@%s@@RW@@ ...`) and are not exported: a key would drop the inserted value. Live copy in `FS3UpdataChs.dat` (the `FS3Bin.dat` copy holds the user's old prototype).

Menu labels seen as DrawTextW text (plana-a6/a7 logs): title menu, save slots, stat names, inventory tabs and headers. The top menu bar (队伍 物品 武学 ...) is not drawn as text (image).

## CFG/DefaultString.bin (battle popups, mission goals) [V structure 2026-10-17]
Loose file outside the archives, same layout as FS2_ItemHelp.bin: name[40] `DefaultString`, `u32 count` @40 (1300), offsets, tiling string blob (620 non-empty, 44 printf templates). The original is `CFG/DefaultString.bin.bak` (22,795 B); the installed 9,021 B file is the user's old prototype (markers like `L985`). Tools read `.bak` when present and write `out/CFG/DefaultString.bin`.

## FS3UI.pak UI textures [V 2026-10-17]
UJ pak (`UI_Chs`): Default.dds, Combat/, combo/, FsFx/, LvUp/, Map/, Menu/ (370), Vic/. DXT3/DXT5 (298 DXT5, 248 DXT3, 9 RGB32, 1 DXT1), menu labels 128x64, 1 mip, transparent with a white glow. Image-only text: top menu bar `Menu/M_{Team,Item,Martial,Pet,System,Mission}` and sub tabs `Menu/M_S_*`, each in 4 states `_Nor/_Ove/_Pre/_Dis`. Victory / level-up titles (战斗胜利, 等级提升) and 获得银两 are NOT images: DrawTextW text (Message.bin 553 / 554 / 557, drawn cell by cell at 32 px). `tools/fsdds.py` (DDS<->PNG, writes A8R8G8B8), `tools/build_ui.py` (renders Thai labels, repacks FS3UI.pak; the pak round-trips byte-identically).
