# καιρός StockBro · Investment Bro

Brief หุ้นสหรัฐฯ ก่อนตลาดเปิด แบบ "เพื่อนนักลงทุน" พูดภาษาคน: ข่าวที่เกี่ยวกับหุ้นของนาย (แปลไทย + ลิงก์ต้นฉบับ), แนวรับ-แนวต้านจากสูตร, และผลย้อนหลังว่าแนวรับแม่นจริงไหม
ใช้ส่วนตัว/กลุ่มเพื่อน **ไม่ใช่คำแนะนำการลงทุน** ดู `docs/SPEC.md` (สเปก), `docs/PROGRESS.md` (ทำถึงไหน), `docs/DECISIONS.md` (ทำไม), `CLAUDE.md` (สำหรับ AI ที่มารับช่วงต่อ)

พอร์ตใน `config/portfolio.json` เป็น **ตัวอย่าง (ตัวเลขสมมติ)** พอร์ตจริงจะทำหลังมีระบบล็อกอิน

## โครงสร้างแบบสั้น
- `services/stockbro_engine/` Python (stdlib) คำนวณทุกอย่าง แล้วเขียน `site/data/report.json`
- `site/` หน้าเว็บล้วน: `index.html` `portfolio.html` `news.html` `market.html` `stock.html` `glossary.html` + `style.css` + `app.js` (ไม่มี build, ไม่มี dependency) แค่อ่าน JSON แล้ววาดหน้า

## รันบน Mac (ใช้ Python 3 ที่มากับเครื่อง)
```bash
cd ~/Desktop/Thanatv/StockBro/services

# 1) เทสต์ (ไม่ใช้เน็ต)
python3 -m unittest discover -s tests -t . -v

# 2) ข้อมูลจริง (ใช้เวลา ~1 นาที)
export STOCKBRO_SEC_UA="ชื่อของคุณ your@email.com"   # SEC บังคับให้ระบุผู้ติดต่อ (ไม่ตั้ง = ข้าม filings)
python3 -m stockbro_engine.run
# ข้ามขั้นแปลภาษา: เติม --no-translate   |   ข้อมูลจำลอง: เติม --offline
```
แล้วเปิดเว็บ **ผ่าน server** (เบราว์เซอร์บล็อกการอ่าน JSON ถ้าเปิดไฟล์ตรงๆ): VS Code Live Server ที่โฟลเดอร์ `site` หรือ
```bash
cd ../site && python3 -m http.server 8000     # แล้วเปิด http://127.0.0.1:8000
```
ถ้ายังไม่เคยรันข้อมูลจริง เว็บจะแสดงข้อมูลตัวอย่าง (`site/data/report.sample.json`) พร้อมแบนเนอร์เตือน

ถ้าดึงบางตัวไม่ได้ จะใช้ cache ล่าสุดและแจ้งใน `errors` — ส่งข้อความ error ที่เห็นให้ AI ช่วยแก้ได้เลย
ใส่หุ้นที่แค่ติดตามใน `watchlist` ของ `config/portfolio.json` เพิ่มหุ้นใหม่ให้เพิ่มชื่อเรียกใน `stockbro_engine/relevance.py` (ALIASES) ด้วย เพื่อให้กรองข่าวถูก

## Push ขึ้น GitHub
```bash
cd ~/Desktop/Thanatv/StockBro
git add . && git commit -m "StockBro v0.3"
git branch -M main && git push -u origin main
```
repo เป็น public (ตั้งใจใช้เป็นผลงาน) **ห้ามใส่พอร์ตจริง/ข้อมูลลับ/.env ลง repo**

## ตั้งให้รันทุกวันอัตโนมัติ (GitHub Actions)
คัดลอก `docs/daily.yml.example` ไปเป็น `.github/workflows/daily.yml` (`mkdir -p .github/workflows && cp docs/daily.yml.example .github/workflows/daily.yml`) รันทุกวัน 19:30 น. เวลาไทย แล้ว commit `site/data` กลับเข้า repo → ตั้ง secret `STOCKBRO_SEC_UA` ที่ Settings → Secrets → Actions ก่อน แล้วเปิด GitHub Pages ที่โฟลเดอร์ `site` (หรือต่อ Vercel) เพื่อเสิร์ฟหน้าเว็บ

## อีเมล brief (ไม่ใช้ LLM)
1. เปิด 2-Step Verification ของ Gmail แล้วสร้าง **App Password** (Google Account → Security → App passwords) ได้รหัส 16 ตัว
2. ทดลองบนเครื่อง: `export STOCKBRO_SMTP_USER="you@gmail.com"; export STOCKBRO_SMTP_PASS="รหัส16ตัว"` แล้ว `cd services && python3 -m stockbro_engine.mail --dry-run` (ดูข้อความ) ตามด้วยรันจริงโดยไม่มี `--dry-run`
3. บน GitHub: ใส่ secrets `STOCKBRO_SMTP_USER`, `STOCKBRO_SMTP_PASS`, `STOCKBRO_MAIL_TO` (ดู `docs/daily.yml.example`) **ห้ามใส่รหัสในไฟล์ใน repo**

## ตรวจข่าวจากลิงก์
`cd services && python3 -m stockbro_engine.check "https://ลิงก์ข่าว"` บอกแหล่ง (ทางการ/สำนักข่าวใหญ่/ไม่รู้จัก), อายุข่าว, หุ้นในพอร์ตที่เกี่ยวข้อง และราคาขยับไปแล้วเท่าไหร่ตั้งแต่ข่าวออก **ไม่ได้ตรวจว่าเนื้อหาจริงหรือเท็จ**

## ปฏิทิน FOMC/CPI/งบ
แก้ได้ที่ `config/calendar.json` (ทุกรายการมีลิงก์แหล่งทางการ) วันประกาศงบของแต่ละหุ้นใส่เองที่ `"next_earnings": "YYYY-MM-DD"` ใน `config/portfolio.json` ระบบไม่เดาวันที่
