/**
 * SQM Perovskite Scout — Frontend v5.2 (Structural Patch Edition)
 * ─────────────────────────────────────────────────────────────────
 * v5.2:
 *  - Calculadora universal: iodine_factor actualiza KPIs, Ledger Y Radar en tiempo real
 *  - Geo-tags (País/Continente) en Ledger y Radar cards
 *  - Timeline filter opera sobre dataset consolidado por empresa
 *  - ERROR FATAL API: detectado y mostrado en rojo con diagnóstico crudo
 */

const API_BASE      = "";
const SUPABASE_URL  = "https://rpibprkdzoxfizssvtuf.supabase.co";
const SUPABASE_ANON = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InJwaWJwcmtkem94Zml6c3N2dHVmIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODIxNTc5NDQsImV4cCI6MjA5NzczMzk0NH0.J_tDZOi-5QFMSmwsba4EUGlu29MEng8ru7hXoRMPUGU";
const DB_URL        = `${SUPABASE_URL}/rest/v1/perovskite_leads?select=*`;
const DB_LOCAL      = `${API_BASE}/database.json`;
const REFRESH_MS    = 5 * 60 * 1000;
const FETCH_TIMEOUT = 10000;
const RATIOS        = { pbi2: 0.60, fai: 0.20, mai: 0.10, csi: 0.10 };

let companyChart  = null;
let compoundChart = null;

let state = {
  db:         null,
  sort:       { col: "date", dir: "desc" },
  fetchError: null,
};

// ── Bootstrap ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  setupManualForm();
  setupTableControls();
  setupSimulatorControls();
  setupChatControls();
  loadAndRender();
  setInterval(loadAndRender, REFRESH_MS);
});

