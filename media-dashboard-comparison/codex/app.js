const DATA_PATHS = {
  mentions: "./data/generated/mentions.json",
  dailyCounts: "./data/generated/daily_counts.json",
  sourceSummary: "./data/generated/source_summary.json",
  topicSummary: "./data/generated/topic_summary.json",
  alerts: "./data/generated/alerts.json",
  metadata: "./data/generated/metadata.json"
};

const state = {
  data: null,
  filtered: [],
  sortKey: "date",
  sortDir: "desc"
};

const $ = (id) => document.getElementById(id);
const novoColor = "#1c6f7d";
const lillyColor = "#bd4052";

async function loadJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path} ${response.status}`);
  return response.json();
}

async function init() {
  try {
    const [mentions, dailyCounts, sourceSummary, topicSummary, alerts, metadata] = await Promise.all([
      loadJson(DATA_PATHS.mentions),
      loadJson(DATA_PATHS.dailyCounts),
      loadJson(DATA_PATHS.sourceSummary),
      loadJson(DATA_PATHS.topicSummary),
      loadJson(DATA_PATHS.alerts),
      loadJson(DATA_PATHS.metadata)
    ]);
    state.data = { mentions, dailyCounts, sourceSummary, topicSummary, alerts, metadata };
    hydrateFilters(mentions);
    bindEvents();
    applyFilters();
  } catch (error) {
    console.error(error);
    $("loadError").classList.remove("hidden");
  }
}

function hydrateFilters(mentions) {
  fillSelect("channelFilter", unique(mentions.map((m) => m.channel)));
  fillSelect("topicFilter", unique(mentions.map((m) => m.topic)));
  fillSelect("tierFilter", unique(mentions.map((m) => m.sourceTier)));
}

function fillSelect(id, values) {
  const select = $(id);
  values.forEach((value) => {
    const option = document.createElement("option");
    option.textContent = value;
    select.appendChild(option);
  });
}

function unique(values) {
  return [...new Set(values.filter(Boolean))].sort();
}

function bindEvents() {
  document.querySelectorAll(".tabs button").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });
  ["dateRange", "companyFilter", "channelFilter", "topicFilter", "sentimentFilter", "tierFilter", "searchBox"].forEach((id) => {
    $(id).addEventListener("input", applyFilters);
  });
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      state.sortDir = state.sortKey === key && state.sortDir === "asc" ? "desc" : "asc";
      state.sortKey = key;
      renderTable();
    });
  });
  $("exportCsv").addEventListener("click", exportCsv);
}

function switchTab(tab) {
  document.querySelectorAll(".tabs button").forEach((button) => button.classList.toggle("active", button.dataset.tab === tab));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === tab));
}

function applyFilters() {
  const { mentions, metadata } = state.data;
  const days = Number($("dateRange").value);
  const cutoff = new Date(metadata.coverageEnd || new Date());
  cutoff.setDate(cutoff.getDate() - days + 1);
  const company = $("companyFilter").value;
  const channel = $("channelFilter").value;
  const topic = $("topicFilter").value;
  const sentiment = $("sentimentFilter").value;
  const tier = $("tierFilter").value;
  const search = $("searchBox").value.trim().toLowerCase();
  state.filtered = mentions.filter((item) => {
    const dateOk = new Date(item.date) >= cutoff;
    const companyOk = company === "Both" || item.company === company;
    const channelOk = channel === "All" || item.channel === channel;
    const topicOk = topic === "All" || item.topic === topic;
    const sentimentOk = sentiment === "All" || item.sentiment === sentiment;
    const tierOk = tier === "All" || item.sourceTier === tier;
    const text = `${item.title} ${item.source} ${item.sourceDomain} ${item.topic} ${(item.matchedKeywords || []).join(" ")}`.toLowerCase();
    return dateOk && companyOk && channelOk && topicOk && sentimentOk && tierOk && (!search || text.includes(search));
  });
  renderAll();
}

function renderAll() {
  const { metadata } = state.data;
  $("lastUpdated").textContent = metadata.lastUpdated ? `Updated ${formatDate(metadata.lastUpdated)}` : "Generated data loaded";
  $("coverageWindow").textContent = `${metadata.coverageStart || "n/a"} to ${metadata.coverageEnd || "n/a"} - ${metadata.recordCount || 0} records`;
  $("emptyState").classList.toggle("hidden", (metadata.recordCount || 0) !== 0);
  renderKpis();
  renderCharts();
  renderSourceList();
  renderMomentum();
  renderTable();
  renderAlerts();
  renderQuality();
}

function companyCounts(records = state.filtered) {
  return {
    novo: records.filter((m) => m.company === "Novo Nordisk").length,
    lilly: records.filter((m) => m.company === "Eli Lilly").length
  };
}

function renderKpis() {
  const counts = companyCounts();
  const total = counts.novo + counts.lilly;
  const novoShare = total ? counts.novo / total : 0;
  const lillyShare = total ? counts.lilly / total : 0;
  const weighted = weightedWinner(state.filtered);
  const sentimentGap = averageSentiment("Novo Nordisk") - averageSentiment("Eli Lilly");
  const momentum = momentumWinner();
  const highRisk = state.data.alerts.filter((a) => a.severity === "High").length;
  const cards = [
    ["Novo total mentions", counts.novo],
    ["Lilly total mentions", counts.lilly],
    ["Novo share of voice", pct(novoShare)],
    ["Lilly share of voice", pct(lillyShare)],
    ["Weighted SOV winner", weighted],
    ["Sentiment gap", `${sentimentGap >= 0 ? "+" : ""}${sentimentGap.toFixed(2)}`],
    ["Exposure momentum winner", momentum],
    ["High-risk alert count", highRisk]
  ];
  $("kpiGrid").innerHTML = cards.map(([label, value]) => `<article class="kpi"><span>${escapeHtml(label)}</span><strong>${escapeHtml(String(value))}</strong></article>`).join("");
}

function weightedWinner(records) {
  const totals = { "Novo Nordisk": 0, "Eli Lilly": 0 };
  records.forEach((m) => { totals[m.company] += Number(m.reach || 0) * (Number(m.sourceAuthority || 0) / 100); });
  if (totals["Novo Nordisk"] === totals["Eli Lilly"]) return "Tie";
  return totals["Novo Nordisk"] > totals["Eli Lilly"] ? "Novo Nordisk" : "Eli Lilly";
}

function averageSentiment(company) {
  const rows = state.filtered.filter((m) => m.company === company);
  if (!rows.length) return 0;
  return rows.reduce((sum, item) => sum + Number(item.sentimentScore || 0), 0) / rows.length;
}

function momentumWinner() {
  const sorted = [...state.filtered].sort((a, b) => a.date.localeCompare(b.date));
  if (!sorted.length) return "No data";
  const midpoint = Math.floor(sorted.length / 2);
  const recent = companyCounts(sorted.slice(midpoint));
  const prior = companyCounts(sorted.slice(0, midpoint));
  const novoDelta = recent.novo - prior.novo;
  const lillyDelta = recent.lilly - prior.lilly;
  if (novoDelta === lillyDelta) return "Tie";
  return novoDelta > lillyDelta ? "Novo Nordisk" : "Eli Lilly";
}

function renderCharts() {
  renderLineChart("mentionsChart", aggregateByDate(state.filtered));
  renderStackedBars("sentimentChart", aggregateByField(state.filtered, "sentiment"));
  renderStackedBars("tierChart", aggregateByField(state.filtered, "sourceTier"));
  renderStackedBars("channelChart", aggregateByField(state.filtered, "channel"));
  renderStackedBars("topicChart", aggregateByField(state.filtered, "topic"), true);
  renderHeatmap();
  renderLineChart("spikeChart", movingAverage(aggregateByDate(state.filtered)));
}

function aggregateByDate(records) {
  const map = new Map();
  records.forEach((m) => {
    if (!map.has(m.date)) map.set(m.date, { label: m.date, novo: 0, lilly: 0 });
    map.get(m.date)[m.company === "Novo Nordisk" ? "novo" : "lilly"] += 1;
  });
  return [...map.values()].sort((a, b) => a.label.localeCompare(b.label));
}

function aggregateByField(records, field) {
  const map = new Map();
  records.forEach((m) => {
    const label = m[field] || "Unknown";
    if (!map.has(label)) map.set(label, { label, novo: 0, lilly: 0 });
    map.get(label)[m.company === "Novo Nordisk" ? "novo" : "lilly"] += 1;
  });
  return [...map.values()].sort((a, b) => (b.novo + b.lilly) - (a.novo + a.lilly)).slice(0, 12);
}

function movingAverage(rows) {
  return rows.map((row, idx) => {
    const window = rows.slice(Math.max(0, idx - 6), idx + 1);
    return {
      label: row.label,
      novo: window.reduce((sum, item) => sum + item.novo, 0) / window.length,
      lilly: window.reduce((sum, item) => sum + item.lilly, 0) / window.length
    };
  });
}

function renderLineChart(id, rows) {
  const el = $(id);
  if (!rows.length) { el.innerHTML = emptyChart(); return; }
  const w = 900, h = 280, pad = 34;
  const max = Math.max(1, ...rows.flatMap((r) => [r.novo, r.lilly]));
  const x = (i) => pad + (rows.length === 1 ? 0 : i * (w - pad * 2) / (rows.length - 1));
  const y = (v) => h - pad - (v / max) * (h - pad * 2);
  const path = (key) => rows.map((r, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(r[key]).toFixed(1)}`).join(" ");
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img">
    <line x1="${pad}" y1="${h-pad}" x2="${w-pad}" y2="${h-pad}" stroke="#dfe4dc"/>
    <path d="${path("novo")}" fill="none" stroke="${novoColor}" stroke-width="3"/>
    <path d="${path("lilly")}" fill="none" stroke="${lillyColor}" stroke-width="3"/>
    <text x="${pad}" y="18" class="legend">Novo Nordisk</text><circle cx="${pad+92}" cy="14" r="5" fill="${novoColor}"/>
    <text x="${pad+120}" y="18" class="legend">Eli Lilly</text><circle cx="${pad+178}" cy="14" r="5" fill="${lillyColor}"/>
    <text x="${pad}" y="${h-8}" class="axis">${rows[0].label}</text>
    <text x="${w-pad-84}" y="${h-8}" class="axis">${rows[rows.length-1].label}</text>
  </svg>`;
}

function renderStackedBars(id, rows, compact = false) {
  const el = $(id);
  if (!rows.length) { el.innerHTML = emptyChart(); return; }
  const w = 900, h = Math.max(260, rows.length * (compact ? 30 : 42) + 30), left = 220;
  const max = Math.max(1, ...rows.map((r) => r.novo + r.lilly));
  el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" role="img">${rows.map((r, i) => {
    const y = 24 + i * (compact ? 30 : 42);
    const total = r.novo + r.lilly;
    const bw = (total / max) * (w - left - 40);
    const nw = total ? bw * (r.novo / total) : 0;
    return `<text x="0" y="${y + 15}" class="chart-label">${escapeHtml(shorten(r.label, 30))}</text>
      <rect x="${left}" y="${y}" width="${nw}" height="22" fill="${novoColor}"></rect>
      <rect x="${left + nw}" y="${y}" width="${Math.max(0, bw - nw)}" height="22" fill="${lillyColor}"></rect>
      <text x="${left + bw + 8}" y="${y + 16}" class="axis">${total}</text>`;
  }).join("")}</svg>`;
}

