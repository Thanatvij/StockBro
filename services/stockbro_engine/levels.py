"""แนวรับ-แนวต้านแบบกฎตายตัว (deterministic)

ทุกฟังก์ชันรับ bars = list ของ dict {date, o, h, l, c, v} เรียงจากเก่าไปใหม่
ค่าคงที่ทั้งหมดเป็นค่าตั้งต้น ต้องปรับจากผล backtest จริง ห้ามถือว่าผ่านการพิสูจน์แล้ว
"""
from __future__ import annotations

from typing import Dict, List, Optional

TRADING_DAYS_YEAR = 252


def classic_pivots(bar: Dict) -> Dict[str, float]:
    """Classic floor pivots จากแท่งราคาหนึ่งแท่ง ใช้เป็นระดับของวันทำการถัดไป"""
    h, l, c = bar["h"], bar["l"], bar["c"]
    p = (h + l + c) / 3.0
    rng = h - l
    return {
        "P": p,
        "R1": 2 * p - l,
        "S1": 2 * p - h,
        "R2": p + rng,
        "S2": p - rng,
    }


def sma(values: List[float], n: int) -> Optional[float]:
    if n <= 0 or len(values) < n:
        return None
    return sum(values[-n:]) / n


def pct(a: float, b: float) -> float:
    """ระยะจาก b ไป a เป็น % ของ b"""
    return (a - b) / b * 100.0


def summarize(bars: List[Dict]) -> Dict:
    """สรุประดับราคาที่ใช้ใน brief ของคืนนี้ (คำนวณจากแท่งล่าสุดที่ปิดแล้ว)"""
    if len(bars) < 2:
        raise ValueError("ต้องมีข้อมูลอย่างน้อย 2 วัน")
    last = bars[-1]
    prev = bars[-2]
    closes = [b["c"] for b in bars]
    price = last["c"]
    window = bars[-TRADING_DAYS_YEAR:]

    piv = classic_pivots(last)
    levels = {
        "S2": piv["S2"], "S1": piv["S1"], "P": piv["P"],
        "R1": piv["R1"], "R2": piv["R2"],
    }
    ma = {"MA20": sma(closes, 20), "MA50": sma(closes, 50), "MA200": sma(closes, 200)}
    hi52 = max(b["h"] for b in window)
    lo52 = min(b["l"] for b in window)

    # รวมทุกระดับที่เป็นไปได้ แล้วแยกเป็นรับ (ต่ำกว่าราคา) / ต้าน (สูงกว่าราคา)
    candidates = dict(levels)
    candidates.update({k: v for k, v in ma.items() if v is not None})
    candidates["52W-Low"] = lo52
    candidates["52W-High"] = hi52
    candidates.pop("P", None)  # P เป็นจุดกลาง ไม่ใช้เป็นแนวรับ/ต้าน

    supports = sorted(
        [(k, v) for k, v in candidates.items() if v < price], key=lambda kv: -kv[1]
    )
    resistances = sorted(
        [(k, v) for k, v in candidates.items() if v > price], key=lambda kv: kv[1]
    )

    return {
        "date": last["date"],
        "price": price,
        "prev_close": prev["c"],
        "change_pct": pct(price, prev["c"]),
        "pivots": levels,
        "ma": ma,
        "hi52": hi52,
        "lo52": lo52,
        "off_hi52_pct": pct(price, hi52),
        "supports": [{"name": k, "level": v, "dist_pct": pct(v, price)} for k, v in supports],
        "resistances": [{"name": k, "level": v, "dist_pct": pct(v, price)} for k, v in resistances],
        "trend": trend_label(price, ma),
    }


def trend_label(price: float, ma: Dict[str, Optional[float]]) -> str:
    m50, m200 = ma.get("MA50"), ma.get("MA200")
    if m50 is None or m200 is None:
        return "ข้อมูลไม่พอ"
    if price > m50 > m200:
        return "ขาขึ้น"
    if price < m50 < m200:
        return "ขาลง"
    return "ไซด์เวย์/กลับตัว"


def plan_zone(summary: Dict, near_pct: float = 3.0) -> Dict:
    """โซนติดตาม + จุดตัดขาดทุนอ้างอิง

    กฎ: โซนรับ = แนวรับที่ใกล้ราคาที่สุด, stop อ้างอิง = แนวรับถัดลงไป -1%
    (ถ้าไม่มี ใช้ -3% จากโซนรับ), เป้าแรก = แนวต้านที่ใกล้ที่สุด
    """
    sup = summary["supports"]
    res = summary["resistances"]
    if not sup:
        return {"status": "no_support", "text": "ราคาต่ำกว่าทุกแนวรับที่ระบบคำนวณ ยังประเมินโซนรับไม่ได้"}
    zone = sup[0]
    stop = sup[1]["level"] * 0.99 if len(sup) > 1 else zone["level"] * 0.97
    target = res[0] if res else None
    near = abs(zone["dist_pct"]) <= near_pct
    rr = None
    if target:
        risk = zone["level"] - stop
        reward = target["level"] - zone["level"]
        rr = reward / risk if risk > 0 else None
    return {
        "status": "near" if near else "far",
        "zone_name": zone["name"],
        "zone": zone["level"],
        "zone_dist_pct": zone["dist_pct"],
        "stop": stop,
        "target_name": target["name"] if target else None,
        "target": target["level"] if target else None,
        "rr": rr,
    }