// ── Fetch ──────────────────────────────────────────────────────
async function fetchWithTimeout(url, ms = FETCH_TIMEOUT, options = {}) {
  const ctrl  = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), ms);
  try {
    const res = await fetch(url, { ...options, signal: ctrl.signal, cache: "no-store" });
    clearTimeout(timer);
    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText}`);
    return await res.json();
  } catch (err) {
    clearTimeout(timer);
    throw err;
  }
}

// ── Data Loading ───────────────────────────────────────────────
async function loadAndRender() {
  setAgentStatus("loading");
  try {
    const rows = await fetchWithTimeout(DB_URL, FETCH_TIMEOUT, {
      headers: {
        "apikey": SUPABASE_ANON,
        "Authorization": `Bearer ${SUPABASE_ANON}`
      }
    });
    if (!Array.isArray(rows)) throw new Error("Respuesta inválida de Supabase");
    
    // Fetch local db to get market_report and meta info
    let localDb = {};
    try {
      localDb = await fetchWithTimeout(DB_LOCAL, FETCH_TIMEOUT);
    } catch(e) {
      console.warn("No se pudo obtener database.json local:", e.message);
    }
    
    // Map rows to original database.json schema
    const db = { articles: [], meta: localDb.meta || {}, market_report: localDb.market_report || "" };
    let totalGw = 0;
    const targetYears = new Set();
    
    rows.forEach(r => {
      const gw = parseFloat(r.capacidad_gw) || 0;
      totalGw += gw;
      if (r.target_year) targetYears.add(r.target_year);
      
      db.articles.push({
        id: r.id,
        company: r.empresa,
        capacityGw: gw,
        capacityValue: "",
        capacityUnit: "",
        phase: "Planned", // Default fallback if missing
        target_year: r.target_year,
        geo: { country: r.geo_pais || "", continent: r.geo_continente || "Global" },
        nivel_riesgo: r.nivel_riesgo || "Neutral",
        invest_proxy: r.invest_proxy || false,
        radar_only: gw === 0,
        source: r.fuente_noticia,
        link: r.fuente_noticia,
        summary: r.resumen_ia || "",
        resumen_ia: r.resumen_ia || "Sin análisis detallado.",
        title: r.empresa + " - " + r.fuente_noticia, // Fallback title
        date: r.fecha_noticia || r.created_at || new Date().toISOString().split('T')[0]
      });
    });
    
    db.meta.target_years = Array.from(targetYears).sort();
    db.meta.total_gw = totalGw;
    db.meta.last_updated = new Date().toISOString();

    state.db = db;
    state.fetchError = null;
    setAgentStatus("online");
    populateTimelineFilter();
    render();
  } catch (err) {
    state.fetchError = err.message;
    setAgentStatus("offline", err.message);
    if (state.db) { render(); }
    else           { renderOfflineState(); }
    console.warn("[Scout] Fetch failed:", err.message);
  }
}

// ── Agent Status ───────────────────────────────────────────────
function setAgentStatus(status, detail = "") {
  const dot   = document.getElementById("agent-dot");
  const label = document.getElementById("agent-status-text");
  const ts    = document.getElementById("last-updated");
  if (!dot) return;
  const cfg = {
    loading: { dot: "bg-yellow-400 animate-pulse", txt: "Cargando datos..." },
    online:  { dot: "bg-green-500",                txt: "Agente en línea"  },
    offline: { dot: "bg-red-500",                  txt: detail || "Agente offline" },
  }[status];
  dot.className     = `inline-block w-2 h-2 rounded-full mr-1.5 ${cfg.dot}`;
  label.textContent = cfg.txt;
  if (status === "online" && state.db?.meta?.last_updated) {
    const d = new Date(state.db.meta.last_updated);
    if (ts) ts.textContent = `Actualizado: ${d.toLocaleString("es-CL")}`;
  }
}

// ── Timeline filter ────────────────────────────────────────────
function populateTimelineFilter() {
  const sel = document.getElementById("timeline_filter");
  if (!sel) return;
  const years   = (state.db?.meta?.target_years || []).filter(Boolean);
  const current = sel.value;
  sel.innerHTML  = `<option value="ALL">Todas las fechas</option>`;
  years.forEach(y => {
    const opt = document.createElement("option");
    opt.value = opt.textContent = y;
    sel.appendChild(opt);
  });
  if ([...sel.options].some(o => o.value === current)) sel.value = current;
}

// ── Simulator Controls ─────────────────────────────────────────
function setupSimulatorControls() {
  document.getElementById("iodine_factor")?.addEventListener("input",  recomputeAndRender);
  document.getElementById("timeline_filter")?.addEventListener("change", recomputeAndRender);
}

// ── Chat Controls ──────────────────────────────────────────────
function setupChatControls() {
  const btn = document.getElementById("chat-btn");
  const input = document.getElementById("chat-input");
  if (!btn || !input) return;

  btn.addEventListener("click", handleChatSubmit);
  input.addEventListener("keypress", (e) => {
    if (e.key === "Enter") handleChatSubmit();
  });
}

async function handleChatSubmit() {
  const input = document.getElementById("chat-input");
  const btn = document.getElementById("chat-btn");
  const history = document.getElementById("chat-history");
  const msg = input.value.trim();
  if (!msg) return;

  // Add User msg
  const userDiv = document.createElement("div");
  userDiv.className = "p-3 bg-slate-100 rounded-xl ml-8 border border-slate-200 text-right";
  userDiv.innerHTML = `<strong>Tú:</strong> ${msg}`;
  history.appendChild(userDiv);
  input.value = "";
  btn.disabled = true;
  history.scrollTop = history.scrollHeight;

  // Add Loading msg
  const loadDiv = document.createElement("div");
  loadDiv.className = "p-3 bg-sqm-purple-lt/30 rounded-xl mr-8 border border-sqm-purple/10 text-slate-500 animate-pulse";
  loadDiv.innerHTML = `<strong>Agente:</strong> Analizando consulta con Cerebro Híbrido...`;
  history.appendChild(loadDiv);
  history.scrollTop = history.scrollHeight;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg })
    });
    const data = await res.json();
    
    history.removeChild(loadDiv);
    const agDiv = document.createElement("div");
    agDiv.className = "p-3 bg-sqm-purple-lt/30 rounded-xl mr-8 border border-sqm-purple/10";
    
    // Basic Markdown to HTML parsing for bold and line breaks
    let formattedReply = data.reply.replace(/\n/g, "<br>");
    formattedReply = formattedReply.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    formattedReply = formattedReply.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    agDiv.innerHTML = `<strong>Agente:</strong><br>${formattedReply}`;
    history.appendChild(agDiv);
    
    // Refresh DB if agent successfully triggered a lead insertion
    if (data.reply.toLowerCase().includes("lead") || data.reply.toLowerCase().includes("insertado")) {
      loadAndRender();
    }
  } catch (err) {
    history.removeChild(loadDiv);
    const errDiv = document.createElement("div");
    errDiv.className = "p-3 bg-red-50 rounded-xl mr-8 border border-red-200 text-red-700";
    errDiv.innerHTML = `<strong>Error:</strong> No se pudo conectar con el agente. ${err.message}`;
    history.appendChild(errDiv);
  }
  
  btn.disabled = false;
  history.scrollTop = history.scrollHeight;
}

/**
 * Master BI engine — called whenever factor or filter changes.
 * Updates KPIs, charts, Ledger rows, AND Radar cards in real time.
 */
function recomputeAndRender() {
  if (!state.db) return;

  const factor  = getLiveFactor();
  const yearSel = document.getElementById("timeline_filter")?.value || "ALL";

  // Filter dataset
  let capArticles = (state.db.articles || []).filter(e => !e.radar_only);
  if (yearSel !== "ALL") capArticles = capArticles.filter(e => e.target_year === yearSel);

  // Recalculate totals
  const totalGw  = capArticles.reduce((s, e) => s + (e.capacityGw || 0), 0);
  const totalIod = totalGw * factor;

  // ── Update KPI elements ──
  setText("kpi-gw",     fmt(totalGw, 3));
  setText("kpi-mw",     fmt(totalGw * 1000, 0));
  setText("kpi-iodine", fmt(totalIod, 3));
  setText("kpi-pbi2",   fmt(totalIod * RATIOS.pbi2, 3));
  setText("kpi-fai",    fmt(totalIod * RATIOS.fai,  3));
  setText("kpi-mai",    fmt(totalIod * RATIOS.mai,  3));
  setText("kpi-csi",    fmt(totalIod * RATIOS.csi,  3));

  // ── Redraw charts ──
  renderCompanyChartFiltered(capArticles, factor);
  renderCompoundChartFiltered(totalIod);

  // ── Update Ledger rows in-place ──
  updateLedgerIodine(factor);

  // ── Update Radar cards in-place ──
  updateRadarIodine(factor);

  // ── Re-render table if year filter changed ──
  renderTable();
}

// ── In-place Ledger update ─────────────────────────────────────
function updateLedgerIodine(factor) {
  document.querySelectorAll("[data-gw]").forEach(row => {
    const gw     = parseFloat(row.dataset.gw) || 0;
    const newIod = gw * factor;
    const iodEl  = row.querySelector("[data-role='iodine-val']");
    const pbi2El = row.querySelector("[data-role='pbi2-val']");
    const faiEl  = row.querySelector("[data-role='fai-val']");
    if (iodEl)  iodEl.textContent  = fmt(newIod, 3);
    if (pbi2El) pbi2El.textContent = fmt(newIod * RATIOS.pbi2, 3);
    if (faiEl)  faiEl.textContent  = fmt(newIod * RATIOS.fai,  3);
  });
}

// ── In-place Radar update ──────────────────────────────────────
function updateRadarIodine(factor) {
  document.querySelectorAll("[data-radar-gw]").forEach(card => {
    const gw     = parseFloat(card.dataset.radarGw) || 0;
    const newIod = gw * factor;
    const iodEl  = card.querySelector("[data-role='radar-iodine']");
    if (iodEl) iodEl.textContent = fmt(newIod, 3);
  });
}

// ── Helper: get live factor value ─────────────────────────────
function getLiveFactor() {
  return parseFloat(document.getElementById("iodine_factor")?.value) || 4.73;
}

// ── Master Render ──────────────────────────────────────────────
function render() {
  if (!state.db) return;
  try { renderKPIs();         } catch(e) { console.error("renderKPIs:", e); }
  try { renderCharts();       } catch(e) { console.error("renderCharts:", e); }
  try { renderMarketReport(); } catch(e) { console.error("renderMarketReport:", e); }
  try { renderTable();        } catch(e) { console.error("renderTable:", e); }
  try { renderRiskRadar();    } catch(e) { console.error("renderRadar:", e); }
  try { renderLLMBadge();     } catch(e) { console.error("renderLLM:", e); }
}

// ── KPIs ───────────────────────────────────────────────────────
function renderKPIs() {
  const capArticles = (state.db?.articles || []).filter(e => !e.radar_only);
  const factor = getLiveFactor();
  const totalGw = capArticles.reduce((s, e) => s + (e.capacityGw || 0), 0);
  const totalIodine = totalGw * factor;

  setText("kpi-gw",        fmt(totalGw, 3));
  setText("kpi-mw",        fmt(totalGw * 1000, 0));
  setText("kpi-iodine",    fmt(totalIodine, 3));
  setText("kpi-pbi2",      fmt(totalIodine * RATIOS.pbi2, 3));
  setText("kpi-fai",       fmt(totalIodine * RATIOS.fai, 3));
  setText("kpi-mai",       fmt(totalIodine * RATIOS.mai, 3));
  setText("kpi-csi",       fmt(totalIodine * RATIOS.csi, 3));
  
  const uniqueComps = new Set((state.db?.articles || []).map(a => a.company)).size;
  setText("kpi-companies", uniqueComps);
  setText("kpi-articles",  (state.db?.articles || []).length);
  
  const rc = { Beneficioso: 0, Riesgo: 0, Neutral: 0 };
  (state.db?.articles || []).forEach(a => {
    if (a.nivel_riesgo && rc[a.nivel_riesgo] !== undefined) rc[a.nivel_riesgo]++;
    else rc.Neutral++;
  });
  
  setText("kpi-beneficioso", rc.Beneficioso);
  setText("kpi-riesgo",      rc.Riesgo);
  setText("kpi-neutral",     rc.Neutral);
}

// ── LLM Badge ─────────────────────────────────────────────────
function renderLLMBadge() {
  const el = document.getElementById("llm-badge");
  if (!el) return;
  const on = state.db?.meta?.llm_enabled;
  el.textContent = on ? "✔ Agente IA Autónomo - Conectado" : "⚠ Sin API Key";
  el.className   = on
    ? "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-green-100 text-green-700 border border-green-300"
    : "px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 border border-amber-300";
}

// ── Charts ─────────────────────────────────────────────────────
function renderCharts() {
  renderCompanyChart();
  renderCompoundChart();
}

function destroyChart(c) {
  if (c) { try { c.destroy(); } catch (_) {} }
  return null;
}

function renderCompanyChart() {
  const factor  = getLiveFactor();
  const yearSel = document.getElementById("timeline_filter")?.value || "ALL";
  let cap       = (state.db?.articles || []).filter(e => (e.capacityGw || 0) > 0);
  if (yearSel !== "ALL") cap = cap.filter(e => e.target_year === yearSel);
  renderCompanyChartFiltered(cap, factor);
}

function renderCompanyChartFiltered(capArticles, factor) {
  const ctx = document.getElementById("chart-company")?.getContext("2d");
  if (!ctx) return;
  companyChart = destroyChart(companyChart);

  const agg = {};
  capArticles.forEach(e => {
    agg[e.company] = (agg[e.company] || 0) + (e.capacityGw || 0) * factor;
  });

  const hasData = Object.keys(agg).length > 0;
  const pairs   = hasData ? Object.entries(agg).sort((a, b) => b[1] - a[1]) : [];
  const labels  = hasData ? pairs.map(([co]) => co) : ["Sin datos disponibles"];
  const data    = hasData ? pairs.map(([, v]) => +v.toFixed(3)) : [0];
  const colors  = hasData ? pairs.map(() => "rgba(91,44,134,0.80)") : ["rgba(200,200,200,0.4)"];

  companyChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{ label: "Yodo (Ton)", data, backgroundColor: colors,
        borderColor: hasData ? "#5B2C86" : "#ccc", borderWidth: 1,
        borderRadius: 5,
        hoverBackgroundColor: hasData ? "rgba(178,210,53,0.85)" : "rgba(200,200,200,0.5)" }],
    },
    options: {
      indexAxis: "y", responsive: true, maintainAspectRatio: false,
      animation: { duration: 300 },
      plugins: {
        legend: { display: false },
        tooltip: { enabled: hasData, callbacks: { label: c => ` ${c.raw} Ton Yodo` } },
      },
      scales: {
        x: { min: 0, grid: { color: "rgba(0,0,0,0.06)" },
             ticks: { color: "#7A7A7A", font: { family: "Inter" } },
             title: { display: true, text: "Toneladas Métricas", color: "#7A7A7A" } },
        y: { grid: { display: false },
             ticks: { color: "#374151", font: { family: "Inter", weight: "600" } } },
      },
    },
  });
}

function renderCompoundChart() {
  const factor  = getLiveFactor();
  const yearSel = document.getElementById("timeline_filter")?.value || "ALL";
  let cap       = (state.db?.articles || []).filter(e => !e.radar_only);
  if (yearSel !== "ALL") cap = cap.filter(e => e.target_year === yearSel);
  renderCompoundChartFiltered(cap.reduce((s, e) => s + (e.capacityGw || 0), 0) * factor);
}

function renderCompoundChartFiltered(totalIod) {
  const ctx = document.getElementById("chart-compound")?.getContext("2d");
  if (!ctx) return;
  compoundChart = destroyChart(compoundChart);

  const values  = [
    +(totalIod * RATIOS.pbi2).toFixed(3), +(totalIod * RATIOS.fai).toFixed(3),
    +(totalIod * RATIOS.mai).toFixed(3),  +(totalIod * RATIOS.csi).toFixed(3),
  ];
  const hasData = values.some(v => v > 0);
  const dLabels = ["PbI₂ (60%)", "FAI (20%)", "MAI (10%)", "CsI (10%)"];
  const dColors = ["rgba(91,44,134,0.85)", "rgba(178,210,53,0.85)", "rgba(122,122,122,0.75)", "rgba(166,122,172,0.75)"];

  compoundChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels:   hasData ? dLabels : ["Sin capacidad registrada"],
      datasets: [{
        data:            hasData ? values : [1],
        backgroundColor: hasData ? dColors : ["rgba(200,200,200,0.3)"],
        borderColor: "#f8fafc", borderWidth: 3, hoverOffset: hasData ? 8 : 0,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
      plugins: {
        legend: { position: "right", labels: { color: "#374151", font: { family: "Inter", size: 12 }, boxWidth: 14 } },
        tooltip: { enabled: hasData, callbacks: { label: c => ` ${c.label}: ${c.raw} Ton` } },
      },
    },
  });
}

// ── Market Report — with ERROR FATAL API detection ─────────────
function markdownToHtml(md) {
  if (!md || typeof md !== "string") return "";
  let html = escHtml(md);
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-bold text-sqm-purple mt-5 mb-2">$1</h3>');
  html = html.replace(/^## (.+)$/gm,  '<h2 class="text-lg font-bold text-sqm-purple mt-6 mb-2 pb-1 border-b border-purple-100">$1</h2>');
  html = html.replace(/^# (.+)$/gm,   '<h2 class="text-xl font-extrabold text-sqm-purple mt-6 mb-3">$1</h2>');
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-slate-900">$1</strong>');
  html = html.replace(/\*(.+?)\*/g,     '<em class="italic text-slate-700">$1</em>');
  html = html.replace(/^[-*] (.+)$/gm,  '<li class="ml-4 pl-2 text-slate-700 leading-relaxed list-disc">$1</li>');
  html = html.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 pl-2 text-slate-700 leading-relaxed list-decimal">$1</li>');
  html = html.replace(/(<li[^>]*>.*?<\/li>\n?)+/gs, m => `<ul class="my-2 space-y-1">${m}</ul>`);
  html = html.replace(/^(?!<)(.*\S.*)$/gm, '<p class="text-slate-700 leading-relaxed mb-3">$1</p>');
  html = html.replace(/^---+$/gm, '<hr class="my-4 border-purple-100">');
  return html;
}

function renderMarketReport() {
  const section = document.getElementById("market-report-section");
  const body    = document.getElementById("market-report-body");
  if (!section || !body) return;
  section.classList.remove("hidden");

  const report = state.db?.market_report || "";

  // ── ERROR FATAL API detection ──────────────────────────────
  if (typeof report === "string" && report.startsWith("ERROR FATAL API:")) {
    body.parentElement?.classList.remove("bg-white");
    body.parentElement?.classList.add("bg-red-50", "border-red-300");
    body.innerHTML = `
      <div class="flex flex-col gap-3 py-6 px-2">
        <div class="flex items-center gap-2">
          <span class="text-2xl">🚨</span>
          <p class="text-red-700 font-bold text-base">Error de conexión con Gemini API</p>
        </div>
        <div class="rounded-lg bg-red-100 border border-red-300 px-4 py-3">
          <p class="text-xs font-mono text-red-800 leading-relaxed break-all">${escHtml(report)}</p>
        </div>
        <p class="text-red-500 text-xs">
          Verifica que la API Key sea válida y que el proxy no bloquee
          <code class="font-mono bg-red-100 px-1 rounded">generativelanguage.googleapis.com</code>.
        </p>
      </div>`;
    return;
  }

  // Reset error styles in case it was previously in error state
  body.parentElement?.classList.remove("bg-red-50", "border-red-300");
  body.parentElement?.classList.add("bg-white");

  if (!report || report === "Informe en proceso de generación") {
    body.innerHTML = `
      <div class="flex flex-col items-center justify-center py-10 gap-3">
        <div class="w-8 h-8 border-2 border-sqm-purple border-t-transparent rounded-full animate-spin"></div>
        <p class="text-slate-500 text-sm font-medium">Informe en proceso de generación&hellip;</p>
        <p class="text-slate-400 text-xs">El agente Gemini redactará el análisis tras el primer escaneo completo.</p>
      </div>`;
    return;
  }
  body.innerHTML = markdownToHtml(report);
}

// ── Geo tag helper ─────────────────────────────────────────────
function geoTag(geo) {
  if (!geo || !geo.country) return "";
  const continentColors = {
    "Asia":          "bg-orange-50 text-orange-700 border-orange-200",
    "Europa":        "bg-blue-50 text-blue-700 border-blue-200",
    "Norteamérica":  "bg-green-50 text-green-700 border-green-200",
    "Global":        "bg-slate-50 text-slate-500 border-slate-200",
  };
  const cls = continentColors[geo.continent] || "bg-slate-50 text-slate-500 border-slate-200";
  const flag = { "China":"🇨🇳","USA":"🇺🇸","UK":"🇬🇧","Japón":"🇯🇵","Polonia":"🇵🇱" }[geo.country] || "🌍";
  return `<span class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs border font-medium ${cls}">${flag} ${geo.country}</span>`;
}

