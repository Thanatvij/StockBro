"""ข่าวต่อ ticker: Yahoo Finance RSS + SEC EDGAR filings (ไม่ใช้ LLM, ไม่ใช้ key)

SEC ต้องส่ง User-Agent ที่ระบุผู้ติดต่อ: ตั้งตัวแปร STOCKBRO_SEC_UA="ชื่อ อีเมล" ก่อนรัน
ถ้าไม่ตั้ง จะข้าม filings (ข่าว Yahoo ยังทำงานปกติ)
"""
from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List
from urllib.parse import urlparse

from .prices import http_get

YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={t}&region=US&lang=en-US"
SEC_TICKERS = "https://www.sec.gov/files/company_tickers.json"
SEC_SUBS = "https://data.sec.gov/submissions/CIK{cik}.json"
FORMS = {"8-K", "10-Q", "10-K", "4", "6-K", "S-1", "SC 13G", "SC 13D"}


def parse_rss(xml_bytes: bytes, ticker: str) -> List[Dict]:
    root = ET.fromstring(xml_bytes)
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate")
        try:
            ts = parsedate_to_datetime(pub).astimezone(timezone.utc) if pub else None
        except (TypeError, ValueError):
            ts = None
        if not title:
            continue
        out.append({
            "ticker": ticker,
            "title": title,
            "link": link,
            "published": ts.isoformat() if ts else None,
            "source": urlparse(link).netloc.replace("www.", "") or "yahoo",
        })
    return out


def fetch_news(ticker: str) -> List[Dict]:
    return parse_rss(http_get(YAHOO_RSS.format(t=ticker)), ticker)


def _sec_headers() -> Dict:
    ua = os.environ.get("STOCKBRO_SEC_UA", "").strip()
    return {"User-Agent": ua} if ua else {}


def fetch_filings(tickers: List[str], max_per: int = 5) -> Dict[str, List[Dict]]:
    hdr = _sec_headers()
    if not hdr:
        return {}
    cik_map = {v["ticker"]: v["cik_str"] for v in json.loads(http_get(SEC_TICKERS, headers=hdr)).values()}
    out: Dict[str, List[Dict]] = {}
    for t in tickers:
        cik = cik_map.get(t)
        if not cik:
            continue
        time.sleep(0.2)
        data = json.loads(http_get(SEC_SUBS.format(cik=str(cik).zfill(10)), headers=hdr))
        rec = data["filings"]["recent"]
        rows = []
        for i, form in enumerate(rec["form"]):
            if form not in FORMS:
                continue
            acc = rec["accessionNumber"][i].replace("-", "")
            rows.append({
                "ticker": t,
                "form": form,
                "date": rec["filingDate"][i],
                "items": rec.get("items", [""] * len(rec["form"]))[i],
                "link": f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{rec['primaryDocument'][i]}",
            })
            if len(rows) >= max_per:
                break
        out[t] = rows
    return out


def load_news(tickers: List[str]) -> Dict:
    news: Dict[str, List[Dict]] = {}
    errors: List[str] = []
    for t in tickers:
        try:
            news[t] = fetch_news(t)
        except Exception as e:  # noqa: BLE001
            news[t] = []
            errors.append(f"news {t}: {e}")
        time.sleep(0.3)
    try:
        filings = fetch_filings(tickers)
    except Exception as e:  # noqa: BLE001
        filings = {}
        errors.append(f"sec: {e}")
    return {"news": news, "filings": filings, "errors": errors}


def sample_news(tickers: List[str]) -> Dict:
    """ข่าวตัวอย่างสำหรับ --offline เท่านั้น (ไม่ใช่ข่าวจริง)"""
    now = datetime.now(timezone.utc).isoformat()
    news = {t: [
        {"ticker": t, "title": f"[ตัวอย่าง] {t} analyst raises price target ahead of earnings",
         "link": "#", "published": now, "source": "sample"},
        {"ticker": t, "title": f"[ตัวอย่าง] {t} faces probe over tariff exposure",
         "link": "#", "published": now, "source": "sample"},
    ] for t in tickers}
    return {"news": news, "filings": {}, "errors": []}
