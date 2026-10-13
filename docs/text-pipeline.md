# Text pipeline (black box; FS3.exe code not analysed — DRM not removed, see open-questions Q7)

Confidence: **[V]** observed in a runtime log, **[I]** inferred, **[?]** unknown. Sources: `work/mb2wc_run1.log`, `work/draw_run1.log`, `work/Logfile.CSV`.

```
FS3UpdataChs.dat / FS3Bin.dat  [V override: Updata first]
  -> DiaNNN.bin / AutoNNN.bin block (bytecode; strings cp950, '*' = line break, @@w(n)@@..@@rw@@ markup)   [V format]
  -> Big5 -> GBK(simplified) conversion through Bin/Code/BIG2GB.idx (every Big5 code) [V: exe references it; PoC garbage = its output]
  -> engine splits the text into lines, positions each CHARACTER itself
  -> ID3DXFont::DrawTextW(sprite, text(1-2 chars), cnt=-1, RECT per char, fmt=0, color)   [V]   (D3DX then calls MultiByteToWideChar cp936 on the GBK bytes -> UTF-16 -> GDI ExtTextOutW into its glyph cache)
```
## Measured [V] (draw_run1.log, 17,811 deduped DrawTextW calls, one font family hooked)
* Only **DrawTextW** is used; `fmt = 0` always: **no DT_WORDBREAK, no DT_CALCRECT** -> D3DX does neither wrapping nor measuring. Layout is done in engine code.
* Only two call sites in `FS3.exe` (module+RVA): `+0x297dba` (17,578 calls) and `+0x297d74` (233 calls) — i.e. one text-draw helper. (RVAs are addresses only; the code behind them was not read.)
* Text is drawn **per character or 2-char piece**; the per-char RECT is `[x, y, x+2*size, y+size]` (box width = twice the font height for both ASCII and CJK; it is a clip box, not the advance).
* Advance: CJK = font height in dialogue (24 px font -> 24 px step); menus use their own spacing (31–32 px steps observed at 24/12 px fonts). ASCII advance not measured (**[?]**).
* **Dialogue box (font 24 px):** lines start at x=140, line pitch 26 px (y=467, 493, 519), longest observed line 30 B GBK = 15 full-width chars, last glyph x=476. Line breaks coincide with `*` in the source (Dia039: segments of 30 B and 28 B became two on-screen lines) **[V]**.
* **Item-help text (font 12 px):** lines never exceed 28 B GBK (1,231 events at exactly 28, two at 29 with a full-width '％') -> a hard wrap at ~28 bytes, 14 CJK chars **[V that this limit exists in this view; I that it is a byte limit]**.
* Colours seen: ff000000, ff480909, ff960000, ff0000ff, ff8a3e00, ... (markup `@@w(1|2|9)@@` colour mapping **[?]**).
* Fonts: sizes 12/16/20/24 observed. `D3DXCreateFontA(height=12, charset=0, face "Terminal")` was the first font created in this run; the engine passes `charset=134` to others (earlier log).

## Implications for Thai (Plan A)
1. The engine already positions glyphs one by one, so combining marks cannot float: either (a) pre-composed glyphs per (consonant, vowel/tone) pair in the channel, or (b) hook `my_DrawTextW`-level layout in the proxy (draw base char + mark with an offset). The proxy sees every piece with its RECT, so (b) is feasible without touching engine code **[I]**.
2. Widths are per-character fixed steps (24 px CJK in dialogue). Thai with narrower glyphs would waste space but needs no engine change; proportional spacing requires proxy-side re-layout **[I]**.
3. Byte budget: dialogue line <= ~30 B and help line <= 28 B *if* these are engine limits. Each Thai channel char costs 2 B (Big5 pair) — same as CJK — so a Thai line holds ~14-15 characters (a CJK char carries far more meaning). Longer lines need the proxy to re-wrap or the engine must tolerate longer segments (**[?]**, see Q8).

## Run 2 (draw_run2.log, Dia039 conversation) [V]
* Source string Dia039 block 0 +3043 (Madame Wu) has `*` segments of **36 / 34 / 10 B**; the screen showed exactly three lines of 36, 34 and 10 B GBK. So `*` = hard line break, and a **36 B (18 CJK chars, x=140..548) line is drawn without any engine re-wrap**.
* Corpus segment lengths (bytes between `*`, markup removed): `Dialog` (7,306 segments) peaks every 2 B at 30,32,...,42 (573/464/141/157/237/230/182) then a thin tail to 50 (269 segments > 40 B); `AutoDialog` (12,215, speech-bubble style) peaks at 30/32 (1,217/1,250) with only 78 segments > 40 B. => authors designed the dialogue box for **up to 42 B (21 CJK chars)** and bubbles for ~32 B (16 chars) **[I]**.
* Not observed: a line > 36 B on screen, so whether 38-50 B segments wrap, clip or overflow is still **[?]**.

## Unknown / next
* Behaviour for segments of 38-50 B on screen (Q8): next probe = Dia039 lines with 40/42 B segments (find them with `tools/fsdialog.py`); or force it by editing a segment longer (PoC).
* Opcode layer / how typewriter timing and `@@w@@` are driven (Q1, Q9).
* ASCII/Thai-width advance, line count per box, behaviour when a segment exceeds the box.

## Plan A PoC (2026-10-13) [V]
Data `FS3UpdataChs.dat` (Dia039, same-length edit) -> channel Big5 codes -> `BIG2GB.idx` (patched, in `FS3Bin.dat`) -> GBK user-defined pairs AAA1..AAF7
-> proxy `MultiByteToWideChar` -> U+0E01..0E5B -> engine calls `DrawTextW` per char -> proxy re-layout: real widths, marks/SARA AM joined into one cluster drawn once with the engine font.
Screenshot: `work/poc_shot6.png` (local only - contains game art, never committed).
