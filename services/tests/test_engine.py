import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from stockbro_engine import run as runmod
from stockbro_engine.backtest import backtest_s1
from stockbro_engine.levels import classic_pivots, plan_zone, summarize
from stockbro_engine.news import parse_rss
from stockbro_engine.newsscore import categorize, cluster, score_news, sentiment
from stockbro_engine.prices import parse_chart, synthetic
from stockbro_engine.signals import connect, evaluate_pending, save_signal


class LevelsTest(unittest.TestCase):
    def test_pivots_known_values(self):
        p = classic_pivots({"h": 110, "l": 90, "c": 100})
        self.assertAlmostEqual(p["P"], 100)
        self.assertAlmostEqual(p["R1"], 110)
        self.assertAlmostEqual(p["S1"], 90)
        self.assertAlmostEqual(p["R2"], 120)
        self.assertAlmostEqual(p["S2"], 80)

    def test_supports_below_resistances_above(self):
        bars = synthetic("AAPL")["bars"]
        s = summarize(bars)
        self.assertTrue(all(x["level"] < s["price"] for x in s["supports"]))
        self.assertTrue(all(x["level"] > s["price"] for x in s["resistances"]))

    def test_plan_stop_below_zone(self):
        s = summarize(synthetic("NVDA")["bars"])
        plan = plan_zone(s)
        if plan.get("zone") is not None:
            self.assertLess(plan["stop"], plan["zone"])


class BacktestTest(unittest.TestCase):
    def test_rates_in_range_and_counts_add_up(self):
        bt = backtest_s1(synthetic("TSLA")["bars"])
        self.assertTrue(bt["ok"])
        p = bt["pivot"]
        self.assertEqual(p["bounce"] + p["broke"] + p["none"], p["touches"])
        if p["touches"]:
            self.assertTrue(0 <= p["bounce_rate"] <= 1)

    def test_too_little_data(self):
        self.assertFalse(backtest_s1(synthetic("X", 20)["bars"])["ok"])


class NewsTest(unittest.TestCase):
    RSS = b"""<rss><channel>
    <item><title>Nvidia CEO sells shares ahead of earnings</title><link>https://www.a.com/1</link><pubDate>Mon, 16 Nov 2026 10:00:00 GMT</pubDate></item>
    <item><title>Nvidia CEO sells shares before earnings report</title><link>https://b.com/2</link><pubDate>Mon, 16 Nov 2026 11:00:00 GMT</pubDate></item>
    <item><title>Apple unveils new phone</title><link>https://c.com/3</link><pubDate>Mon, 16 Nov 2026 09:00:00 GMT</pubDate></item>
    </channel></rss>"""

    def test_parse_and_cluster(self):
        items = parse_rss(self.RSS, "NVDA")
        self.assertEqual(len(items), 3)
        self.assertEqual(items[0]["source"], "a.com")
        self.assertEqual(len(cluster(items)), 2)

    def test_scoring_prefers_multi_source_recent(self):
        items = parse_rss(self.RSS, "NVDA")
        now = datetime(2026, 11, 16, 12, 0, tzinfo=timezone.utc)
        res = score_news(items, now)
        self.assertEqual(res[0]["n_sources"], 2)
        self.assertGreater(res[0]["score"], res[1]["score"])

    def test_stale_flag(self):
        items = [{"ticker": "X", "title": "old news", "link": "#", "source": "s", "published": "2024-01-01T00:00:00+00:00"}]
        self.assertTrue(score_news(items)[0]["stale"])

    def test_category_and_sentiment(self):
        self.assertEqual(categorize("Tesla faces DOJ probe")[0], "กฎหมาย/ภาครัฐ")
        self.assertEqual(sentiment("Stock surges on record sales"), "บวก")
        self.assertEqual(sentiment("Shares plunge after miss"), "ลบ")


class PricesTest(unittest.TestCase):
    def test_parse_chart_skips_null_bars(self):
        payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 10},
                   "timestamp": [1700000000, 1700086400],
                   "indicators": {"quote": [{"open": [1, None], "high": [2, 2], "low": [0.5, 0.5],
                                             "close": [1.5, None], "volume": [100, 0]}]}}]}}
        d = parse_chart(payload, "X")
        self.assertEqual(len(d["bars"]), 1)


