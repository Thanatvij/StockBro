"""จัดกลุ่มข่าวซ้ำ + ให้คะแนนด้วยกฎ (deterministic, ไม่ใช้ LLM)

คะแนน = น้ำหนักหมวด × ความสดของข่าว × โบนัสจำนวนสำนักที่รายงานเรื่องเดียวกัน
ทิศทาง (บวก/ลบ) ตัดสินจากคำในพาดหัวเท่านั้น ไม่ใช่การวิเคราะห์ของระบบ ค่าทั้งหมดเป็นค่าตั้งต้น
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional

CATEGORIES = [
    ("งบ/คาดการณ์", re.compile(r"earnings|guidance|revenue|forecast|outlook|quarter", re.I), 3),
    ("ผู้บริหาร", re.compile(r"\bCEO\b|\bCFO\b|resign|steps down|appoint|chairman", re.I), 3),
    ("กฎหมาย/ภาครัฐ", re.compile(r"lawsuit|sues|probe|investigat|\bSEC\b|\bFTC\b|\bDOJ\b|antitrust|tariff|\bban\b|export|sanction", re.I), 3),
    ("ควบรวม/ดีลใหญ่", re.compile(r"acquir|acquisition|merger|buyout|takeover|stake", re.I), 3),
    ("นักวิเคราะห์", re.compile(r"upgrade|downgrade|price target|raises target|cuts target|initiates|rating", re.I), 2),
    ("ผลิตภัณฑ์/สัญญา", re.compile(r"launch|unveil|recall|\bFDA\b|approval|trial|contract|partnership|order", re.I), 2),
]
DEFAULT_CAT = ("ข่าวทั่วไป", 1)
POS = re.compile(r"beat|surge|jump|soar|rally|upgrade|record|approv|raises|win|gain|rise", re.I)
NEG = re.compile(r"miss|fall|plunge|drop|slump|downgrade|lawsuit|probe|recall|cut|layoff|resign|ban|fine|warn", re.I)
STOP = {"with", "that", "this", "from", "after", "over", "will", "have", "stock", "shares", "says", "about", "into", "than", "what"}


def _tokens(title: str) -> set:
    return {w for w in re.findall(r"[a-z0-9$%.]+", title.lower()) if len(w) > 3 and w not in STOP}


def cluster(items: List[Dict], thr: float = 0.5) -> List[List[Dict]]:
    groups: List[List[Dict]] = []
    toks: List[set] = []
    for it in items:
        t = _tokens(it["title"])
        for g, gt in zip(groups, toks):
            inter = len(t & gt)
            union = len(t | gt) or 1
            if inter / union >= thr:
                g.append(it)
                gt |= t
                break
        else:
            groups.append([it])
            toks.append(set(t))
    return groups


def age_hours(published: Optional[str], now: Optional[datetime] = None) -> Optional[float]:
    if not published:
        return None
    now = now or datetime.now(timezone.utc)
    try:
        dt = datetime.fromisoformat(published)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (now - dt).total_seconds() / 3600.0


def recency(h: Optional[float]) -> float:
    if h is None:
        return 0.3
    if h <= 24:
        return 1.0
    if h <= 48:
        return 0.7
    if h <= 24 * 7:
        return 0.3
    return 0.1


def categorize(title: str):
    for name, rx, w in CATEGORIES:
        if rx.search(title):
            return name, w
    return DEFAULT_CAT


def sentiment(title: str) -> str:
    p, n = bool(POS.search(title)), bool(NEG.search(title))
    if p and not n:
        return "บวก"
    if n and not p:
        return "ลบ"
    return "กลาง/ไม่ชัด"


def score_news(items: List[Dict], now: Optional[datetime] = None, top: int = 5) -> List[Dict]:
    out = []
    for g in cluster(items):
        rep = sorted(g, key=lambda x: x.get("published") or "", reverse=True)[0]
        cat, w = categorize(rep["title"])
        h = age_hours(rep.get("published"), now)
        score = w * recency(h) * (1 + 0.2 * min(len(g) - 1, 4))
        out.append({
            "title": rep["title"],
            "link": rep["link"],
            "source": rep["source"],
            "published": rep.get("published"),
            "age_hours": h,
            "category": cat,
            "sentiment": sentiment(rep["title"]),
            "n_sources": len(g),
            "score": round(score, 2),
            "stale": h is not None and h > 24 * 7,
        })
    out.sort(key=lambda x: -x["score"])
    return out[:top]
