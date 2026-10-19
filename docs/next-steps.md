# แผนงานถัดไป (Plan A) — ฉบับละเอียด

สถานะ ณ 2026-10-17: ระบบแสดงภาษาไทยเสร็จและผ่านการทดสอบในเกมแล้ว (ชุดทดสอบล่าสุด `work/plana-a30` + ini จาก `work/plana-a32`)
รายละเอียดหลักฐานแต่ละขั้นอยู่ใน [open-questions.md](open-questions.md) (Q1–Q22) และรูปแบบไฟล์ใน [file-formats.md](file-formats.md)

เอกสารนี้ครอบคลุมงานที่เหลือ 4 ข้อ เรียงตามลำดับที่แนะนำ:

1. [ตัวติดตั้ง (installer)](#1-ตัวติดตั้ง-installer)
2. [CFG/Mission.bin (บันทึกภารกิจ)](#2-cfgmissionbin-บันทึกภารกิจ)
3. [ภาพที่ยังเป็นภาษาจีน](#3-ภาพที่ยังเป็นภาษาจีน)
4. [ข้อจำกัดที่รู้แล้ว และวิธีแก้](#4-ข้อจำกัดที่รู้แล้ว-และวิธีแก้)

กติกาที่ใช้กับทุกข้อ (ห้ามเปลี่ยน):
* ไม่แก้ / ไม่ unpack / ไม่ dump `FS3.exe` (Steam DRM) — ทำงานผ่าน proxy `d3dx9_25.dll` และไฟล์ข้อมูลเท่านั้น
* ไม่ commit ไฟล์เกม (ข้อความ ภาพ `.dat` `.pak` log ภาพหน้าจอ) — repo มีแต่โค้ด เอกสาร และไฟล์ map/label ของเราเอง
* ทำงานบนสำเนา `work/fs3-copy` เสมอ; เครื่องมือ build อ่านต้นฉบับ (`FS3Bin.dat.bak`, `FS3UpdataChs.dat`, `*.bak` ใน CFG) ไม่อ่านไฟล์ที่ถูกแก้แล้ว
* หลังทำแต่ละขั้น: อัปเดต `docs/open-questions.md`, commit, แล้ว sync ไป `D:\claude.ai\fs3` (ดูวิธี sync ท้ายเอกสาร)

---

## 1. ตัวติดตั้ง (installer)

> **สถานะ 2026-10-19: ตัวติดตั้งทำเสร็จและทดสอบแล้ว (ยกเว้น Python ฝัง)** — `installer/install.py` + `installer/launcher.c` (install.exe / uninstall.exe) + `tools/pack_translations.py` + `tools/make_dist.py`
> สร้างแพ็กเกจ: `python -I tools/pack_translations.py` ถูกเรียกโดย `make_dist.py <game_copy> <strings_all.tsv> <proxy.dll> <launcher.exe> <out> [python-embed.zip]`
> ทดสอบบนเกมสะอาดจำลอง (`work/testgame`): ไฟล์ที่ติดตั้งตรงกับ plana-a30 ทุกไบต์, ติดตั้งซ้ำได้ผลเดิม, uninstall คืนไฟล์ต้นฉบับครบ, ไฟล์ไม่ตรง hash → หยุดโดยไม่แก้อะไร
> เครื่องมือ build อ่านต้นฉบับผ่าน `fszip.orig()` (`$FS3_ORIG` > `.bak` > ไฟล์ปกติ)
> ยังไม่ทำ: ฝัง Python (ต้องดาวน์โหลด embeddable zip), Q4 (hash `FS3Bin.dat` / `DefaultString.bin` ของ Steam จริงยังไม่ได้ยืนยัน — ถ้าไม่ตรงผู้เล่นจะเจอข้อความให้ Verify integrity)

### 1.1 ทำไมต้องมี
* รอบ plana-a28: `FS3_TH_hook.ini` หายจากโฟลเดอร์เกม → ภาษาไทยหายทั้งเกม (แก้แล้วโดยให้ค่าตั้งต้นใน DLL = ค่าที่ทดสอบแล้ว แต่ไฟล์อื่นหายก็ยังพังได้)
* รอบ plana-a17 / a26: ไฟล์ prototype เก่า (`CFG/DefaultString.bin`, `CFG/Mission.bin`) ค้างอยู่ ทำให้เห็น `L985`, `L706`
* แจก mod ห้ามแจกไฟล์เกม: `Pack/*.dat`, `Pack/FS3UI.pak`, `CFG/DefaultString.bin` เป็นไฟล์เกมที่ถูกแก้ → ต้อง**สร้างบนเครื่องผู้เล่นจากเกมของผู้เล่นเอง**

### 1.2 สิ่งที่แจก (ไม่มีไฟล์เกม)
```
FS3_Thai/
  install.exe  (หรือ install.bat + tools/)
  uninstall.exe
  mod/
    d3dx9_25.dll            proxy (เราคอมไพล์เอง)
    FS3_TH_hook.ini         ค่าตั้ง (wrap_rules ฯลฯ)
    FS3_TH_map.txt          ตารางช่องทางไทย (สร้างจาก build_channel.py, คงที่)
    translations.tsv        คำแปล: member/block/offset/thai  (ไม่มีคอลัมน์ source = ไม่มีข้อความเกม)
    ui_labels.tsv           ป้ายรูปภาพ
    ui_edit/*.png           ป้ายที่วาดด้วยมือ (ถ้ามี) — เป็นงานของเรา แต่ระวัง: ถ้าคัดลอกพื้นหลังจากภาพเกมมาทั้งภาพ = มีส่วนของภาพเกม
```
> หมายเหตุ: `translations.tsv` สำหรับแจกต้องตัดคอลัมน์ source (ข้อความจีน) ออก — `build_keys.py` รองรับไฟล์ 4 คอลัมน์อยู่แล้ว
> แต่การ "แปลซ้ำตามต้นฉบับเดียวกัน" (by_src) ต้องมี source → ให้ขยาย (expand) คำแปลลงทุกแถวก่อนตัด source (เขียนสคริปต์ `tools/pack_translations.py`)

### 1.3 ขั้นตอนที่ตัวติดตั้งต้องทำ (ตามลำดับ)
1. **หาโฟลเดอร์เกม**: อ่าน registry Steam (`HKCU\Software\Valve\Steam\SteamPath` → `steamapps/libraryfolders.vdf` → หา `FantasiaSango3`) หรือให้ผู้ใช้เลือก; ตรวจว่ามี `FS3.exe` และ `Pack/FS3UpdataChs.dat`
2. **ตรวจไฟล์ต้นฉบับด้วย sha256** (ค่าใน [baseline.md](baseline.md)):
   * `Pack/FS3UpdataChs.dat` = `5e21a339…` (ต้นฉบับ Steam)
   * `Pack/FS3Bin.dat` ต้นฉบับ (Q4 ยังไม่ยืนยันว่า `.bak` ของผู้ใช้เป็นตัวแท้ → **ทำก่อน**: Steam "Verify integrity" บนเครื่องสะอาดแล้วบันทึก sha256 ของ `FS3Bin.dat`, `FS3UI.pak`, `CFG/DefaultString.bin`, `CFG/Mission.bin`)
   * ถ้า hash ไม่ตรง: ถ้ามี backup ของเรา (`.th_backup`) ใช้ตัวนั้น; ไม่งั้นแจ้งให้ผู้เล่น Verify integrity ใน Steam แล้วรันใหม่ — **ไม่สร้างทับไฟล์ที่ไม่รู้ที่มา**
3. **สำรอง**: คัดลอกไฟล์ที่จะถูกแทนไปที่ `<game>/FS3_TH_backup/` (ครั้งแรกเท่านั้น; ถ้ามีแล้วไม่ทับ) — `Pack/FS3Bin.dat`, `Pack/FS3UpdataChs.dat`, `Pack/FS3UI.pak`, `CFG/DefaultString.bin`, `CFG/Mission.bin`, `d3dx9_25.dll`
4. **เตรียม proxy**: `d3dx9_25.dll` ของเกม → เปลี่ยนชื่อเป็น `d3dx9_25_orig.dll` (ถ้ายังไม่มี) แล้ววาง DLL ของเรา
5. **build** (เหมือนที่ทำใน work/ ตอนนี้):
   ```
   build_channel.py  <game> <map> <tmp>                     → tmp/FS3Bin.dat (BIG2GB.idx), tmp/FS3_TH_map.txt
   build_keys.py     <game> tmp/FS3_TH_map.txt <tsv> <tmp>  → tmp/FS3UpdataChs.dat, tmp/FS3Bin.dat, tmp/CFG/DefaultString.bin,
                                                               tmp/FS3_TH_text.txt, tmp/FS3_TH_exe.txt
   build_ui.py       <game> ui_labels.tsv <tmp>             → tmp/FS3UI.pak
   ```
   ต้องอ่านจาก**สำเนาต้นฉบับใน backup** ไม่ใช่ไฟล์ในเกม (กันกรณีติดตั้งซ้ำแล้วไปอ่านไฟล์ที่แก้แล้ว)
   * ปัญหาที่ต้องแก้ก่อน: `build_channel.py` / `build_keys.py` อ่าน `Pack/FS3Bin.dat.bak` ตายตัว → เพิ่มพารามิเตอร์ "โฟลเดอร์ต้นฉบับ"
   * `CFG/Mission.bin` ต้นฉบับ = `CFG/Mission.bnk.bin` ถ้าไฟล์หลักถูกแก้ (ดูข้อ 2)
6. **ตรวจผล**: เปิด archive ที่สร้างได้ (`fszip.open_fszip`, `ujpak.read_tree`), `testzip()` ผ่าน, ไฟล์ข้อความมีครบ
7. **วางไฟล์แบบ atomic**: เขียนเป็น `*.th_new` ก่อน แล้ว rename ทีละไฟล์ (ถ้าล้มกลางทาง → กู้จาก backup)
8. วาง `FS3_TH_hook.ini`, `FS3_TH_map.txt`, `FS3_TH_text.txt`, `FS3_TH_exe.txt` ในโฟลเดอร์เกม
9. เขียน `FS3_TH_installed.txt` (เวอร์ชัน mod, วันที่, sha256 ของทุกไฟล์ที่วาง) — ใช้ตอน uninstall / update

**uninstall**: คืนไฟล์จาก `FS3_TH_backup/`, ลบ `FS3_TH_*.txt`, ini, คืน `d3dx9_25_orig.dll` → `d3dx9_25.dll`

### 1.4 ทางเลือกการทำ (ต้องตัดสินใจ)
| ทาง | ข้อดี | ข้อเสีย | งาน |
|---|---|---|---|
| **A. `.exe` ตัวเดียว (Python ฝัง)** — embeddable Python 3.12 (zip ทางการจาก python.org) + tools/ + `install.py`, เรียกผ่าน `install.bat` ที่อยู่ข้างกัน | ผู้เล่นไม่ต้องลงอะไร; ใช้เครื่องมือเดิมทั้งหมด; `thaibreak.py` (Uniscribe) และ `build_ui.py` (GDI) ทำงานได้เพราะเป็น Windows API | ไฟล์แจก ~10 MB; ต้องตรวจ license (PSF อนุญาตแจก) | 1–2 วัน |
| B. `.bat` + ให้ผู้เล่นลง Python เอง | ง่ายสุด | ผู้เล่นส่วนใหญ่ไม่มี Python | ครึ่งวัน |
| C. พอร์ตเป็น C (exe เดียว ~200 KB) | เล็ก เร็ว | ต้องเขียน zip/deflate writer, DDS, Uniscribe ใหม่หมด | 1–2 สัปดาห์ |

**แนะนำ A**: โครงสร้าง
```
FS3_Thai/
  install.bat        → python\python.exe -I install.py install
  uninstall.bat      → python\python.exe -I install.py uninstall
  python\            (embeddable 3.12, ไม่ต้องติดตั้ง)
  tools\             (fszip ujpak fsdialog fstables fsexe fsdds thaichan thaibreak build_* )
  mod\               (ตาม 1.2)
  install.py         (ขั้นตอน 1.3)
```
* ใช้แค่ stdlib → embeddable Python พอ ไม่ต้อง pip
* ทดสอบบนเครื่อง/บัญชี Windows ที่ไม่มี Python + โฟลเดอร์เกมที่ Verify integrity แล้ว

### 1.5 เช็กลิสต์ทดสอบตัวติดตั้ง
- [ ] ติดตั้งบนเกมสะอาด → เล่นได้ ภาษาไทยครบเหมือน plana-a30/a32
- [ ] ติดตั้งซ้ำ 2 ครั้ง → ผลเหมือนครั้งแรก (sha256 ไฟล์ที่วางตรงกัน)
- [ ] uninstall → sha256 ไฟล์เกมกลับเป็นต้นฉบับทุกไฟล์
- [ ] ไฟล์ต้นฉบับ hash ไม่ตรง → หยุดพร้อมข้อความแนะนำ ไม่แก้อะไร
- [ ] ไม่มีสิทธิ์เขียนโฟลเดอร์ (Program Files) → แจ้งให้รันแบบ admin
- [ ] Steam อัปเดตเกมทับ → รัน install ใหม่ได้

---

## 2. CFG/Mission.bin (บันทึกภารกิจ)

### 2.1 ข้อเท็จจริงที่รู้แล้ว
* ไฟล์หลวม (นอก archive) `CFG/Mission.bin` 39,777 B; **ตัวในเครื่องผู้ใช้เป็น prototype เก่า** (มี `L706`) — ต้นฉบับคือ `CFG/Mission.bnk.bin` (ขนาดเท่ากัน, วันที่ 2024-08-18, ต่างกัน 6,758 ไบต์ช่วงข้อความ)
* หัวไฟล์: name[40] = `Mission`, ต่อด้วย u32 ที่ @40 = `999, 999, 999, 311, 922, 234, 77, …` — **ไม่ใช่** layout ของ FS2_ItemHelp (ลองแล้ว: blob ไม่ tile)
* เกมแสดงข้อความจากไฟล์นี้ในหน้า 记事 (บันทึก) เช่น `主线：在城中找太平道弟子打探范氏消息` วาดด้วย DrawTextW → คีย์ใช้ได้

### 2.2 ขั้นตอนถอดรูปแบบ
1. หาข้อความ: สแกน string cp950 ที่จบด้วย NUL ทั้งไฟล์ (เหมือน `fsexe.strs`) → ได้ตำแหน่งเริ่มของทุกข้อความ และดูว่าข้อความอยู่เป็นก้อนเดียวท้ายไฟล์ (blob) หรือฝังใน record
2. หาตัวชี้: ลองแบบที่เจอแล้วในเกมนี้ ตามลำดับ
   * **multi-list** (แบบ FS2_Fighter): ค่าใน header @40 คือจำนวนของแต่ละ list (`999, 999, 999, 311…` อาจเป็น 3 list ละ 999 ช่อง = สถานะต้องทำ/สำเร็จ/ชื่อ?) แล้วหา offset list ที่ไล่จาก 0
   * **fixed record** (แบบ Objects/ArrayData): ระยะห่างระหว่างข้อความเท่ากัน
   * **length-prefixed** (แบบ Message.bin): u32 ความยาวหน้าข้อความ
   * วิธีตรวจ: เอาตำแหน่งข้อความจากข้อ 1 ไปค้นเป็น u32 (absolute และ relative กับจุดเริ่ม blob) ในส่วนหัว — ถ้าเจอครบทุกตัว = ตัวชี้
3. เขียน reader/writer ใน `tools/fstables.py` (เพิ่มชนิดใหม่) + self-test round-trip (`patch(m, d, {}) == d` และเขียนทุกข้อความกลับเดิมได้ไฟล์เดิม)
4. ถ้ายังไม่เข้าใจตัวชี้ทั้งหมด → ใช้วิธี **same-length + เติมช่องว่าง** (แบบ FS2_Fighter) ซึ่งปลอดภัยเสมอ เพราะคีย์ยาวแค่ 6 ไบต์ (หรือ 2 ไบต์สำหรับคีย์สั้น)
5. เพิ่มเข้า `export_strings.py` และ `build_keys.py` แบบเดียวกับ `CFG/DefaultString.bin` (รายการ `LOOSE` / loop loose file):
   * อ่านต้นฉบับจาก `CFG/Mission.bnk.bin` ถ้ามี (ไม่ใช่ `.bak` เหมือน DefaultString — ต้องเพิ่มกฎ "ต้นฉบับ = .bak หรือ .bnk.bin")
   * เขียนผลที่ `out/CFG/Mission.bin`
6. ข้อความในบันทึกมี prefix `主线：` / `支线：` (เส้นเรื่องหลัก/รอง) — ตรวจว่าเป็นส่วนหนึ่งของ string หรือเป็น template (`%s`) → ถ้าเป็น template ใช้กลไก template piece ที่มีแล้ว
7. ทดสอบในเกม: หน้า 记事 ทั้งแท็บ "ภารกิจที่ต้องทำ" และ "ภารกิจที่สำเร็จ"; รายการยาวอาจต้องเพิ่ม `wrap_rules` (ดูตำแหน่งใน log บรรทัด `key N at h= x= y=`)

### 2.3 ไฟล์ CFG อื่นที่ควรตรวจในรอบเดียวกัน
`CFG/DefData.bin`, `CFG/*.XML` (DialogINI, MapInput, SelectMember, StorySelectDialog, TradeMenu, WorkingHouse) — มีข้อความจีนหรือไม่ (`grep` cp950) และเปรียบกับคู่ `.bnk.*` ว่าตัวไหนถูก prototype แก้

---

## 3. ภาพที่ยังเป็นภาษาจีน

เครื่องมือ: `tools/build_ui.py` + `poc/ui_labels.tsv` (2 โหมด)
* **โหมดทั้งภาพ**: `Menu/M_Team<TAB>ทีม[<TAB>ระยะเผื่อ px]` — สำหรับป้ายที่ทั้งภาพเป็นตัวอักษรบนพื้นโปร่งใส (4 สถานะ `_Nor/_Ove/_Pre/_Dis`)
* **โหมดพื้นที่ (atlas)**: `Combat/DlgMainDisk.dds@x,y,w,h<TAB>ท่า` — ลบตัวจีนในกรอบแล้ววาดไทยด้วยสีเดิม
* **วาดเอง**: วาง PNG ขนาดเท่าเดิมที่ `work/ui_edit/<path_with_underscores>.png` → ใช้แทนอัตโนมัติ (แปลงจาก DDS ได้ด้วย `python -I tools/fsdds.py topng <in.dds> <out.png>`)

### 3.1 รายการที่เหลือ
| ภาพ | ไฟล์ใน FS3UI.pak | วิธีที่แนะนำ |
|---|---|---|
| คอมโบ "2连击" | `combo/` (51 ไฟล์: `0-0000.dds` … — ตัวเลขแยกเฟรมกับคำ 连击) | หาไฟล์ที่เป็นคำ 连击 (render ทั้งโฟลเดอร์ดู) → โหมดพื้นที่ เช่น "คอมโบ" / "ฮิต" |
| ป้ายแนวตั้งสีแดง "请选择..." | `Menu/ST_PleaseSelcet.dds` (แนวตั้ง) | ภาษาไทยเขียนแนวตั้งไม่ได้ → วาดใหม่เป็น PNG ด้วยมือ (หมุนข้อความ 90° หรือย่อเป็นคำสั้น) แล้ววางใน `ui_edit/` |
| ชื่อสถานที่แนวตั้ง 粹神塔 麒麟镇 存菁鼎 | `Menu/WH_*_Title*.dds`, `WH_LU_*` | เหมือนข้างบน — วาดมือ |
| อื่นที่อาจมี | `Map/` (65), `LvUp/`, `Vic/`, `FsFx/` และ `FS3MergeImage.pak`, `Patch.pak` | สแกนหา: render thumbnail ทั้งโฟลเดอร์ (สคริปต์แบบ `_thumbs*.png` ที่ใช้ใน 2026-10-17) แล้วไล่ดูด้วยตา |

### 3.2 ขั้นตอนต่อหนึ่งภาพ (โหมดพื้นที่)
1. แปลงเป็น PNG ซ้อนกริด 10 px ขยาย 2–3 เท่า (สคริปต์ `grid.py` ที่ใช้ใน 2026-10-17: crop + เส้นกริดเขียวทุก 10 px ม่วงทุก 50 px)
2. อ่านกรอบตัวอักษร (x, y, w, h) ให้ชิดตัวอักษรที่สุด แต่ไม่ตัดขอบเรืองแสง
3. เพิ่มแถวใน `poc/ui_labels.tsv` → `python -I tools/build_ui.py work/fs3-copy poc/ui_labels.tsv work/out`
4. ดูภาพตัวอย่างใน `work/out/ui_preview/` — ถ้ามีรอย (inpaint ไม่เนียน) ขยายกรอบ 1–2 px หรือวาดมือแทน
5. ทดสอบในเกม: ภาพแปลงเป็น A8R8G8B8 (ไม่บีบอัด) ยืนยันแล้วว่าเกมรับ (plana-a26)

### 3.3 ข้อควรระวัง
* ไฟล์ใน `FS3UI.pak` ขยายใหญ่ขึ้นทุกภาพที่แก้ (ไม่บีบอัด): ตอนนี้ +3.3 MB — ถ้าเยอะมากค่อยเพิ่มตัวบีบอัด DXT5 ใน `fsdds.py`
* ป้ายที่มี 4 สถานะ ต้องทำครบทุกสถานะ ไม่งั้นตอนชี้/กดจะกลับเป็นจีน
* ปุ่มที่อยู่ติดกันต้องคุมความกว้าง (คอลัมน์ที่ 3 ใน ui_labels.tsv)

---

## 4. ข้อจำกัดที่รู้แล้ว และวิธีแก้

### 4.1 ข้อความบทสนทนาไม่ทยอยพิมพ์ (typewriter)
* สาเหตุ: เกมวาดเฉพาะคีย์ 3 ตัว แล้ว proxy วาดภาษาไทยทั้งบรรทัดในครั้งเดียว (`expand_draw`)
* วิธีแก้ (proxy):
  1. จับเวลาที่คีย์ถูกวาดครั้งแรก ต่อ (คีย์, ตำแหน่ง) → เก็บ `t0` (ใช้ `GetTickCount`)
  2. ใน `expand_draw` วาดเพียง `n = (now - t0) / ms_per_cluster` กลุ่มอักษรแรก
  3. ค่าตั้ง `typewriter_ms=30` ใน ini (0 = ปิด)
  4. ปัญหาที่ต้องดู: ปุ่มกดข้ามข้อความ — เกมจะแสดงทั้งบรรทัดทันทีเมื่อกด แต่ proxy ไม่รู้ → ทางออก: ถ้าเกมวาด "คีย์ครบ 3 ตัวในเฟรมเดียว" ตั้งแต่เฟรมแรกอยู่แล้ว (ไม่ทยอย) ก็ไม่รู้; ต้องดู log ว่าตอนเกมทยอยพิมพ์ภาษาจีน มันวาดทีละตัวหรือไม่ (ถ้าใช่ = ตัวคีย์ตัวที่ 1, 2, 3 จะมาทีละเฟรม → ใช้เวลาที่คีย์ตัวสุดท้ายมาเป็น t0 และถ้าคีย์ทั้ง 3 มาพร้อมกัน = ผู้เล่นกดข้าม → วาดเต็มทันที)
  5. ทดสอบกับบทสนทนายาว 3 บรรทัด + กดข้าม

### 4.2 ปุ่มเมนูสถานะ "กด" ไม่มีเปลวไฟประดับ
* `build_ui.py` วาดเฉพาะตัวอักษร + ขอบเรืองแสง; ภาพ `_Pre` ต้นฉบับมีเปลวไฟส้มด้านหลังตัวจีน
* วิธีแก้: ใช้โหมดพื้นที่สำหรับไฟล์ `_Pre` (ลบเฉพาะตัวอักษร เก็บเปลวไฟไว้) — เพิ่มแถว `Menu/M_Team_Pre.dds@x,y,w,h<TAB>ทีม`; ลำดับใน `build_ui.py` คือ PNG วาดมือ > แถวพื้นที่ > แถวทั้งภาพ (ตรวจแล้วในโค้ด) จึงใช้แทนได้ทันทีโดยไม่ต้องลบแถว `Menu/M_Team`

### 4.3 ไฟล์ prototype เก่าในเครื่องผู้ใช้
* ไฟล์ที่ถูกแก้ด้วย prototype (ไม่ใช่ต้นฉบับ): `CFG/DefaultString.bin` (ต้นฉบับ `.bak`), `CFG/Mission.bin` (ต้นฉบับ `.bnk.bin`), `Pack/FS3Bin.dat` (ต้นฉบับ `.bak`, Q4 ยังไม่ยืนยัน)
* วิธีแก้ถาวร: ตัวติดตั้งตรวจ sha256 (ข้อ 1.3 ขั้น 2) — ต้องบันทึก hash ต้นฉบับทุกไฟล์ใน baseline ก่อน
* เครื่องมือ build ต้องอ่านต้นฉบับเท่านั้น (ตอนนี้ทำแล้วสำหรับ `.bak`; Mission ต้องเพิ่ม `.bnk.bin`)

### 4.4 อื่นๆ ที่ควรจำ
* ชื่อในตาราง (Objects.bin) หลายแถวเป็นชื่อภายในที่ไม่แสดง — แปลเฉพาะที่เห็นในเกม (ดูจาก log `key N at` หรือหน้าจอ)
* ช่องว่างในข้อความ `FS3.exe` (`%s 装备的 [25 ช่องว่าง] 损坏了`) เป็นที่ว่างให้ชื่ออุปกรณ์ที่เกมวาดทับ — คำแปลต้องเว้นช่องว่างเท่าเดิม
* ประโยคเดียวกันในต้นฉบับใช้คำแปลร่วมกันทั้งเกม (by_src) — ถ้าอยากต่างกันตามที่ ใส่คำแปลแยกในแต่ละแถว
* คีย์สั้นมีได้ 127 ข้อความ (ตอนนี้ใช้ 27) — ถ้าเกินจะ assert ใน `build_keys.py`
* `wrap_rules` เต็มบัฟเฟอร์ 512 ไบต์ (ตอนนี้ ~360) — ถ้ากฎเพิ่มมากต้องขยาย `char v[512]` ใน `load_config`

---

## ภาคผนวก: วงจรทดสอบกับผู้ใช้ (ใช้ทุกข้อ)
1. สร้างชุดทดสอบ**ครบทุกไฟล์**ใน `work/plana-aNN/` โครงสร้างเหมือนโฟลเดอร์เกม (`Pack/`, `CFG/`, ไฟล์หลัก) — ห้ามส่งเฉพาะไฟล์ที่เปลี่ยน (บทเรียน a28)
2. ผู้ใช้คัดลอกทับโฟลเดอร์เกม เล่น ถ่ายภาพ แล้ววาง log + ภาพไว้ใน `work/plana-aNN/` (log จริงอยู่ที่ `<game>/FS3_TH_hook.log`)
3. อ่าน log: `grep exception`, บรรทัดท้าย `=== unloaded ===` (= ไม่ crash), `key N at h= x= y= wrap=` (ตำแหน่งใช้ตั้ง wrap_rules)
4. ทดสอบที่ต้องดู log การวาด: ตั้ง `log_drawtext=1` ชั่วคราวในชุดนั้นเท่านั้น
5. บันทึกผลใน `docs/open-questions.md` → commit → sync

## ภาคผนวก: sync ไป D:\claude.ai\fs3
```bash
# ในโฟลเดอร์เกม (repo หลัก)
git format-patch <commit ล่าสุดที่ sync แล้ว>..HEAD -o <scratch>/patches
cd /d/claude.ai/fs3 && git am --keep-cr <scratch>/patches/*.patch
# ตรวจ: tree hash ต้องตรงกัน
git -C /d/claude.ai/fs3 rev-parse HEAD^{tree}; git -C <game> rev-parse HEAD^{tree}
```
ยังไม่ push ขึ้น GitHub (`linlijian/fs3-thai`) — push เมื่อผู้ใช้สั่งเท่านั้น