class SignalsTest(unittest.TestCase):
    def test_save_and_evaluate(self):
        with tempfile.TemporaryDirectory() as td:
            con = connect(Path(td) / "t.db")
            plan = {"zone": 100.0, "zone_name": "S1", "stop": 97.0, "target": 105.0, "status": "near"}
            save_signal(con, "2026-01-01", "AAA", 101.0, plan, "yahoo")
            save_signal(con, "2026-01-01", "AAA", 101.0, plan, "yahoo")  # ซ้ำ ต้องไม่เพิ่ม
            self.assertEqual(con.execute("select count(*) from signals").fetchone()[0], 1)
            bars = [{"date": f"2026-01-0{d}", "o": 101, "h": 102, "l": 100.5, "c": 101, "v": 1} for d in range(1, 8)]
            bars[2] = {"date": "2026-01-03", "o": 101, "h": 103, "l": 99.5, "c": 102, "v": 1}  # แตะโซน
            bars[3] = {"date": "2026-01-04", "o": 102, "h": 103, "l": 101.5, "c": 102.5, "v": 1}  # เด้ง >2%
            self.assertEqual(evaluate_pending(con, {"AAA": bars}, horizon=5), 1)
            self.assertEqual(con.execute("select outcome from signals").fetchone()[0], "bounce")


class RelevanceTest(unittest.TestCase):
    def test_filters_unrelated(self):
        from stockbro_engine.relevance import filter_relevant
        items = [{"title": "Apple unveils new iPhone"}, {"title": "unspun raises funds"},
                 {"title": "Why NVDA stock jumped"}, {"title": "Lilly weight drug approved"}]
        k, d = filter_relevant(items, "AAPL", "Apple")
        self.assertEqual((len(k), d), (1, 3))
        self.assertEqual(len(filter_relevant(items, "NVDA", "NVIDIA")[0]), 1)
        self.assertEqual(len(filter_relevant(items, "LLY", "Eli Lilly")[0]), 1)

    def test_ticker_case_sensitive(self):
        from stockbro_engine.relevance import filter_relevant
        self.assertEqual(filter_relevant([{"title": "he said it really is fine"}], "LLY", "Eli Lilly")[1], 1)


class TranslateTest(unittest.TestCase):
    def test_cache_and_quota_stop(self):
        from stockbro_engine.translate import translate_titles
        calls = []

        def fake(url, **kw):
            calls.append(url)
            return json.dumps({"responseStatus": 200, "responseData": {"translatedText": "สวัสดี"}}).encode()
        with tempfile.TemporaryDirectory() as td:
            cf = Path(td) / "c.json"
            r = translate_titles(["a", "b"], cf, fetch=fake)
            self.assertEqual(r, {"a": "สวัสดี", "b": "สวัสดี"})
            translate_titles(["a", "b"], cf, fetch=fake)  # จาก cache ไม่เรียกซ้ำ
            self.assertEqual(len(calls), 2)

            def bad(url, **kw):
                return json.dumps({"responseStatus": 200, "responseData": {"translatedText": "MYMEMORY WARNING: x"}}).encode()
            self.assertEqual(translate_titles(["z"], Path(td) / "d.json", fetch=bad), {})


class EndToEndTest(unittest.TestCase):
    def test_offline_run_writes_json_for_site(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(runmod.main(["--offline", "--out", td]), 0)
            d = json.loads((Path(td) / "data" / "report.sample.json").read_text(encoding="utf-8"))
            self.assertEqual(d["app"], "StockBro")
            self.assertEqual(d["mode"], "offline")
            self.assertEqual(len(d["holdings"]), 8)
            h = d["holdings"][0]
            for k in ("ticker", "price", "weight", "line", "trend_text", "level_text", "series", "plan", "backtest", "news"):
                self.assertIn(k, h)
            self.assertLessEqual(len(h["series"]), 120)
            self.assertTrue(d["greeting"].startswith("ว่าไง Bro"))
            self.assertLessEqual(sum(1 for a in d["top_things"] if a["kind"] == "ใกล้แนวรับ"), 2)
            self.assertIn("ไซด์เวย์", [g["name"] for g in d["glossary"]])
            self.assertIn("ไม่ใช่คำแนะนำการลงทุน", d["disclaimer"])
            for bad in ("ซื้อเลย", "ขายเลย", "ควรซื้อ", "ควรขาย"):
                self.assertNotIn(bad, json.dumps(d, ensure_ascii=False))

    def test_site_files_exist(self):
        site = Path(__file__).resolve().parents[2] / "site"
        for f in ("index.html", "portfolio.html", "news.html", "market.html", "stock.html", "glossary.html", "style.css", "app.js"):
            self.assertTrue((site / f).exists(), f)


if __name__ == "__main__":
    unittest.main()
