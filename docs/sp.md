# FS3_SP (the expansion) — what FS3_SP.exe loads  (branch `FS3_SP`)

Tags as in the other docs: **[V]** verified, **[I]** inferred, **[?]** unknown. Static only so far (exe .rdata strings,
`CFG_SP/AllDesignFile.ini`, archive listings); FS3_SP.exe has the same Steam DRM stub as FS3.exe (open-questions Q7), so the
run-time order still needs the Procmon run below.

## Launch, start to title screen
1. `FS3_SP.exe` sits next to `FS3.exe` and uses the same `steam_api.dll` / `steam_appid.txt`; Locale Emulator has its own
   profile `FS3_SP.exe.le.config` (zh-CN) **[V]**. Same folder, so it loads our proxy `d3dx9_25.dll` too and writes the same
   `FS3_TH_hook.log` **[I]** (one log for both exes: keep the runs apart).
2. Design table list: `Cfg_SP\AllDesignFile.ini` (`VersionStr = 2.0.0`) instead of `Cfg\AllDesignFile.ini` **[V]** (exe string
   @0x411d0c). Every text table moves to `SP\bin\...` (Objects, FS2_Items, FS2_ItemHelp, Fighter(Help), Message, KINDLE,
   FS3Maps, Narrate, Compound, ArrayData, dialog/AutoDialog/Npc ...). Only `bin\menu\ChatMenu.bin` stays shared.
