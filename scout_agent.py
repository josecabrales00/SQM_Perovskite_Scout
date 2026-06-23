"""
SQM Perovskite Scout — Agent v6.0  (Supabase Integration)
=========================================================
Arquitectura: procesamiento 100% local (regex) + informe ejecutivo REST/SSL bypass.
v6.0: Escritura dual — database.json (cache local) + Supabase Postgres (analytics).
CONFIGURACIÓN DE API — pon tu clave aquí:
"""

# ─────────────────────────────────────────────────────────────────
#   ⚙️  PON AQUÍ TU CLAVE DE GOOGLE AI STUDIO
#   Obtén una gratis en: https://aistudio.google.com/apikey
# ─────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("GEMINI_API_KEY", "")
# ─────────────────────────────────────────────────────────────────

import json
import re
import time
import math
import difflib
import threading
import os
import sys
import logging
import requests
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import quote_plus

try:
    from googlesearch import search
except ImportError:
    search = None

# ── Silenciar InsecureRequestWarning del proxy corporativo (SSL MITM) ──
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

# ── Logging ────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("SQM")

# ── .env Loader (credenciales backend — nunca en el cliente) ────
def _load_dotenv() -> dict:
    """Lee el archivo .env del directorio del proyecto."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

_DOTENV = _load_dotenv()

# ── Supabase config (solo backend — regla AGENTS.md) ───────────
SUPABASE_URL      = _DOTENV.get("SUPABASE_URL", os.environ.get("SUPABASE_URL", "")).rstrip("/")
SUPABASE_SRK      = _DOTENV.get("SUPABASE_SERVICE_ROLE_KEY",
                                  os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
SUPABASE_ENABLED  = bool(SUPABASE_URL and SUPABASE_SRK)
_SB_HEADERS = {
    "apikey":        SUPABASE_SRK,
    "Authorization": f"Bearer {SUPABASE_SRK}",
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
} if SUPABASE_ENABLED else {}

# ── Resolve API key ────────────────────────────────────────────
_RESOLVED_KEY = (
    os.environ.get("GEMINI_API_KEY", "").strip()
    or API_KEY.strip()
)
LLM_ENABLED = bool(_RESOLVED_KEY)

# ── Constants ──────────────────────────────────────────────────
IODINE_PER_GW      = 4.73
RATIOS             = {"pbi2": 0.60, "fai": 0.20, "mai": 0.10, "csi": 0.10}
SCAN_INTERVAL_SEC  = 3600
DB_FILE            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.json")
HTTP_PORT          = 8080
CURRENT_YEAR       = str(datetime.now().year)   # e.g. "2026"

# ── Gemini REST endpoints (requests only — no SDK) ────────────
# Primary: gemini-3.1-flash-lite (capa gratuita 2026)
GEMINI_ENDPOINTS = [
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}",
]

# ── Hybrid Brain System Prompt ────────────────────────────────
HYBRID_SYSTEM_PROMPT = (
    "Eres un Analista de Inteligencia Comercial Experto para SQM Perovskite Scout. "
    "Tu objetivo es rastrear la web en busca de anuncios de nuevas plantas solares y "
    "responder preguntas técnicas sobre celdas de perovskita.\n\n"
    "REGLA DE CITAS (Grounding Estricto): Tienes terminantemente prohibido inventar datos. "
    "Si extraes información de la base de datos (buscar_docs), debes citar el documento "
    "de origen exacto (ej: '[Fuente: doc_perovskita.pdf]'). Si extraes de internet "
    "(buscar_web), cita obligatoriamente la URL (ej: '[Fuente: https://solarnews.com/...]').\n\n"
    "Flujo de Resolución:\n"
    "1. Siempre usa primero 'buscar_docs' para buscar conocimiento interno corporativo.\n"
    "2. Si la información no está o es insuficiente, usa 'buscar_web' para buscar en internet.\n"
    "3. Si detectas un anuncio de una nueva planta comercial, usa 'insertar_lead' para registrarlo. "
    "Aplica matemáticamente la regla de 4.73 toneladas métricas de yodo por cada 1 GW instalado.\n\n"
    "Genera una respuesta en español, clara, ejecutiva y profesional."
)

# ── Executive Market Report Prompt ────────────────────────────
EXECUTIVE_REPORT_SYSTEM_PROMPT = (
    "Eres el Analista Estratégico Jefe de inteligencia de mercado en SQM. "
    "Redacta un informe ejecutivo completo, exhaustivo y sin límite de extensión "
    "(usa todo el espacio que necesites, incluso una plana entera) sobre el mercado "
    "de celdas solares de perovskita y su impacto en la demanda global de Yodo. "
    "Estructura obligatoria: "
    "1. Panorama General del Mercado: Estado actual de la tecnología, barreras, "
    "celdas tándem y el rol fundamental del Yodo. "
    "2. Análisis de Eventos Recientes: Analiza las noticias que te estoy entregando. "
    "Si hay un evento disruptivo (ej. nuevas inversiones, eficiencias récord, GW construidos), "
    "destácalo y explica cómo cambia las reglas del juego. Si no hay nada disruptivo, "
    "integra las noticias para confirmar las tendencias actuales. "
    "3. Apreciaciones Objetivas y Cifras: Incluye fechas, volúmenes de GW, y proyecta "
    "de forma directa y financiera el impacto futuro en las toneladas de Yodo. "
    "Usa un tono corporativo, experto y certero."
)

# ── Company Dictionary ─────────────────────────────────────────
COMPANIES = [
    "UtmoLight", "Renshine Solar", "Oxford PV", "CNNC", "CNNP",
    "BOE", "GCL", "Microquanta", "Caelux", "Sekisui Chemical",
    "Photon Crystal Energy", "Mellow Energy",
]

# ── Geographic Dictionary (static) ────────────────────────────
GEO_MAP: dict[str, dict] = {
    "Caelux":             {"country": "USA",    "continent": "Norteamérica"},
    "Saule Technologies": {"country": "Polonia", "continent": "Europa"},
    "Oxford PV":          {"country": "UK",      "continent": "Europa"},
    "CNNC":               {"country": "China",   "continent": "Asia"},
    "CNNP":               {"country": "China",   "continent": "Asia"},
    "BOE":                {"country": "China",   "continent": "Asia"},
    "GCL":                {"country": "China",   "continent": "Asia"},
    "Microquanta":        {"country": "China",   "continent": "Asia"},
    "UtmoLight":          {"country": "China",   "continent": "Asia"},
    "Renshine Solar":     {"country": "China",   "continent": "Asia"},
    "Photon Crystal Energy": {"country": "China","continent": "Asia"},
    "Mellow Energy":      {"country": "China",   "continent": "Asia"},
    "Sekisui Chemical":   {"country": "Japón",   "continent": "Asia"},
}
GEO_DEFAULT = {"country": "Desconocido", "continent": "Global"}

def geo_lookup(company: str) -> dict:
    return GEO_MAP.get(company, GEO_DEFAULT)

# ── RSS Sources ────────────────────────────────────────────────
def build_feed_urls():
    base = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
    urls = [
        {"url": "https://perovskite-info.com/rss.xml",                              "label": "Perovskite-Info"},
        {"url": base.format(q=quote_plus("perovskite solar GW MW production")),     "label": "GNews-Capacity"},
        {"url": base.format(q=quote_plus("perovskite solar factory gigawatt")),     "label": "GNews-Factory"},
        {"url": base.format(q=quote_plus("perovskite investment million funding")), "label": "GNews-Finance"},
    ]
    for co in COMPANIES:
        urls.append({"url": base.format(q=quote_plus(f"{co} perovskite")), "label": f"GNews-{co}"})
    return urls

FEED_URLS = build_feed_urls()

# ── Regex: capacity ────────────────────────────────────────────
_CAP_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(gw|gwp|gigawat\w*|gigavatio\w*|mw|mwp|megawat\w*|megavatio\w*)",
    re.IGNORECASE,
)

# ── Regex: investment / financial proxy ────────────────────────
# Matches: "$10 million", "100M USD", "€50 million", "£200M", "500 million dollars"
_INVEST_RE = re.compile(
    r"(?:[\$€£¥])?\s*(\d+(?:[.,]\d+)?)\s*"
    r"(?:M\b|million|billion|B\b|bn\b)(?:\s*(?:USD|EUR|GBP|dollars?|euros?))?",
    re.IGNORECASE,
)
# Keywords that must appear within 50 chars of the money figure
# to qualify as a CAPEX/project investment (not a corporate funding round)
_CAPEX_CONTEXT_RE = re.compile(
    r"\b(factory|plant|facility|manufacturing|capacity|production.line|module.line|fab\b)",
    re.IGNORECASE,
)
# CAPEX proxy: $100M = 1 GW  → each $1M = 0.01 GW
CAPEX_GW_PER_MILLION = 0.01
CAPEX_MAX_GW         = 5.0   # hard cap per article to prevent inflation

def regex_investment_gw(text: str) -> float:
    """
    Converts a financial investment figure to proxy GW ONLY when a facility-
    context keyword (factory, plant, etc.) appears within 50 characters of
    the money figure. Capped at CAPEX_MAX_GW to prevent data inflation.
    Returns 0.0 if context guard fails.
    """
    m = _INVEST_RE.search(text)
    if not m:
        return 0.0

    # ── Context guard: require facility keyword within 50 chars ──
    start = max(0, m.start() - 50)
    end   = min(len(text), m.end() + 50)
    window = text[start:end]
    if not _CAPEX_CONTEXT_RE.search(window):
        return 0.0

    raw = float(m.group(1).replace(",", ""))
    span_text = m.group(0).lower()
    if "billion" in span_text or span_text.strip().endswith("b") or "bn" in span_text:
        raw_millions = raw * 1000
    else:
        raw_millions = raw

    gw = raw_millions * CAPEX_GW_PER_MILLION
    return round(min(gw, CAPEX_MAX_GW), 4)

# ── Regex: phase & sentiment ───────────────────────────────────
_PHASE_OP  = re.compile(r"inaugur|commission|operational|mass.produc|production.start|en.marcha", re.I)
_PHASE_CON = re.compile(r"under.construct|en.construcci|groundbreak|building", re.I)
_KW_GOOD   = re.compile(r"produc|manufactur|commerci|factory|gigawatt|megawatt|plant|line|facility|invest|fund", re.I)
_KW_BAD    = re.compile(r"lead.free|tin.based|without.iodine|no.iodine|cancel|stability.issue|recall", re.I)

# ── Regex: target year (EXPANDED — any 2024-2035) ──────────────
_YEAR_RE = re.compile(
    r"(?:by|in|until|for|target(?:ing)?|by\s+end\s+of|expected\s+(?:in|by)|planned\s+for|goal\s+(?:of|for))?"
    r"\s*(20[2-3]\d)\b",
    re.IGNORECASE,
)

def regex_capacity(text: str) -> float:
    m = _CAP_RE.search(text)
    if not m:
        return 0.0
    val = float(m.group(1).replace(",", "."))
    return val if m.group(2).lower().startswith("g") else val / 1000.0

def regex_phase(text: str) -> str:
    if _PHASE_OP.search(text):  return "Operational"
    if _PHASE_CON.search(text): return "Under Construction"
    return "Planned"

def keyword_sentiment(text: str) -> str:
    if _KW_BAD.search(text):  return "Riesgo"
    if _KW_GOOD.search(text): return "Beneficioso"
    return "Neutral"

def regex_target_year(text: str, fallback: str = CURRENT_YEAR) -> str:
    """
    Extract the earliest year in range 2024–2039 from text.
    Falls back to `fallback` (default: current year) if none found.
    """
    years = _YEAR_RE.findall(text)
    if not years:
        return fallback
    return str(min(int(y) for y in years))

# ── Iodine Math ────────────────────────────────────────────────
def calc_iodine(gw: float) -> dict:
    total = round(gw * IODINE_PER_GW, 4)
    return {
        "iodineDemand": total,
        "pbi2":  round(total * RATIOS["pbi2"], 4),
        "fai":   round(total * RATIOS["fai"],  4),
        "mai":   round(total * RATIOS["mai"],  4),
        "csi":   round(total * RATIOS["csi"],  4),
    }

# ── Anti-duplicates engine (difflib) ──────────────────────────
def is_duplicate(new_entry: dict, existing_entries: list[dict]) -> bool:
    """
    Returns True if new_entry duplicates any existing entry.
    Criteria (any one triggers dedup):
      1. Title similarity >= 80% (SequenceMatcher)
      2. Same company + same capacityGw (non-zero, exact float)
      3. Same company + both are CAPEX-proxy articles (prevents stacking
         multiple financial news items as independent GW sources)
    """
    new_title   = (new_entry.get("title") or "").lower().strip()
    new_co      = new_entry.get("company", "")
    new_gw      = new_entry.get("capacityGw", 0.0)
    new_is_capex = new_entry.get("invest_proxy", False)

    for ex in existing_entries:
        ex_title = (ex.get("title") or "").lower().strip()

        # Criterion 1: title similarity
        ratio = difflib.SequenceMatcher(None, new_title, ex_title).ratio()
        if ratio >= 0.80:
            log.debug("Dedup (título %.0f%%): %s", ratio * 100, new_title[:60])
            return True

        # Criterion 2: same company + identical GW (non-zero)
        if (new_gw > 0
                and new_co == ex.get("company", "")
                and abs(new_gw - ex.get("capacityGw", -1)) < 1e-6):
            log.debug("Dedup (empresa+GW): %s %.4f GW", new_co, new_gw)
            return True

        # Criterion 3: same company + both are CAPEX-proxy entries
        # (avoids stacking multiple financial articles for the same firm)
        if (new_is_capex
                and ex.get("invest_proxy", False)
                and new_co == ex.get("company", "")):
            log.debug("Dedup (CAPEX repeat): %s", new_co)
            return True

    return False

# ── Executive Market Report Generator ─────────────────────────
def generate_market_report(articles: list[dict]) -> str:
    """
    REST call to Gemini with verify=False (SSL MITM bypass).
    Tries GEMINI_ENDPOINTS in order (primary flash-latest, fallback gemini-pro).
    Returns diagnostic 'ERROR FATAL API: ...' string on failure so the
    frontend can display it for triage.
    """
    if not LLM_ENABLED:
        log.info("Informe ejecutivo omitido — LLM deshabilitado.")
        return "Informe en proceso de generación"

    try:
        import requests
    except ImportError:
        return "ERROR FATAL API: requests no instalado"

    # ── Build context (Optimized Payload) ──────────────────────
    # Limitar a las 15 más recientes y enviar JSON compacto sin 'summary'
    # para evitar sobrepasar los tokens de la capa gratuita (Error 429).
    sorted_articles = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
    top_articles = []
    for art in sorted_articles[:15]:
        top_articles.append({
            "date": art.get("date", ""),
            "company": art.get("company", ""),
            "capacityGw": round(art.get("capacityGw", 0), 3),
            "target_year": art.get("target_year", CURRENT_YEAR),
            "title": (art.get("title") or "")[:150]
        })
    news_context = json.dumps(top_articles, indent=2, ensure_ascii=False) if top_articles else "[]"

    full_prompt = (
        f"{EXECUTIVE_REPORT_SYSTEM_PROMPT}\n\n"
        f"NOTICIAS RECOPILADAS HOY:\n{news_context}"
    )
    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 8192},
    }

    # ── Try each endpoint in order ────────────────────────────
    last_error = "ERROR FATAL API: ningún endpoint respondió"
    for endpoint_tpl in GEMINI_ENDPOINTS:
        url = endpoint_tpl.format(key=_RESOLVED_KEY)
        model_name = url.split("/models/")[1].split(":")[0]
        try:
            log.info("Intentando Gemini endpoint: %s", model_name)
            resp = requests.post(url, json=payload, verify=False, timeout=120)

            # 404 → model not found → try next endpoint
            if resp.status_code == 404:
                log.warning("Endpoint %s → 404, probando siguiente...", model_name)
                continue

            # Other HTTP errors → unmask and return diagnostic
            if not resp.ok:
                try:
                    err_json = resp.json()
                    reason = (
                        err_json.get("error", {}).get("message")
                        or err_json.get("error", {}).get("status")
                        or resp.reason or "Sin detalle"
                    )
                except Exception:
                    reason = resp.reason or "Sin detalle"
                last_error = f"ERROR FATAL API: {resp.status_code} — {reason}"
                log.error("Informe Ejecutivo (%s): %s", model_name, last_error)
                # Non-404 errors (e.g. 400 bad key) are not retried
                return last_error

            data = resp.json()
            report_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            log.info("✓ Informe Ejecutivo [%s] — %d caracteres.", model_name, len(report_text))
            return report_text

        except Exception as e:
            last_error = f"ERROR FATAL API: {type(e).__name__} — {str(e)[:200]}"
            log.warning("Informe Ejecutivo (%s) excepción: %s", model_name, last_error)
            continue   # try next endpoint

    log.error("Todos los endpoints de Gemini fallaron.")
    return last_error

# ── RSS Fetch ──────────────────────────────────────────────────
def fetch_feed(feed: dict) -> list[dict]:
    try:
        import feedparser, requests
        try:
            r = requests.get(feed["url"], timeout=15,
                             headers={"User-Agent": "SQM-Scout/5.2"})
        except requests.exceptions.SSLError:
            r = requests.get(feed["url"], timeout=15, verify=False,
                             headers={"User-Agent": "SQM-Scout/5.2"})
        r.raise_for_status()
        parsed = feedparser.parse(r.content)
    except Exception as e:
        log.debug("Feed '%s' falló: %s", feed["label"], e)
        return []

    items = []
    for e in parsed.entries:
        title   = getattr(e, "title",    "") or ""
        summary = getattr(e, "summary",  "") or ""
        link    = getattr(e, "link",     "") or ""
        pub     = getattr(e, "published","") or ""
        items.append({
            "title":    title,
            "summary":  summary[:700],
            "link":     link,
            "pub_raw":  pub,
            "source":   feed["label"],
            "full_text":f"{title} {summary}",
        })
    log.info("  ✓ %-40s %3d", feed["label"], len(items))
    return items

# ── Company pre-filter ────────────────────────────────────────
def detect_company(text: str) -> str | None:
    for co in sorted(COMPANIES, key=len, reverse=True):
        pattern = re.escape(co).replace(r"\ ", r"\s*")
        if re.search(pattern, text, re.IGNORECASE):
            return co
    return None

# ── Parse pub date ─────────────────────────────────────────────
def parse_date(pub_raw: str) -> str:
    if not pub_raw:
        return ""
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(pub_raw).strftime("%Y-%m-%d")
    except Exception:
        return pub_raw[:10]

# ── Main Analysis — 100% Local (Regex) + Dedup + Geo ──────────
def analyse(raw_articles: list[dict]) -> list[dict]:
    """
    v5.2:
      - Expanded year regex with current-year fallback
      - Financial CAPEX proxy when no explicit GW found
      - Geo-tagging from static GEO_MAP
      - Company-level consolidation: if an article has a year but no GW,
        and the same company already has a GW article without a year,
        the year propagates forward in build_database().
      - Anti-duplicates via difflib
    """
    seen: set = set()
    candidates = []
    for art in raw_articles:
        link = art["link"]
        if not link or link in seen:
            continue
        co = detect_company(art["full_text"])
        if not co:
            continue
        seen.add(link)
        art["pre_company"] = co
        candidates.append(art)

    log.info("Pre-filtro: %d artículos candidatos de %d totales.",
             len(candidates), len(raw_articles))

    entries    = []
    dedup_count = 0

    for art in candidates:
        title    = art["title"]
        content  = art["summary"]
        link     = art["link"]
        company  = art["pre_company"]
        pub_date = parse_date(art["pub_raw"])
        full     = art["full_text"]

        # ── Capacity: explicit GW/MW first, then financial proxy ──
        cap_gw = regex_capacity(full)
        invest_proxy = 0.0
        if cap_gw == 0.0:
            invest_proxy = regex_investment_gw(full)
            cap_gw = invest_proxy

        phase       = regex_phase(full)
        riesgo      = keyword_sentiment(full)
        target_year = regex_target_year(full)   # uses CURRENT_YEAR as fallback
        geo         = geo_lookup(company)

        resumen = (
            f"Análisis local — Empresa: {company} ({geo['country']}). "
            f"Capacidad: {cap_gw:.3f} GW"
            + (f" (proxy CAPEX ${invest_proxy/CAPEX_GW_PER_MILLION:.0f}M)" if invest_proxy > 0 else "")
            + f". Fase: {phase}. Nivel: {riesgo}. Año objetivo: {target_year}."
        )

        iodine     = calc_iodine(cap_gw)
        radar_only = (cap_gw == 0.0)
        unit       = "GW" if cap_gw >= 0.5 else "MW"
        disp_v     = cap_gw if unit == "GW" else round(cap_gw * 1000, 1)
        cache_key  = str(abs(hash(link)) % 10**12)

        candidate_entry = {
            "id":            f"a-{cache_key}",
            "company":       company,
            "capacityValue": disp_v,
            "capacityUnit":  unit,
            "capacityGw":    cap_gw,
            **iodine,
            "phase":         phase,
            "nivel_riesgo":  riesgo,
            "resumen_ia":    resumen,
            "target_year":   target_year,
            "invest_proxy":  invest_proxy > 0,   # flag: True if GW came from CAPEX
            "geo":           geo,
            "llm_used":      False,
            "radar_only":    radar_only,
            "date":          pub_date,
            "source":        art["source"],
            "title":         title[:160],
            "link":          link,
            "summary":       content[:300],
        }

        if is_duplicate(candidate_entry, entries):
            dedup_count += 1
            continue

        entries.append(candidate_entry)

    log.info(
        "Análisis local: %d artículos (%d con cap, %d solo-radar, %d CAPEX-proxy, %d dedup).",
        len(entries),
        sum(1 for e in entries if not e["radar_only"]),
        sum(1 for e in entries if e["radar_only"]),
        sum(1 for e in entries if e.get("invest_proxy")),
        dedup_count,
    )

    # ── Company-level consolidation: propagate target_year across articles ──
    return consolidate_by_company(entries)


def consolidate_by_company(entries: list[dict]) -> list[dict]:
    """
    For each company, find the best target_year (non-default) and best capacity.
    Articles that have a year but no GW get the company's best GW, and vice-versa.
    This fixes the filter de-coupling bug: filtering by year now returns capacity data.

    CAPEX inflation guard (v5.5 — Regla de Hierro #3):
      If a company has multiple CAPEX-proxy articles, the TOTAL proxy GW attributed
      to that company is capped at CAPEX_COMPANY_MAX_GW. Articles whose cumulative
      sum would exceed this cap have their capacityGw (and iodine fields) zeroed out
      and are demoted to radar-only, preventing GW stack inflation.
    """
    CAPEX_COMPANY_MAX_GW = 10.0  # hard cap per company for CAPEX-proxy totals

    # Pass 1: gather best year per company
    co_best_year: dict[str, str] = {}
    for e in entries:
        co   = e["company"]
        yr   = e.get("target_year", CURRENT_YEAR)
        prev = co_best_year.get(co, CURRENT_YEAR)
        if yr != CURRENT_YEAR and (prev == CURRENT_YEAR or int(yr) < int(prev)):
            co_best_year[co] = yr

    # Pass 2: propagate best year to articles still on the fallback year
    for e in entries:
        co = e["company"]
        if co in co_best_year and e.get("target_year") == CURRENT_YEAR:
            e["target_year"] = co_best_year[co]

    # Pass 3: enforce company-level CAPEX cap
    # Count accumulated proxy GW per company; zero out articles that overflow.
    co_proxy_gw: dict[str, float] = {}
    for e in entries:
        if not e.get("invest_proxy"):
            continue
        co        = e["company"]
        art_gw    = e.get("capacityGw", 0.0)
        accrued   = co_proxy_gw.get(co, 0.0)
        remaining = max(CAPEX_COMPANY_MAX_GW - accrued, 0.0)

        if remaining <= 0:
            # Company already at cap — demote this article to radar-only
            log.debug("CAPEX company cap: %s — artículo zeroed (acum %.2f GW)", co, accrued)
            e["capacityGw"]    = 0.0
            e["capacityValue"] = 0.0
            e["capacityUnit"]  = "GW"
            e["radar_only"]    = True
            iodine_zero = calc_iodine(0.0)
            e.update(iodine_zero)
        else:
            allowed_gw = min(art_gw, remaining)
            if allowed_gw < art_gw:
                log.debug("CAPEX company cap: %s — GW recortado %.4f→%.4f", co, art_gw, allowed_gw)
                e["capacityGw"]    = allowed_gw
                e["capacityValue"] = allowed_gw if e["capacityUnit"] == "GW" else round(allowed_gw * 1000, 1)
                iodine_adjusted = calc_iodine(allowed_gw)
                e.update(iodine_adjusted)
                e["radar_only"]  = (allowed_gw == 0.0)
            co_proxy_gw[co] = accrued + allowed_gw

    return entries


# ── Build & Merge Database ─────────────────────────────────────
def build_database(new_entries: list[dict], market_report: str = "") -> dict:
    manual = []
    existing_report = ""
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, encoding="utf-8") as f:
                old = json.load(f)
            manual = [e for e in old.get("articles", [])
                     if str(e.get("id", "")).startswith("manual-")]
            existing_report = old.get("market_report", "")
        except Exception:
            pass

    merged = {e["id"]: e for e in new_entries}
    for m in manual:
        merged[m["id"]] = m

    all_entries = sorted(merged.values(),
                         key=lambda x: x.get("date", ""), reverse=True)

    cap_entries = [e for e in all_entries if not e.get("radar_only", False)]
    total_gw    = round(sum(e["capacityGw"]   for e in cap_entries), 4)
    total_iod   = round(sum(e["iodineDemand"] for e in cap_entries), 4)

    risk_counts = {"Beneficioso": 0, "Riesgo": 0, "Neutral": 0}
    for e in all_entries:
        r = e.get("nivel_riesgo", "Neutral")
        risk_counts[r] = risk_counts.get(r, 0) + 1

    # Collect sorted unique target years for the timeline filter
    all_years = sorted({
        e.get("target_year", "")
        for e in all_entries
        if e.get("target_year") and e.get("target_year") != CURRENT_YEAR
    } | {
        e.get("target_year", "")
        for e in all_entries
        if e.get("target_year") == CURRENT_YEAR
    })
    all_years = sorted(filter(None, all_years))

    final_report = market_report if market_report else existing_report

    return {
        "meta": {
            "last_updated":      datetime.now(timezone.utc).isoformat(),
            "total_gw":          total_gw,
            "total_iodine_ton":  total_iod,
            "total_pbi2_ton":    round(total_iod * RATIOS["pbi2"], 4),
            "total_fai_ton":     round(total_iod * RATIOS["fai"],  4),
            "total_mai_ton":     round(total_iod * RATIOS["mai"],  4),
            "total_csi_ton":     round(total_iod * RATIOS["csi"],  4),
            "unique_companies":  len({e["company"] for e in cap_entries}),
            "article_count":     len(all_entries),
            "capacity_count":    len(cap_entries),
            "iodine_per_gw":     IODINE_PER_GW,
            "risk_counts":       risk_counts,
            "llm_enabled":       LLM_ENABLED,
            "target_years":      all_years,
        },
        "companies":     COMPANIES,
        "articles":      all_entries,
        "market_report": final_report,
    }

# ── Atomic Write ───────────────────────────────────────────────
def write_database(db: dict):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_FILE)
    m = db["meta"]
    log.info("database.json — %d art | %.3f GW | %.3f Ton I | LLM:%s | Anos:%s",
             m["article_count"], m["total_gw"], m["total_iodine_ton"],
             "ON" if m["llm_enabled"] else "OFF",
             ",".join(m.get("target_years", [])) or "-")


# ── Supabase Sync ──────────────────────────────────────
def sync_to_supabase(db: dict):
    """
    Sincroniza todos los artículos al warehouse Postgres en Supabase.
    Estrategia: DELETE de filas autogeneradas + batch INSERT del ciclo actual.
    Las credenciales vienen exclusivamente del .env (nunca del cliente).
    """
    if not SUPABASE_ENABLED:
        log.debug("Supabase deshabilitado — omitiendo sync.")
        return

    try:
        import requests as _req
    except ImportError:
        log.warning("Supabase sync: 'requests' no disponible.")
        return

    table_url = f"{SUPABASE_URL}/rest/v1/perovskite_leads"

    # ── 1. DELETE filas autogeneradas (invest_proxy = true o false, no-manual) ──
    # Usamos el filtro neq=id.like.manual-% para borrar solo filas del agente
    del_url = f"{table_url}?id=gte.1"   # borra todo (el agente no tiene PKs tipo 'manual-')
    del_resp = requests.delete(del_url, headers=_SB_HEADERS, verify=False, timeout=20)
    if not del_resp.ok and del_resp.status_code != 404:
        log.warning("Supabase DELETE: %s %s", del_resp.status_code,
                    del_resp.text[:120].encode("ascii", errors="replace").decode())

    # ── 2. Preparar registros para INSERT ──────────────────────
    articles = db.get("articles", [])
    records  = []
    for e in articles:
        gw = e.get("capacityGw", 0.0)
        records.append({
            "empresa":          e.get("company", ""),
            "capacidad_gw":     round(gw, 6),
            # yodo_teorico_toneladas es columna GENERATED — no se envía
            "desglose_quimico": {
                "pbi2_ton": round(gw * IODINE_PER_GW * RATIOS["pbi2"], 6),
                "fai_ton":  round(gw * IODINE_PER_GW * RATIOS["fai"],  6),
                "mai_ton":  round(gw * IODINE_PER_GW * RATIOS["mai"],  6),
                "csi_ton":  round(gw * IODINE_PER_GW * RATIOS["csi"],  6),
            },
            "fuente_noticia":   (e.get("link") or e.get("source") or "")[:500],
            "target_year":      e.get("target_year", CURRENT_YEAR),
            "geo_pais":         e.get("geo", {}).get("country", ""),
            "geo_continente":   e.get("geo", {}).get("continent", ""),
            "nivel_riesgo":     e.get("nivel_riesgo", "Neutral"),
            "invest_proxy":     bool(e.get("invest_proxy", False)),
            "fecha_publicacion": e.get("date", "")[:10],
        })

    if not records:
        log.info("Supabase sync: sin registros para insertar.")
        return

    # ── 3. Batch INSERT (50 filas por lote para evitar payload limits) ──
    BATCH = 50
    total_ok = 0
    headers_insert = {**_SB_HEADERS, "Prefer": "return=minimal"}
    for i in range(0, len(records), BATCH):
        batch = records[i : i + BATCH]
        ins_resp = requests.post(table_url, json=batch,
                             headers=headers_insert, verify=False, timeout=30)
        if ins_resp.ok:
            total_ok += len(batch)
        else:
            body = ins_resp.text[:200].encode("ascii", errors="replace").decode()
            log.warning("Supabase INSERT lote %d: %s %s",
                        i // BATCH + 1, ins_resp.status_code, body)

    log.info("Supabase sync: %d/%d registros insertados en perovskite_leads.",
             total_ok, len(records))

# ── Hybrid Brain Tools ─────────────────────────────────────────

def _get_embedding(text: str) -> list[float]:
    if not LLM_ENABLED: return []
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={_RESOLVED_KEY}"
    payload = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": text[:8000]}]},
        "taskType": "RETRIEVAL_DOCUMENT",
        "outputDimensionality": 768,
    }
    try:
        resp = requests.post(url, json=payload, verify=False, timeout=10)
        if resp.ok:
            return resp.json()["embedding"]["values"]
    except Exception as e:
        log.error("Error getting embedding: %s", e)
    return []

def _cosine_sim(a: list[float], b: list[float]) -> float:
    dot = sum(x*y for x,y in zip(a,b))
    maga = math.sqrt(sum(x*x for x in a))
    magb = math.sqrt(sum(x*x for x in b))
    if maga == 0 or magb == 0: return 0.0
    return dot / (maga * magb)

def tool_buscar_docs(query: str) -> str:
    """Busca en Supabase perovskite_knowledge via embeddings."""
    if not SUPABASE_ENABLED: return "Error: Base de datos corporativa no disponible."
    
    q_emb = _get_embedding(query)
    if not q_emb: return "Error: No se pudo generar embedding para la búsqueda."
    
    # 1. Intentar RPC match_knowledge
    url_rpc = f"{SUPABASE_URL}/rest/v1/rpc/match_knowledge"
    payload = {"query_embedding": q_emb, "match_count": 3, "similarity_threshold": 0.5}
    try:
        resp = requests.post(url_rpc, json=payload, headers=_SB_HEADERS, verify=False, timeout=10)
        if resp.ok:
            results = resp.json()
            if not results: return "No se encontró información en la base de datos corporativa."
            text_res = "\n".join([f"[Fuente: {r['fuente']}] {r['contenido']}" for r in results])
            return text_res
    except Exception as e:
        log.error("RPC Fallback: %s", e)
        
    # 2. Fallback local (simulación)
    url_all = f"{SUPABASE_URL}/rest/v1/perovskite_knowledge?select=contenido,fuente,embedding&limit=100"
    try:
        resp = requests.get(url_all, headers=_SB_HEADERS, verify=False, timeout=10)
        if not resp.ok: return "Error al consultar la base de datos."
        rows = resp.json()
        scored = []
        for r in rows:
            emb_str = r.get("embedding", "")
            if not emb_str: continue
            if isinstance(emb_str, str):
                doc_emb = json.loads(emb_str.replace("{", "[").replace("}", "]"))
            else: doc_emb = emb_str
            sim = _cosine_sim(q_emb, doc_emb)
            if sim > 0.5:
                scored.append((sim, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        if not scored: return "No se encontró información en la base de datos corporativa."
        text_res = "\n".join([f"[Fuente: {r[1]['fuente']}] {r[1]['contenido']}" for r in scored[:3]])
        return text_res
    except Exception as e:
        return f"Error en búsqueda: {e}"

def tool_buscar_web(query: str) -> str:
    """Busca en Google en tiempo real."""
    if not search: return "Error: Librería googlesearch no está instalada."
    try:
        results = []
        for res in search(query, num_results=3, advanced=True):
            if hasattr(res, "url"):
                url = getattr(res, "url", "")
                title = getattr(res, "title", "")
                desc = getattr(res, "description", "")
                results.append(f"[Fuente: {url}] {title}: {desc}")
            else:
                results.append(f"[Fuente: {str(res)}]")
        if not results: return "No se encontraron resultados en la web."
        return "\n".join(results)
    except Exception as e:
        return f"Error en búsqueda web: {e}"

def tool_insertar_lead(empresa: str, capacidad_gw: float, target_year: str, fuente: str, fecha_publicacion: str = "") -> str:
    """Inserta un lead automáticamente en Supabase."""
    if not SUPABASE_ENABLED: return "Error: Base de datos de leads no disponible."
    
    if not fecha_publicacion:
        fecha_publicacion = datetime.now().strftime("%Y-%m-%d")

    table_url = f"{SUPABASE_URL}/rest/v1/perovskite_leads"
    payload = {
        "empresa": empresa,
        "capacidad_gw": round(float(capacidad_gw), 6),
        "desglose_quimico": {
            "pbi2_ton": round(float(capacidad_gw) * IODINE_PER_GW * RATIOS["pbi2"], 6),
            "fai_ton":  round(float(capacidad_gw) * IODINE_PER_GW * RATIOS["fai"],  6),
            "mai_ton":  round(float(capacidad_gw) * IODINE_PER_GW * RATIOS["mai"],  6),
            "csi_ton":  round(float(capacidad_gw) * IODINE_PER_GW * RATIOS["csi"],  6),
        },
        "fuente_noticia": fuente[:500],
        "target_year": str(target_year),
        "geo_pais": geo_lookup(empresa).get("country", ""),
        "geo_continente": geo_lookup(empresa).get("continent", ""),
        "nivel_riesgo": "Agente IA (Automático)",
        "invest_proxy": False,
        "fecha_publicacion": fecha_publicacion[:10]
    }
    try:
        resp = requests.post(table_url, json=payload, headers={**_SB_HEADERS, "Prefer": "return=minimal"}, verify=False, timeout=10)
        if resp.ok:
            return f"Éxito: Lead de {empresa} ({capacidad_gw} GW) insertado correctamente."
        else:
            return f"Error de inserción: {resp.text}"
    except Exception as e:
        return f"Error al insertar: {e}"

TOOLS_DECLARATION = {
    "functionDeclarations": [
        {
            "name": "buscar_docs",
            "description": "Busca en la base de datos de conocimiento corporativo sobre perovskita (Supabase pgvector) usando similitud semántica. Obligatorio usar primero.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Consulta técnica a buscar en la documentación interna."}
                },
                "required": ["query"]
            }
        },
        {
            "name": "buscar_web",
            "description": "Busca en la web en tiempo real información reciente, noticias o datos faltantes. Usa esto si buscar_docs no tiene la respuesta.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Consulta a buscar en DuckDuckGo."}
                },
                "required": ["query"]
            }
        },
        {
            "name": "insertar_lead",
            "description": "Inserta un anuncio firme de una nueva planta comercial de perovskita en la base de datos de negocio.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "empresa": {"type": "STRING"},
                    "capacidad_gw": {"type": "NUMBER", "description": "Capacidad en Gigawatts (GW). Convierte MW a GW."},
                    "target_year": {"type": "STRING", "description": "Año objetivo de producción o 'TBD'"},
                    "fuente": {"type": "STRING", "description": "URL exacta o documento de origen del anuncio"},
                    "fecha_publicacion": {"type": "STRING", "description": "Fecha de publicación original de la noticia o anuncio (formato YYYY-MM-DD)."}
                },
                "required": ["empresa", "capacidad_gw", "target_year", "fuente", "fecha_publicacion"]
            }
        }
    ]
}

# ── Scan Cycle ─────────────────────────────────────────────────
def run_scan():
    log.info("=" * 65)
    log.info("SCAN — %s | LLM: %s",
             datetime.now().strftime("%Y-%m-%d %H:%M"),
             f"Gemini 1.5 Flash ✓ ({_RESOLVED_KEY[:8]}...)" if LLM_ENABLED else "OFF")
    log.info("=" * 65)

    raw = []
    for feed in FEED_URLS:
        raw.extend(fetch_feed(feed))
    log.info("Total raw: %d artículos", len(raw))

    entries = analyse(raw)

    log.info("Generando Informe Ejecutivo de Mercado...")
    market_report = generate_market_report(entries)

    db = build_database(entries, market_report)
    write_database(db)
    sync_to_supabase(db)

def schedule_scans():
    run_scan()
    t = threading.Timer(SCAN_INTERVAL_SEC, schedule_scans)
    t.daemon = True
    t.start()

# ── HTTP Server ────────────────────────────────────────────────
class Handler(BaseHTTPRequestHandler):
    BASE = os.path.dirname(os.path.abspath(__file__))
    MIME = {
        ".html": "text/html; charset=utf-8",
        ".js":   "application/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".css":  "text/css; charset=utf-8",
    }

    def log_message(self, *_): pass

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Cache-Control", "no-store")

    def do_OPTIONS(self):
        self.send_response(200); self._cors(); self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0] or "/"
        if path == "/": path = "/index.html"
        fp = os.path.normpath(os.path.join(self.BASE, path.lstrip("/")))
        if not fp.startswith(self.BASE) or not os.path.isfile(fp):
            self.send_response(404); self._cors(); self.end_headers(); return
        with open(fp, "rb") as f: data = f.read()
        ext = os.path.splitext(fp)[1].lower()
        self.send_response(200)
        self.send_header("Content-Type", self.MIME.get(ext, "application/octet-stream"))
        self.send_header("Content-Length", str(len(data)))
        self._cors(); self.end_headers(); self.wfile.write(data)

    def do_POST(self):
        if self.path == "/api/chat":
            return self.handle_chat()
        
        if self.path != "/api/entries":
            self.send_response(404); self.end_headers(); return

        try:
            body  = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            entry = json.loads(body)
            val   = float(entry["capacityValue"])
            unit  = entry.get("capacityUnit", "MW")
            gw    = val if unit == "GW" else val / 1000.0
            co    = entry.get("company", "Unknown")
            iod   = calc_iodine(gw)
            new   = {
                "id":            f"manual-{int(time.time()*1000)}",
                "company":       co,
                "capacityValue": val,
                "capacityUnit":  unit,
                "capacityGw":    round(gw, 4),
                **iod,
                "phase":         entry.get("phase", "Planned"),
                "nivel_riesgo":  entry.get("nivel_riesgo", "Neutral"),
                "resumen_ia":    entry.get("notes", "Entrada manual del analista."),
                "target_year":   entry.get("target_year", CURRENT_YEAR),
                "invest_proxy":  False,
                "geo":           geo_lookup(co),
                "llm_used":      False,
                "radar_only":    gw == 0.0,
                "date":          entry.get("date", ""),
                "source":        entry.get("source", "Manual"),
                "title":         entry.get("source", "Entrada Manual"),
                "link":          "",
                "summary":       entry.get("notes", ""),
            }
            db_data = {"articles": [], "meta": {}, "companies": COMPANIES, "market_report": ""}
            if os.path.exists(DB_FILE):
                with open(DB_FILE, encoding="utf-8") as f:
                    db_data = json.load(f)
            db_data["articles"].insert(0, new)
            existing_mr = db_data.get("market_report", "")
            db_final = build_database(db_data["articles"], existing_mr)
            write_database(db_final)
            sync_to_supabase(db_final)
            self.send_response(201)
            self.send_header("Content-Type", "application/json")
            self._cors(); self.end_headers()
            self.wfile.write(json.dumps({"ok": True, "id": new["id"]}).encode())
        except Exception as e:
            log.error("POST /api/entries: %s", e)
            self.send_response(400); self._cors(); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def handle_chat(self):
        """Maneja el endpoint /api/chat con Function Calling para Gemini."""
        if not LLM_ENABLED:
            self.send_response(503); self._cors(); self.end_headers()
            self.wfile.write(b'{"error": "LLM API Key not configured."}')
            return
            
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            req_data = json.loads(body)
            user_msg = req_data.get("message", "")
            
            # Historial de conversación (si se implementara state)
            history = req_data.get("history", [])
            contents = history + [{"role": "user", "parts": [{"text": user_msg}]}]
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={_RESOLVED_KEY}"
            
            # Ejecución en bucle para resolver Function Calls (max 3 iteraciones)
            MAX_ITERS = 3
            
            for iter_count in range(MAX_ITERS):
                payload = {
                    "systemInstruction": {"parts": [{"text": HYBRID_SYSTEM_PROMPT}]},
                    "contents": contents,
                    "tools": [TOOLS_DECLARATION]
                }
                
                resp = requests.post(url, json=payload, verify=False, timeout=30)
                if not resp.ok:
                    self.send_response(500); self._cors(); self.end_headers()
                    self.wfile.write(json.dumps({"error": f"API Error: {resp.text}"}).encode())
                    return
                
                resp_json = resp.json()
                try:
                    candidate = resp_json["candidates"][0]
                    message = candidate["content"]
                    parts = message.get("parts", [])
                except KeyError:
                    self.send_response(500); self._cors(); self.end_headers()
                    self.wfile.write(b'{"error": "Invalid response format from Gemini."}')
                    return
                
                # Check for function call
                function_call = None
                for part in parts:
                    if "functionCall" in part:
                        function_call = part["functionCall"]
                        break
                        
                if function_call:
                    name = function_call["name"]
                    args = function_call.get("args", {})
                    log.info("Cerebro Híbrido invoca herramienta: %s(%s)", name, args)
                    
                    # Ejecutar herramienta localmente
                    tool_res_text = ""
                    if name == "buscar_docs":
                        tool_res_text = tool_buscar_docs(args.get("query", ""))
                    elif name == "buscar_web":
                        tool_res_text = tool_buscar_web(args.get("query", ""))
                    elif name == "insertar_lead":
                        tool_res_text = tool_insertar_lead(
                            args.get("empresa",""), args.get("capacidad_gw",0),
                            args.get("target_year",""), args.get("fuente",""),
                            args.get("fecha_publicacion","")
                        )
                    else:
                        tool_res_text = "Error: Herramienta desconocida."
                        
                    log.info("Resultado %s: %s...", name, tool_res_text[:50])
                    
                    # Añadir la respuesta del modelo (functionCall) y el result (functionResponse) al historial
                    contents.append(message)
                    contents.append({
                        "role": "function",
                        "parts": [{
                            "functionResponse": {
                                "name": name,
                                "response": {"result": tool_res_text}
                            }
                        }]
                    })
                else:
                    # No function call, return final text
                    final_text = ""
                    for part in parts:
                        if "text" in part:
                            final_text += part["text"]
                            
                    self.send_response(200); self._cors(); self.end_headers()
                    self.wfile.write(json.dumps({"reply": final_text}).encode("utf-8"))
                    return
                    
            # Si excede iteraciones
            self.send_response(500); self._cors(); self.end_headers()
            self.wfile.write(b'{"error": "Max tool loop iterations reached."}')
            
        except Exception as e:
            log.error("POST /api/chat: %s", e)
            self.send_response(400); self._cors(); self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

# ── Entry Point ────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-only", action="store_true")
    args = ap.parse_args()

    try:
        import feedparser, requests
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "feedparser", "requests", "-q"])
        import feedparser, requests

    if not LLM_ENABLED:
        log.warning("╔═══════════════════════════════════════════════════════════╗")
        log.warning("║  GEMINI_API_KEY no configurado.                           ║")
        log.warning("║  Edita la variable API_KEY en la línea 18 del script.     ║")
        log.warning("║  Obtén tu clave gratis en: https://aistudio.google.com   ║")
        log.warning("╚═══════════════════════════════════════════════════════════╝")
    else:
        log.info("✓ Gemini API Key configurada (%s...)", _RESOLVED_KEY[:8])

    if args.scan_only:
        run_scan(); sys.exit(0)

    log.info("SQM Perovskite Scout v6.0 | Supabase: %s | http://localhost:%d",
             "ON" if SUPABASE_ENABLED else "OFF", HTTP_PORT)
    threading.Thread(target=schedule_scans, daemon=True).start()
    time.sleep(2)

    server = HTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    log.info("Servidor en puerto %d — Ctrl+C para detener.", HTTP_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Detenido."); server.server_close()
