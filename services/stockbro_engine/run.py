"""CLI: python3 -m stockbro_engine.run [--offline]   (รันจากโฟลเดอร์ services/)"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import news as newsmod
from .prices import load_prices
from .export import build_payload
from .translate import translate_titles
from .levels import summarize
from .report import build_report
from .signals import connect, evaluate_pending, forward_stats, save_signal

ROOT = Path(__file__).resolve().parents[2]
MARKET = ["^GSPC", "^IXIC", "^VIX", "THB=X"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="StockBro daily brief")
    ap.add_argument("--offline", action="store_true", help="ใช้ข้อมูลจำลอง (ไม่แตะเน็ต) สำหรับทดสอบเท่านั้น")
    ap.add_argument("--no-translate", action="store_true", help="ไม่แปลพาดหัว")
    ap.add_argument("--config", default=str(ROOT / "config" / "portfolio.json"))
    ap.add_argument("--out", default=str(ROOT / "site"))
    args = ap.parse_args(argv)

    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    tickers = [h["ticker"] for h in cfg["holdings"]] + cfg.get("watchlist", [])
    cfg["holdings"] += [{"ticker": t, "name": t, "cost_usd": 0, "value_usd": 0} for t in cfg.get("watchlist", [])]
    mode = "offline" if args.offline else "live"

    prices = load_prices(tickers, ROOT / "data" / "cache", offline=args.offline)
    nd = newsmod.sample_news(tickers) if args.offline else newsmod.load_news(tickers)
    rep = build_report(cfg, prices, nd, mode)

    # ตลาดโดยรวม (ดึงพังได้ ไม่กระทบส่วนอื่น)
    idx = load_prices(MARKET, ROOT / "data" / "cache", offline=args.offline)
    for k, d in idx.items():
        if len(d.get("bars", [])) >= 2:
            sm = summarize(d["bars"])
            rep["market"][k] = {"price": sm["price"], "change_pct": sm["change_pct"], "date": sm["date"]}

    # แปลพาดหัว (เฉพาะ live; offline ไม่แตะเน็ต)
    if not args.offline and not args.no_translate:
        titles = [n["title"] for r in rep["holdings"] for n in r["news"]]
        tr = translate_titles(titles, ROOT / "data" / "cache" / "translations.json")
        for r in rep["holdings"]:
            for n in r["news"]:
                if n["title"] in tr:
                    n["title_th"] = tr[n["title"]]
        print(f"แปลพาดหัวได้ {len(tr)}/{len(titles)} เรื่อง")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    bars = {t: p.get("bars", []) for t, p in prices.items()}
    # ข้อมูลจำลองเขียนเป็น report.sample.json แยกจาก report.json จริง ไม่ทับกัน
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    fname = "report.sample.json" if args.offline else "report.json"
    (data_dir / fname).write_text(json.dumps(build_payload(rep, bars), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # เก็บสัญญาณ + ตัดสินผลของสัญญาณเก่า (ไม่เก็บถ้าเป็นข้อมูลจำลอง)
    if not args.offline:
        con = connect(ROOT / "data" / "stockbro.db")
        for r in rep["holdings"]:
            if "plan" in r:
                save_signal(con, r["price_date"], r["ticker"], r["price"], r["plan"], r["source"])
        n = evaluate_pending(con, {t: p.get("bars", []) for t, p in prices.items()})
        print("forward-test:", forward_stats(con), f"(ตัดสินใหม่ {n})")

    print(f"✓ เขียน {data_dir / fname} ({mode}) — เปิดเว็บผ่าน Live Server แล้วรีเฟรช")
    for a in rep["alerts"][:5]:
        print(f"  • {a['ticker']}: {a['kind']} — {a['text']}")
    for r in rep["holdings"]:
        if r.get("source") in ("error", "cache"):
            print(f"  ! {r['ticker']}: ใช้ {r['source']} ({r.get('error')})", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
