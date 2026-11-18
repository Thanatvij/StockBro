"""ตรวจข่าวจากลิงก์: แหล่งเป็นใคร / ข่าวเก่าแค่ไหน / ราคาขยับไปแล้วเท่าไหร่ (กฎตายตัว ไม่ใช้ LLM)

ระบบนี้ตรวจ "อายุ แหล่ง และราคาขยับหลังข่าวออก" เท่านั้น **ไม่ได้ตรวจว่าเนื้อหาข่าวเป็นข้อเท็จจริงหรือไม่**
รัน: python3 -m stockbro_engine.check "https://..."   (ต้องมีเน็ต)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from .newsscore import age_hours
from .prices import http_get, load_prices
from .relevance import ALIASES, filter_relevant

ROOT = Path(__file__).resolve().parents[2]
BIG_MOVE_PCT = 3.0  # ค่าตั้งต้น: ขยับเกินนี้ = ตลาดน่าจะรับรู้ข่าวไปแล้ว

OFFICIAL = {"sec.gov": "SEC", "federalreserve.gov": "Fed", "bls.gov": "BLS", "treasury.gov": "คลังสหรัฐฯ"}
MAJOR = {"reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "apnews.com", "nytimes.com",
         "marketwatch.com", "barrons.com", "finance.yahoo.com"}  # ค่าตั้งต้น ปรับได้


def source_tier(url: str) -> Dict:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    for dom, name in OFFICIAL.items():
        if host == dom or host.endswith("." + dom):
            return {"host": host, "tier": "official", "label": f"แหล่งทางการ ({name})"}
    if any(host == d or host.endswith("." + d) for d in MAJOR):
        return {"host": host, "tier": "major", "label": "สำนักข่าวใหญ่ในลิสต์ของระบบ"}
    return {"host": host, "tier": "unknown", "label": "ไม่อยู่ในลิสต์แหล่งที่ระบบรู้จัก (ไม่ได้แปลว่าผิด แต่ควรหาแหล่งที่สองยืนยัน)"}


def _meta(page: str, *names: str) -> Optional[str]:
    for n in names:
        for pat in (rf'<meta[^>]+(?:property|name|itemprop)=["\']{re.escape(n)}["\'][^>]*content=["\']([^"\']+)',
                    rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name|itemprop)=["\']{re.escape(n)}["\']'):
            m = re.search(pat, page, re.I)
            if m:
                return html.unescape(m.group(1)).strip()
    return None


def parse_page(page: str) -> Dict:
    title = _meta(page, "og:title", "twitter:title")
    if not title:
        m = re.search(r"<title[^>]*>(.*?)</title>", page, re.I | re.S)
        title = html.unescape(m.group(1)).strip() if m else None
    pub = _meta(page, "article:published_time", "og:article:published_time", "datePublished", "pubdate", "date", "publish-date")
    if not pub:
        m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', page) or re.search(r'<time[^>]+datetime=["\']([^"\']+)', page, re.I)
        pub = m.group(1) if m else None
    desc = _meta(page, "og:description", "description")
    return {"title": title, "published": _norm_date(pub), "description": desc}


def _norm_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).isoformat()
    except ValueError:
        return None


def price_move_since(bars: List[Dict], published: Optional[str]) -> Optional[Dict]:
    """% ขยับจากราคาปิดวันที่ข่าวออก (หรือวันทำการล่าสุดก่อนหน้า) ถึงราคาปิดล่าสุด"""
    if not published or not bars:
        return None
    day = published[:10]
    base = [b for b in bars if b["date"] <= day]
    if not base:
        return None
    b0, b1 = base[-1], bars[-1]
    if b0["c"] <= 0:
        return None
    return {"from_date": b0["date"], "to_date": b1["date"], "pct": (b1["c"] - b0["c"]) / b0["c"] * 100}


def check_url(url: str, cfg: Dict, now: Optional[datetime] = None, fetch: Callable = http_get,
              prices_loader: Callable = load_prices, cache_dir: Optional[Path] = None) -> Dict:
    now = now or datetime.now(timezone.utc)
    page = fetch(url, timeout=15).decode("utf-8", "replace")
    info = parse_page(page)
    text = " ".join(x for x in (info["title"], info["description"]) if x)
    tickers = []
    for h in cfg["holdings"]:
        kept, _ = filter_relevant([{"title": text}], h["ticker"], h["name"], h.get("aliases", []))
        if kept:
            tickers.append(h["ticker"])
    age = age_hours(info["published"], now)
    res: Dict = {"url": url, "title": info["title"], "published": info["published"], "age_hours": age,
                 "source": source_tier(url), "tickers": tickers, "moves": {}, "notes": []}
    if tickers:
        px = prices_loader(tickers, cache_dir or ROOT / "data" / "cache")
        for t in tickers:
            mv = price_move_since(px.get(t, {}).get("bars", []), info["published"])
            if mv:
                res["moves"][t] = mv
    # ข้อสังเกตจากกฎ (ไม่ใช่การตัดสินว่าจริง/เท็จ)
    if age is None:
        res["notes"].append("หน้าเว็บไม่ระบุวันที่เผยแพร่ → ประเมินอายุไม่ได้ ระวังข่าวเก่าถูกแชร์ซ้ำ")
    elif age > 24 * 7:
        res["notes"].append(f"ข่าวเก่า ออกมา {age / 24:.0f} วันแล้ว (เกิน 7 วัน)")
    elif age > 24:
        res["notes"].append(f"ข่าวออกมา {age / 24:.1f} วันแล้ว ตลาดมีเวลาตอบสนองมาแล้ว")
    else:
        res["notes"].append(f"ข่าวสด ออกมา {age:.0f} ชั่วโมงที่แล้ว")
    for t, mv in res["moves"].items():
        if abs(mv["pct"]) >= BIG_MOVE_PCT:
            res["notes"].append(f"{t} ขยับไปแล้ว {mv['pct']:+.1f}% นับจากราคาปิด {mv['from_date']} → ตลาดน่าจะรับรู้ข่าวนี้ไปแล้วส่วนหนึ่ง")
        else:
            res["notes"].append(f"{t} ขยับ {mv['pct']:+.1f}% นับจากราคาปิด {mv['from_date']} (ยังไม่มาก)")
    if not tickers:
        res["notes"].append("ไม่พบหุ้นในพอร์ตที่พาดหัว/คำโปรยกล่าวถึง (เช็กแค่พาดหัวและคำโปรย)")
    if res["source"]["tier"] == "unknown":
        res["notes"].append("แหล่งนี้ระบบไม่รู้จัก: หาข่าวเดียวกันจากสำนักข่าวใหญ่หรือเอกสารทางการมายืนยันก่อน")
    res["disclaimer"] = "ระบบตรวจแค่อายุ แหล่ง และราคาขยับ ไม่ได้ตรวจว่าเนื้อหาจริงหรือเท็จ ผู้ใช้ตัดสินใจเอง"
    return res


def render(r: Dict) -> str:
    out = [f"ข่าว: {r['title'] or '(อ่านหัวข้อไม่ได้)'}", f"ลิงก์: {r['url']}",
           f"แหล่ง: {r['source']['host']} — {r['source']['label']}",
           f"เผยแพร่: {r['published'] or 'ไม่ทราบ'}",
           f"หุ้นในพอร์ตที่เกี่ยวข้อง: {', '.join(r['tickers']) or 'ไม่พบ'}", ""]
    out += [f"• {n}" for n in r["notes"]] + ["", r["disclaimer"]]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ตรวจข่าวจากลิงก์ (อายุ/แหล่ง/ราคาขยับ)")
    ap.add_argument("url")
    ap.add_argument("--config", default=str(ROOT / "config" / "portfolio.json"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8"))
    try:
        r = check_url(a.url, cfg)
    except Exception as e:  # noqa: BLE001
        print(f"เปิดลิงก์ไม่ได้: {e}", file=sys.stderr)
        return 1
    print(json.dumps(r, ensure_ascii=False, indent=2) if a.json else render(r))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
