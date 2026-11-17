"""ประกอบรายงานรายวัน: พอร์ต + ระดับราคา + ข่าว + backtest + รายการที่ควรดู (ทั้งหมดมาจากกฎ)"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from .backtest import backtest_s1
from .levels import plan_zone, summarize
from .newsscore import score_news
from .relevance import filter_relevant

CONCENTRATION_PCT = 35.0   # ค่าตั้งต้น
BIG_MOVE_PCT = 3.0         # ค่าตั้งต้น
NEAR_ZONE_PCT = 1.5        # ค่าตั้งต้น (เดิม 3.0 ทำให้ทุกตัวขึ้นว่า 'ใกล้')
MAX_NEAR_ALERTS = 2


def _close_on_or_before(bars: List[Dict], day: str) -> float:
    cand = [b for b in bars if b["date"] <= day]
    return (cand[-1] if cand else bars[0])["c"]


def build_report(cfg: Dict, prices: Dict[str, Dict], newsdata: Dict, mode: str,
                 now: datetime = None) -> Dict:
    now = now or datetime.now(timezone.utc)
    holdings = []
    for h in cfg["holdings"]:
        t = h["ticker"]
        pdata = prices.get(t, {})
        bars = pdata.get("bars") or []
        row = {"ticker": t, "name": h["name"], "cost": h["cost_usd"], "source": pdata.get("source"),
               "error": pdata.get("error"), "news": [], "filings": [], "flags": []}
        if len(bars) < 30:
            row["flags"].append("ไม่มีข้อมูลราคาพอสำหรับคำนวณ")
            holdings.append(row)
            continue
        summary = summarize(bars)
        shares = h.get("shares") or h["value_usd"] / _close_on_or_before(bars, cfg["snapshot_date"])
        row.update({
            "shares": shares, "shares_estimated": not h.get("shares"),
            "price": summary["price"], "change_pct": summary["change_pct"],
            "value": shares * summary["price"], "summary": summary,
            "plan": plan_zone(summary, NEAR_ZONE_PCT), "backtest": backtest_s1(bars),
            "price_date": summary["date"],
        })
        row["pl"] = row["value"] - row["cost"]
        row["pl_pct"] = row["pl"] / row["cost"] * 100 if row["cost"] else None
        kept, dropped = filter_relevant(newsdata["news"].get(t, []), t, h["name"], h.get("aliases", []))
        row["news"] = score_news(kept, now, top=6)
        row["news_dropped"] = dropped
        row["filings"] = newsdata["filings"].get(t, [])
        holdings.append(row)

    total = sum(r.get("value", 0) for r in holdings)
    cost = sum(r["cost"] for r in holdings)
    for r in holdings:
        r["weight"] = r["value"] / total * 100 if total and "value" in r else None
        if r["weight"] and r["weight"] >= CONCENTRATION_PCT:
            r["flags"].append(f"สัดส่วน {r['weight']:.0f}% ของพอร์ตหุ้นรายตัว (เกณฑ์เตือน {CONCENTRATION_PCT:.0f}%)")

    return {
        "generated_at": now.isoformat(),
        "mode": mode,
        "fx": cfg.get("fx_usdthb"),
        "total_value": total,
        "total_cost": cost,
        "total_pl": total - cost,
        "total_pl_pct": (total - cost) / cost * 100 if cost else None,
        "holdings": holdings,
        "alerts": build_alerts(holdings, now),
        "market": {},
        "errors": newsdata.get("errors", []),
    }


def build_alerts(holdings: List[Dict], now: datetime) -> List[Dict]:
    """รายการ "คืนนี้ควรดู" เรียงตามน้ำหนักพอร์ต × ความสำคัญ"""
    alerts = []
    near_n = 0
    cutoff = (now - timedelta(days=3)).strftime("%Y-%m-%d")
    for r in sorted(holdings, key=lambda x: -(x.get("weight") or 0)):
        if "price" not in r:
            continue
        w = r.get("weight") or 0
        t = r["ticker"]
        plan = r["plan"]
        if plan.get("status") == "near" and near_n < MAX_NEAR_ALERTS:
            near_n += 1
            alerts.append({"p": 3 + w / 100, "ticker": t, "kind": "ใกล้แนวรับ",
                           "text": f"ราคาห่างแนวรับ {plan['zone_name']} ({plan['zone']:.2f}) อยู่ {abs(plan['zone_dist_pct']):.1f}%"})
        if abs(r["change_pct"]) >= BIG_MOVE_PCT:
            alerts.append({"p": 2.5 + w / 100, "ticker": t, "kind": "ราคาขยับแรง",
                           "text": f"วันล่าสุด {r['change_pct']:+.1f}% — เช็กว่ามีข่าวอะไร และตลาดตอบรับไปแล้วเท่าไหร่"})
        for f in r["filings"]:
            if f["form"] == "8-K" and f["date"] >= cutoff:
                alerts.append({"p": 3.5 + w / 100, "ticker": t, "kind": "SEC 8-K ใหม่",
                               "text": f"ยื่น 8-K วันที่ {f['date']} (แหล่งทางการ) {f.get('items') or ''}".strip(), "link": f["link"]})
        if r["news"] and r["news"][0]["score"] >= 2.5 and not r["news"][0]["stale"]:
            n = r["news"][0]
            alerts.append({"p": 1.5 + n["score"] / 3 + w / 100, "ticker": t, "kind": f"ข่าว: {n['category']}",
                           "text": n["title"], "link": n["link"]})
        for flag in r["flags"]:
            alerts.append({"p": 1 + w / 100, "ticker": t, "kind": "ข้อสังเกตพอร์ต", "text": flag})
    alerts.sort(key=lambda a: -a["p"])
    return alerts[:8]
