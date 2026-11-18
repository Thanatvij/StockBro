/* StockBro · หน้าเว็บ (แสดงผลอย่างเดียว)
 * ตรรกะคำนวณทั้งหมดอยู่ใน Python (services/stockbro_engine) แล้วออกมาเป็น data/report.json
 * ไฟล์นี้แค่อ่าน JSON แล้ววาดหน้า ยกเว้นหน้า "พอร์ต" ที่คำนวณกำไร/สัดส่วนใหม่เมื่อผู้ใช้แก้ตัวเลขเอง
 * ไม่มี dependency ไม่มี build: เปิดผ่าน Live Server (หรือ python3 -m http.server) ได้เลย
 */
"use strict";

const NAV = [
  ["index.html", "หน้าแรก"], ["portfolio.html", "พอร์ต"], ["news.html", "ข่าว"],
  ["market.html", "ตลาด"], ["glossary.html", "ศัพท์"],
];
const TH_TZ = "Asia/Bangkok";
const LOGO = '<svg viewBox="0 0 48 48" aria-hidden="true"><rect width="48" height="48" rx="13" fill="#12151c" stroke="#2c3550"/><path d="M14 14v22M24 10v24M34 8v22" stroke="#3ddc97" stroke-width="2" stroke-linecap="round"/><rect x="11" y="20" width="6" height="12" rx="1.5" fill="#ff6b81"/><rect x="21" y="16" width="6" height="14" rx="1.5" fill="#3ddc97"/><rect x="31" y="12" width="6" height="12" rx="1.5" fill="#3ddc97"/></svg>';
let D = null;            // ข้อมูลทั้งหมดจาก report.json
let GLOSS = {};          // key -> {name, short, long}

/* ---------- helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (v, d = 2) => (v == null ? "–" : Number(v).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }));
const money = (v) => (v == null ? "–" : "$" + num(v));
const pct = (v, d = 1) => (v == null ? "–" : (v > 0 ? "+" : "") + num(v, d) + "%");
const cls = (v) => (v > 0 ? "up" : v < 0 ? "dn" : "mut");
const tip = (key) => {
  const g = GLOSS[key];
  return g ? `<a class="term" href="glossary.html#${esc(key)}" title="${esc(g.short)}">${esc(g.name)}</a>` : esc(key);
};
function ago(h) {
  if (h == null) return "ไม่ทราบเวลา";
  if (h < 1) return "ไม่ถึงชั่วโมงที่แล้ว";
  if (h < 48) return `${Math.round(h)} ชม.ที่แล้ว`;
  return `${Math.round(h / 24)} วันที่แล้ว`;
}
const holdings = () => D.holdings.filter((h) => h.ok);

/* ---------- โหลดข้อมูล ---------- */
async function fetchJson(path) {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}
async function loadData() {
  const wantSample = new URLSearchParams(location.search).has("sample");
  if (!wantSample) {
    try { return await fetchJson("data/report.json"); } catch (e) { /* ลองไฟล์ตัวอย่างต่อ */ }
  }
  const d = await fetchJson("data/report.sample.json");
  d._fallback = true;
  return d;
}

/* ---------- โครงหน้า ---------- */
function chrome(active, body) {
  const gen = new Date(D.generated_at).toLocaleString("th-TH", { timeZone: TH_TZ, dateStyle: "medium", timeStyle: "short" });
  const nav = NAV.map(([f, n]) => `<a class="link ${f === active ? "on" : ""}" href="${f}">${n}</a>`).join("");
  let banner = "";
  if (D.mode === "offline") banner = '<div class="banner">⚠ ข้อมูลตัวอย่าง (offline) ราคา/ข่าวในหน้านี้ไม่ใช่ของจริง ใช้ทดสอบหน้าตาเท่านั้น</div>';
  else if (D._fallback) banner = '<div class="banner">ยังไม่มีข้อมูลจริง (data/report.json) กำลังแสดงข้อมูลตัวอย่าง รัน <code>python3 -m stockbro_engine.run</code> เพื่อสร้างข้อมูลจริง</div>';
  $("#app").innerHTML =
    `<nav><a class="logo" href="index.html">${LOGO}<span>Stock<i>Bro</i></span></a>${nav}</nav>` +
    `${banner}${body}<div class="foot">ข้อมูล ณ ${esc(gen)} · ${esc(D.disclaimer)}</div>`;
}
function fail(e) {
  $("#app").innerHTML = `<div class="err"><b>โหลดข้อมูลไม่ได้</b><br>${esc(e.message)}<br><br>
  1) รัน <code>cd services && python3 -m stockbro_engine.run</code> ก่อน<br>
  2) เปิดเว็บผ่าน Live Server หรือ <code>python3 -m http.server</code> ที่โฟลเดอร์ site (เปิดไฟล์ตรงๆ แบบ file:// เบราว์เซอร์จะบล็อกการอ่าน JSON)</div>`;
}

