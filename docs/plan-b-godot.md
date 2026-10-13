# Plan B — rebuilding FS3 on Godot 4.x: feasibility and next steps

Confidence: **[V]** verified on the files / in game, **[I]** inferred, **[?]** unknown. Date: 2026-10-13.

## สรุปสำหรับตัดสินใจ (Thai summary)
* **สร้างเกมใหม่ทั้งเกมบน Godot ทำได้ในทางเทคนิค แต่เป็นงานขนาดหลายปีคน** ส่วนที่หนักไม่ใช่ภาพหรือเสียง แต่เป็น
  (1) ชั้น opcode ของสคริปต์เหตุการณ์ (`Dia*/Auto*.bin`, `MapEvent.BIN`, `Schedule`) ที่ยังไม่รู้ และ
  (2) ตรรกะเกม (สูตรต่อสู้ AI เงื่อนไขเนื้อเรื่อง) ซึ่งอยู่ในโค้ดของ `FS3.exe` ที่อ่านไม่ได้เพราะเราเลือกไม่แตะ DRM
  ต้องอนุมานจากพฤติกรรมในเกมทั้งหมด
* **ภาษาไทยบน Godot ไม่ใช่ปัญหา:** TextServerAdvanced (HarfBuzz + ICU) วางสระ/วรรณยุกต์และตัดคำไทยได้เอง
  ปัญหาของ Plan A ทั้งหมด (ไม่มี shaping, glyph เล็ก, งบไบต์) หายไป
* **ข้อแนะนำ:** อย่าเริ่มจากการสร้างใหม่ทั้งเกม ให้เดินสองทางพร้อมกัน
  1. **Plan A ทำต่อให้เป็น mod ที่เล่นได้จริง** (ทำงานในเกมแล้ว) เพราะได้ผลเร็วที่สุด
  2. **Plan B เริ่มจาก "B0: Dialogue Viewer"** ขนาดเล็ก ใช้ parser ร่วมกับ Plan A ใช้เป็นเครื่องมือตรวจคำแปล
     และเป็นฐานของ Plan B แล้วค่อยตัดสินใจลงทุนเต็มรูปแบบหลังถอด opcode layer ได้ (ซึ่งช่วย Plan A ด้วย)

## 1. What a remake must read — inventory with status