function renderHeatmap() {
  const rows = aggregateByField(state.filtered, "topic");
  const max = Math.max(1, ...rows.flatMap((r) => [r.novo, r.lilly]));
  $("topicHeatmap").innerHTML = rows.map((r) => `
    <div class="heat-row">
      <strong>${escapeHtml(r.label)}</strong>
      <div class="heat-cell" style="background:${novoColor};opacity:${0.25 + (r.novo / max) * 0.75}">${r.novo}</div>
      <div class="heat-cell" style="background:${lillyColor};opacity:${0.25 + (r.lilly / max) * 0.75}">${r.lilly}</div>
    </div>`).join("") || "<p>No topic data.</p>";
}

function renderSourceList() {
  const rows = aggregateByField(state.filtered, "sourceDomain").slice(0, 15);
  $("sourceList").innerHTML = rows.map((r) => `<div class="rank-row"><strong>${escapeHtml(r.label)}</strong><span>${r.novo + r.lilly}</span></div>`).join("") || "No source data.";
}

function renderMomentum() {
  const counts = companyCounts();
  const total = counts.novo + counts.lilly;
  $("momentumNotes").innerHTML = `<p>${escapeHtml(momentumWinner())} has the stronger recent momentum in the current filter set.</p><p>Filtered share of voice: Novo ${pct(total ? counts.novo / total : 0)}, Lilly ${pct(total ? counts.lilly / total : 0)}.</p>`;
}