/* ---------- ข่าว ---------- */
function newsItem(n, ticker, chg, showTicker = true) {
  const sent = n.sentiment === "บวก" ? "pos" : n.sentiment === "ลบ" ? "neg" : "";
  const main = esc(n.title_th || n.title);
  const en = n.title_th ? `<div class="en">ต้นฉบับ: ${esc(n.title)}</div>` : "";
  const mt = n.title_th ? ` · ${tip("machine_tr")}` : "";
  const old = n.stale ? ' · <span class="warn">ข่าวเก่า (เกิน 7 วัน)</span>' : "";
  const multi = n.n_sources > 1 ? ` · รายงานโดย ${n.n_sources} แหล่ง` : "";
  const price = chg != null ? ` · ราคาวันล่าสุดของหุ้นนี้ <span class="${cls(chg)}">${pct(chg)}</span>` : "";
  const link = n.link && n.link !== "#" ? `<a href="${esc(n.link)}" target="_blank" rel="noopener">อ่านต้นฉบับ ↗</a>` : "";
  const tk = showTicker ? `<span class="chip tk">${esc(ticker)}</span>` : "";
  return `<div class="news" data-t="${esc(ticker)}">${tk}<span class="chip">${esc(n.category)}</span><span class="chip ${sent}">${esc(n.sentiment)}</span>
    <div class="t">${main}</div>${en}
    <div class="small mut">${esc(n.source)} · ${ago(n.age_hours)}${multi}${old}${price}${mt} · ${link}</div></div>`;
}
const allNews = () => holdings().flatMap((h) => h.news.map((n) => ({ n, h }))).sort((a, b) => b.n.score - a.n.score);

/* ---------- หน้าแรก ---------- */
function pageIndex() {
  const t = D.totals, hs = holdings();
  const kpi = `<div class="grid">
    <div class="card kpi"><span class="mut small">มูลค่าพอร์ตหุ้นรายตัว</span><b>${money(t.value)}</b><span class="mut small">≈ ฿${num((t.value || 0) * (D.fx || 0), 0)}</span></div>
    <div class="card kpi"><span class="mut small">${tip("pl")}</span><b class="${cls(t.pl)}">${money(t.pl)}</b><span class="${cls(t.pl)} small">${pct(t.pl_pct)}</span></div></div>`;
  const todo = D.top_things.map((a, i) => `<div class="todo"><b>${i + 1}. ${esc(a.ticker)} · ${esc(a.kind)}</b><br>${esc(a.text)}
    ${a.link ? ` <a href="${esc(a.link)}" target="_blank" rel="noopener">ต้นฉบับ ↗</a>` : ""}
    <div class="small mut">ทำไมน่าดู: ${esc(a.why)}</div></div>`).join("") || '<div class="card mut">คืนนี้ยังไม่มีเรื่องเด่นตามเกณฑ์ของระบบ</div>';
  const say = D.portfolio_lines.map((x) => `<li>${esc(x)}</li>`).join("");
  const cards = hs.map((h) => `<a class="card" href="stock.html?t=${esc(h.ticker)}">
    <div class="row"><b>${esc(h.ticker)}</b><span class="${cls(h.change_pct)}">${pct(h.change_pct)}</span></div>
    <div class="row small mut"><span>${esc(h.name)}</span><span>${money(h.price)}</span></div>
    <div class="small" style="margin-top:6px">${esc(h.line)}</div></a>`).join("");
  const latest = allNews().filter((x) => !x.n.stale).slice(0, 6)
    .map(({ n, h }) => newsItem(n, h.ticker, h.change_pct)).join("") || '<div class="mut">ไม่พบข่าวที่เกี่ยวข้องโดยตรง</div>';
  chrome("index.html", `<div class="hello">${esc(D.greeting)}</div>
    <h2>คืนนี้ดู 3 เรื่องนี้ก่อนเลย</h2>${todo}
    <h2>Bro ขอพูดเรื่องพอร์ตนายหน่อย</h2>
    <div class="card"><ul style="margin:0;padding-left:18px">${say}</ul>
      <div class="small mut" style="margin-top:8px">คำนวณจากสัดส่วนจริงของพอร์ต ไม่ใช่คำแนะนำซื้อ/ขายนะ ตัดสินใจเองเสมอ</div></div>
    <h2>ภาพรวม</h2>${kpi}
    <h2>หุ้นของนาย (กดดูรายละเอียด)</h2><div class="grid">${cards}</div>
    <h2>ข่าวเด่นที่เกี่ยวกับหุ้นนาย</h2>${latest}<p><a href="news.html">ดูข่าวทั้งหมด →</a></p>`);
}

