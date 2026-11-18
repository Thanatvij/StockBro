"""ปฏิทินเหตุการณ์ล่วงหน้า (FOMC/CPI/PPI + งบของหุ้นในพอร์ต)

ข้อมูลมาจาก config/calendar.json (ลงมือใส่จากแหล่งทางการ พร้อมลิงก์) และ field "next_earnings"
ของแต่ละหุ้นใน config/portfolio.json (ใส่เอง ถ้าไม่ใส่ = "ยังไม่ระบุ" ไม่เดา) ไม่ใช้ LLM ไม่ดึงเน็ต
เวลา ET (ตะวันออกสหรัฐฯ) → แสดงเป็นเวลาไทยโดยประมาณ ET = UTC-5 (ฤดูหนาว) / UTC-4 (ฤดูร้อน)
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

HORIZON_DAYS = 45


def _et_offset(d: date) -> int:
    """ชั่วโมงที่ ET ตามหลัง UTC: DST สหรัฐฯ = อาทิตย์ที่ 2 ของ มี.ค. ถึง อาทิตย์แรกของ พ.ย."""
    def nth_sunday(y, m, n):
        d0 = date(y, m, 1)
        first = d0 + timedelta(days=(6 - d0.weekday()) % 7)
        return first + timedelta(weeks=n - 1)
    start, end = nth_sunday(d.year, 3, 2), nth_sunday(d.year, 11, 1)
    return 4 if start <= d < end else 5


def thai_time(d: date, time_et: Optional[str]) -> Optional[str]:
    """แปลงเวลา ET → เวลาไทย (UTC+7) คืน "ข้อความเวลา" เช่น "20:30 น. (คืนวันที่ 10)" """
    if not time_et:
        return None
    h, m = map(int, time_et.split(":"))
    dt = datetime(d.year, d.month, d.day, h, m) + timedelta(hours=_et_offset(d) + 7)
    suffix = "" if dt.date() == d else f" ของวันที่ {dt.day}"
    return f"{dt:%H:%M} น. เวลาไทย{suffix}"


def upcoming(today: date, cfg: Dict, cal_path: Path, horizon: int = HORIZON_DAYS) -> List[Dict]:
    events: List[Dict] = []
    if cal_path.exists():
        for e in json.loads(cal_path.read_text(encoding="utf-8")).get("events", []):
            events.append(dict(e))
    for h in cfg.get("holdings", []):
        if h.get("next_earnings"):
            events.append({"date": h["next_earnings"], "type": "earnings", "ticker": h["ticker"],
                           "title": f"{h['ticker']} ประกาศงบ", "time_et": None,
                           "source": h.get("earnings_source", "")})
    out = []
    for e in events:
        try:
            d = date.fromisoformat(e["date"])
        except (KeyError, ValueError):
            continue
        days = (d - today).days
        if 0 <= days <= horizon:
            out.append({**e, "days_until": days, "time_th": thai_time(d, e.get("time_et"))})
    out.sort(key=lambda x: (x["days_until"], x["type"]))
    return out


def missing_earnings(cfg: Dict) -> List[str]:
    return [h["ticker"] for h in cfg.get("holdings", []) if h.get("value_usd", 0) and not h.get("next_earnings")]
