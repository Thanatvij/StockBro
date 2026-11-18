"""เสียง "เพื่อนนักลงทุน" ภาษาไทย: แม่แบบประโยค + ตัวเลขจากสูตร (ไม่ใช้ LLM, ไม่แนะนำซื้อ/ขาย)

ทุกประโยคอ้างตัวเลขที่คำนวณได้จริงเท่านั้น ถ้าไม่มีข้อมูลต้องบอกว่า "ยังประเมินไม่ได้"
เกณฑ์ที่ใช้เป็นค่าตั้งต้น ยังไม่ผ่านการพิสูจน์
"""
from __future__ import annotations

from typing import Dict, List

DROP_SCENARIO_PCT = 10.0


def trend_plain(r: Dict) -> str:
    s = r["summary"]
    t = s["trend"]
    if t == "ขาขึ้น":
        return "ภาพรวมระยะกลางยังขาขึ้นอยู่นะ (ราคาอยู่เหนือเส้นเฉลี่ย 50 และ 200 วัน)"
    if t == "ขาลง":
        return "ภาพรวมระยะกลางยังขาลงอยู่นะ (ราคาอยู่ใต้เส้นเฉลี่ย 50 และ 200 วัน)"
    if t == "ข้อมูลไม่พอ":
        return "ข้อมูลย้อนหลังยังไม่พอจะบอกแนวโน้มว่ะ"
    return "ตอนนี้ยังไม่ชัดว่าไปทางไหนนะ ราคาแกว่งไปมาแถวเส้นเฉลี่ย ไม่ได้ขึ้นหรือลงต่อเนื่อง เขาเรียกว่า ไซด์เวย์"


def level_plain(r: Dict) -> str:
    s, plan, bt = r["summary"], r["plan"], r["backtest"]
    if plan.get("status") == "no_support":
        return "ราคาหลุดต่ำกว่าทุกแนวรับที่คำนวณได้แล้ว เลยยังประเมินโซนรับไม่ได้"
    parts = [f"ถ้าลงต่อ จุดแรกที่สูตรมองว่าอาจมีแรงรับคือ {plan['zone']:.2f} (อีก {abs(plan['zone_dist_pct']):.1f}% จากราคาตอนนี้)"]
    if plan.get("target"):
        parts.append(f"ถ้าขึ้น ด่านแรกที่อาจเจอแรงขายคือ {plan['target']:.2f}")
    if bt.get("ok"):
        v = bt["verdict"]
        parts.append(f"แล้วระดับพวกนี้แม่นแค่ไหน? ผลทดสอบย้อนหลังของตัวนี้บอกว่า: {v}")
    else:
        parts.append("ยังทดสอบความแม่นของระดับพวกนี้ไม่ได้ ข้อมูลไม่พอว่ะ")
    return " ".join(parts) + "."


def stock_line(r: Dict) -> str:
    """ประโยคเดียวต่อหุ้นสำหรับหน้าแรก"""
    if "price" not in r:
        return "ยังไม่มีข้อมูลราคาตัวนี้ ประเมินไม่ได้นะ"
    mv = r["change_pct"]
    move = "ทรงตัว" if abs(mv) < 0.5 else (f"ขึ้น {mv:.1f}%" if mv > 0 else f"ลง {abs(mv):.1f}%")
    pl = ""
    if r.get("pl_pct") is not None and r["cost"]:
        pl = f" ตัวนี้ในพอร์ตนายตอนนี้{'กำไร' if r['pl'] >= 0 else 'ขาดทุน'} {abs(r['pl_pct']):.1f}%"
    n = len(r["news"])
    news = f" มีข่าวเกี่ยวข้อง {n} เรื่อง" if n else " วันนี้ไม่เจอข่าวที่เกี่ยวกับตัวนี้โดยตรง"
    return f"วันล่าสุด{move}{pl}.{news}"


