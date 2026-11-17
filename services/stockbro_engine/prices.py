"""ดึงราคารายวันจาก Yahoo Finance chart API (ไม่ต้องใช้ key, ใช้แค่ stdlib)

หมายเหตุ: เป็น endpoint ไม่ทางการ อาจเปลี่ยนหรือพังได้ ถ้าพังให้ใช้ cache ล่าสุดแทน
ราคาอาจต่างจากในแอป Dime เล็กน้อย เพราะ Dime ใช้ราคาจากโบรกเกอร์ของตัวเอง
"""
from __future__ import annotations

import json
import math
import random
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) stockbro/0.2"
CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?range={r}&interval=1d"


def http_get(url: str, timeout: int = 20, headers: Dict = None) -> bytes:
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def parse_chart(payload: Dict, ticker: str) -> Dict:
    res = payload["chart"]["result"][0]
    ts = res.get("timestamp") or []
    q = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        bars.append({
            "date": time.strftime("%Y-%m-%d", time.gmtime(t)),
            "o": float(o), "h": float(h), "l": float(l), "c": float(c),
            "v": int(q["volume"][i] or 0),
        })
    meta = res.get("meta", {})
    return {
        "ticker": ticker,
        "bars": bars,
        "last_price": meta.get("regularMarketPrice"),
        "market_time": meta.get("regularMarketTime"),
        "source": "yahoo",
    }


def fetch_daily(ticker: str, rng: str = "2y") -> Dict:
    raw = http_get(CHART_URL.format(t=ticker, r=rng))
    return parse_chart(json.loads(raw), ticker)


def load_prices(tickers: List[str], cache_dir: Path, offline: bool = False) -> Dict[str, Dict]:
    """คืน {ticker: {bars, source, ...}} พร้อมเขียน cache; ถ้าดึงไม่ได้ใช้ cache"""
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for t in tickers:
        cache = cache_dir / f"{t}.json"
        if offline:
            out[t] = synthetic(t)
            continue
        try:
            data = fetch_daily(t)
            if len(data["bars"]) < 30:
                raise ValueError("ข้อมูลน้อยเกินไป")
            cache.write_text(json.dumps(data))
            out[t] = data
        except Exception as e:  # noqa: BLE001 - แหล่งข้อมูลภายนอก พังได้หลายแบบ
            if cache.exists():
                data = json.loads(cache.read_text())
                data["source"] = "cache"
                data["error"] = str(e)
                out[t] = data
            else:
                out[t] = {"ticker": t, "bars": [], "source": "error", "error": str(e)}
        time.sleep(0.3)
    return out


# ---------- ข้อมูลตัวอย่างสำหรับ --offline (ห้ามนำเสนอเป็นราคาจริง) ----------
_BASE = {"AAPL": 352, "TSLA": 380, "JPM": 338, "NVDA": 156, "MRNA": 215,
         "LLY": 1432, "PLTR": 160, "SPCX": 137}   # ราคาปิดสุดท้ายของข้อมูลจำลอง (ประมาณ) ให้ตัวเลขดูสมเหตุสมผล


def synthetic(ticker: str, days: int = 500) -> Dict:
    rnd = random.Random(sum(ord(ch) for ch in ticker))
    price = _BASE.get(ticker, 100) * 0.8
    d = date(2026, 11, 16) - timedelta(days=int(days * 1.45))
    bars = []
    while len(bars) < days:
        d += timedelta(days=1)
        if d.weekday() >= 5:
            continue
        drift = 0.0004
        vol = 0.022
        o = price * (1 + rnd.gauss(0, vol / 3))
        c = o * math.exp(rnd.gauss(drift, vol))
        h = max(o, c) * (1 + abs(rnd.gauss(0, vol / 2)))
        l = min(o, c) * (1 - abs(rnd.gauss(0, vol / 2)))
        bars.append({"date": d.isoformat(), "o": o, "h": h, "l": l, "c": c, "v": rnd.randint(10**6, 10**7)})
        price = c
    k = _BASE.get(ticker, 100) / bars[-1]["c"]   # ปรับสเกลให้ปิดที่ราคาอ้างอิง (รูปร่างกราฟเหมือนเดิม)
    for b in bars:
        for f in ("o", "h", "l", "c"):
            b[f] *= k
    return {"ticker": ticker, "bars": bars, "last_price": bars[-1]["c"], "source": "synthetic"}
