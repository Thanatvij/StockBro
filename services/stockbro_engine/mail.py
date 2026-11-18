"""อีเมล brief ก่อนตลาดสหรัฐฯ เปิด (stdlib smtplib ไม่ใช้ LLM ไม่มี dependency)

อ่าน site/data/report.json ที่ run.py สร้าง แล้วส่งสรุป "คืนนี้ดู 3 เรื่อง + พอร์ต + ปฏิทิน + disclaimer"
ตั้งค่าผ่าน environment variable เท่านั้น (ห้ามใส่รหัสในไฟล์/ใน repo):
  STOCKBRO_SMTP_USER   อีเมลผู้ส่ง (Gmail)
  STOCKBRO_SMTP_PASS   Gmail App Password 16 ตัว (ไม่ใช่รหัสผ่านปกติ; ต้องเปิด 2-Step Verification ก่อน)
  STOCKBRO_MAIL_TO     ผู้รับ คั่นหลายคนด้วยจุลภาค (ค่าเริ่มต้น = ผู้ส่ง)
  STOCKBRO_SMTP_HOST / STOCKBRO_SMTP_PORT  ถ้าไม่ใช้ Gmail (ค่าเริ่มต้น smtp.gmail.com / 465)
รัน: python3 -m stockbro_engine.mail [--dry-run]   (--dry-run พิมพ์อีเมลให้ดู ไม่ส่ง)
"""
from __future__ import annotations

import argparse
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from html import escape as h
from pathlib import Path
from typing import Callable, Dict, Tuple

ROOT = Path(__file__).resolve().parents[2]


def build_email(d: Dict) -> Tuple[str, str, str]:
    """คืน (subject, text, html) จาก payload ของ export.build_payload"""
    date = (d.get("generated_at") or "")[:10]
    subject = f"StockBro · สรุปก่อนตลาดสหรัฐฯ เปิด {date}".strip()
    if d.get("mode") == "offline":
        subject = "[ข้อมูลตัวอย่าง] " + subject
    tops = d.get("top_things", [])
    lines = d.get("portfolio_lines", [])
    cal = (d.get("calendar") or {}).get("events", [])[:3]

    text = [d["greeting"], ""]
    text.append("คืนนี้ดู " + (f"{len(tops)} เรื่องนี้ก่อนเลย" if tops else "— ยังไม่มีเรื่องเด่นจากกฎของระบบ"))
    for i, t in enumerate(tops, 1):
        text += [f"{i}. {t['ticker']} · {t['kind']}", f"   {t['text']}", f"   ทำไมน่าดู: {t['why']}"]
    if lines:
        text += ["", "Bro ขอพูดเรื่องพอร์ตนายหน่อย"] + [f"- {x}" for x in lines]
    if cal:
        text += ["", "เหตุการณ์ที่ใกล้เข้ามา"] + [f"- {e['date']} {e.get('time_th') or ''} {e['title']}".replace("  ", " ") for e in cal]
    text += ["", d["disclaimer"]]

    box = "background:#f4f6fb;border-radius:10px;padding:12px 14px;margin:8px 0"
    parts = [f'<div style="font:16px/1.6 -apple-system,\'Sukhumvit Set\',sans-serif;color:#1b2030;max-width:620px">',
             '<div style="font-size:24px;font-weight:700;letter-spacing:-.3px">Stock<span style="color:#1aa974">Bro</span></div>',
             f'<p>{h(d["greeting"])}</p>']
    if tops:
        parts.append(f'<h3 style="margin:18px 0 4px">คืนนี้ดู {len(tops)} เรื่องนี้ก่อนเลย</h3>')
        for i, t in enumerate(tops, 1):
            parts.append(f'<div style="{box}"><b>{i}. {h(t["ticker"])} · {h(t["kind"])}</b><br>{h(t["text"])}'
                         f'<br><span style="color:#667;font-size:13px">ทำไมน่าดู: {h(t["why"])}</span></div>')
    else:
        parts.append('<div style="%s">ยังไม่มีเรื่องเด่นจากกฎของระบบ</div>' % box)
    if lines:
        parts.append('<h3 style="margin:18px 0 4px">Bro ขอพูดเรื่องพอร์ตนายหน่อย</h3><ul style="padding-left:20px">'
                     + "".join(f"<li>{h(x)}</li>" for x in lines) + "</ul>")
    if cal:
        parts.append('<h3 style="margin:18px 0 4px">เหตุการณ์ที่ใกล้เข้ามา</h3><ul style="padding-left:20px">'
                     + "".join(f'<li>{h(e["date"])} {h(e.get("time_th") or "")} · {h(e["title"])}</li>' for e in cal) + "</ul>")
    parts.append(f'<p style="color:#778;font-size:12px;margin-top:22px">{h(d["disclaimer"])}</p></div>')
    return subject, "\n".join(text), "".join(parts)


def send(d: Dict, env=os.environ, smtp_factory: Callable = smtplib.SMTP_SSL) -> str:
    user, pw = env.get("STOCKBRO_SMTP_USER", "").strip(), env.get("STOCKBRO_SMTP_PASS", "").strip()
    if not user or not pw:
        raise SystemExit("ยังไม่ได้ตั้ง STOCKBRO_SMTP_USER / STOCKBRO_SMTP_PASS (ดู README หัวข้ออีเมล)")
    to = [x.strip() for x in (env.get("STOCKBRO_MAIL_TO") or user).split(",") if x.strip()]
    subject, text, html = build_email(d)
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, f"StockBro <{user}>", ", ".join(to)
    msg.set_content(text)
    msg.add_alternative(html, subtype="html")
    with smtp_factory(env.get("STOCKBRO_SMTP_HOST", "smtp.gmail.com"), int(env.get("STOCKBRO_SMTP_PORT", "465")), timeout=30) as s:
        s.login(user, pw)
        s.send_message(msg)
    return f"ส่งอีเมลถึง {len(to)} คนแล้ว"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ส่งอีเมล brief ของ StockBro")
    ap.add_argument("--data", default=str(ROOT / "site" / "data" / "report.json"))
    ap.add_argument("--dry-run", action="store_true", help="พิมพ์ข้อความให้ดู ไม่ส่งจริง")
    args = ap.parse_args(argv)
    p = Path(args.data)
    if not p.exists():
        print(f"ไม่พบ {p} — รัน python3 -m stockbro_engine.run ก่อน", file=sys.stderr)
        return 1
    d = json.loads(p.read_text(encoding="utf-8"))
    if args.dry_run:
        s, t, _ = build_email(d)
        print("Subject:", s, "\n", t, sep="\n")
        return 0
    print(send(d))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
