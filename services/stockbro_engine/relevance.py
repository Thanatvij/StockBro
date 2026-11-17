"""กรองข่าวที่ไม่เกี่ยวกับหุ้นตัวนั้น (กฎตายตัว ไม่ใช้ LLM)

Yahoo RSS ต่อ ticker มักแถมข่าวบริษัทอื่นที่แค่ถูกพูดถึง กฎ: พาดหัวต้องมี
ticker (ตัวพิมพ์ใหญ่ ติดกันทั้งคำ) หรือชื่อบริษัท/ชื่อเรียกที่ระบุใน ALIASES เท่านั้น
ค่า ALIASES เป็นรายการตั้งต้น เพิ่มเองได้ใน config ที่ key "aliases" ของแต่ละหุ้น
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

ALIASES: Dict[str, List[str]] = {
    "AAPL": ["apple", "iphone", "ipad", "tim cook", "app store"],
    "TSLA": ["tesla", "elon musk", "cybertruck", "robotaxi"],
    "JPM": ["jpmorgan", "jp morgan", "jamie dimon", "chase"],
    "NVDA": ["nvidia", "jensen huang", "blackwell", "geforce"],
    "MRNA": ["moderna"],
    "LLY": ["eli lilly", "lilly", "zepbound", "mounjaro"],
    "PLTR": ["palantir", "alex karp"],
    "SPCX": ["spacex", "starlink", "starship"],
}


def _terms(ticker: str, name: str, extra: Iterable[str] = ()) -> Tuple[re.Pattern, re.Pattern]:
    words = [w.lower() for w in ALIASES.get(ticker, [])] + [name.lower()] + [x.lower() for x in extra]
    words = [w for w in dict.fromkeys(words) if len(w) >= 3]
    alias_rx = re.compile(r"\b(?:" + "|".join(re.escape(w) for w in words) + r")\b", re.I) if words else re.compile(r"$^")
    tick_rx = re.compile(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])")  # case-sensitive
    return alias_rx, tick_rx


def filter_relevant(items: List[Dict], ticker: str, name: str, extra: Iterable[str] = ()) -> Tuple[List[Dict], int]:
    """คืน (ข่าวที่เกี่ยวข้อง, จำนวนที่ตัดทิ้ง)"""
    alias_rx, tick_rx = _terms(ticker, name, extra)
    kept = [it for it in items if tick_rx.search(it["title"]) or alias_rx.search(it["title"])]
    return kept, len(items) - len(kept)
