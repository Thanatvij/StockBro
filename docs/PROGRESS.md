# Progress log

อัปเดตล่าสุด: 17 พ.ย. 2569 ~14:50 น. (Claude Sonnet 5.5) — v0.3

## สถานะ (v0.2)
- [x] v0.1: engine (levels/backtest/prices/news/newsscore/signals/report) — **รันจริงบน Mac แล้ว** Yahoo ราคา+ข่าวใช้ได้ทั้ง 8 ตัว (16 พ.ย.)
- [x] v0.3 **เปลี่ยนชื่อทั้งระบบเป็น StockBro** (แพ็กเกจ `stockbro_engine`, env `STOCKBRO_SEC_UA`/`STOCKBRO_MYMEMORY_EMAIL`, db `data/stockbro.db`, repo `Thanatvij/StockBro`)
- [x] v0.3 **พอร์ตใน config เป็นตัวอย่างสมมติ** (repo public) พอร์ตจริงรอระบบล็อกอิน
- [x] v0.3 **แยกหน้าเว็บ**: `site/` = 6 .html + `style.css` + `app.js` (vanilla ไม่มี build) อ่าน `site/data/report.json` ที่ `export.py` สร้าง (ดู D-15) ลบ `site.py`/`render.py` แล้ว
- [x] ถ้อยคำเป็นโทน "Bro" พูดกับผู้ใช้ตรงๆ
- [x] `relevance.py` กรองข่าวไม่เกี่ยว (ต้องมี ticker ตัวพิมพ์ใหญ่หรือชื่อบริษัท/alias ในพาดหัว)
- [x] `translate.py` แปลพาดหัว EN→TH ด้วย MyMemory (ไม่ใช้ LLM) + cache `data/cache/translations.json` ติดป้าย "แปลโดยเครื่อง" ถ้าแปลไม่ได้แสดงอังกฤษ
- [x] `friend.py` ถ้อยคำเพื่อนจากแม่แบบ + ตัวเลขจริง (สัดส่วนพอร์ต, ถ้าตัวใหญ่สุดตก 10%, ตัวที่ติดลบ) ไม่มีคำสั่งซื้อ/ขาย
- [x] `glossary.py` ทุกศัพท์มีคำอธิบาย (tooltip + หน้า glossary.html)
- [x] แก้บั๊ก "ใกล้แนวรับ" ขึ้นทุกตัว: เกณฑ์ 3%→1.5% และเตือนไม่เกิน 2 ตัว
- [x] เทสต์ 16 ข้อผ่าน หน้าเว็บตรวจด้วยภาพ (headless Chrome ผ่าน http server) แล้ว
- [ ] **ยังไม่ได้ทดสอบ v0.3 (เว็บแยกไฟล์) กับข้อมูลจริง** (v0.2 ทดสอบจริงแล้ว: ราคา+ข่าว+แปล 40/48 ใช้ได้) (ต้องรันบน Mac: `cd services && python3 -m stockbro_engine.run`) โดยเฉพาะ: ตัวกรองข่าวกับพาดหัว Yahoo จริง, MyMemory, ดึง ^GSPC ^IXIC ^VIX THB=X
- [ ] Push ขึ้น GitHub + GitHub Actions (copy `docs/daily.yml.example` → `.github/workflows/daily.yml` ด้วยมือ) + secret `STOCKBRO_SEC_UA`
- [ ] อีเมล brief 19:30 น. (Gmail App Password หรือ Resend)
- [ ] เฟส 2: Next.js + Better Auth + Neon + Vercel (login, พอร์ตแยกคน — ตอนนี้พอร์ตที่แก้เก็บในเบราว์เซอร์เครื่องเดียว) ดู D-15
- [ ] ฟีเจอร์ "ตรวจข่าว" (วางลิงก์ → จริง/เก่า/ราคาขยับไปแล้ว)
- [ ] ปฏิทินงบ/FOMC/CPI (ตอนนี้หน้าตลาดบอกตรงๆ ว่า "ยังประเมินไม่ได้")
- [ ] ผู้ให้บริการแปลที่ดีกว่า MyMemory (Azure/Google/DeepL) — เพิ่มใน `translate.PROVIDERS` (ยังไม่ได้เขียน)
- [ ] ปรับ ALIASES ใน `relevance.py` เมื่อเพิ่มหุ้นใหม่ (หรือใส่ "aliases" ใน config ของหุ้นนั้น)

## ข้อจำกัด/ความเสี่ยงที่รู้อยู่แล้ว
- ราคา Yahoo ต่างจาก Dime เล็กน้อย; `shares` ประมาณจากมูลค่า ไม่แม่นเท่าใส่จำนวนจริง (แก้ใน portfolio.json)
- พอร์ตมีมูลค่าน้อย (~$122) — สัดส่วน/กำไรขาดทุนเป็น % คำนวณจากตัวเลขในแอป
- ทิศทางข่าวจาก keyword ในพาดหัวหยาบมาก (ใช้อ้างอิงเท่านั้น)
- ตัวอย่างข้อมูลจำลอง (`--offline`) ไม่มีความหมายทางสถิติ ผล backtest จากมันห้ามเชื่อ
- SEC ต้องตั้ง `STOCKBRO_SEC_UA` มิฉะนั้นข้าม filings

## Log
- **17 พ.ย. 04:14–04:50** คุยไอเดียกับ Thanat: ถอดแบบจาก ARGUS, ตัด Bloomberg/Reuters, เลือกจุดขาย (ตรวจข่าวจริง/เก่า + accuracy tracker), เลือกชื่อ Kairos, ตรวจ backend เดิม (Better Auth+Neon), เลือกเฟส 1 แบบรันบน Mac
- **17 พ.ย. 04:50–05:00** เขียน engine ทั้งชุด + เทสต์ + เอกสาร ในโหมด Thanat หลับ; ตั้งงานให้ตัวเองตื่น 05:45 น. เผื่อโควตาเต็ม
- **17 พ.ย. 14:00–14:20** Thanat ดู v0.1 แล้วบอกว่าเป็นหน้าเดียว กดไม่ได้ ไม่เห็นข่าว ไม่เข้าใจศัพท์ → ทำ v0.2 (ดู D-10..D-12) เลือก "ข" + "ก. เริ่มเลย"
- **17 พ.ย. 14:30–14:50** Thanat สั่ง: เปลี่ยนเป็น StockBro ทั้งระบบ, ไม่เอาพอร์ตจริงใน repo, แยก index.html/style.css/app.js, เลือกเทคโนโลยีได้อิสระ → v0.3 (D-13..D-15)
- (เพิ่มรายการต่อท้ายที่นี่ทุกครั้งที่ทำงาน)
