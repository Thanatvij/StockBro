"""แปลพาดหัวข่าวอังกฤษ→ไทย (แค่แปล ไม่วิเคราะห์ ไม่ใช้ LLM, ไม่ใช้ API key ของ Claude)

ผู้ให้บริการตั้งต้น: MyMemory (ไม่ต้องมี key ฟรี 5,000 ตัวอักษร/วัน; ตั้ง STOCKBRO_MYMEMORY_EMAIL
เพื่อเพิ่มเป็น 50,000/วัน) คุณภาพเป็นแบบเครื่องแปล ต้องติดป้าย "แปลโดยเครื่อง" เสมอ
แปลไม่ได้/โควตาหมด → คืน {} ให้หน้าเว็บแสดงพาดหัวอังกฤษเดิม
เพิ่มเจ้าอื่น (Azure/Google/DeepL) ได้โดยเพิ่มฟังก์ชันใน PROVIDERS
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Callable, Dict, Iterable, List

from .prices import http_get

MAX_NEW_PER_RUN = 100
CALL_TIMEOUT = 6      # วินาทีต่อครั้ง (เดิม 20 ทำให้ค้างนาน)
TOTAL_BUDGET = 90     # วินาทีรวมทั้งขั้นแปล เกินแล้วข้ามที่เหลือ ใช้ข่าวอังกฤษแทน
MAX_FAILS = 3         # พังติดกันกี่ครั้งแล้วเลิก (มักเกิดเมื่อโควตา MyMemory รายวันหมด)
LAST_STATS: Dict[str, object] = {}   # สถิติรอบล่าสุด ให้ run.py พิมพ์บอกสาเหตุที่แปลไม่ครบ


# ── ปกป้องชื่อคน/บริษัท/ตัวย่อ ไม่ให้เครื่องแปลทับศัพท์เพี้ยน ──────────────────────────
# วิธี: แทนชื่อด้วยโทเค็น X1, X2… ก่อนส่งแปล แล้วใส่ชื่อเดิม (อังกฤษ) กลับหลังแปล
# ถ้าโทเค็นหายหรือซ้ำ = คำแปลไม่น่าเชื่อถือ → ทิ้ง แสดงพาดหัวอังกฤษเดิมแทน (ดีกว่าแปลเละ)
# COMMON = คำที่มักขึ้นต้นด้วยตัวใหญ่ในพาดหัวแบบ Title Case แต่ไม่ใช่ชื่อเฉพาะ (ค่าตั้งต้น เพิ่มได้)
COMMON = set("""a an and or of to in on at for by with from as is are was be the this that these those it its his her their
up down out over under after before ahead into than more most less new old big top best first last next
why how what when where who which will could would should may might can has have had not no yes
stock stocks share shares market markets deal deals billion million trillion earnings report reports plan plans price prices target targets
raises raise cuts cut buy buys sell sells acquire acquires acquisition merger launches launch unveils unveil says say said
analyst analysts rating ratings upgrade upgrades downgrade downgrades quarter results revenue profit profits sales growth outlook guidance
record high low rally surge jumps jump falls fall drops drop slides slide soars soar gains gain loses lose beats beat misses miss
trial trials approval approved approves drug drugs weight loss company companies inc corp ltd co group holdings
ceo cfo chief executive president chairman board investors investor shareholders week day today tonight morning year years
weak strong demand supply preview previews expects expect warns warn track key major rise rises hit hits cash flow rate rates hike fed outlook
cheap cheaper costly early late rising falling bullish bearish bets bet buying selling wall street move moves hot cold power value growth
news update updates latest breaking exclusive report: what's here here's heres ai chip chips""".split())
_WORD = r"[A-Z][A-Za-z0-9'’\-]*"
_RUN = re.compile(rf"(?:{_WORD})(?:\s+(?:{_WORD}))*")
_INDEX = re.compile(r"(?<![A-Za-z0-9])(?:S&P\s?\d{3}|S&P|Dow Jones|Dow|Nasdaq(?:\s?\d{2,3})?|Russell\s?\d{4})(?![A-Za-z0-9])")
_ACRO = re.compile(r"(?<![A-Za-z0-9])[A-Z]{2,6}(?![A-Za-z0-9])")


def mask_names(title: str, known: Iterable[str] = ()):
    """คืน (ข้อความที่แทนชื่อด้วย X1.., [ชื่อเดิม])"""
    known_l = sorted({k for k in known if len(k) >= 3}, key=len, reverse=True)
    spans = []  # (start, end)
    for k in known_l:
        for m in re.finditer(rf"(?<![A-Za-z0-9]){re.escape(k)}(?![A-Za-z0-9])", title, re.I):
            spans.append((m.start(), m.end()))
    for m in _INDEX.finditer(title):
        spans.append((m.start(), m.end()))
    for m in _ACRO.finditer(title):
        spans.append((m.start(), m.end()))
    for m in _RUN.finditer(title):
        words = [(w.start() + m.start(), w.end() + m.start(), w.group()) for w in re.finditer(_WORD, m.group())]
        # ตัดคำสามัญหน้า-หลังออก เหลือแกนชื่อ
        kl = {k.lower() for k in known_l}

        def _edge(w):  # คำสามัญ หรือรูปกริยา/พหูพจน์ (-s/-ed/-ing) ที่ไม่ใช่ชื่อที่รู้จัก ตรงขอบของกลุ่มคำ
            lw = w.lower().strip("'’")
            return lw in COMMON or (lw not in kl and len(lw) > 4 and lw.endswith(("s", "ed", "ing")) and not lw.endswith("ss"))
        while words and _edge(words[0][2]):
            words.pop(0)
        while words and _edge(words[-1][2]):
            words.pop()
        if not words:
            continue
        if len(words) > 3:   # ยาวเกินชื่อเฉพาะ = พาดหัว Title Case ทั้งประโยค ปกป้องเฉพาะชื่อที่รู้จัก (ซึ่งจับไว้แล้วด้านบน)
            continue
        if len(words) == 1 and words[0][0] == 0 and words[0][2].lower() not in {k.lower() for k in known_l}:
            continue  # คำเดี่ยวต้นประโยค ถ้าไม่รู้จัก ถือว่าเป็นคำปกติ
        spans.append((words[0][0], words[-1][1]))
    # รวมช่วงที่ซ้อนกัน
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    out, names, last = [], [], 0
    for a, b in merged:
        out.append(title[last:a])
        names.append(title[a:b])
        out.append(f"X{len(names)}")
        last = b
    out.append(title[last:])
    return "".join(out), names


def unmask(text: str, names: List[str]) -> str:
    """ใส่ชื่อเดิมกลับ คืน "" ถ้าโทเค็นไม่ครบ/ซ้ำ"""
    if not names:
        return text
    found = re.findall(r"\bX(\d+)\b", text)
    if sorted(int(x) for x in found) != list(range(1, len(names) + 1)):
        return ""
    return re.sub(r"\bX(\d+)\b", lambda m: names[int(m.group(1)) - 1], text)


def translate_chunks(masked: str, names: List[str], fn: Callable) -> str:
    """แผนสำรองเมื่อเครื่องแปลทำโทเค็นหาย: แปลเฉพาะท่อนที่ไม่ใช่ชื่อทีละท่อน แล้วประกอบกับชื่อเดิม
    ชื่อไม่มีทางหายหรือเพี้ยน แต่บริบทข้ามท่อนหายไปบ้าง"""
    parts = re.split(r"\bX\d+\b", masked)
    out = []
    for i, part in enumerate(parts):
        txt = part.strip(" ,:;—-–|")
        seg = fn(txt) if re.search(r"[A-Za-z]{2,}", txt) else part
        out.append(seg.strip() if re.search(r"[A-Za-z]{2,}", txt) else part)
        if i < len(names):
            out.append(names[i])
    return re.sub(r"\s+", " ", " ".join(x for x in out if x)).strip()


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
                     fetch: Callable = http_get, known: Iterable[str] = ()) -> Dict[str, str]:
    """คืน {title_en: title_th} จาก cache + แปลของใหม่ (สูงสุด MAX_NEW_PER_RUN ต่อรอบ)"""
    cache: Dict[str, str] = {}
    if cache_file.exists():
        try:
            cache = json.loads(cache_file.read_text(encoding="utf-8"))
        except ValueError:
            cache = {}
    fn = PROVIDERS[provider]
    new = fails = 0
    stats = {"cached": 0, "new": 0, "fallback": 0, "errors": 0, "last_error": "", "skipped_budget": 0}
    LAST_STATS.clear()
    LAST_STATS.update(stats)
    start = time.monotonic()
    for t in dict.fromkeys(titles):
        if t in cache:
            stats["cached"] += 1
            continue
        if new >= MAX_NEW_PER_RUN or time.monotonic() - start > TOTAL_BUDGET:
            stats["skipped_budget"] += 1
            continue
        try:
            masked, names = mask_names(t, known)
            call = (lambda x: fn(x, fetch=fetch)) if fn is mymemory else fn
            raw = call(masked)
            fails = 0
            th = unmask(raw, names)
            if not th and names:           # โทเค็นหาย → แผนสำรองแปลทีละท่อน
                stats["fallback"] += 1
                th = translate_chunks(masked, names, call)
        except Exception as e:  # noqa: BLE001 - เจ้าบริการภายนอก พังได้หลายแบบ
            fails += 1
            stats["errors"] += 1
            stats["last_error"] = str(e)[:120]
            if fails >= MAX_FAILS:
                break
            continue
        if th:
            cache[t] = th
            new += 1
            stats["new"] += 1
        time.sleep(0.3)
    LAST_STATS.update(stats)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return {t: cache[t] for t in titles if t in cache}