// ── Data Table ─────────────────────────────────────────────────
function renderTable() {
  const tbody   = document.getElementById("ledger-body");
  const empty   = document.getElementById("ledger-empty");
  const counter = document.getElementById("ledger-count");
  if (!tbody) return;

  const search  = (document.getElementById("search-input")?.value || "").toLowerCase();
  const phase   = document.getElementById("filter-phase")?.value || "ALL";
  const yearSel = document.getElementById("timeline_filter")?.value || "ALL";
  const factor  = getLiveFactor();

  let rows = (state.db?.articles || []).filter(e => {
    if (e.radar_only) return false;
    const ms = (e.company || "").toLowerCase().includes(search) ||
               (e.title   || "").toLowerCase().includes(search);
    const mp = phase   === "ALL" || e.phase        === phase;
    const my = yearSel === "ALL" || e.target_year  === yearSel;
    return ms && mp && my;
  });

  rows.sort((a, b) => {
    let va = a[state.sort.col] ?? "", vb = b[state.sort.col] ?? "";
    if (typeof va === "string") va = va.toLowerCase();
    if (typeof vb === "string") vb = vb.toLowerCase();
    return va < vb ? (state.sort.dir === "asc" ? -1 :  1)
         : va > vb ? (state.sort.dir === "asc" ?  1 : -1) : 0;
  });

  const total = (state.db?.articles || []).filter(e => !e.radar_only).length;
  if (counter) counter.textContent = `${rows.length} de ${total} registros`;

  if (!rows.length) { tbody.innerHTML = ""; empty?.classList.remove("hidden"); return; }
  empty?.classList.add("hidden");

  const phaseMap = {
    Operational:          { cls: "bg-green-100 text-green-700 border-green-300",   label: "Operativo" },
    "Under Construction": { cls: "bg-amber-100 text-amber-700 border-amber-300",   label: "Construcción" },
    Planned:              { cls: "bg-purple-100 text-purple-700 border-purple-300", label: "Planificado" },
  };
  const riskEmoji = { Beneficioso: "📈", Riesgo: "⚠️", Neutral: "ℹ️" };

  tbody.innerHTML = rows.map(e => {
    const ph      = phaseMap[e.phase] || phaseMap.Planned;
    const emoji   = riskEmoji[e.nivel_riesgo] || "ℹ️";
    const date    = (e.date || "").split("-").reverse().join("/") || "—";
    const iodLive = (e.capacityGw || 0) * factor;
    const yearTag = e.target_year
      ? `<span class="ml-1 px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200 font-mono">${e.target_year}</span>`
      : "";
    const link    = e.link
      ? `<a href="${e.link}" target="_blank" rel="noopener"
             class="text-sqm-purple hover:underline text-xs font-medium">↗ Fuente</a>`
      : `<span class="text-slate-400 text-xs">Manual</span>`;
    const capTag  = e.invest_proxy
      ? `<span class="ml-1 px-1 py-0.5 text-xs bg-amber-50 text-amber-700 border border-amber-200 rounded">CAPEX</span>`
      : "";

    // data-gw enables in-place update by updateLedgerIodine()
    return `<tr class="border-b border-slate-100 hover:bg-slate-50 transition-colors group"
                data-gw="${e.capacityGw || 0}">
      <td class="px-4 py-3">
        <div class="font-semibold text-slate-800 text-sm">${escHtml(e.company)}</div>
        <div class="mt-0.5">${geoTag(e.geo)}</div>
      </td>
      <td class="px-4 py-3">
        <span class="font-bold text-slate-900">${fmt(e.capacityGw, 3)}</span>
        <span class="text-slate-400 text-xs ml-1">GW</span>${capTag}
      </td>
      <td class="px-4 py-3 font-bold text-sqm-purple text-sm">
        <span data-role="iodine-val">${fmt(iodLive, 3)}</span> t
      </td>
      <td class="px-4 py-3 text-sm">
        <div class="text-slate-600">
          <span class="font-semibold text-sqm-purple">PbI₂</span>
          <span data-role="pbi2-val">${fmt(iodLive * RATIOS.pbi2, 3)}</span> t
        </div>
        <div class="text-slate-600">
          <span class="font-semibold text-sqm-green-dark">FAI</span>&nbsp;&nbsp;
          <span data-role="fai-val">${fmt(iodLive * RATIOS.fai, 3)}</span> t
        </div>
      </td>
      <td class="px-4 py-3">
        <span class="px-2 py-0.5 rounded-full text-xs font-semibold border ${ph.cls}">${ph.label}</span>
      </td>
      <td class="px-4 py-3 text-slate-600 text-sm">${date}${yearTag}</td>
      <td class="px-4 py-3 max-w-xs">
        <div class="text-slate-700 text-sm truncate" title="${escHtml(e.title)}">${emoji} ${escHtml(e.title || e.source)}</div>
        <div class="mt-1">${link}</div>
      </td>
      <td class="px-4 py-3 text-center">
        <button onclick="deleteEntry('${e.id}')"
          class="opacity-0 group-hover:opacity-100 p-1.5 rounded text-slate-400
                 hover:text-red-600 hover:bg-red-50 transition-all" title="Eliminar">
          <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
            <path d="M6 19c0 1.1.9 2 2 2h8c1.1 0 2-.9 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/>
          </svg>
        </button>
      </td>
    </tr>`;
  }).join("");
}