/* ---------- หน้าพอร์ต (แก้ตัวเลขเองได้ เก็บใน localStorage) ---------- */
function pagePortfolio() {
  const KEY = "stockbro_pf_v1";
  const rows0 = holdings();
  let S = {};
  try { S = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { /* ใช้ค่าเริ่มต้น */ }
  const est = rows0.some((h) => h.shares_estimated);
  chrome("portfolio.html", `<h1>พอร์ตของฉัน</h1>
    <p class="mut">แก้ต้นทุนและจำนวนหุ้นได้เลย ระบบคำนวณกำไร/ขาดทุนและสัดส่วนใหม่ทันที ข้อมูลที่แก้เก็บในเบราว์เซอร์เครื่องนี้เท่านั้น (ยังไม่ส่งไปไหน จนกว่าจะทำระบบล็อกอิน)
    ตอนนี้เป็นพอร์ตตัวอย่าง (ตัวเลขสมมติ) ${est ? '<span class="warn">จำนวนหุ้นบางตัวเป็นค่าประมาณ</span>' : ""}</p>
    <div class="tablewrap"><table id="pf"><thead><tr><th>หุ้น</th><th>ราคา</th><th>ต้นทุนรวม ($)</th><th>จำนวนหุ้น</th><th>มูลค่า</th>
    <th>${tip("pl")}</th><th>${tip("weight")}</th></tr></thead><tbody></tbody><tfoot></tfoot></table></div>
    <p><button id="reset">คืนค่าเดิม</button></p><div class="say" id="warn"></div>`);
  function draw() {
    const rows = rows0.map((h) => {
      const s = S[h.ticker] || {};
      const cost = s.cost ?? h.cost, sh = s.shares ?? h.shares;
      return { h, cost, sh, val: sh * h.price };
    });
    const tot = rows.reduce((a, r) => a + r.val, 0);
    let tc = 0, html = "";
    rows.forEach((r) => {
      const pl = r.val - r.cost, pp = r.cost ? (pl / r.cost) * 100 : 0;
      tc += r.cost;
      html += `<tr><td><a href="stock.html?t=${esc(r.h.ticker)}"><b>${esc(r.h.ticker)}</b></a></td><td>${num(r.h.price)}</td>
        <td><input data-t="${esc(r.h.ticker)}" data-k="cost" value="${+r.cost.toFixed(2)}"></td>
        <td><input data-t="${esc(r.h.ticker)}" data-k="shares" value="${+r.sh.toFixed(6)}"></td><td>${num(r.val)}</td>
        <td class="${cls(pl)}">${pl >= 0 ? "+" : ""}${num(pl)} (${pct(pp)})</td><td>${tot ? num((r.val / tot) * 100, 1) : 0}%</td></tr>`;
    });
    $("#pf tbody").innerHTML = html;
    const pl = tot - tc;
    $("#pf tfoot").innerHTML = `<tr><td><b>รวม</b></td><td></td><td>${num(tc)}</td><td></td><td>${num(tot)}</td><td class="${cls(pl)}">${pl >= 0 ? "+" : ""}${num(pl)}</td><td>100%</td></tr>`;
    const top = rows.slice().sort((a, b) => b.val - a.val)[0];
    $("#warn").textContent = top && tot ? `Bro ${top.h.ticker} คือตัวใหญ่สุด ${num((top.val / tot) * 100, 0)}% ถ้ามันตก 10% พอร์ตจะลดราว ${num((top.val / tot) * 10, 1)}%` : "";
    document.querySelectorAll("#pf input").forEach((i) => {
      i.onchange = () => {
        const v = parseFloat(i.value);
        if (isNaN(v) || v < 0) return draw();
        S[i.dataset.t] = Object.assign(S[i.dataset.t] || {}, { [i.dataset.k]: v });
        try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { /* เก็บไม่ได้ก็ใช้ชั่วคราว */ }
        draw();
      };
    });
  }
  $("#reset").onclick = () => { S = {}; try { localStorage.removeItem(KEY); } catch (e) { /* ignore */ } draw(); };
  draw();
}

/* ---------- หน้าข่าว ---------- */
function pageNews() {
  const hs = holdings();
  const dropped = hs.reduce((a, h) => a + (h.news_dropped || 0), 0);
  const btns = '<button class="on" data-f="">ทั้งหมด</button> ' + hs.map((h) => `<button data-f="${esc(h.ticker)}">${esc(h.ticker)}</button>`).join(" ");
  const list = allNews().map(({ n, h }) => newsItem(n, h.ticker, h.change_pct)).join("") || '<div class="mut">ไม่พบข่าวที่เกี่ยวข้อง</div>';
  const fil = hs.flatMap((h) => h.filings.map((f) => ({ f, t: h.ticker }))).sort((a, b) => (a.f.date < b.f.date ? 1 : -1)).slice(0, 12)
    .map(({ f, t }) => `<div class="news"><span class="chip tk">${esc(t)}</span><span class="chip">${f.form === "8-K" ? tip("8k") : esc(f.form)}</span>
      ยื่นเมื่อ ${esc(f.date)} · <a href="${esc(f.link)}" target="_blank" rel="noopener">เปิดเอกสาร SEC ↗</a></div>`).join("")
    || '<div class="mut small">ยังไม่มีข้อมูลเอกสาร SEC (ต้องตั้งตัวแปร STOCKBRO_SEC_UA ก่อนรัน ดู README)</div>';
  chrome("news.html", `<h1>ข่าวที่เกี่ยวกับหุ้นของนาย</h1>
    <p class="mut">เรียงตามคะแนนความสำคัญ (ประเภทข่าว × ความสด × จำนวนแหล่งที่รายงาน) คัดเฉพาะพาดหัวที่เอ่ยชื่อบริษัท/ticker นั้นจริง ตัดข่าวที่ไม่เกี่ยวข้องออกแล้ว ${dropped} เรื่อง ·
    ป้าย บวก/ลบ มาจากคำในพาดหัวเท่านั้น ไม่ใช่การวิเคราะห์ · ข่าวนี้ราคาสะท้อนไปแล้วหรือยัง (${tip("priced_in")}) ให้ดูเลขราคาวันล่าสุดข้างข่าวประกอบ</p>
    <p id="fl">${btns}</p><div id="nl">${list}</div><h2>เอกสารทางการ SEC (แหล่งที่เชื่อได้ที่สุด)</h2>${fil}`);
  document.querySelectorAll("#fl button").forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll("#fl button").forEach((x) => x.classList.remove("on"));
      b.classList.add("on");
      document.querySelectorAll("#nl .news").forEach((n) => { n.style.display = !b.dataset.f || n.dataset.t === b.dataset.f ? "" : "none"; });
    };
  });
}