3. Archives: the 7 shared ones (`FS3UpdataChs.dat, FS3Man.dat, FS3Bin.dat, FS3UI.pak, FS3Data.pak, FS3MergeImage.pak,
   Patch.pak`) **plus `Pack\SP_FS3.pak`** (exe string @0x4173fc, only in FS3_SP.exe) **[V]**.
   `SP_FS3.pak` = UJ pak, 414 leaves under `/Bin /Data /MergeImage`; it is mounted as `SP\` **[I]** (ini paths `SP\bin\X`
   all exist as `/Bin/X` in the pak; exe has `SP\Bin\Dialog\`, `SP\Bin\AutoDialog\`, `SP\Bin\Schedule\`, `SP\MergeImage\*SP.Img`).
   `SP_FS3.pak` is pristine: byte-identical to `SP_FS3.pk.pak` (baseline.md).
4. Shared with FS3 (same strings in both exes) **[V]**: `Bin\Code\BIG2GB.idx` (in FS3Bin.dat: our Thai channel applies to
   SP as is), `Font\GB\FontTypeS.bin`, `\CFG\*.XML` UI layouts (DialogINI, TradeMenu, WorkingHouse ... from `CFG\`, not
   `CFG_SP\`), `CFG\FloatingNum\`.
5. Loose `CFG_SP\DefaultString.bin`, `CFG_SP\Mission.bin` (+ pristine `.bnk.bin` copies, same bytes) **[I]** used the way
   FS3 uses `CFG\` ones (the ini names `SP\bin\FS2_DefaultString.bin / FS2_Mission.bin`, which are in no archive -- same
   as FS3's ini).
6. Saves: `Save\SP\Uj_SPFS%02d.sav`, `Uj_FS%02d.sav`, `Uj_AutoFS%02d.sav`, magic `UjFS3SPSaveFile` **[V]** (strings).
7. `Pack\SP_FS3Updata.dat` = `loadersetupsp.ini` (old retail FSLoader for `FS.EXE`), `Version.txt`, `Font/CH/fonttype.bin`;
   no exe references it **[?]** probably unused. No text to translate.

## Text inventory — `export_strings.py <game> work/sp/strings_sp.tsv --sp`
Members are named as the engine asks for them: `SP/Bin/...`, `CFG_SP/...`, `FS3_SP.exe`. 12,509 strings / 5,856 unique.
All parsers of the FS3 pipeline work unchanged except KINDLE.BIN and FS3Maps.BIN, whose record counts now come from the
header @40 (SP: KINDLE 902/1533/790, FS3Maps 55; for FS3 the result equals the old constants, FS3 export byte-identical).
Reuse of `work/strings_master.tsv` (same source text): 4,801 / 5,856 unique already translated (`work/sp/strings_sp_prefill.tsv`).
Still new: mostly the SP story (Dialog 506 rows, AutoDialog 439), FS3Maps 30, Narrate 30, Mission 16, FS3_SP.exe 15.
Not exported (same as FS3): `Bin/Schedule/NPC*.bin`, `FS2_RoleManDefault`, `*.mig`, `*.BFL`. Empty in SP: `BlessTable.bin`.

## Risks while the FS3 mod is installed
* Thai channel codes: 24 SP occurrences of channel Big5 chars (骷 瑤 瓣 茹 蠐 怦 絢 尼) would draw as Thai letters until translated.
* Does `FS3UpdataChs.dat` (modded, `Bin/...` members) shadow anything that FS3_SP opens as `SP\bin\...`? **[?]** -> Procmon.

## Runtime test for the user (Procmon)
Filter: `Process Name is FS3_SP.exe`, `Path contains FantasiaSango3`; start capture, run FS3_SP.exe, go to the title
screen, start/load a game, quit. Export CSV (Time of Day, Process Name, PID, Operation, Path, Result, Detail) to
`work/sp/procmon_sp.csv`, plus one screenshot of the title screen and one of SP dialogue. Analyse with
`tools/procmon_summary.py <game> work/sp/procmon_sp.csv` (SP_FS3.pak is in its archive set).

## Build (2026-10-24) [V on work/testgame: install, v1 -> this upgrade, uninstall back to pristine]
One package for both exes (same folder, same proxy, one text-id space): the SP sheet is appended to the FS3 sheet.
```bat
python -I -c "import sys; a=open('work/strings_master.tsv',encoding='utf-8').read(); b=''.join(l for l in open('work/sp_save/strings_sp_prefill.tsv',encoding='utf-8') if l[0]!='#'); open('work/strings_master_sp.tsv','w',encoding='utf-8',newline='\n').write(a+b)"
python -I tools/build_channel.py work/fs3-copy poc/FS3_TH_map.txt work/out_sp
python -I tools/build_keys.py    work/fs3-copy work/out_sp/FS3_TH_map.txt work/strings_master_sp.tsv work/out_sp poc/key_ids.tsv
python -I tools/make_dist.py     work/fs3-copy work/strings_master_sp.tsv work/sp/d3dx9_25.dll work/launcher/install.exe work/dist_sp work/python-embed.zip
```
* build_keys: `SP/...` members are patched IN PLACE into `SP_FS3.pak` (65 members, `ujpak.patch_in_place`: same offsets, same size; a rebuilt pak moved 400 of 414 entries and the hero's skill effect drew as flat yellow quads, plana-sp1 2026-10-24 -- cause not proven, fix to be confirmed in game), `CFG_SP/*` from their `.bnk.bin`,
  `FS3_SP.exe` rows go to `FS3_TH_exe.txt` (patterns FS3.exe already has are skipped). FS3-only input still builds byte-identical.
* All 127 SHORT ids (slots < 6 B) were taken by FS3: SP's 2-byte choices 是 / 否 (Dia028, Dia053) keep their Chinese and
  `FS3_TH_exe.txt` gets `是 -> ใช่`, `否 -> ไม่` (exact whole-string match only).
* Same-source reuse also fills FS3 rows: FS3's staff credits (FS2_Narrate 38-65, untranslated before) now take the SP translation.
* Installer: also backs up / rebuilds `Pack/SP_FS3.pak`, `CFG_SP/DefaultString.bin`, `CFG_SP/Mission.bin`; checks
  `FS3_SP.exe`, `SP_FS3.pak`, `CFG_SP/*.bnk.bin` (source_hashes.txt).
* Not yet seen in game: FS3_SP needs a play test (title, SP dialogue, the 是/否 choice, item/skill screens).

## Title-screen credit (v2) [V 2026-10-24, FS3 + FS3_SP title screens]
The version number (`1.1.2023.10.26` FS3 / `2.1.2023.10.26` FS3_SP, ASCII literal in each exe, one DrawTextW at x=656 y=574 in
800x600) is a drawn-text replacement: build_keys writes `<version>\tแปลไทยโดย ชายกลัวดอกพิกุล <version>\tr` (CREDIT in build_keys.py).
The 3rd column `r` (proxy `g_rr` / `g_ralign`) right-aligns the replacement to where the game's own text ended (measured with the
engine font), no panel rule, so it holds at any resolution.
The UserJoy logo before the title is Bink video (`IMAGE/*.Bks`, exe also names `Anim\logo.bik`, not on disk): no credit there
(re-encoding Bink needs RAD's encoder).