// ── Risk Radar ─────────────────────────────────────────────────
function renderRiskRadar() {
  const container = document.getElementById("risk-radar-feed");
  if (!container) return;

  const factor      = getLiveFactor();
  const yearSel     = document.getElementById("timeline_filter")?.value || "ALL";
  const allArticles = state.db?.articles || [];
  let radarItems    = allArticles.filter(e => e.nivel_riesgo && e.resumen_ia);
  if (yearSel !== "ALL") radarItems = radarItems.filter(e => e.target_year === yearSel);

  radarItems.sort((a, b) => {
    const ord = { Riesgo: 0, Beneficioso: 1, Neutral: 2 };
    const oa = ord[a.nivel_riesgo] ?? 3, ob = ord[b.nivel_riesgo] ?? 3;
    return oa !== ob ? oa - ob : (b.date || "").localeCompare(a.date || "");
  });

  if (!radarItems.length) {
    container.innerHTML = `
      <div class="rounded-xl border border-slate-200 bg-white py-12 text-center">
        <div class="text-4xl mb-3">🔬</div>
        <p class="text-slate-500 font-medium">Sin análisis disponible</p>
        <p class="text-slate-400 text-sm mt-1">
          Inicia el agente con <code class="font-mono text-sqm-purple">py scout_agent.py</code>
        </p>
      </div>`;
    return;
  }

  const cfg = {
    Beneficioso: { badge: "bg-green-100 text-green-700 border-green-300",  card: "border-l-4 border-l-sqm-green", icon: "📈" },
    Riesgo:      { badge: "bg-red-100 text-red-700 border-red-300",        card: "border-l-4 border-l-red-500",   icon: "⚠️" },
    Neutral:     { badge: "bg-slate-100 text-slate-600 border-slate-300",  card: "border-l-4 border-l-slate-400", icon: "ℹ️" },
  };

  container.innerHTML = radarItems.map(e => {
    const c       = cfg[e.nivel_riesgo] || cfg.Neutral;
    const date    = (e.date || "").split("-").reverse().join("/") || "—";
    const iodLive = (e.capacityGw || 0) * factor;
    const capInfo = (e.capacityGw || 0) > 0
      ? `<span class="font-mono text-sqm-purple font-semibold">${fmt(e.capacityGw, 3)} GW</span>
         <span class="text-slate-400 mx-1">→</span>
         <span class="font-mono font-semibold" style="color:#5B2C86">
           <span data-role="radar-iodine">${fmt(iodLive, 3)}</span> Ton Yodo
         </span>`
      : `<span class="text-slate-400 text-xs italic">Sin nueva capacidad anunciada</span>`;

    const yearTag = e.target_year
      ? `<span class="px-1.5 py-0.5 rounded text-xs bg-blue-50 text-blue-700 border border-blue-200 font-mono">${e.target_year}</span>`
      : "";
    const capexBadge = e.invest_proxy
      ? `<span class="px-1.5 py-0.5 rounded text-xs bg-amber-50 text-amber-700 border border-amber-200">💰 CAPEX proxy</span>`
      : "";
    const src = e.link
      ? `<a href="${e.link}" target="_blank" rel="noopener"
             class="text-sqm-purple hover:underline text-xs font-medium">↗ Ver artículo</a>`
      : "";

    // data-radar-gw enables in-place update by updateRadarIodine()
    return `
      <article class="flex rounded-xl border border-slate-200 bg-white shadow-sm
                      ${c.card} hover:shadow-md transition-all overflow-hidden"
               data-radar-gw="${e.capacityGw || 0}">
        <div class="flex-1 p-4">
          <div class="flex flex-wrap items-center justify-between gap-2 mb-2">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="px-2.5 py-0.5 rounded-full text-xs font-bold border ${c.badge}">
                ${c.icon} ${e.nivel_riesgo}
              </span>
              <span class="text-sm font-bold text-slate-800">${escHtml(e.company)}</span>
              ${geoTag(e.geo)}
              ${yearTag}
              ${capexBadge}
              <span class="text-slate-400 text-xs">· ${date}</span>
            </div>
            <div class="text-xs flex items-center gap-1">${capInfo}</div>
          </div>
          <h3 class="text-sm font-semibold text-slate-800 leading-snug mb-2 line-clamp-2">
            ${escHtml(e.title || e.source)}
          </h3>
          <div class="rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
            <p class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1">
              Análisis — Perspectiva Demanda Yodo SQM
            </p>
            <p class="text-sm text-slate-700 leading-relaxed">${escHtml(e.resumen_ia)}</p>
          </div>
          ${src ? `<div class="mt-2">${src}</div>` : ""}
        </div>
      </article>`;
  }).join("");
}