function renderTable() {
  const rows = [...state.filtered].sort((a, b) => {
    const av = String(a[state.sortKey] || "");
    const bv = String(b[state.sortKey] || "");
    return state.sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
  });
  $("tableCount").textContent = `${rows.length} filtered records`;
  $("mentionsTable").innerHTML = rows.slice(0, 500).map((m) => `<tr data-id="${m.id}">
    <td>${escapeHtml(m.date)}</td>
    <td>${escapeHtml(m.company)}</td>
    <td>${escapeHtml(m.source || m.sourceDomain)}</td>
    <td>${escapeHtml(m.topic)}</td>
    <td class="sentiment-${m.sentiment}">${escapeHtml(m.sentiment)}</td>
    <td>${escapeHtml(m.title)}</td>
  </tr>`).join("");
  document.querySelectorAll("#mentionsTable tr").forEach((tr) => tr.addEventListener("click", () => showDetail(tr.dataset.id)));
}

function showDetail(id) {
  const m = state.filtered.find((item) => item.id === id);
  if (!m) return;
  $("detailPanel").innerHTML = `<h2>${escapeHtml(m.title)}</h2>
    <p><strong>${escapeHtml(m.company)}</strong> - ${escapeHtml(m.source)} - ${escapeHtml(m.date)}</p>
    <p>${escapeHtml(m.snippet || "No snippet supplied by source.")}</p>
    <p>${(m.matchedKeywords || []).map((k) => `<span class="pill">${escapeHtml(k)}</span>`).join("")}</p>
    <p>Topic: <strong>${escapeHtml(m.topic)}</strong><br>Source tier: <strong>${escapeHtml(m.sourceTier)}</strong><br>Sentiment score: <strong>${m.sentimentScore}</strong></p>
    <p>${escapeHtml((m.dataQualityNotes || []).join(" "))}</p>
    ${m.url ? `<p><a href="${escapeAttr(m.url)}" target="_blank" rel="noopener">Open article</a></p>` : ""}`;
}