| Data | Where | Format status | Difficulty | Godot target |
|---|---|---|---|---|
| Archives | `Pack/*.pak` (UJ), `Pack/*.dat` (ZIP, `PK`→`03 05`) | **[V]** readers + byte-identical writers (`ujpak.py`, `fszip.py`) | done | — |
| Override order | `FS3UpdataChs.dat` over `FS3Bin.dat` | **[V]** (Procmon) | done | loader rule |
| Dialogue text | `Bin/Dialog/Dia*.bin`, `Bin/AutoDialog/Auto*.bin` | container + string groups **[V]** (`fsdialog.py`, 10,292 strings); **bytecode opcodes [?]** | text easy / logic **hard** | JSON + Translation (PO/CSV) |
| Event scripts / schedules | `MapEvent.BIN`, `Bin/Schedule/*`, `FS2_EVENT.BIN`, `DIALOG.BIN` | **[?]** same bytecode family [I] | **hard** (needs a VM) | GDScript interpreter of decoded ops |
| Data tables | `FS2_Items`, `FS2_ItemHelp`, `FS2_Fighter`, `MartialArt`, `NPC`, `RoleInf`, `KINDLE`, `Compound`, ... (~60 files) | named-header fixed-record tables + string pools **[I]**; `DefaultString.bin` **[V]** (prior work) | medium each, many files | JSON / Resources |
| UI layout | `CFG/*.XML` (UTF-8: DialogINI, TradeMenu, WorkingHouse...) | plain XML **[V]** | easy | Control scenes generated from XML |
| UI textures | `FS3UI.pak` (557 DDS/TGA) | standard DDS/TGA **[V]** | easy | PNG (convert) or DDS import |
| Field maps | `Map/*.MAP` | u32 raw size, u32 packed size, **zlib** **[V]**; header `2400, 1800, 100, 100, 24, 18` = 2400x1800 px in 100 px tiles **[I]** | medium | TileMap / Sprite2D layers |
| Map image banks | `Map/*.img`, `FS3MergeImage.pak` (`BottomLayer.Img`, `SaveMap.Img`, `Head.HED`, `Items.img`) | index of (id, offset, size) **[V]**; pixel format **[?]** | medium | PNG atlases |
| Field characters | `FS3Man.dat` `Man/*.PS2` (251) | u32 raw size, u32 packed size, **zlib** **[V]**; inner sprite/animation format **[?]** | medium | SpriteFrames / AnimatedSprite2D |
| Combat 3D | `FS3Data.pak`: `.bw3` 1,002, `.bwc` 480, `.bwn` 40, `.bwm` 22, `.cw3` 6 | custom exporter formats (node names like `Plane02`, source paths inside) **[V header only]** | **hard** | glTF via converter |
| Effects | `.cfx` 960, `MapFx.BFL`, `MapParticle.BIN` | **[?]** | hard | GPUParticles / custom |
| Textures | `FS3Data.pak` 5,623 DDS | standard **[V]** | easy | DDS import or PNG |
| Stage backgrounds / video | `IMAGE/*.Bks` (1.05 GB) | named table + **Bink** streams (`BIK` magic) **[V]** | easy-medium | OGV (Theora) via ffmpeg at conversion time |
| Music | `Music/*.mp3` (63), `.wav` (3) | standard **[V]** | easy | AudioStreamMP3 |
| Sound effects | `Sound/Sound.bin`, `spSound.bin` | offset table + **RIFF WAV** **[V]** | easy | WAV/OGG |
| Game rules | combat formulas, AI, flags, shop logic | **not in data; engine code unreadable (DRM not removed)** | **very hard** | re-design from observation |

## 2. Thai support in Godot 4.x
* Text rendering: the default desktop text server **TextServerAdvanced** uses HarfBuzz shaping and ICU, so Thai vowels and tone marks
  stack correctly with any OpenType Thai font. **[I — Godot docs; to verify in the B0 prototype]**
* Line breaking: Thai has no spaces, so dictionary-based break iterators are needed. Godot includes the ICU data in the editor but
  **not in exported projects**: enable *Project Settings → General → Internationalization → Locale → Include Text Server Data*
  (≈ 4 MB). **[V — official docs]**
* Fonts: ship an OFL Thai font (e.g. Noto Sans Thai, Sarabun) as the primary or fallback font. **[I]**
* Translations: TranslationServer with CSV or gettext PO files; `tr()` / auto-translate on Controls. Our `poc/translations_*.tsv`
  (member, block, offset, Thai) converts directly to PO msgctxt/msgstr keyed by the same address. **[I]**
* Compared with Plan A: no byte budget, real shaping, proper glyph size, RichText effects (typewriter, colours for `@@w(n)@@`).

## 3. Proposed architecture
```
user's own game copy ──► converter (Python, this repo, runs locally) ──► intermediate folder on the user's disk (never in git)
   Pack/*.dat|*.pak        ujpak / fszip / fsdialog / table parsers         json/   dialogue, tables, events (decoded)
   Map, IMAGE, Sound...    zlib, image-bank and sprite decoders            img/    PNG atlases, tiles, portraits
                           ffmpeg (user-installed) for Bink               audio/  OGG/WAV/MP3,  video/ OGV
                           3D converter (later)                           models/ glTF
                                                                                  │
Godot 4 project (code only, MIT) ──── reads the intermediate folder at runtime (path chosen on first start, FileAccess / Image.load)
   - DialogueBox scene (RichTextLabel, Thai font, typewriter)       - Translation from PO generated by the converter
   - MapScene (TileMap from .MAP + .img)  - EventVM (later, after opcode RE)  - Combat (much later)
```
Rules: the Godot project and the converter contain **no game data**; assets are produced on the user's machine from their copy
(like ScummVM/OpenMW). Imported resources are loaded at runtime from the user folder instead of being baked into `res://`.