// ── Offline State ──────────────────────────────────────────────
function renderOfflineState() {
  const radar = document.getElementById("risk-radar-feed");
  if (radar) {
    radar.innerHTML = `
      <div class="rounded-xl border border-slate-200 bg-white py-12 text-center">
        <div class="text-4xl mb-3">🔌</div>
        <p class="text-slate-600 font-medium">Agente no disponible</p>
        <p class="text-slate-400 text-sm mt-1">Ejecuta: <code class="font-mono text-sqm-purple">py scout_agent.py</code></p>
        ${state.fetchError ? `<p class="text-red-400 text-xs mt-2 font-mono">${escHtml(state.fetchError)}</p>` : ""}
      </div>`;
  }
}

// ── Table Controls ─────────────────────────────────────────────
function setupTableControls() {
  document.getElementById("search-input")?.addEventListener("input", renderTable);
  document.getElementById("filter-phase")?.addEventListener("change", renderTable);
  
  // Interactive sorting on headers
  document.querySelectorAll("th[data-sort]").forEach(th => {
    th.addEventListener("click", () => {
      const col = th.dataset.sort;
      if (state.sort.col === col) {
        state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
      } else {
        state.sort.col = col;
        state.sort.dir = "asc"; // Default starting dir
        if (col === "date" || col === "capacityGw") state.sort.dir = "desc";
      }
      renderTable();
    });
  });
}