function renderAlerts() {
  const alerts = state.data.alerts;
  $("alertsList").innerHTML = alerts.length ? alerts.map((a) => `<article class="alert-row"><div><strong>${escapeHtml(a.title)}</strong><p>${escapeHtml(a.detail)}</p></div><span class="pill">${escapeHtml(a.severity)}</span></article>`).join("") : "<article class='panel'><h2>No generated alerts</h2><p>The current real dataset did not cross the configured alert thresholds.</p></article>";
}

function renderQuality() {
  const m = state.data.metadata;
  const fields = [
    ["Last updated", m.lastUpdated],
    ["Coverage window", `${m.coverageStart} to ${m.coverageEnd}`],
    ["Record count", m.recordCount],
    ["Sources used", (m.sourcesUsed || []).join(", ")],
    ["Unavailable sources", (m.sourcesUnavailable || []).join(", ")],
    ["Proxy fields", (m.proxyMetricFields || []).join(", ")],
    ["Version", m.version]
  ];
  $("metadataList").innerHTML = fields.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd>${escapeHtml(String(v ?? ""))}</dd>`).join("");
  $("queryDefinitions").textContent = JSON.stringify(m.queryDefinitions || {}, null, 2);
  $("warningsList").innerHTML = (m.warnings || []).map((w) => `<p>${escapeHtml(w)}</p>`).join("") || "<p>No warnings in metadata.</p>";
}

function exportCsv() {
  const headers = ["date","company","source","sourceDomain","sourceTier","channel","topic","sentiment","sentimentScore","title","url","rawSource","isProxyMetrics"];
  const csv = [headers.join(",")].concat(state.filtered.map((row) => headers.map((key) => `"${String(row[key] ?? "").replaceAll('"', '""')}"`).join(","))).join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "novo-lilly-media-exposure-filtered.csv";
  link.click();
  URL.revokeObjectURL(url);
}

function emptyChart() { return "<div class='empty-state'><h2>No chart data</h2><p>No matching records for the current filters.</p></div>"; }
function pct(value) { return `${Math.round(value * 100)}%`; }
function formatDate(value) { return new Date(value).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" }); }
function shorten(value, length) { return String(value).length > length ? `${String(value).slice(0, length - 3)}...` : value; }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])); }
function escapeAttr(value) { return escapeHtml(value).replace(/`/g, "&#96;"); }

init();