/* ---------- หน้าตลาด ---------- */
function calendarHtml() {
  const c = D.calendar || { events: [], missing_earnings: [] };
  const rows = c.events.map((e) => {
    const when = e.days_until === 0 ? "วันนี้" : e.days_until === 1 ? "พรุ่งนี้" : `อีก ${e.days_until} วัน`;
    const src = e.source ? ` <a href="${esc(e.source)}" target="_blank" rel="noopener">แหล่งทางการ ↗</a>` : "";
    return `<div class="card"><b>${esc(e.date)} · ${when}</b> ${e.time_th ? `<span class="mut small">· ${esc(e.time_th)}</span>` : ""}
      <div>${esc(e.title)} ${GLOSS[e.type] ? tip(e.type) : ""}${src}</div></div>`;
  }).join("") || '<div class="card mut">ยังประเมินไม่ได้ — ไม่มีเหตุการณ์ใน 45 วันข้างหน้าในไฟล์ปฏิทิน</div>';
  const miss = c.missing_earnings.length
    ? `<div class="card mut small">วันประกาศงบของ ${esc(c.missing_earnings.join(", "))} ยังไม่ระบุ (ระบบไม่เดาวันที่) ใส่เองได้โดยเพิ่ม <code>"next_earnings": "YYYY-MM-DD"</code> ในไฟล์ config ของหุ้นตัวนั้น</div>` : "";
  return rows + miss + '<div class="mut small">วันเวลาเป็นตามตารางที่แหล่งทางการประกาศ อาจเลื่อน ตรวจที่ลิงก์ก่อนใช้ตัดสินใจ</div>';
}
function pageMarket() {
  const names = { "^GSPC": "S&P 500", "^IXIC": "Nasdaq", "^VIX": "VIX (ความกลัวของตลาด)", "THB=X": "USD/THB" };
  const m = D.market || {};
  const cards = Object.entries(m).map(([k, v]) => `<div class="card"><span class="mut small">${esc(names[k] || k)}</span>
    <b style="display:block;font-size:22px">${num(v.price)}</b><span class="${cls(v.change_pct)}">${pct(v.change_pct)}</span>
    <span class="mut small">ณ ${esc(v.date)}</span></div>`).join("") || '<div class="card mut">ยังประเมินไม่ได้ (ดึงข้อมูลตลาดไม่สำเร็จ)</div>';
  let vix = "";
  if (m["^VIX"]) {
    const v = m["^VIX"].price;
    const lvl = v < 15 ? "ค่อนข้างนิ่ง" : v < 20 ? "ปกติถึงเริ่มกังวล" : v < 30 ? "ตลาดกังวลพอสมควร" : "ตลาดตื่นตระหนก";
    vix = `<div class="say">VIX อยู่ที่ ${num(v, 1)} → ${lvl} (เกณฑ์โดยประมาณ ดู ${tip("vix")})</div>`;
  }
  chrome("market.html", `<h1>ภาพรวมตลาด</h1><div class="grid">${cards}</div>${vix}
    <h2>ปฏิทินเหตุการณ์ (FOMC, CPI, งบ)</h2>${calendarHtml()}`);
}

