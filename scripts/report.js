/* Chart code for the session-patterns report. Plain SVG, no libraries. */
(function () {
"use strict";
const D = DATA;
const NS = "http://www.w3.org/2000/svg";
const $ = (id) => document.getElementById(id);
const tip = $("tip");
const fmt = (n, d = 0) => Number(n).toLocaleString(undefined, { maximumFractionDigits: d, minimumFractionDigits: d });
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const shortDate = (iso) => new Date(iso + "T12:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
const hhmm = (iso) => new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", hour12: false });

function el(tag, attrs = {}, parent) {
  const n = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (parent) parent.appendChild(n);
  return n;
}
function svg(container, w, h) {
  const s = el("svg", { viewBox: `0 0 ${w} ${h}`, width: "100%", role: "img" });
  s.style.minWidth = Math.min(w, 520) + "px";
  $(container).appendChild(s);
  return s;
}
function text(s, x, y, str, attrs = {}) {
  const t = el("text", { x, y, ...attrs }, s);
  t.textContent = str;
  return t;
}
function showTip(evt, html) {
  tip.innerHTML = html;
  tip.style.display = "block";
  const r = tip.getBoundingClientRect();
  let x = evt.clientX + 14, y = evt.clientY + 14;
  if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - 14;
  if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - 14;
  tip.style.left = x + "px";
  tip.style.top = y + "px";
}
function hideTip() { tip.style.display = "none"; }
function hover(node, html) {
  node.setAttribute("tabindex", "0");
  node.addEventListener("mousemove", (e) => showTip(e, html));
  node.addEventListener("mouseleave", hideTip);
  node.addEventListener("focus", () => {
    const r = node.getBoundingClientRect();
    showTip({ clientX: r.right, clientY: r.top }, html);
  });
  node.addEventListener("blur", hideTip);
}
function niceMax(v) {
  // Smallest 4 x step >= v where step is 1, 2 or 5 x 10^k (integer steps below 1).
  if (v <= 0) return 4;
  const raw = v / 4, p = Math.pow(10, Math.floor(Math.log10(raw)));
  for (const m of [1, 2, 5, 10]) { const st = Math.max(1, m * p); if (st * 4 >= v) return st * 4; }
  return 40 * p;
}
// Bar with 4px rounded data-end, square at the baseline.
function barPath(x, y, w, h) {
  if (h <= 0) return "";
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}
function legend(id, items) {
  $(id).innerHTML = items.map(([label, color, kind]) =>
    `<span><i class="${kind || ""}" style="background:var(${color})"></i>${esc(label)}</span>`).join("");
}
function table(id, cols, rows) {
  $(id).innerHTML = `<table><thead><tr>${cols.map((c) => `<th>${esc(c)}</th>`).join("")}</tr></thead><tbody>${
    rows.map((r) => `<tr>${r.map((v) => `<td>${esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
// Y grid + ticks; returns y(v) scale.
function yAxis(s, m, W, H, max, fmtTick = (v) => fmt(v)) {
  const y = (v) => m.t + (H - m.t - m.b) * (1 - v / max);
  for (let i = 0; i <= 4; i++) {
    const v = (max / 4) * i, yy = y(v);
    el("line", { x1: m.l, x2: W - m.r, y1: yy, y2: yy, class: i ? "grid" : "axis" }, s);
    text(s, m.l - 6, yy + 4, fmtTick(v), { "text-anchor": "end" });
  }
  return y;
}

// ---- Header, tiles, findings ------------------------------------------------
const T = D.totals, TH = D.thresholds;
const C = D.coverage || { history_days: 0, no_data_days: 0 };
const cov = [C.history_days ? `${C.history_days} days from daily history` : "", C.no_data_days ? `${C.no_data_days} days with no data` : ""].filter(Boolean).join(" · ");
$("subtitle").textContent = `Last ${D.days} days (since ${shortDate(D.since)})${cov ? " · " + cov : ""} · generated ${D.generated.replace("T", " ")}`;
$("footer").textContent = `Thresholds: break ≥ ${TH.break_gap} min · light nudge ${TH.light} min · firm ${TH.firm} min · cool-down ${TH.cooldown} min · working hours ${TH.work_start}:00–${TH.work_end}:00 weekdays. Raw logs last as long as cleanupPeriodDays (30 by default); older days come from the numbers-only daily history (--save-daily). Timeline, friction-by-hour, prompt-length and sensitivity charts use raw logs only.`;
const tiles = [
  ["Active hours", fmt(T.active_h, 1), `${T.active_days} active days`],
  ["Days with no activity", T.zero_days, "see 7. Recovery"],
  ["Outside working hours", fmt(T.late_share * 100) + "%", "of prompts"],
  ["Longest stretch", T.longest_stretch + " min", `median ${T.median_stretch} min`],
  ["Interruptions", T.interrupts, `${fmt(T.tool_errors)} failed tool calls`],
  ["Replayed nudges", T.nudges, `${fmt(T.nudges / Math.max(T.active_days, 1), 2)} per active day`],
];
$("tiles").innerHTML = tiles.map(([l, v, s]) =>
  `<div class="tile"><div class="label">${esc(l)}</div><div class="value">${esc(v)}</div><div class="sub">${esc(s)}</div></div>`).join("");

const findings = [];
const busiest = [...D.daily].sort((a, b) => b.active_h - a.active_h)[0];
if (busiest && busiest.active_h) findings.push(`Busiest day: ${busiest.weekday} ${shortDate(busiest.date)} with ${fmt(busiest.active_h, 1)} active hours (${busiest.span_start}–${busiest.span_end}).`);
findings.push(T.stretches_over_light
  ? `${T.stretches_over_light} stretch${T.stretches_over_light === 1 ? "" : "es"} passed ${TH.light} min, ${T.stretches_over_firm} passed ${TH.firm} min.`
  : `No stretch reached ${TH.light} min: by time alone, the watcher would rarely speak up.`);
if (T.prompt_only_longest < T.longest_stretch)
  findings.push(`Counting only gaps between your prompts, the longest stretch would be ${T.prompt_only_longest} min instead of ${T.longest_stretch}: Claude working for 10+ minutes looks like a break. The watcher's activity hooks now count both sides.`);
const weekendPrompts = D.heatmap.slice(5).flat().reduce((a, b) => a + b, 0);
if (weekendPrompts) findings.push(`${weekendPrompts} prompt${weekendPrompts === 1 ? " was" : "s were"} sent on weekends.`);
$("findings").innerHTML = findings.map((f) => `<li>${esc(f)}</li>`).join("");

// ---- 1. Daily active hours ----------------------------------------------------
(function () {
  const W = 1040, H = 240, m = { t: 12, r: 12, b: 34, l: 40 };
  const s = svg("c-daily", W, H);
  const n = D.daily.length, band = (W - m.l - m.r) / n, bw = Math.min(24, band - 2);
  const max = niceMax(Math.max(...D.daily.map((d) => d.active_h), 1));
  const y = yAxis(s, m, W, H, max, (v) => v + "h");
  const avg = D.daily.map((d, i) => {
    const w = D.daily.slice(Math.max(0, i - 6), i + 1).filter((x) => !x.no_data);
    return w.length ? w.reduce((a, b) => a + b.active_h, 0) / w.length : null;
  });
  D.daily.forEach((d, i) => {
    const x = m.l + i * band + (band - bw) / 2;
    if (d.no_data) el("rect", { x, y: y(0) - 3, width: bw, height: 3, rx: 1.5, fill: "none", stroke: "var(--grid)", "stroke-dasharray": "2 2" }, s);
    else if (d.active_h) el("path", { d: barPath(x, y(d.active_h), bw, y(0) - y(d.active_h)), fill: "var(--series-1)" }, s);
    else el("rect", { x, y: y(0) - 3, width: bw, height: 3, rx: 1.5, fill: "var(--grid)" }, s);
    if (i % Math.ceil(n / 15) === 0 || i === n - 1) text(s, x + bw / 2, H - m.b + 16, shortDate(d.date), { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${d.weekday} ${shortDate(d.date)}</b><br>${d.active_h ? `${fmt(d.active_h, 1)} active hours<br><span class="muted">${d.span_start}–${d.span_end} · ${d.prompts} prompts · ${d.sessions} sessions</span>` : d.no_data ? "No data (before raw logs and daily history)" : "No activity"}<br><span class="muted">7-day avg ${avg[i] == null ? "–" : fmt(avg[i], 1) + "h"}</span>`);
  });
  const pts = avg.map((v, i) => v == null ? null : `${m.l + i * band + band / 2},${y(v)}`).filter(Boolean).join(" ");
  el("polyline", { points: pts, fill: "none", stroke: "var(--text-secondary)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round", "pointer-events": "none" }, s);
  const last = avg.length - 1;
  text(s, W - m.r, m.t + 4, `7-day avg now ${fmt(avg[last] || 0, 1)}h`, { "text-anchor": "end", class: "lbl" });
  table("t-daily", ["Date", "Active h", "Span", "Prompts", "Late prompts", "Sessions", "Max parallel", "Interrupts", "Failed tools", "Lines edited", "Nudges"],
    D.daily.map((d) => d.no_data ? [`${d.weekday} ${d.date}`, "no data", "", "", "", "", "", "", "", "", ""] : [`${d.weekday} ${d.date}`, fmt(d.active_h, 1), d.span_start ? `${d.span_start}–${d.span_end}` : "–", d.prompts, d.late_prompts, d.sessions, d.max_parallel, d.interrupts, d.tool_errors, fmt(d.lines_edited), d.nudges]));
})();

// ---- 1b. Heatmap weekday x hour ---------------------------------------------
(function () {
  const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const W = 1040, cell = 38, gap = 2, m = { t: 6, l: 40, b: 26 };
  const H = m.t + 7 * cell + m.b;
  const s = svg("c-heat", W, H);
  const cw = (W - m.l - 8) / 24;
  const max = Math.max(...D.heatmap.flat(), 1);
  const step = (v) => (v === 0 ? 0 : Math.min(7, 1 + Math.floor((v / max) * 6.999)));
  D.heatmap.forEach((row, wd) => {
    text(s, m.l - 8, m.t + wd * cell + cell / 2 + 4, days[wd], { "text-anchor": "end" });
    row.forEach((v, h) => {
      const x = m.l + h * cw, yy = m.t + wd * cell;
      const late = wd >= 5 || h < TH.work_start || h >= TH.work_end;
      const r = el("rect", { x: x + gap / 2, y: yy + gap / 2, width: cw - gap, height: cell - gap, rx: 3,
        fill: `var(--seq-${step(v)})` }, s);
      if (late) { r.setAttribute("stroke", "var(--axis)"); r.setAttribute("stroke-width", 1); }
      hover(r, `<b>${days[wd]} ${String(h).padStart(2, "0")}:00</b><br>${v} prompts${late ? '<br><span class="muted">outside working hours</span>' : ""}`);
    });
  });
  for (let h = 0; h < 24; h += 3) text(s, m.l + h * cw + cw / 2, H - 8, String(h).padStart(2, "0"), { "text-anchor": "middle" });
})();

// ---- 2. Day timeline --------------------------------------------------------
(function () {
  const top = D.projects.slice(0, 3).map((p) => p[0]);
  const colorOf = (p) => { const i = top.indexOf(p); return i >= 0 ? `var(--series-${i + 1})` : "var(--text-muted)"; };
  legend("l-timeline", [...top.map((p, i) => [p, `--series-${i + 1}`]),
    ...(D.projects.length > 3 ? [["Other projects", "--text-muted"]] : []),
    ["Replayed nudge", "--critical"]]);
  const days = D.daily.filter((d) => d.prompts && (d.source || "raw") === "raw").map((d) => d.date);
  if (!days.length) return;
  const segs = D.segments.map((g) => ({ ...g, s: new Date(g.start), e: new Date(g.end) }));
  const hourOf = (dt) => dt.getHours() + dt.getMinutes() / 60;
  let h0 = 24, h1 = 0;
  segs.forEach((g) => { h0 = Math.min(h0, Math.floor(hourOf(g.s))); h1 = Math.max(h1, Math.ceil(hourOf(g.e))); });
  h0 = Math.max(0, Math.min(h0, TH.work_start)); h1 = Math.min(24, Math.max(h1, TH.work_end));
  const row = 18, m = { t: 8, r: 12, b: 26, l: 70 }, W = 1040, H = m.t + days.length * row + m.b;
  const s = svg("c-timeline", W, H);
  const x = (h) => m.l + (W - m.l - m.r) * (h - h0) / (h1 - h0);
  // working-hours band
  el("rect", { x: x(TH.work_start), y: m.t, width: x(TH.work_end) - x(TH.work_start), height: days.length * row, fill: "var(--series-1-wash)" }, s);
  for (let h = h0; h <= h1; h++) {
    el("line", { x1: x(h), x2: x(h), y1: m.t, y2: m.t + days.length * row, class: "grid" }, s);
    if ((h - h0) % 2 === 0) text(s, x(h), H - 8, String(h).padStart(2, "0") + ":00", { "text-anchor": "middle" });
  }
  const rowOf = Object.fromEntries(days.map((d, i) => [d, i]));
  const localDate = (dt) => `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
  days.forEach((d, i) => text(s, m.l - 8, m.t + i * row + row / 2 + 4, `${new Date(d + "T12:00").toLocaleDateString(undefined, { weekday: "short" })} ${shortDate(d)}`, { "text-anchor": "end" }));
  segs.forEach((g) => {
    const r = rowOf[localDate(g.s)];
    if (r === undefined) return;
    const xs = x(hourOf(g.s)), xe = Math.max(xs + 3, x(Math.min(h1, hourOf(g.e) + (localDate(g.e) !== localDate(g.s) ? 24 : 0))));
    const rect = el("rect", { x: xs, y: m.t + r * row + 4, width: xe - xs, height: row - 8, rx: 3, fill: colorOf(g.project), "fill-opacity": 0.85 }, s);
    const mins = Math.round((g.e - g.s) / 60000);
    hover(rect, `<b>${esc(g.project)}</b><br>${hhmm(g.start)}–${hhmm(g.end)} · ${mins} min<br><span class="muted">session ${esc(g.session)}</span>`);
  });
  D.nudges.forEach((n) => {
    const dt = new Date(n.ts), r = rowOf[localDate(dt)];
    if (r === undefined) return;
    const cx = x(hourOf(dt)), cy = m.t + r * row + row / 2;
    const c = el("circle", { cx, cy, r: 5, fill: "var(--critical)", stroke: "var(--surface-1)", "stroke-width": 2 }, s);
    hover(c, `<b>${n.kind} nudge</b> at ${hhmm(n.ts)}<br>stretch ${n.stretch_min} min${n.signals.length ? "<br>" + esc(n.signals.join(", ")) : ""}`);
  });
})();

// ---- 2b. Stretch length histogram --------------------------------------------
(function () {
  const bins = [[5, 15], [15, 30], [30, 45], [45, 60], [60, 90], [90, 120], [120, 150], [150, 9999]];
  const counts = bins.map(([a, b]) => D.stretches.filter((s) => s.minutes >= a && s.minutes < b).length);
  const W = 520, H = 220, m = { t: 16, r: 8, b: 34, l: 36 };
  const s = svg("c-stretch", W, H);
  const max = niceMax(Math.max(...counts, 1));
  const y = yAxis(s, m, W, H, max);
  const band = (W - m.l - m.r) / bins.length, bw = Math.min(24, band - 4);
  bins.forEach(([a, b], i) => {
    const x = m.l + i * band + (band - bw) / 2;
    const over = a >= TH.light;
    el("path", { d: barPath(x, y(counts[i]), bw, y(0) - y(counts[i])), fill: over ? "var(--series-2)" : "var(--series-1)" }, s);
    if (counts[i]) text(s, x + bw / 2, y(counts[i]) - 4, counts[i], { "text-anchor": "middle", class: "lbl" });
    text(s, x + bw / 2, H - m.b + 16, b > 999 ? `${a}+ min` : `${a}–${b}`, { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${b > 999 ? a + "+ min" : a + "–" + b + " min"}</b><br>${counts[i]} stretches${over ? '<br><span class="muted">at or past the light-nudge threshold</span>' : ""}`);
  });
})();

// ---- 2c. Parallel sessions --------------------------------------------------
(function () {
  const dist = D.parallel_dist;
  const total = dist.reduce((a, [, n]) => a + n, 0) || 1;
  const W = 520, H = 220, m = { t: 16, r: 8, b: 34, l: 36 };
  const s = svg("c-parallel", W, H);
  const max = niceMax(Math.max(...dist.map(([, n]) => n), 1));
  const y = yAxis(s, m, W, H, max);
  const band = (W - m.l - m.r) / Math.max(dist.length, 4), bw = Math.min(24, band - 4);
  dist.forEach(([k, n], i) => {
    const x = m.l + i * band + (band - bw) / 2;
    el("path", { d: barPath(x, y(n), bw, y(0) - y(n)), fill: k >= 3 ? "var(--series-2)" : "var(--series-1)" }, s);
    text(s, x + bw / 2, y(n) - 4, `${fmt(n / total * 100)}%`, { "text-anchor": "middle", class: "lbl" });
    text(s, x + bw / 2, H - m.b + 16, k === 1 ? "1 session" : `${k} sessions`, { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${k} parallel</b><br>${n} prompts (${fmt(n / total * 100, 1)}%)`);
  });
})();

// Small multi-line chart on one axis (same unit).
function lines(id, xs, series, { W = 1040, H = 220, xLabel = (v) => v, unit = "", tipTitle = (i) => xs[i] } = {}) {
  const m = { t: 14, r: 90, b: 34, l: 40 };
  const s = svg(id, W, H);
  const max = niceMax(Math.max(1, ...series.flatMap((sr) => sr.values.filter((v) => v != null))));
  const y = yAxis(s, m, W, H, max);
  const x = (i) => m.l + (W - m.l - m.r) * (xs.length === 1 ? 0.5 : i / (xs.length - 1));
  xs.forEach((v, i) => { if (i % Math.ceil(xs.length / 12) === 0 || i === xs.length - 1) text(s, x(i), H - m.b + 16, xLabel(v), { "text-anchor": "middle" }); });
  const ends = series.map((sr) => { let li = sr.values.length - 1; while (li > 0 && sr.values[li] == null) li--; return sr.values[li] == null ? null : y(sr.values[li]); });
  const sorted = ends.filter((v) => v != null).sort((a, b) => a - b);
  const labelEnds = sorted.every((v, i) => i === 0 || v - sorted[i - 1] >= 13);
  series.forEach((sr) => {
    let d = "", pen = false;
    sr.values.forEach((v, i) => { if (v == null) { pen = false; return; } d += `${pen ? "L" : "M"}${x(i)},${y(v)}`; pen = true; });
    el("path", { d, fill: "none", stroke: `var(${sr.color})`, "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }, s);
    let li = sr.values.length - 1; while (li > 0 && sr.values[li] == null) li--;
    if (sr.values[li] != null) {
      el("circle", { cx: x(li), cy: y(sr.values[li]), r: 4, fill: `var(${sr.color})`, stroke: "var(--surface-1)", "stroke-width": 2 }, s);
      if (labelEnds) text(s, x(li) + 8, y(sr.values[li]) + 4, sr.label, { class: "lbl" });
    }
  });
  const cross = el("line", { y1: m.t, y2: H - m.b, class: "axis", opacity: 0 }, s);
  const step = (W - m.l - m.r) / Math.max(xs.length - 1, 1);
  xs.forEach((_, i) => {
    const hit = el("rect", { x: x(i) - step / 2, y: m.t, width: step, height: H - m.t - m.b, class: "hit" }, s);
    hit.addEventListener("mouseenter", () => { cross.setAttribute("x1", x(i)); cross.setAttribute("x2", x(i)); cross.setAttribute("opacity", 1); });
    hit.addEventListener("mouseleave", () => cross.setAttribute("opacity", 0));
    hover(hit, `<b>${tipTitle(i)}</b>` + series.map((sr) => `<br><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:var(${sr.color});margin-right:6px"></i>${esc(sr.label)}: ${sr.values[i] == null ? "–" : fmt(sr.values[i], 1) + unit}`).join(""));
  });
}

// ---- 3. Friction per day ------------------------------------------------------
(function () {
  const days = D.daily;
  const per10 = (d, k) => (d.prompts >= 3 ? (d[k] / d.prompts) * 10 : null);
  const series = [
    { label: "Interruptions", color: "--series-1", values: days.map((d) => per10(d, "interrupts")) },
    { label: "Short follow-ups", color: "--series-2", values: days.map((d) => per10(d, "short_followups")) },
    { label: "Failed tools", color: "--series-3", values: days.map((d) => per10(d, "tool_errors")) },
  ];
  legend("l-friction", series.map((s) => [s.label, s.color, "line"]));
  lines("c-friction", days.map((d) => d.date), series, { xLabel: shortDate, tipTitle: (i) => `${days[i].weekday} ${shortDate(days[i].date)} · ${days[i].prompts} prompts` });
})();

// ---- 3b. Friction by hour, prompt length by stretch position ----------------
(function () {
  const fh = D.friction_hour.filter((h) => h.prompts >= 5);
  const W = 520, H = 220, m = { t: 16, r: 8, b: 34, l: 36 };
  const s = svg("c-fhour", W, H);
  const vals = fh.map((h) => ((h.interrupts + h.short_followups) / h.prompts) * 10);
  const max = niceMax(Math.max(...vals, 1));
  const y = yAxis(s, m, W, H, max);
  const band = (W - m.l - m.r) / Math.max(fh.length, 1), bw = Math.min(24, band - 3);
  fh.forEach((h, i) => {
    const x = m.l + i * band + (band - bw) / 2;
    const late = h.hour < TH.work_start || h.hour >= TH.work_end;
    el("path", { d: barPath(x, y(vals[i]), bw, y(0) - y(vals[i])), fill: late ? "var(--series-2)" : "var(--series-1)" }, s);
    text(s, x + bw / 2, H - m.b + 16, String(h.hour).padStart(2, "0"), { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${String(h.hour).padStart(2, "0")}:00</b><br>${fmt(vals[i], 1)} per 10 prompts<br><span class="muted">${h.interrupts} interrupts · ${h.short_followups} short follow-ups · ${h.prompts} prompts</span>`);
  });

  const pl = D.prompt_len_by_pos;
  const s2 = svg("c-plen", W, H);
  const max2 = niceMax(Math.max(...pl.map((p) => p.median_chars), 1));
  const y2 = yAxis(s2, m, W, H, max2);
  const band2 = (W - m.l - m.r) / Math.max(pl.length, 1), bw2 = Math.min(24, band2 - 4);
  pl.forEach((p, i) => {
    const x = m.l + i * band2 + (band2 - bw2) / 2;
    el("path", { d: barPath(x, y2(p.median_chars), bw2, y2(0) - y2(p.median_chars)), fill: "var(--series-1)" }, s2);
    text(s2, x + bw2 / 2, y2(p.median_chars) - 4, p.median_chars, { "text-anchor": "middle", class: "lbl" });
    text(s2, x + bw2 / 2, H - m.b + 16, p.bucket, { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band2, y: m.t, width: band2, height: H - m.t - m.b, class: "hit" }, s2);
    hover(hit, `<b>${p.bucket} into a stretch</b><br>median ${p.median_chars} characters<br><span class="muted">${p.n} prompts${p.n < 20 ? " · small sample" : ""}</span>`);
  });
})();

// ---- 4. Review load -----------------------------------------------------------
(function () {
  const W = 1040, H = 200, m = { t: 12, r: 12, b: 34, l: 48 };
  const s = svg("c-lines", W, H);
  const n = D.daily.length, band = (W - m.l - m.r) / n, bw = Math.min(24, band - 2);
  const max = niceMax(Math.max(...D.daily.map((d) => d.lines_edited), 1));
  const y = yAxis(s, m, W, H, max, (v) => (v >= 1000 ? fmt(v / 1000, v % 1000 ? 1 : 0) + "K" : fmt(v)));
  D.daily.forEach((d, i) => {
    const x = m.l + i * band + (band - bw) / 2;
    if (d.lines_edited) el("path", { d: barPath(x, y(d.lines_edited), bw, y(0) - y(d.lines_edited)), fill: "var(--series-1)" }, s);
    if (i % Math.ceil(n / 15) === 0 || i === n - 1) text(s, x + bw / 2, H - m.b + 16, shortDate(d.date), { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${d.weekday} ${shortDate(d.date)}</b><br>${fmt(d.lines_edited)} lines written/edited<br><span class="muted">${d.subagents} subagents launched</span>`);
  });
})();

// ---- 5. Nudges ------------------------------------------------------------------
(function () {
  const kinds = [["light", "--series-1"], ["step back", "--series-2"], ["firm", "--series-3"]];
  legend("l-nudges", kinds.map(([k, c]) => [k[0].toUpperCase() + k.slice(1), c]));
  const W = 520, H = 220, m = { t: 16, r: 8, b: 34, l: 36 };
  const s = svg("c-nudges", W, H);
  const byDay = D.daily.map((d) => Object.fromEntries(kinds.map(([k]) => [k, d.nudges_kind ? d.nudges_kind[k] || 0 : D.nudges.filter((n) => n.ts.slice(0, 10) === d.date && n.kind === k).length])));
  const max = niceMax(Math.max(3, ...byDay.map((b) => kinds.reduce((a, [k]) => a + b[k], 0))));
  const y = yAxis(s, m, W, H, max);
  const n = D.daily.length, band = (W - m.l - m.r) / n, bw = Math.max(3, Math.min(24, band - 2));
  D.daily.forEach((d, i) => {
    const x = m.l + i * band + (band - bw) / 2;
    let acc = 0;
    const total = kinds.reduce((a, [k]) => a + byDay[i][k], 0);
    kinds.forEach(([k, c], ki) => {
      const v = byDay[i][k]; if (!v) return;
      const y0 = y(acc), y1 = y(acc + v);
      const isTop = kinds.slice(ki + 1).every(([k2]) => !byDay[i][k2]);
      const gap = acc ? 2 : 0;
      el("path", { d: isTop ? barPath(x, y1, bw, y0 - y1 - gap) : `M${x},${y1}H${x + bw}V${y0 - gap}H${x}Z`, fill: `var(${c})` }, s);
      acc += v;
    });
    if (i % Math.ceil(n / 8) === 0 || i === n - 1) text(s, x + bw / 2, H - m.b + 16, shortDate(d.date), { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${d.weekday} ${shortDate(d.date)}</b><br>${total} nudges` + kinds.filter(([k]) => byDay[i][k]).map(([k]) => `<br>${k}: ${byDay[i][k]}`).join(""));
  });

  const sens = D.sensitivity;
  legend("l-sens", [["Any activity counts", "--series-1", "line"], ["Your prompts only (old watcher)", "--series-2", "line"]]);
  lines("c-sens", sens.map((r) => r.light_min), [
    { label: "Any activity", color: "--series-1", values: sens.map((r) => r.nudges) },
    { label: "Prompts only", color: "--series-2", values: sens.map((r) => r.nudges_prompt_only) },
  ], { W: 520, xLabel: (v) => v + " min", tipTitle: (i) => `Light nudge at ${sens[i].light_min} min` });

  if (!D.nudges.length) { $("t-nudges").innerHTML = '<p class="note">No nudges would have fired.</p>'; return; }
  table("t-nudges", ["When", "Kind", "Stretch (min)", "Signals"],
    D.nudges.map((n) => [new Date(n.ts).toLocaleString(undefined, { weekday: "short", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }), n.kind, n.stretch_min, n.signals.join(", ") || "time only"]));
})();

// ---- 6. Check-ins ---------------------------------------------------------------
(function () {
  const c = D.checkins;
  if (!c.length) {
    $("checkins").innerHTML = '<h3>No check-ins yet</h3><p class="note">Run <code>/battery</code> (or answer a battery check after a nudge) for a week or two. Ratings will appear here next to the signals from the hours before each one, which is the real test of whether the signals track how you feel.</p>';
    return;
  }
  const bat = c.filter((x) => x.instrument === "samn-perelli");
  const burn = c.filter((x) => x.instrument === "burnout");
  $("checkins").innerHTML = `<h3>Self-reported check-ins</h3><p class="sub">${bat.length} battery ratings (1 fully alert … 7 completely exhausted) · ${burn.length} burnout answers</p><div class="tablewrap" id="t-checkins"></div>`;
  table("t-checkins", ["When", "Instrument", "Answer"], c.map((x) => [new Date(x.ts).toLocaleString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", hour12: false }), x.instrument, x.value]));
})();

// ---- 6b. Monthly check ------------------------------------------------------------
(function () {
  const M = (D.monthly_checks || []);
  const box = $("monthly");
  if (!M.length) {
    box.innerHTML = '<h3>Monthly check</h3><p class="note">Not taken yet. <code>/battery month</code> (or <code>/observe 7d</code>, which offers it every 28 days) asks four exhaustion questions and seven optional ones about workload, control, support, recognition, fairness, meaning and work–life.</p>';
    return;
  }
  const LABEL = { qd2: "Not enough time for tasks", in3: "Influence over amount of work", sc1: "Support from colleagues", re1: "Recognition", ju4: "Work distributed fairly", mw1: "Work feels meaningful", wf2: "Work drains private life" };
  const DEMAND = new Set(["qd2", "wf2"]);
  const last = M[M.length - 1], prev = M.length > 1 ? M[M.length - 2] : null;
  const when = (iso) => shortDate(iso.slice(0, 10));
  const sc = (m) => m.exhaustion == null ? "no score (fewer than 3 of 4 answered)" : fmt(m.exhaustion);
  const causes = Object.entries(last.causes).map(([k, v]) => {
    const poor = DEMAND.has(k) ? v >= 75 : v <= 25;
    return `<tr><td>${esc(LABEL[k] || k)}</td><td>${DEMAND.has(k) ? "demand" : "resource"}</td><td${poor ? ' style="color:var(--critical);font-weight:600"' : ""}>${v}</td></tr>`;
  }).join("");
  box.innerHTML = `<h3>Monthly check</h3><p class="sub">Exhaustion 0–100 (mean of 4 items, higher = more often exhausted) · latest ${when(last.ts)}</p>
    <div class="tiles" style="margin-top:0"><div class="tile"><div class="label">Exhaustion</div><div class="value">${esc(sc(last))}</div><div class="sub">${prev ? "previous " + esc(sc(prev)) + " on " + when(prev.ts) : "first check"}</div></div></div>
    ${causes ? `<div class="tablewrap"><table><thead><tr><th>Cause area (latest)</th><th>Type</th><th>0–100</th></tr></thead><tbody>${causes}</tbody></table></div><p class="note">Demands: high is worse. Resources: low is worse. Red = 75+ demand or 25-or-less resource. Items from COPSOQ III, used verbatim; scores are only comparable with your own earlier answers.</p>` : ""}
    ${M.length > 1 ? `<details><summary>All monthly checks</summary><div class="tablewrap" id="t-monthly"></div></details>` : ""}`;
  if (M.length > 1) table("t-monthly", ["Date", "Exhaustion", "Items answered"], M.map((m) => [when(m.ts), m.exhaustion == null ? "–" : fmt(m.exhaustion), m.answered]));
})();

// ---- 6c. Does it match how you feel? -----------------------------------------------
(function () {
  const V = D.validation, box = $("validation");
  if (!V) { box.remove(); return; }
  const NAMES = { rest_days: "Days without Claude sessions", late_days: "Late days", long_days: "Long days (8h+)", active_h: "Active hours" };
  const part = (title, v, unit) => {
    if (!v.rho) return `<p><b>${title}:</b> ${v.n} of ${V.min_pairs} paired weeks so far.</p>`;
    const rows = Object.entries(v.rho).map(([k, r]) => `<tr><td>${NAMES[k]}</td><td>${r == null ? "–" : (r > 0 ? "+" : "") + fmt(r, 2)}</td></tr>`).join("");
    return `<p><b>${title}</b> (${v.n} weeks, ${unit}):</p><div class="tablewrap"><table><thead><tr><th>Recovery number, week before</th><th>ρ</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  };
  box.innerHTML = `<h3>Does it match how you feel?</h3><p class="sub">Spearman rank correlation between each self-report and the recovery numbers of the week before it. Shown after ${V.min_pairs}+ paired weeks.</p>
    ${part("Weekly burnout item", V.burnout, "1–5")}${part("Monthly exhaustion", V.exhaustion, "0–100")}
    <p class="note">"Moved together in your data", not "predicts": with a few months of weeks this is a rough hint for tuning thresholds. |ρ| under ~0.4 means little.</p>`;
})();

// ---- 7. Recovery --------------------------------------------------------------------
(function () {
  const R = D.recovery;
  if (!R) return;
  const w = R.week, b = R.baseline, TR = R.thresholds;
  const base = (k, d) => b[k] == null ? "no baseline yet" : `usually ${fmt(b[k], d)}`;
  $("r-tiles").innerHTML = [
    ["Days without Claude sessions", w.rest_days, base("rest_days", 1)],
    ["Late days", w.late_days, base("late_days", 1)],
    ["Long days", w.long_days, base("long_days", 1)],
    ["Active hours", fmt(w.active_h, 1), base("active_h", 1)],
    ["Work streak", R.work_streak + " d", "days in a row with sessions"],
    ["Recovery debt", R.debt_weeks + " wk", R.debt_weeks >= 2 ? "flagged weeks in a row: sustained" : "flagged weeks in a row"],
  ].map(([l, v, sub]) => `<div class="tile"><div class="label">${esc(l)}</div><div class="value">${esc(v)}</div><div class="sub">${esc(sub)}</div></div>`).join("");
  const SAY = {
    fewer_rest_days: `Fewer days without Claude sessions than usual (${w.rest_days} vs ${b.rest_days == null ? "–" : fmt(b.rest_days, 1)}).`,
    more_late_days: `More late days than usual (${w.late_days} vs ${b.late_days == null ? "–" : fmt(b.late_days, 1)}).`,
    more_long_days: `More long days than usual (${w.long_days} vs ${b.long_days == null ? "–" : fmt(b.long_days, 1)}).`,
    long_streak: `${R.work_streak} days in a row with sessions.`,
  };
  const f = R.flags.map((k) => SAY[k]);
  if (!f.length) f.push(b.rest_days == null ? `Last 7 finished days: ${w.known_days} with data. Not enough history for a baseline yet (needs ~2 weeks).` : "No drift from your baseline in the last 7 finished days.");
  if (R.debt_weeks >= 2) f.push(`Drift flags for ${R.debt_weeks} weeks in a row.`);
  $("r-findings").innerHTML = f.map((x) => `<li>${esc(x)}</li>`).join("");

  const weeks = [...R.weeks].reverse();
  const W = 1040, H = 220, m = { t: 16, r: 12, b: 34, l: 36 };
  const s = svg("c-recovery", W, H);
  const y = yAxis(s, m, W, H, 8);  // 8 so ticks fall on whole days (0, 2, 4, 6, 8)
  const band = (W - m.l - m.r) / weeks.length, bw = Math.min(40, band - 8);
  weeks.forEach((wk, i) => {
    const x = m.l + i * band + (band - bw) / 2;
    const end = new Date(wk.end + "T12:00"), start = new Date(end - 6 * 864e5);
    const lbl = `${shortDate(start.toISOString().slice(0, 10))}–${shortDate(wk.end)}`;
    if (wk.known_days === 0) el("rect", { x, y: y(0) - 3, width: bw, height: 3, rx: 1.5, fill: "none", stroke: "var(--grid)", "stroke-dasharray": "2 2" }, s);
    else if (wk.rest_days) el("path", { d: barPath(x, y(wk.rest_days), bw, y(0) - y(wk.rest_days)), fill: wk.flags.length ? "var(--series-2)" : "var(--series-1)" }, s);
    else el("rect", { x, y: y(0) - 3, width: bw, height: 3, rx: 1.5, fill: wk.flags.length ? "var(--series-2)" : "var(--grid)" }, s);
    if (wk.known_days && wk.rest_days) text(s, x + bw / 2, y(wk.rest_days) - 4, wk.rest_days, { "text-anchor": "middle", class: "lbl" });
    text(s, x + bw / 2, H - m.b + 16, shortDate(wk.end), { "text-anchor": "middle" });
    const hit = el("rect", { x: m.l + i * band, y: m.t, width: band, height: H - m.t - m.b, class: "hit" }, s);
    hover(hit, `<b>${lbl}</b><br>${wk.known_days ? `${wk.rest_days} days without Claude sessions<br>${wk.late_days} late · ${wk.long_days} long · ${fmt(wk.active_h, 1)}h active<br><span class="muted">${wk.known_days} of 7 days with data</span>${wk.flags.length ? "<br>Flags: " + esc(wk.flags.join(", ").replace(/_/g, " ")) : ""}` : "No data"}`);
  });
  if (b.rest_days != null) {
    el("line", { x1: m.l, x2: W - m.r, y1: y(b.rest_days), y2: y(b.rest_days), stroke: "var(--text-secondary)", "stroke-dasharray": "4 4", "stroke-width": 1.5, "pointer-events": "none" }, s);
    text(s, m.l + 4, y(b.rest_days) - 6, `baseline ${fmt(b.rest_days, 1)}`, { class: "lbl" });
  }
  table("t-recovery", ["Week ending", "Days with data", "Without sessions", "Late", "Long", "Active h", "Flags"],
    weeks.map((wk) => [wk.end, wk.known_days, wk.rest_days, wk.late_days, wk.long_days, fmt(wk.active_h, 1), wk.flags.join(", ").replace(/_/g, " ") || "–"]));
  $("footer").textContent += ` Recovery: rest day < ${TR.rest_max_h} h active · late day ≥ ${TR.late_day_prompts} late prompts · long day ≥ ${TR.long_day_h} h · streak flag at ${TR.long_streak_days} days.`;
})();

})();