def portfolio_lines(rep: Dict) -> List[str]:
    hs = [h for h in rep["holdings"] if "value" in h and h["cost"]]
    if not hs:
        return ["ยังไม่มีข้อมูลพอร์ตให้คำนวณนะ"]
    out = []
    top = max(hs, key=lambda h: h["weight"] or 0)
    drop = top["weight"] * DROP_SCENARIO_PCT / 100
    out.append(f"{top['ticker']} คือตัวใหญ่สุดในพอร์ตนายเลย {top['weight']:.0f}% ถ้ามันตก {DROP_SCENARIO_PCT:.0f}% พอร์ตหุ้นรายตัวจะหายไปราว {drop:.1f}% "
               f"(คิดแบบง่ายๆ ไม่รวมตัวอื่นขยับตาม) ยิ่งตัวเดียวใหญ่ พอร์ตยิ่งเสี่ยงขึ้นกับมันตัวเดียวนะ")
    losers = sorted([h for h in hs if h["pl"] < 0], key=lambda h: h["pl_pct"])
    if losers:
        txt = ", ".join(f"{h['ticker']} {h['pl_pct']:.1f}%" for h in losers[:3])
        out.append(f"ตัวที่แดงอยู่ตอนนี้: {txt} ติดลบวันเดียวไม่ได้บอกอะไรมากนะ ลองดูว่าข่าวที่ทำให้ตกยังอยู่ไหม")
    big = [h for h in hs if (h["weight"] or 0) >= 15]
    out.append(f"ตอนนี้นายถือหุ้นรายตัว {len(hs)} ตัว มูลค่ารวมราว ${rep['total_value']:.0f} ก้อนยังไม่ใหญ่ เป็นช่วงฝึกมือที่ดี แต่ก็ควรดูสัดส่วนไว้ตั้งแต่ตอนนี้")
    if len(big) >= 3:
        out.append(f"มี {len(big)} ตัวที่แต่ละตัวเกิน 15% ของพอร์ต: {', '.join(h['ticker'] for h in big)} ถ้าตัวพวกนี้ลงพร้อมกัน พอร์ตจะสะเทือนเยอะ")
    return out


def greeting(rep: Dict) -> str:
    hs = [h for h in rep["holdings"] if "change_pct" in h and "weight" in h and h["weight"]]
    if not hs:
        return "ว่าไง Bro วันนี้ยังดึงราคาไม่ได้ ลองรันใหม่อีกทีนะ"
    wchg = sum(h["change_pct"] * h["weight"] for h in hs) / sum(h["weight"] for h in hs)
    date = hs[0]["price_date"]
    mood = "ค่อนข้างนิ่ง" if abs(wchg) < 0.5 else ("เป็นสีเขียวโดยรวม" if wchg > 0 else "เป็นสีแดงโดยรวม")
    return (f"ว่าไง Bro สรุปให้ก่อนตลาดสหรัฐฯ เปิดนะ ราคาปิดล่าสุดคือวันที่ {date} "
            f"พอร์ตนาย{mood} (ถ่วงน้ำหนักตามสัดส่วน {wchg:+.1f}%)")


def top_things(rep: Dict, n: int = 3) -> List[Dict]:
    """3 เรื่องที่ควรดูคืนนี้ = alerts จัดอันดับแล้ว + คำอธิบายภาษาคน"""
    why = {
        "SEC 8-K ใหม่": "บริษัทยื่นเอกสารทางการเรื่องสำคัญ อ่านก่อนใครเลย",
        "ราคาขยับแรง": "ตัวนี้ขยับแรงกว่าปกติ ลองเปิดดูว่ามีข่าวอะไรอยู่เบื้องหลัง",
        "ใกล้แนวรับ": "ราคาอยู่ใกล้จุดที่สูตรมองว่ามักมีแรงรับ ถ้าหลุดลงไปถือว่าอ่อนแรงลงนะ",
        "ข้อสังเกตพอร์ต": "เรื่องโครงสร้างพอร์ตของนายเอง",
    }
    out = []
    for a in rep["alerts"][:n]:
        out.append({**a, "why": why.get(a["kind"], "ข่าวที่คะแนนสูงสุดของตัวนี้ตามกฎของระบบ อ่านต้นฉบับประกอบด้วยนะ")})
    return out
