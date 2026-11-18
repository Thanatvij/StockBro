"""แปลงรายงาน (report) เป็น JSON ให้หน้าเว็บใน site/ อ่าน

หน้าเว็บ (site/*.html + style.css + app.js) แค่แสดงผล ไม่มีตรรกะคำนวณ/จัดระดับ
ทุกตัวเลขและทุกประโยคภาษา Bro มาจากที่นี่ (friend.py + กฎใน engine)
"""
from __future__ import annotations

from typing import Dict, List

from . import friend
from .glossary import as_list

DISCLAIMER = ("StockBro เป็นเครื่องมือส่วนตัวสำหรับศึกษาข้อมูล ไม่ใช่คำแนะนำการลงทุน ตัวเลขมาจากสูตรตายตัว "
              "พารามิเตอร์ทั้งหมดเป็นค่าตั้งต้นที่ยังไม่ผ่านการพิสูจน์ ผู้ใช้ตัดสินใจเอง")
CHART_DAYS = 120


def _bt(bt: Dict) -> Dict:
    if not bt.get("ok"):
        return {"ok": False}
    p, b = bt["pivot"], bt["baseline"]
    return {"ok": True, "verdict": bt["verdict"], "period": bt["period"], "touches": p["touches"],
            "bounce_rate": p["bounce_rate"], "baseline_bounce_rate": b["bounce_rate"], "edge_pp": bt["edge_pp"]}


def holding_view(r: Dict, bars: List[Dict]) -> Dict:
    base = {"ticker": r["ticker"], "name": r["name"], "ok": "price" in r, "flags": r.get("flags", [])}
    if "price" not in r:
        base["line"] = friend.stock_line(r)
        return base
    s, plan = r["summary"], r["plan"]
    base.update({
        "price": r["price"], "change_pct": r["change_pct"], "price_date": r["price_date"],
        "cost": r["cost"], "shares": r["shares"], "shares_estimated": r.get("shares_estimated", False),
        "value": r["value"], "pl": r["pl"], "pl_pct": r["pl_pct"], "weight": r.get("weight"),
        "source": r.get("source"),
        "line": friend.stock_line(r), "trend_text": friend.trend_plain(r), "level_text": friend.level_plain(r),
        "supports": s["supports"][:4], "resistances": s["resistances"][:4],
        "ma": s["ma"], "hi52": s["hi52"], "lo52": s["lo52"],
        "plan": {k: plan.get(k) for k in ("status", "zone_name", "zone", "zone_dist_pct", "stop", "target_name", "target", "rr")},
        "backtest": _bt(r["backtest"]),
        "news": r["news"], "news_dropped": r.get("news_dropped", 0), "filings": r["filings"],
        "series": [[b["date"], round(b["c"], 2)] for b in bars[-CHART_DAYS:]],
        "chart_lines": [
            {"name": "แนวรับ", "value": plan.get("zone"), "color": "#3ddc97"},
            {"name": "แนวต้าน", "value": plan.get("target"), "color": "#ff6b81"},
            {"name": "เส้นเฉลี่ย 50 วัน", "value": s["ma"].get("MA50"), "color": "#ffc857"},
        ],
    })
    return base


def build_payload(rep: Dict, bars_by_ticker: Dict[str, List[Dict]]) -> Dict:
    return {
        "app": "StockBro",
        "generated_at": rep["generated_at"],
        "mode": rep["mode"],
        "fx": rep["fx"],
        "disclaimer": DISCLAIMER,
        "greeting": friend.greeting(rep),
        "top_things": friend.top_things(rep),
        "portfolio_lines": friend.portfolio_lines(rep),
        "totals": {"value": rep["total_value"], "cost": rep["total_cost"], "pl": rep["total_pl"], "pl_pct": rep["total_pl_pct"]},
        "holdings": [holding_view(h, bars_by_ticker.get(h["ticker"], [])) for h in rep["holdings"]],
        "market": rep.get("market", {}),
        "calendar": rep.get("calendar", {"events": [], "missing_earnings": []}),
        "errors": rep.get("errors", []),
        "glossary": as_list(),
    }
