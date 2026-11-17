"""Accuracy tracker แบบย้อนหลัง: แนวรับ Pivot S1 แม่นจริงไหม

นิยาม "แม่น" (ค่าตั้งต้น ปรับได้):
- วันที่ i ใช้ S1 ที่คำนวณจากแท่งวันที่ i-1
- "แตะ" = low ของวันที่ i <= S1
- หลังแตะ ดูต่อไปอีก horizon วัน:
    bounce = high >= S1 * (1 + target) ก่อน low <= S1 * (1 - stop)
    broke  = low <= S1 * (1 - stop) ก่อน (ถ้าเกิดทั้งคู่ในวันเดียว นับเป็น broke แบบระวังไว้ก่อน)
    none   = ไม่ถึงทั้งสองอย่างภายใน horizon วัน
- วันที่แตะเองก็หลุด stop ได้ (low ของวันแตะ <= S1*(1-stop) = broke ทันที)

baseline: ใช้กติกาเดียวกันกับ "ระดับสุ่ม" ที่อยู่ห่างจากราคาปิดวันก่อนเท่ากับระยะเฉลี่ยของ S1
ถ้า S1 ไม่ดีกว่า baseline แปลว่าสูตรไม่ได้ให้ข้อมูลมากกว่าการเดาระยะ
"""
from __future__ import annotations

from statistics import median
from typing import Callable, Dict, List

from .levels import classic_pivots


def _outcome(bars: List[Dict], i: int, lv: float, horizon: int, target: float, stop: float) -> str:
    if bars[i]["l"] <= lv * (1 - stop):
        return "broke"
    for b in bars[i + 1 : i + 1 + horizon]:
        hit_stop = b["l"] <= lv * (1 - stop)
        hit_target = b["h"] >= lv * (1 + target)
        if hit_stop:
            return "broke"
        if hit_target:
            return "bounce"
    return "none"


def _run(bars: List[Dict], level_fn: Callable[[int], float], horizon: int, target: float, stop: float) -> Dict:
    n_days = touches = bounce = broke = none = 0
    for i in range(1, len(bars) - horizon):
        n_days += 1
        lv = level_fn(i)
        if bars[i]["l"] > lv:
            continue
        touches += 1
        o = _outcome(bars, i, lv, horizon, target, stop)
        if o == "bounce":
            bounce += 1
        elif o == "broke":
            broke += 1
        else:
            none += 1
    return {
        "days": n_days,
        "touches": touches,
        "bounce": bounce,
        "broke": broke,
        "none": none,
        "touch_rate": touches / n_days if n_days else None,
        "bounce_rate": bounce / touches if touches else None,
        "broke_rate": broke / touches if touches else None,
    }


def backtest_s1(bars: List[Dict], horizon: int = 5, target: float = 0.02, stop: float = 0.02) -> Dict:
    if len(bars) < horizon + 30:
        return {"ok": False, "reason": "ข้อมูลย้อนหลังไม่พอ"}

    s1 = [None] + [classic_pivots(bars[i - 1])["S1"] for i in range(1, len(bars))]
    dists = [(bars[i - 1]["c"] - s1[i]) / bars[i - 1]["c"] for i in range(1, len(bars)) if s1[i] is not None]
    d = median(dists) if dists else 0.0

    pivot = _run(bars, lambda i: s1[i], horizon, target, stop)
    base = _run(bars, lambda i: bars[i - 1]["c"] * (1 - d), horizon, target, stop)

    edge = None
    if pivot["bounce_rate"] is not None and base["bounce_rate"] is not None:
        edge = (pivot["bounce_rate"] - base["bounce_rate"]) * 100

    return {
        "ok": True,
        "method": "Pivot S1",
        "params": {"horizon_days": horizon, "target_pct": target * 100, "stop_pct": stop * 100},
        "period": {"from": bars[0]["date"], "to": bars[-1]["date"]},
        "median_s1_dist_pct": d * 100,
        "pivot": pivot,
        "baseline": base,
        "edge_pp": edge,
        "verdict": verdict(pivot, edge),
    }


def verdict(pivot: Dict, edge) -> str:
    if not pivot["touches"] or pivot["touches"] < 20:
        return "ตัวอย่างน้อยเกินไป ยังสรุปไม่ได้"
    if edge is None:
        return "ยังสรุปไม่ได้"
    if edge >= 5:
        return "ดีกว่าการเดาระยะอย่างเห็นได้ชัด"
    if edge <= -5:
        return "แย่กว่าการเดาระยะ ไม่ควรเชื่อแนวรับนี้"
    return "ใกล้เคียงการเดาระยะ ใช้อ้างอิงคร่าวๆ เท่านั้น"