/* ---------- หน้าหุ้นรายตัว ---------- */
function chartSvg(series, lines) {
  if (!series || series.length < 2) return '<div class="mut">ไม่มีข้อมูลกราฟ</div>';
  const cs = series.map((p) => p[1]);
  const vals = cs.concat(lines.filter((l) => l.value).map((l) => l.value));
  const lo = Math.min(...vals), hi = Math.max(...vals);
  const W = 640, H = 230, P = 36;
  const sx = (i) => P + (i * (W - P - 8)) / (cs.length - 1);
  const sy = (v) => H - 20 - ((v - lo) / (hi - lo || 1)) * (H - 40);
  const pts = cs.map((v, i) => `${sx(i).toFixed(1)},${sy(v).toFixed(1)}`).join(" ");
  const ls = lines.filter((l) => l.value).map((l) =>
    `<line x1="${P}" x2="${W - 8}" y1="${sy(l.value).toFixed(1)}" y2="${sy(l.value).toFixed(1)}" stroke="${l.color}" stroke-dasharray="4 4" opacity=".8"/>
     <text x="${W - 10}" y="${(sy(l.value) - 3).toFixed(1)}" text-anchor="end" style="fill:${l.color}">${esc(l.name)} ${num(l.value)}</text>`).join("");
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="กราฟราคา ${cs.length} วัน">
    <polyline points="${pts}" fill="none" stroke="#7c9cff" stroke-width="2"/>${ls}
    <text x="${P}" y="${H - 4}">${esc(series[0][0])}</text><text x="${W - 8}" y="${H - 4}" text-anchor="end">${esc(series[series.length - 1][0])}</text></svg>`;
}
function pageStock() {
  const t = new URLSearchParams(location.search).get("t");
  const h = D.holdings.find((x) => x.ticker === t);
  if (!h) return chrome("", `<p><a href="index.html">← กลับ</a></p><div class="card mut">ไม่พบหุ้นตัวนี้ในพอร์ต</div>`);
  if (!h.ok) return chrome("", `<p><a href="index.html">← กลับ</a></p><h1>${esc(h.ticker)}</h1><div class="card mut">${esc(h.line)}</div>`);
  const p = h.plan, bt = h.backtest;
  const chips = (arr) => arr.map((x) => `<span class="chip">${esc(x.name)} ${num(x.level)} (${pct(x.dist_pct)})</span>`).join("");
  const stop = p.stop && p.rr ? `${tip("stop")} ${num(p.stop)} · ${tip("rr")} ${num(p.rr, 1)}` : "";
  let bts = "ยังทดสอบไม่ได้ (ข้อมูลไม่พอ)";
  if (bt.ok) {
    const r = (v) => (v == null ? "–" : Math.round(v * 100) + "%");
    bts = `ช่วง ${esc(bt.period.from)} ถึง ${esc(bt.period.to)}: ราคาแตะแนวรับ S1 ${bt.touches} ครั้ง เด้งขึ้น 2% ก่อนหลุด 2% ใน 5 วัน ${r(bt.bounce_rate)}
      (ระดับสุ่มระยะเท่ากัน ${r(bt.baseline_bounce_rate)}) → <b>${esc(bt.verdict)}</b>`;
  }
  const news = h.news.map((n) => newsItem(n, h.ticker, h.change_pct, false)).join("") || '<div class="mut">ไม่พบข่าวที่เกี่ยวข้องโดยตรง</div>';
  const fil = h.filings.slice(0, 5).map((f) => `<div class="small">${esc(f.form)} · ${esc(f.date)} · <a href="${esc(f.link)}" target="_blank" rel="noopener">เปิด ↗</a></div>`).join("")
    || '<div class="small mut">ไม่มีข้อมูลเอกสาร SEC</div>';
  chrome("", `<p><a href="index.html">← กลับ</a></p>
    <h1>${esc(h.ticker)} <span class="mut" style="font-size:15px">${esc(h.name)}</span></h1>
    <div class="grid"><div class="card kpi"><span class="mut small">ราคาปิดล่าสุด (${esc(h.price_date)})</span><b>${money(h.price)}</b><span class="${cls(h.change_pct)}">${pct(h.change_pct)}</span></div>
    <div class="card kpi"><span class="mut small">ของนาย</span><b class="${cls(h.pl)}">${pct(h.pl_pct)}</b>
      <span class="small mut">${tip("weight")} ${h.weight != null ? Math.round(h.weight) + "%" : "–"} · ต้นทุน ${money(h.cost)}</span></div></div>
    <h2>Bro สรุปให้</h2><div class="say">${esc(h.trend_text)}</div><div class="say">${esc(h.level_text)}</div>
    <h2>กราฟ ${h.series.length} วัน + ระดับสำคัญ</h2><div class="card">${chartSvg(h.series, h.chart_lines)}</div>
    <h2>${tip("support")} (ใต้ราคา)</h2><div class="lv">${chips(h.supports)}</div>
    <h2>${tip("resistance")} (เหนือราคา)</h2><div class="lv">${chips(h.resistances)}</div>
    <div class="small mut" style="margin-top:8px">${stop} · ${tip("ma")}: MA50 ${num(h.ma.MA50)} / MA200 ${num(h.ma.MA200)} · ${tip("hi52")}: ${num(h.lo52)} – ${num(h.hi52)}</div>
    <h2>${tip("backtest")}: แนวรับของหุ้นตัวนี้แม่นไหม</h2><div class="card small">${bts}</div>
    <h2>ข่าวของ ${esc(h.ticker)}</h2>${news}<h2>เอกสาร SEC</h2>${fil}`);
  document.title = `${h.ticker} · StockBro`;
}

/* ---------- หน้าศัพท์ ---------- */
function pageGlossary() {
  const items = D.glossary.map((g) => `<div class="card" id="${esc(g.key)}" style="margin-bottom:10px"><b>${esc(g.name)}</b>
    <div>${esc(g.short)}</div><div class="small mut">${esc(g.long)}</div></div>`).join("");
  chrome("glossary.html", `<h1>ศัพท์ที่เจอบนเว็บนี้</h1>${items}`);
  if (location.hash) { const el = document.getElementById(location.hash.slice(1)); if (el) el.scrollIntoView(); }
}

/* ---------- เริ่มทำงาน ---------- */
const PAGES = { index: pageIndex, portfolio: pagePortfolio, news: pageNews, market: pageMarket, stock: pageStock, glossary: pageGlossary };
document.addEventListener("DOMContentLoaded", async () => {
  try {
    D = await loadData();
    GLOSS = Object.fromEntries(D.glossary.map((g) => [g.key, g]));
    PAGES[document.body.dataset.page]();
  } catch (e) {
    fail(e);
  }
});
