# Patch points (Plan A) — where Thai can enter, safest first

FS3.exe is Steam-DRM wrapped and is **not** modified or unpacked (user decision, open-questions Q7). Every patch point below is data or the proxy DLL.
Confidence tags as in the other docs.

| # | Point | What changes | Risk | Status |
|---|---|---|---|---|
| 1 | **`FS3UpdataChs.dat` members** (dialogs, `Message.bin`, `FS2_Items.bin`, ...) | Strings replaced with Thai-channel Big5 codes, **same byte length or shorter (NUL pad)** via `fsdialog.patch_same_len` + `fszip.write_like` | Low: bytecode/jump targets untouched; archive rebuilt byte-identical except edited members. Must be Updata, not FS3Bin: Updata overrides (Q2 [V]) | **PoC working [V]** (Dia039) |
| 2 | `FS3Bin.dat` member `Bin/Code/BIG2GB.idx` | 87 entries: channel Big5 code -> GBK user-defined pair AAA1..AAF7 (`tools/build_channel.py`) | Low: pairs never produced by any other code [V, checked over the whole table]; channel codes unused in dialog text [V]; Updata has no `Code/` so FS3Bin's copy is live. (The prototype patched `b2g.dat`, which the engine never loads.) | **PoC working [V]** |
| 3 | Proxy `MultiByteToWideChar` hook | reserved GBK pair -> U+0E01..0E5B (`FS3_TH_map.txt`) | Low: only fires on reserved pairs; other text goes to the real API | done (prototype) |
| 4 | Proxy `ID3DXFont::DrawTextW` vtable wrap | Thai pieces drawn with a Thai font, own pen per row, marks zero-advance, tone lift | Medium: layout heuristics (row = same font+y; new pass when x goes back), no real shaping; vtable layout is runtime-verified before patching | **PoC working [V]** (engine font for glyphs; own Thai font crashes d3dx9_25 on combining marks) |
| 5 | Same-length limit | Thai = 2 B/char like CJK but needs ~2-3x the characters | **Budget is the real constraint**: the PoC line kept 3 short Thai lines in 82 B. Full translation needs either terse Thai, or relocation (needs opcode layer Q1, engine code unavailable) | open |
| 6 | Growing strings | rewrite block + TOC + descriptors + **jump targets** | High without the opcode layer; blanket "fix every u32 that looks like an offset" corrupts game logic (prior analysis) | not attempted |
| 7 | Engine binary | — | out of scope (DRM) | rejected |

Ideas not yet tried, ranked:
* **Proxy-side text expansion — DONE, works in game [V]:** each slot holds a 6-byte key (U+E000 + 2 base-128 digits via Big5 FA41..FAE3 -> BIG2GB.idx -> GBK UDA -> PUA); the proxy draws the Thai text from `FS3_TH_text.txt`, wrapping at U+200B hints. Byte budget removed; limit is the box (~4 lines). Tools: `build_channel.py`, `build_keys.py`; translations: TSV of (member, block, offset, thai). Cost: no typewriter reveal on expanded lines; Thai glyph size still from the engine font fallback (Q12).
* Single-byte packing (one Thai char per byte) is impossible through this engine: bytes >= 0x80 are always consumed as 2-byte pairs [V prototype PROXY_DLL.md].