window.sortTable = col => {
  state.sort = state.sort.col === col
    ? { col, dir: state.sort.dir === "asc" ? "desc" : "asc" }
    : { col, dir: "desc" };
  renderTable();
};

window.deleteEntry = id => {
  if (!confirm("¿Eliminar este registro?") || !state.db) return;
  state.db.articles = state.db.articles.filter(e => e.id !== id);
  const cap  = state.db.articles.filter(e => !e.radar_only);
  const tGw  = cap.reduce((s, e) => s + (e.capacityGw    || 0), 0);
  const tIod = cap.reduce((s, e) => s + (e.iodineDemand  || 0), 0);
  Object.assign(state.db.meta, {
    total_gw:          +tGw.toFixed(4),
    total_iodine_ton:  +tIod.toFixed(4),
    total_pbi2_ton:    +(tIod * 0.60).toFixed(4),
    total_fai_ton:     +(tIod * 0.20).toFixed(4),
    total_mai_ton:     +(tIod * 0.10).toFixed(4),
    total_csi_ton:     +(tIod * 0.10).toFixed(4),
    article_count:     state.db.articles.length,
    unique_companies:  new Set(cap.map(e => e.company)).size,
  });
  render();
  showToast("Eliminado", "Registro removido.", "info");
};

// ── Manual Form ────────────────────────────────────────────────
function setupManualForm() {
  document.getElementById("manual-form")?.addEventListener("submit", async ev => {
    ev.preventDefault();
    const payload = {
      company:       document.getElementById("m-company").value,
      capacityValue: parseFloat(document.getElementById("m-capacity").value) || 0,
      capacityUnit:  document.getElementById("m-unit").value,
      phase:         document.getElementById("m-phase").value,
      nivel_riesgo:  document.getElementById("m-risk").value,
      date:          document.getElementById("m-date").value,
      source:        document.getElementById("m-source").value,
      notes:         document.getElementById("m-notes").value,
    };
    try {
      const res = await fetch(`${API_BASE}/api/entries`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify(payload),
      });
      if (res.ok) {
        showToast("Guardado", `Entrada de ${payload.company} añadida.`, "success");
        ev.target.reset();
        document.getElementById("m-date").value = new Date().toISOString().split("T")[0];
        loadAndRender();
      } else {
        const err = await res.json().catch(() => ({}));
        showToast("Error del servidor", err.error || `HTTP ${res.status}`, "error");
      }
    } catch(e) {
      showToast("Sin conexión", "Inicia scout_agent.py.", "error");
    }
  });
}