## 4. Roadmap (milestones, rough effort, decision points)

| # | Milestone | Content | Effort [I] | Depends on |
|---|---|---|---|---|
| **B0** | **Dialogue Viewer** | Godot app: pick a Dia/Auto file → list groups/strings with speaker, show Chinese (from user data) side by side with Thai (from TSV/PO) in a dialogue box styled with the FS3UI dialog texture; Thai shaping + wrapping check; export to Windows | 3–5 days | existing parsers; DDS→PNG |
| B1 | Map backdrop | decode `.MAP` + `.img` → render one town (Dia039 town) as a static scene | 1–3 weeks | image-bank pixel format |
| B2 | Field sprites | decode `Man/*.PS2` → animated NPC/player on the map, simple walking | 2–4 weeks | sprite format |
| B3 | Opcode layer | decode `Dia/Auto` bytecode (branching, jumps, speaker, waits, flags) by data-diffing + in-game observation via the proxy | 1–3 months, open-ended | B0 tooling; also unlocks Plan A string resizing + typewriter |
| B4 | Event VM | GDScript interpreter that plays one story scene end to end | 1–2 months | B3 |
| B5 | Systems | menus, items, shops, save — from tables + CFG XML | months | table parsers |
| B6 | Combat | 3D formats → glTF, battle rules re-designed from observation | 6–12+ months | 3D RE; rules unreadable |

**Decision point after B0+B3:** if the opcode layer decodes cleanly, a story-only remake (field + dialogue, simplified combat) becomes
realistic; if not, Plan B stays a viewer/QA tool and Plan A is the delivery vehicle.

## 5. Minimal first prototype (B0) — concrete spec
1. Converter: `tools/export_dialogue.py <game_copy> <out>` → `out/dialogue/DiaNNN.json` (`[{block, offset, group, index, text_cp950, ...}]`) and
   `out/ui/dialog_box.png` (from FS3UI.pak DDS). Output lives in the user's folder only.
2. Godot 4 project `godot/` (code only): `Main.tscn` with a FileDialog to pick `out/`, a list of files/groups, a `DialogueBox.tscn`
   (`NinePatchRect` with the converted texture + `RichTextLabel`, Noto Sans Thai, `autowrap_mode = WORD_SMART`, typewriter via `visible_characters`).
3. Translations: `poc/translations_poc.tsv` → `godot/translations/th.po` (msgctxt = `Dia039:0:3043`).
4. Acceptance: Madame Wu's line (Dia039 block 0 +3043) and the shopkeeper line (Dia040) render in Thai with correct stacking and
   word wrapping in an **exported** build (proves *Include Text Server Data*).

## 6. Series reuse
The archive readers, the dialogue container parser and the converter → JSON → Godot pattern carry over to other Fantasia Sango titles
only if they share the UserJoy engine generation (FS2/FS3 share `FS2Dialog` magic **[V]**). FS4/FS5 formats are **[?]**; check the
archive magics first (`UJ  `, `03 05 03 04`).

## 7. Open questions specific to Plan B
* Pixel formats of `.img` / `.Img` / `.HED` banks and the inner `PS2` sprite layout.
* Opcode semantics (shared with Plan A Q1); whether `MapEvent.BIN` / `Schedule` use the same VM.
* Meaning of the combat model formats (`.bw3/.bwc/.bwn/.bwm/.cw3`) and `.cfx`.
* Whether Godot's DDS importer handles all FS3 DDS variants (verify in B0; fallback: convert to PNG in the converter).
