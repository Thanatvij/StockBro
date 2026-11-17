"""แปลพาดหัวข่าวอังกฤษ→ไทย (แค่แปล ไม่วิเคราะห์ ไม่ใช้ LLM, ไม่ใช้ API key ของ Claude)

ผู้ให้บริการตั้งต้น: MyMemory (ไม่ต้องมี key ฟรี 5,000 ตัวอักษร/วัน; ตั้ง STOCKBRO_MYMEMORY_EMAIL
เพื่อเพิ่มเป็น 50,000/วัน) คุณภาพเป็นแบบเครื่องแปล ต้องติดป้าย "แปลโดยเครื่อง" เสมอ
แปลไม่ได้/โควตาหมด → คืน {} ให้หน้าเว็บแสดงพาดหัวอังกฤษเดิม
เพิ่มเจ้าอื่น (Azure/Google/DeepL) ได้โดยเพิ่มฟังก์ชันใน PROVIDERS
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Dict, List

from .prices import http_get

MAX_NEW_PER_RUN = 40
CALL_TIMEOUT = 6      # วินาทีต่อครั้ง (เดิม 20 ทำให้ค้างนาน)
TOTAL_BUDGET = 40     # วินาทีรวมทั้งขั้นแปล เกินแล้วข้ามที่เหลือ ใช้ข่าวอังกฤษแทน
MAX_FAILS = 2         # พังติดกันกี่ครั้งแล้วเลิก


def mymemory(text: str, fetch: Callable = http_get) -> str:
    q = {"q": text[:450], "langpair": "en|th"}
    email = os.environ.get("STOCKBRO_MYMEMORY_EMAIL", "").strip()
    if email:
        q["de"] = email
    data = json.loads(fetch("https://api.mymemory.translated.net/get?" + urllib.parse.urlencode(q), timeout=CALL_TIMEOUT))
    out = (data.get("responseData") or {}).get("translatedText") or ""
    if data.get("responseStatus") not in (200, "200") or "MYMEMORY WARNING" in out.upper():
        raise RuntimeError("โควตา/สถานะ MyMemory ไม่ผ่าน")
    return out.strip()


PROVIDERS = {"mymemory": mymemory}


def translate_titles(titles: List[str], cache_file: Path, provider: str = "mymemory",
                     fetch: Callable = http_get) -> Dict[str, str]:
    """คืน {title_en: title_th} จาก cache + แปลของใหม่ (สูงสุด MAX_NEW_PER_RUN ต่อรอบ)"""
    cache: Dict[str, str] = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    fn = PROVIDERS[provider]
    new = fails = 0
    start = time.monotonic()
    for t in dict.fromkeys(titles):
        if t in cache or new >= MAX_NEW_PER_RUN:
            continue
        if time.monotonic() - start > TOTAL_BUDGET:
            break
        try:
            th = fn(t, fetch=fetch) if fn is mymemory else fn(t)
            fails = 0
        except Exception:  # noqa: BLE001 - เจ้าบริการภายนอก พังได้หลายแบบ
            fails += 1
            if fails >= MAX_FAILS:
                break
            continue
        if th:
            cache[t] = th
            new += 1
        time.sleep(0.3)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {t: cache[t] for t in titles if t in cache}