// ── CSV Export ─────────────────────────────────────────────────
window.exportCSV = () => {
  const articles = state.db?.articles || [];
  if (!articles.length) { showToast("Sin datos", "Nada que exportar.", "error"); return; }
  const hdrs = ["Empresa","País","Continente","Cap.GW","Yodo Total","PbI2","FAI","MAI","CsI",
                "Fase","Nivel Riesgo","Año Objetivo","CAPEX Proxy","Resumen IA","Fecha","Fuente","Enlace"];
  const ph = { Operational:"Operativo","Under Construction":"En Construccion",Planned:"Planificado" };
  const rows = articles.map(e => [
    e.company, e.geo?.country || "—", e.geo?.continent || "—",
    e.capacityGw, e.iodineDemand, e.pbi2, e.fai, e.mai, e.csi,
    ph[e.phase] || e.phase, e.nivel_riesgo || "Neutral",
    e.target_year || "—", e.invest_proxy ? "Sí" : "No",
    (e.resumen_ia || "").replace(/;/g,","),
    e.date, (e.title || e.source).replace(/;/g,","), e.link
  ]);
  const csv = ["sep=;", hdrs.join(";"),
    ...rows.map(r => r.map(v => `"${String(v ?? "").replace(/"/g,'""')}"`).join(";"))
  ].join("\r\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
  const url  = URL.createObjectURL(blob);
  const a    = Object.assign(document.createElement("a"), {
    href: url, download: `SQM_Perovskita_${new Date().toISOString().slice(0,10)}.csv`,
  });
  document.body.appendChild(a); a.click(); document.body.removeChild(a);
  URL.revokeObjectURL(url);
  showToast("Exportado", "CSV listo para Excel (BOM UTF-8).", "success");
};

// ── Toast ──────────────────────────────────────────────────────
function showToast(title, msg, type = "success") {
  const border = { success: "border-green-400", error: "border-red-400", info: "border-blue-400" }[type];
  const icon   = {
    success: `<svg class="w-5 h-5 text-green-600 flex-shrink-0" fill="currentColor" viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`,
    error:   `<svg class="w-5 h-5 text-red-600 flex-shrink-0"   fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-2h2v2zm0-4h-2V7h2v6z"/></svg>`,
    info:    `<svg class="w-5 h-5 text-blue-600 flex-shrink-0"  fill="currentColor" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm1 15h-2v-6h2v6zm0-8h-2V7h2v2z"/></svg>`,
  }[type];
  const t = document.createElement("div");
  t.className = `flex items-start gap-3 min-w-72 max-w-sm px-4 py-3 rounded-xl border ${border}
    bg-white shadow-xl text-slate-800 translate-y-4 opacity-0 transition-all duration-300 pointer-events-auto`;
  t.innerHTML = `${icon}
    <div class="flex-1 min-w-0">
      <p class="font-semibold text-sm">${escHtml(title)}</p>
      <p class="text-xs text-slate-500 mt-0.5">${escHtml(msg)}</p>
    </div>
    <button onclick="this.parentElement.remove()" class="text-slate-300 hover:text-slate-600 text-lg leading-none">&times;</button>`;
  document.getElementById("toast-area")?.appendChild(t);
  requestAnimationFrame(() => t.classList.remove("translate-y-4","opacity-0"));
  setTimeout(() => { t.classList.add("opacity-0","translate-y-4"); setTimeout(()=>t.remove(),300); }, 5500);
}

// ── Utilities ──────────────────────────────────────────────────
function fmt(v, d = 2)  { return (typeof v === "number" && isFinite(v)) ? v.toFixed(d) : "—"; }
function setText(id, v) { const el = document.getElementById(id); if (el) el.textContent = v ?? "—"; }
function escHtml(s) {
  return String(s ?? "")
    .replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")
    .replace(/"/g,"&quot;").replace(/'/g,"&#39;");
}
