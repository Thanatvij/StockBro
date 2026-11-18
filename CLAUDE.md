# StockBro — ชื่อเดิม Kairos

อ่านไฟล์นี้ก่อน (AI ตัวไหนก็ตามที่มารับช่วงต่อ) แล้วอ่าน `docs/PROGRESS.md` เพื่อรู้ว่าทำถึงไหน และ `docs/DECISIONS.md` เพื่อรู้ว่าทำไมถึงตัดสินใจแบบนั้น

## โปรเจกต์คืออะไร (สั้นๆ)
Brief รายวันก่อนตลาดหุ้นสหรัฐฯ เปิด สำหรับ **Thanat (นักศึกษา DTI สาย Data Scientist) และกลุ่มเพื่อน** ที่ถือหุ้นรายตัว: ดึงข่าว+filings+ราคา → จัดกลุ่มข่าว/ให้คะแนนด้วยกฎ → คำนวณแนวรับ-แนวต้านด้วยสูตร → วัดผลว่าแนวรับแม่นแค่ไหน (backtest + forward-test) → หน้าเว็บธีมมืด
แยกออกมาจาก ARGUS (โปรเจกต์วิเคราะห์ข่าวภัยพิบัติไทย ที่ `~/Desktop/Thanatv/ARGUS`) แต่เป็น repo/โฟลเดอร์แยก **ห้ามแก้ ARGUS**
Repo: https://github.com/Thanatvij/StockBro (**public โดยเจ้าของตั้งใจ ใช้เป็นผลงานพอร์ตโฟลิโอ** — พอร์ตใน config/portfolio.json เป็นตัวอย่างสมมติ ห้ามใส่พอร์ตจริงของใครลง repo) ถ้า `git log` ว่าง/ยังไม่ push ให้ Thanat push เอง (ดู README)

## หลักการที่ห้ามละเมิด
1. ตัวเลขทุกตัวมาจากกฎ deterministic ไม่ใช่ LLM (เฟส 1 ไม่เรียก LLM — Thanat ไม่ต้องการใช้ API key/โควตา)
2. แสดงแหล่ง เวลา อายุข่าวเสมอ; ข่าว >7 วันติดป้ายเก่า; SEC filings = แหล่งทางการ
3. **ห้ามเขียนคำว่า "ซื้อ/ขาย/แนะนำ"** ใช้ "โซนติดตาม" "จุดตัดขาดทุนอ้างอิง" "ราคาห่างแนวรับ X%" + disclaimer ทุกหน้า
4. ห้ามแต่งตัวเลข ถ้าข้อมูลไม่พอบอกว่า "ยังสรุปไม่ได้"
5. พารามิเตอร์เป็นค่าตั้งต้น ห้ามนำเสนอว่าผ่านการพิสูจน์ ปรับจากผลวัดจริงเท่านั้น
6. ห้าม commit `.env`, API key, หรือพอร์ตของคนอื่น
7. **อย่าเปลี่ยนหน้าตาเป็นธีมสว่าง** — Thanat ต้องการธีมมืด

## โครงสร้าง
```
config/portfolio.json         พอร์ตตัวอย่าง (สมมติ) 8 ตัว — พอร์ตจริงทำหลังมีระบบล็อกอิน
services/stockbro_engine/     Python stdlib — ตรรกะทั้งหมดอยู่ที่นี่ ผลลัพธ์คือ site/data/report.json
  prices.py levels.py backtest.py news.py newsscore.py signals.py report.py   ราคา/สูตร/วัดผล/ข่าว/คะแนน/forward-test/ประกอบรายงาน
  relevance.py  กรองข่าวไม่เกี่ยวด้วยกฎ ticker/alias
  translate.py  แปลพาดหัวด้วย API แปล (MyMemory) ไม่ใช้ LLM
  friend.py     ถ้อยคำภาษา "Bro" จากแม่แบบ+ตัวเลขจริง (พูดกับผู้ใช้ตรงๆ)
  glossary.py   ศัพท์+คำอธิบาย (ทุกศัพท์บนเว็บต้องมีที่นี่)
  export.py     รายงาน → JSON ให้หน้าเว็บ
  run.py        CLI
services/tests/test_engine.py
site/                         หน้าเว็บล้วน แยกไฟล์ ไม่มี build: index/portfolio/news/market/stock/glossary .html + style.css + app.js
site/data/report.json         ข้อมูลจริง (สร้างโดย run.py)   report.sample.json = ข้อมูลจำลอง (--offline)
docs/SPEC.md  docs/PROGRESS.md  docs/DECISIONS.md
docs/daily.yml.example        ต้นแบบ GitHub Actions (Thanat ต้อง copy ไป .github/workflows/ เอง — เครื่องมือของ Claude เขียนโฟลเดอร์ .github ไม่ได้)
```
กติกาแยกหน้าที่: **JS ไม่มีตรรกะจัดระดับ/คำนวณ** (ยกเว้นหน้าพอร์ตที่คำนวณกำไร/สัดส่วนจากตัวเลขที่ผู้ใช้แก้เอง) ทุกประโยคภาษา Bro และตัวเลขมาจาก Python

## คำสั่ง
```bash
cd services
python3 -m unittest discover -s tests -t . -v      # เทสต์ (ต้องผ่านก่อนอ้างว่าเสร็จ)
python3 -m stockbro_engine.run --offline             # ข้อมูลจำลอง (ไม่แตะเน็ต) เขียน report.sample.json
python3 -m stockbro_engine.run                       # ข้อมูลจริง (ต้องมีเน็ต)
```
Python 3.9+ , **stdlib เท่านั้น** (ไม่มี dependency)

## ข้อควรรู้ด้านสภาพแวดล้อม
- Sandbox ของ Claude ออกเน็ตไป Yahoo/SEC/Finnhub **ไม่ได้** (allowlist) → ทดสอบดึงข้อมูลจริงไม่ได้ในแชต ต้องให้ Thanat รันบน Mac
- ภาษา: ตอบและเขียนเอกสารเป็นภาษาไทย ศัพท์เทคนิคอังกฤษได้ โค้ด/ชื่อไฟล์เป็นอังกฤษ
- Thanat ถนัด Python/ML ไม่ถนัด backend/frontend: อธิบายส่วนเว็บสั้นๆ เก็บ logic ไว้ใน `stockbro_engine`
- เพิ่มเทสต์ทุกครั้งที่แก้ตรรกะ และอย่าอ้างว่าเสร็จก่อนรันเทสต์
- ชื่อ: **StockBro** เท่านั้น (ไม่มีสโลแกน/ไม่ใช้ καιρός) โลโก้ = แท่งเทียน 3 แท่ง (site/favicon.svg) ชื่อโลโก้ฟอนต์ Grenze Gotisch (โกธิก), ฟอนต์ Outfit (หัวข้อ/ตัวเลข) + Anuphan (ไทย) จาก Google Fonts
- เว็บเปิดผ่าน server เท่านั้น (Live Server / python3 -m http.server) เพราะ fetch JSON ผ่าน file:// ไม่ได้
