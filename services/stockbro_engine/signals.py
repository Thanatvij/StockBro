"""เก็บสัญญาณทุกวันลง SQLite เพื่อทำ accuracy tracker (forward-test)

schema เขียนแบบที่ย้ายไป Postgres/Neon ได้ตรงๆ (เปลี่ยน INTEGER PRIMARY KEY เป็น SERIAL)
ต้องเก็บตั้งแต่วันแรก: สัญญาณที่ไม่ได้บันทึกไว้ย้อนกลับไปเก็บไม่ได้
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from .backtest import _outcome

SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
  id INTEGER PRIMARY KEY,
  signal_date TEXT NOT NULL,
  ticker TEXT NOT NULL,
  method TEXT NOT NULL,
  price REAL NOT NULL,
  zone_name TEXT,
  zone REAL,
  stop REAL,
  target REAL,
  status TEXT,
  data_source TEXT,
  created_at TEXT NOT NULL,
  outcome TEXT,
  evaluated_at TEXT,
  UNIQUE (signal_date, ticker, method)
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def save_signal(con, signal_date, ticker, price, plan, data_source, method="pivot_s1") -> None:
    if plan.get("zone") is None:
        return
    con.execute(
        "INSERT OR IGNORE INTO signals (signal_date,ticker,method,price,zone_name,zone,stop,target,status,data_source,created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (signal_date, ticker, method, price, plan["zone_name"], plan["zone"], plan["stop"],
         plan.get("target"), plan["status"], data_source, datetime.now(timezone.utc).isoformat()),
    )
    con.commit()


def evaluate_pending(con, bars_by_ticker: Dict[str, List[Dict]], horizon: int = 5,
                     target: float = 0.02, stop: float = 0.02) -> int:
    """ตัดสินผลสัญญาณที่ผ่านมาแล้ว >= horizon วันทำการ: no_touch / bounce / broke / none"""
    rows = con.execute(
        "SELECT id, signal_date, ticker, zone FROM signals WHERE outcome IS NULL AND data_source != 'synthetic'"
    ).fetchall()
    done = 0
    for sid, sdate, ticker, zone in rows:
        bars = bars_by_ticker.get(ticker) or []
        after = [i for i, b in enumerate(bars) if b["date"] > sdate]
        if len(after) < horizon:
            continue
        window = after[:horizon]
        touch = next((i for i in window if bars[i]["l"] <= zone), None)
        outcome = "no_touch" if touch is None else _outcome(bars, touch, zone, horizon, target, stop)
        con.execute("UPDATE signals SET outcome=?, evaluated_at=? WHERE id=?",
                    (outcome, datetime.now(timezone.utc).isoformat(), sid))
        done += 1
    con.commit()
    return done


def forward_stats(con) -> Dict:
    rows = con.execute(
        "SELECT outcome, COUNT(*) FROM signals WHERE outcome IS NOT NULL GROUP BY outcome").fetchall()
    d = {k: v for k, v in rows}
    touched = sum(d.get(k, 0) for k in ("bounce", "broke", "none"))
    total = sum(d.values())
    pending = con.execute("SELECT COUNT(*) FROM signals WHERE outcome IS NULL").fetchone()[0]
    return {"total": total, "touched": touched, "bounce": d.get("bounce", 0),
            "broke": d.get("broke", 0), "none": d.get("none", 0),
            "no_touch": d.get("no_touch", 0), "pending": pending}
