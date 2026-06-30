"""
SQM Perovskite Scout â€” Agent v6.0  (Supabase Integration)
=========================================================
Arquitectura: procesamiento 100% local (regex) + informe ejecutivo REST/SSL bypass.
v6.0: Escritura dual â€” database.json (cache local) + Supabase Postgres (analytics).
CONFIGURACIÃ“N DE API â€” pon tu clave aquÃ­:
"""

# ─────────────────────────────────────────────────────────────────
#   ⚙️  PON AQUÍ TU CLAVE DE GOOGLE AI STUDIO
#   Obtén una gratis en: https://aistudio.google.com/apikey
# ─────────────────────────────────────────────────────────────────
import os
from dotenv import load_dotenv
load_dotenv()

try:
    from duckduckgo_search import DDGS
except ImportError:
    DDGS = None


API_KEY = os.environ.get("GEMINI_API_KEY", "")
# ─────────────────────────────────────────────────────────────────

import os

import json

import re

import time

import math

import difflib

import threading

import sys

import logging

import requests

import feedparser

import urllib.parse

from datetime import datetime, timezone

from http.server import HTTPServer, BaseHTTPRequestHandler

from urllib.parse import quote_plus



from dotenv import load_dotenv

load_dotenv()



# ── Silenciar InsecureRequestWarning del proxy corporativo (SSL MITM) ──
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    pass

# â”€â”€ Logging â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("SQM")

# â”€â”€ .env Loader (credenciales backend â€” nunca en el cliente) â”€â”€â”€â”€
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

# â”€â”€ Supabase config (solo backend â€” regla AGENTS.md) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Resolve API key â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_RESOLVED_KEY = (
    os.environ.get("GEMINI_API_KEY", "").strip()
    or API_KEY.strip()
)
LLM_ENABLED = bool(_RESOLVED_KEY)

# â”€â”€ Constants â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
IODINE_PER_GW      = 4.73
RATIOS             = {"pbi2": 0.60, "fai": 0.20, "mai": 0.10, "csi": 0.10}
SCAN_INTERVAL_SEC  = 3600
DB_FILE            = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database.json")
HTTP_PORT          = 8080
CURRENT_YEAR       = str(datetime.now().year)   # e.g. "2026"

# â”€â”€ Gemini REST endpoints (requests only â€” no SDK) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Primary: gemini-3.1-flash-lite (capa gratuita 2026)
GEMINI_ENDPOINTS = [
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}",
]

# â”€â”€ Hybrid Brain System Prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
HYBRID_SYSTEM_PROMPT = (
    "Eres un Analista de Inteligencia Comercial Experto para SQM Perovskite Scout. "
    "Tu objetivo es rastrear la web en busca de anuncios de nuevas plantas solares y "
    "responder preguntas tÃ©cnicas sobre celdas de perovskita.\n\n"
    "REGLA DE CITAS (Grounding Estricto): Tienes terminantemente prohibido inventar datos. "
    "Si extraes informaciÃ³n de la base de datos (buscar_docs), debes citar el documento "
    "de origen exacto (ej: '[Fuente: doc_perovskita.pdf]'). Si extraes de internet "
    "(buscar_web), cita obligatoriamente la URL (ej: '[Fuente: https://solarnews.com/...]').\n\n"
    "ERES UN AGENTE HIBRIDO. Si el usuario pregunta por 'noticias', 'actualidad', 'ultimas novedades' o fechas futuras (ej. 2026/2027), ESTAS OBLIGADO a ejecutar la herramienta buscar_web para buscar en internet ANTES de responder. Debes cruzar la informacion de internet con los documentos locales.\n\n"
    "Flujo de Resolucion:\n"
    "1. Siempre usa primero 'buscar_docs' para buscar conocimiento interno corporativo.\n"
    "2. Si la informacion no esta o es insuficiente, usa 'buscar_web' para buscar en internet.\n"
    "3. Si detectas un anuncio de una nueva planta comercial, usa 'insertar_lead' para registrarlo. "
    "Aplica matematicamente la regla de 4.73 toneladas metricas de yodo por cada 1 GW instalado.\n\n"
    "Genera una respuesta en espanol, clara, ejecutiva y profesional."
)

# â”€â”€ Executive Market Report Prompt â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
EXECUTIVE_REPORT_SYSTEM_PROMPT = (
    "Eres el Analista EstratÃ©gico Jefe de inteligencia de mercado en SQM. "
    "Redacta un informe ejecutivo completo, exhaustivo y sin lÃ­mite de extensiÃ³n "
    "(usa todo el espacio que necesites, incluso una plana entera) sobre el mercado "
    "de celdas solares de perovskita y su impacto en la demanda global de Yodo. "
    "Estructura obligatoria: "
    "1. Panorama General del Mercado: Estado actual de la tecnologÃ­a, barreras, "
    "celdas tÃ¡ndem y el rol fundamental del Yodo. "
    "2. AnÃ¡lisis de Eventos Recientes: Analiza las noticias que te estoy entregando. "
    "Si hay un evento disruptivo (ej. nuevas inversiones, eficiencias rÃ©cord, GW construidos), "
    "destÃ¡calo y explica cÃ³mo cambia las reglas del juego. Si no hay nada disruptivo, "
    "integra las noticias para confirmar las tendencias actuales. "
    "3. Apreciaciones Objetivas y Cifras: Incluye fechas, volÃºmenes de GW, y proyecta "
    "de forma directa y financiera el impacto futuro en las toneladas de Yodo. "
    "Usa un tono corporativo, experto y certero."
)

# â”€â”€ Company Dictionary â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
COMPANIES = [
    "UtmoLight", "Renshine Solar", "Oxford PV", "CNNC", "CNNP",
    "BOE", "GCL", "Microquanta", "Caelux", "Sekisui Chemical",
    "Photon Crystal Energy", "Mellow Energy",
]

# â”€â”€ Geographic Dictionary (static) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
GEO_MAP: dict[str, dict] = {
    "Caelux":             {"country": "USA",    "continent": "NorteamÃ©rica"},
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
    "Sekisui Chemical":   {"country": "JapÃ³n",   "continent": "Asia"},
}
GEO_DEFAULT = {"country": "Desconocido", "continent": "Global"}

def geo_lookup(company: str) -> dict:
    return GEO_MAP.get(company, GEO_DEFAULT)

# â”€â”€ RSS Sources â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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

# â”€â”€ Regex: capacity â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_CAP_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(gw|gwp|gigawat\w*|gigavatio\w*|mw|mwp|megawat\w*|megavatio\w*)",
    re.IGNORECASE,
)

# â”€â”€ Regex: investment / financial proxy â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Matches: "$10 million", "100M USD", "â‚¬50 million", "Â£200M", "500 million dollars"
_INVEST_RE = re.compile(
    r"(?:[\$â‚¬Â£Â¥])?\s*(\d+(?:[.,]\d+)?)\s*"
    r"(?:M\b|million|billion|B\b|bn\b)(?:\s*(?:USD|EUR|GBP|dollars?|euros?))?",
    re.IGNORECASE,
)
# Keywords that must appear within 50 chars of the money figure
# to qualify as a CAPEX/project investment (not a corporate funding round)
_CAPEX_CONTEXT_RE = re.compile(
    r"\b(factory|plant|facility|manufacturing|capacity|production.line|module.line|fab\b)",
    re.IGNORECASE,
)
# CAPEX proxy: $100M = 1 GW  â†’ each $1M = 0.01 GW
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

    # â”€â”€ Context guard: require facility keyword within 50 chars â”€â”€
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

# â”€â”€ Regex: phase & sentiment â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
_PHASE_OP  = re.compile(r"inaugur|commission|operational|mass.produc|production.start|en.marcha", re.I)
_PHASE_CON = re.compile(r"under.construct|en.construcci|groundbreak|building", re.I)
_KW_GOOD   = re.compile(r"produc|manufactur|commerci|factory|gigawatt|megawatt|plant|line|facility|invest|fund", re.I)
_KW_BAD    = re.compile(r"lead.free|tin.based|without.iodine|no.iodine|cancel|stability.issue|recall", re.I)

# â”€â”€ Regex: target year (EXPANDED â€” any 2024-2035) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
    Extract the earliest year in range 2024â€“2039 from text.
    Falls back to `fallback` (default: current year) if none found.
    """
    years = _YEAR_RE.findall(text)
    if not years:
        return fallback
    return str(min(int(y) for y in years))

# â”€â”€ Iodine Math â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def calc_iodine(gw: float) -> dict:
    total = round(gw * IODINE_PER_GW, 4)
    return {
        "iodineDemand": total,
        "pbi2":  round(total * RATIOS["pbi2"], 4),
        "fai":   round(total * RATIOS["fai"],  4),
        "mai":   round(total * RATIOS["mai"],  4),
        "csi":   round(total * RATIOS["csi"],  4),
    }

# â”€â”€ Anti-duplicates engine (difflib) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            log.debug("Dedup (tÃ­tulo %.0f%%): %s", ratio * 100, new_title[:60])
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

# -- Executive Market Report Generator (Fix 2 -- RAG desde Supabase) --
def generate_market_report(articles: list[dict]) -> str:
    """
    Fix 2: Obtiene las ultimas noticias directamente de Supabase y genera
    el informe ejecutivo con Gemini usando el prompt estricto de SQM Analista.
    REST call con verify=False (SSL MITM bypass corporativo).
    """
    if not LLM_ENABLED:
        log.info("Informe ejecutivo omitido -- LLM deshabilitado.")
        return "Informe en proceso de generacion"

    try:
        import requests as _req
    except ImportError:
        return "ERROR FATAL API: requests no instalado"

    # -- Fix 2: Obtener noticias reales de Supabase --------------------------
    noticias_supabase = []
    if SUPABASE_ENABLED:
        try:
            sb_url = (
                f"{SUPABASE_URL}/rest/v1/perovskite_leads"
                f"?select=empresa,capacidad_gw,titulo,analisis,fecha_publicacion,nivel_riesgo"
                f"&order=created_at.desc"
            )
            sb_resp = _req.get(sb_url, headers=_SB_HEADERS, verify=False, timeout=15)
            if sb_resp.ok:
                rows = sb_resp.json()
                for r in rows:
                    titulo_r   = (r.get("titulo") or "").strip()
                    analisis_r = (r.get("analisis") or "").strip()
                    empresa_r  = r.get("empresa", "")
                    gw_r       = round(float(r.get("capacidad_gw") or 0), 3)
                    fecha_r    = r.get("fecha_publicacion", "")
                    riesgo_r   = r.get("nivel_riesgo", "Neutral")
                    if titulo_r or analisis_r:
                        noticias_supabase.append({
                            "empresa":   empresa_r,
                            "gw":        gw_r,
                            "yodo_ton":  round(gw_r * IODINE_PER_GW, 2),
                            "titulo":    titulo_r or analisis_r[:120],
                            "analisis":  analisis_r or titulo_r,
                            "fecha":     fecha_r,
                            "riesgo":    riesgo_r,
                        })
                log.info("RAG Report: %d noticias obtenidas de Supabase.", len(noticias_supabase))
        except Exception as e:
            log.warning("RAG: error consultando Supabase: %s", e)

    # Fallback: usar articulos del ciclo actual si Supabase falla
    if not noticias_supabase:
        sorted_arts = sorted(articles, key=lambda x: x.get("date", ""), reverse=True)
        for art in sorted_arts[:15]:
            gw_a = round(art.get("capacityGw", 0), 3)
            noticias_supabase.append({
                "empresa":  art.get("company", ""),
                "gw":       gw_a,
                "yodo_ton": round(gw_a * IODINE_PER_GW, 2),
                "titulo":   (art.get("title") or "")[:160],
                "analisis": (art.get("resumen_ia") or "")[:300],
                "fecha":    art.get("date", ""),
                "riesgo":   art.get("nivel_riesgo", "Neutral"),
            })

    # -- Calcular metricas globales -------------------------------------------
    total_gw  = round(sum(n["gw"]       for n in noticias_supabase), 3)
    total_iod = round(total_gw * IODINE_PER_GW, 2)
    empresas  = list({n["empresa"] for n in noticias_supabase if n["empresa"]})

    noticias_txt = "\n".join([
        f"- [{n['fecha']}] {n['empresa']} ({n['gw']} GW -> {n['yodo_ton']} Ton Yodo) | {n['riesgo']}\n"
        f"  Titulo: {n['titulo']}\n"
        f"  Analisis: {n['analisis']}"
        for n in noticias_supabase[:15]
    ])

    # -- Prompt estricto SQM Analista ----------------------------------------
    full_prompt = (
        "Actua como Analista Senior de SQM (Sociedad Quimica y Minera de Chile), "
        "especialista en demanda de yodo para celdas perovskita.\n\n"
        "Lee estas noticias recientes sobre perovskita y redacta un informe ejecutivo "
        "de exactamente 3 parrafos cruzando esta actualidad con la proyeccion de demanda "
        "de yodo (usando la metrica de 4.73 Ton/GW). Se especifico y cita las empresas "
        "mencionadas. No uses bullet points, solo parrafos corporativos.\n\n"
        f"METRICAS GLOBALES DEL CICLO:\n"
        f"  - Capacidad total detectada: {total_gw} GW\n"
        f"  - Demanda proyectada de yodo: {total_iod} Ton (factor 4.73 Ton/GW)\n"
        f"  - Empresas monitoreadas: {', '.join(empresas[:10]) or 'N/D'}\n\n"
        f"NOTICIAS RECIENTES EXTRAIDAS DE SUPABASE:\n{noticias_txt}\n\n"
        "Redacta el informe ejecutivo ahora (3 parrafos concretos, corporativos, "
        "citando empresas especificas y cifras de yodo):"
    )

    payload = {
        "contents": [{"parts": [{"text": full_prompt}]}],
        "generationConfig": {"temperature": 0.35, "maxOutputTokens": 4096},
    }

    # -- Try each Gemini endpoint in order -----------------------------------
    last_error = "ERROR FATAL API: ningun endpoint respondio"
    for endpoint_tpl in GEMINI_ENDPOINTS:
        url = endpoint_tpl.format(key=_RESOLVED_KEY)
        model_name = url.split("/models/")[1].split(":")[0]
        try:
            log.info("Intentando Gemini endpoint: %s", model_name)
            resp = _req.post(url, json=payload, verify=False, timeout=120)

            if resp.status_code == 404:
                log.warning("Endpoint %s -> 404, probando siguiente...", model_name)
                continue

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
                last_error = f"ERROR FATAL API: {resp.status_code} -- {reason}"
                log.error("Informe Ejecutivo (%s): %s", model_name, last_error)
                return last_error

            data = resp.json()
            report_text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
            log.info("OK Informe Ejecutivo RAG [%s] -- %d caracteres.", model_name, len(report_text))
            return report_text

        except Exception as e:
            last_error = f"ERROR FATAL API: {type(e).__name__} -- {str(e)[:200]}"
            log.warning("Informe Ejecutivo (%s) excepcion: %s", model_name, last_error)
            continue

    log.error("Todos los endpoints de Gemini fallaron.")
    return last_error
    return last_error

# â”€â”€ RSS Fetch â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â# â”€â”€ Deep Scrape HTML + IA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def deep_scrape(url: str) -> dict:
    """
    v6.1 - Extraccion de fecha INFALIBLE en 4 capas.
    Capas 1-3 NO requieren Gemini y siempre se ejecutan.
    Capa 4 usa Gemini via REST (sin SDK) solo si LLM_ENABLED.
    GARANTIA: nunca lanza excepcion sin capturar, siempre devuelve dict.
    """
    import requests as _req, json as _json, time as _time, re as _re

    res = {"fecha_publicacion": "Fecha Desconocida", "analisis": "Sin analisis detallado.", "titulo": ""}
    if not url:
        return res

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        log.warning("deep_scrape: bs4 no instalado, omitiendo extraccion HTML.")
        return res

    try:
        try:
            r = _req.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"}, verify=False)
            if not r.ok:
                return res
        except _req.exceptions.RequestException:
            log.warning("Pagina muy lenta, saltando... (%s)", url[:60])
            return res

        soup = BeautifulSoup(r.content, "html.parser")
        hoy = datetime.now().strftime("%Y-%m-%d")

        # Capa 1: meta tags HTML estandar (NO requiere Gemini)
        fecha_html = None
        DATE_META_ATTRS = [
            ("property", "article:published_time"),
            ("property", "og:article:published_time"),
            ("name",     "datePublished"),
            ("name",     "date"),
            ("name",     "dc.date"),
            ("name",     "publish_date"),
            ("itemprop", "datePublished"),
            ("name",     "article:modified_time"),
        ]
        for attr_name, attr_val in DATE_META_ATTRS:
            tag = soup.find("meta", {attr_name: attr_val})
            if tag and tag.get("content"):
                raw = tag["content"].strip()[:30]
                m = _re.search(r"(\d{4}-\d{2}-\d{2})", raw)
                if m:
                    candidate = m.group(1)
                    if candidate != hoy:
                        fecha_html = candidate
                        log.debug("Capa1 meta[%s]: %s", attr_val, fecha_html)
                        break

        # Capa 2: time datetime (NO requiere Gemini)
        if not fecha_html:
            for t_tag in soup.find_all("time", attrs={"datetime": True})[:5]:
                raw = t_tag["datetime"].strip()[:30]
                m = _re.search(r"(\d{4}-\d{2}-\d{2})", raw)
                if m:
                    candidate = m.group(1)
                    if candidate != hoy:
                        fecha_html = candidate
                        log.debug("Capa2 time: %s", fecha_html)
                        break

        # Capa 3: JSON-LD schema.org (NO requiere Gemini)
        if not fecha_html:
            for schema_tag in soup.find_all("script", type="application/ld+json"):
                try:
                    sdata = _json.loads(schema_tag.string or "{}")
                    if isinstance(sdata, list):
                        sdata = sdata[0] if sdata else {}
                    for k in ["datePublished", "dateCreated", "dateModified"]:
                        val = sdata.get(k, "")
                        m = _re.search(r"(\d{4}-\d{2}-\d{2})", val)
                        if m:
                            candidate = m.group(1)
                            if candidate != hoy:
                                fecha_html = candidate
                                break
                    if fecha_html:
                        log.debug("Capa3 JSON-LD: %s", fecha_html)
                        break
                except Exception:
                    pass

        if fecha_html:
            res["fecha_publicacion"] = fecha_html
            log.info("Fecha extraida del HTML sin Gemini: %s -> %s", fecha_html, url[:60])

        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.extract()
        text = soup.get_text(separator=" ", strip=True)[:12000]

        # Capa 4: Gemini via REST, SOLO si LLM_ENABLED
        if not LLM_ENABLED:
            log.debug("deep_scrape: LLM deshabilitado, usando solo extraccion HTML.")
            return res

        if fecha_html:
            prompt = (
                "Eres un extractor de datos para inteligencia comercial de SQM.\n"
                "Lee el texto de esta pagina web y extrae:\n\n"
                "TAREA 1 - TITULO DEL ARTICULO:\n"
                "  - El titulo exacto tal como aparece publicado.\n\n"
                "TAREA 2 - RESUMEN COMERCIAL:\n"
                "  - 2 lineas sobre el impacto en demanda de yodo.\n\n"
                'RESPONDE UNICAMENTE un JSON: {"titulo": "...", "analisis": "..."}\n\n'
                f"TEXTO DE LA PAGINA:\n{text}"
            )
        else:
            prompt = (
                "Eres un extractor de datos estructurado para inteligencia comercial.\n\n"
                "TAREA 1 - FECHA: formato YYYY-MM-DD o 'Fecha Desconocida'\n"
                "TAREA 2 - TITULO: el titulo exacto\n"
                "TAREA 3 - RESUMEN COMERCIAL: 2 lineas sobre impacto en yodo\n\n"
                'RESPONDE UNICAMENTE un JSON: {"fecha_publicacion": "...", "titulo": "...", "analisis": "..."}\n\n'
                f"TEXTO DE LA PAGINA:\n{text}"
            )

        # REST call, sin SDK de Google
        try:
            gem_url = GEMINI_ENDPOINTS[0].format(key=_RESOLVED_KEY)
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 512},
            }
            gem_resp = _req.post(gem_url, json=payload, verify=False, timeout=30)
            if gem_resp.ok:
                gem_json = gem_resp.json()
                t_text = gem_json["candidates"][0]["content"]["parts"][0]["text"]
                idx1, idx2 = t_text.find("{"), t_text.rfind("}")
                if idx1 != -1 and idx2 != -1:
                    data = _json.loads(t_text[idx1:idx2 + 1])
                    res["titulo"]   = (data.get("titulo") or "").strip()[:200]
                    res["analisis"] = (data.get("analisis") or "Sin analisis detallado.").strip()[:800]
                    if not fecha_html:
                        fecha_g = (data.get("fecha_publicacion") or "Fecha Desconocida").strip()
                        if fecha_g and fecha_g != hoy and _re.match(r"\d{4}-\d{2}-\d{2}$", fecha_g):
                            res["fecha_publicacion"] = fecha_g
                        else:
                            res["fecha_publicacion"] = "Fecha Desconocida"
                else:
                    log.warning("deep_scrape: no JSON en respuesta Gemini para %s", url[:60])
            else:
                log.warning("deep_scrape Gemini HTTP %s para %s", gem_resp.status_code, url[:60])
        except Exception as e:
            log.warning("deep_scrape Gemini error (%s): %s", url[:60], e)

        _time.sleep(2)
    except Exception as e:
        log.warning("deep_scrape request error (%s): %s", url[:60], e)
        _time.sleep(2)

    if not res.get("fecha_publicacion"):
        res["fecha_publicacion"] = "Fecha Desconocida"
    return res

def detect_company(text: str) -> str:
    for c in COMPANIES:
        if c.lower() in text.lower():
            return c
    return ""

def parse_date(raw: str) -> str:
    if raw:
        return raw[:10]
    return "Fecha Desconocida"


# â”€â”€ Main Analysis â€” 100% Local (Regex) + Dedup + Geo â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def analyse(raw_articles: list[dict]) -> list[dict]:
    seen: set = set()
    candidates = []
    
    for art in raw_articles:
        link = art.get("link") or art.get("url") or ""
        if not link or link in seen:
            continue
        co = detect_company(art.get("full_text", ""))
        if not co:
            continue
        seen.add(link)
        art["pre_company"] = co
        candidates.append(art)
        
    log.info("Pre-filtro: %d artículos candidatos de %d totales.", len(candidates), len(raw_articles))
    
    entries = []
    dedup_count = 0
    
    for art in candidates:
        title = art.get("title", "")
        content_summary = art.get("summary", "")
        link = art.get("link") or art.get("url") or ""
        company = art["pre_company"]
        pub_date = parse_date(art.get("pub_raw", ""))
        full = art.get("full_text", "")
        source = art.get("source", "Google News")
        
        # ── Capacity: explicit GW/MW first, then financial proxy ──
        cap_gw = regex_capacity(full)
        invest_proxy = 0.0
        if cap_gw == 0.0:
            invest_proxy = regex_investment_gw(full)
            cap_gw = invest_proxy
            
        phase = regex_phase(full)
        riesgo = keyword_sentiment(full)
        target_year = regex_target_year(full)
        geo = geo_lookup(company)
        
        iodine = calc_iodine(cap_gw)
        radar_only = (cap_gw == 0.0)
        unit = "GW" if cap_gw >= 0.5 else "MW"
        disp_v = cap_gw if unit == "GW" else round(cap_gw * 1000, 1)
        cache_key = str(abs(hash(link)) % 10**12)
        
        # FIX: Evitar doble deep_scrape. run_scan ya hizo el deep_scrape y lo guardó en art["summary"], art["title"] y art["pub_raw"].
        fecha_ia = art.get("pub_raw") or "Fecha Desconocida"
        if not fecha_ia:
            fecha_ia = "Fecha Desconocida"
            
        resumen_ia_real = content_summary if content_summary else "Sin análisis detallado."
        titulo_real = title[:160] if title else ""
        
        candidate_entry = {
            "id": f"a-{cache_key}",
            "company": company,
            "capacityValue": disp_v,
            "capacityUnit": unit,
            "capacityGw": cap_gw,
            **iodine,
            "phase": phase,
            "nivel_riesgo": riesgo,
            "resumen_ia": resumen_ia_real,
            "target_year": target_year,
            "invest_proxy": invest_proxy > 0,
            "geo": geo,
            "llm_used": False,
            "radar_only": radar_only,
            "date": fecha_ia,
            "fecha_publicacion": fecha_ia,
            "source": source,
            "title": titulo_real,
            "titulo": titulo_real,
            "link": link,
            "summary": content_summary[:300],
        }
        
        # FIX: Ahora is_duplicate compara el resumen_ia_real (que es el análisis de Gemini), no un string estático genérico.
        # Esto soluciona el bug crítico donde se borraban todas las noticias.
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
    
    return consolidate_by_company(entries)





def consolidate_by_company(entries: list[dict]) -> list[dict]:
    """
    For each company, find the best target_year (non-default) and best capacity.
    Articles that have a year but no GW get the company's best GW, and vice-versa.
    This fixes the filter de-coupling bug: filtering by year now returns capacity data.

    CAPEX inflation guard (v5.5 â€” Regla de Hierro #3):
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
            # Company already at cap â€” demote this article to radar-only
            log.debug("CAPEX company cap: %s â€” artÃ­culo zeroed (acum %.2f GW)", co, accrued)
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


# ── Supabase Sync ───────────────────────────────────────────────────
def sync_to_supabase(db: dict):
    """
    Sincroniza los articulos del ciclo actual al warehouse Postgres en Supabase.

    FIX CRITICO: se eliminó por completo el Auto-Wipe (requests.delete masivo
    que vaciaba toda la tabla perovskite_leads antes de insertar). Ese borrado
    sistemático era el motivo por el que los datos parecían "desaparecer" y
    nunca se acumulaban entre ciclos. Ahora la función ÚNICAMENTE hace INSERT
    — los datos se acumulan, nunca se eliminan en masa.

    Si en el futuro se necesita evitar duplicados exactos del mismo artículo,
    eso debe resolverse con un UPSERT (on_conflict) sobre una columna única
    como 'fuente_noticia', NUNCA con un DELETE previo de toda la tabla.
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

    # ── Preparar registros para INSERT (sin DELETE previo) ──────────
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
            "fecha_publicacion": (e.get("fecha_publicacion") or e.get("date") or "Fecha Desconocida")[:30],
            "titulo":           (e.get("titulo") or e.get("title") or "")[:300],
            "analisis":         (e.get("resumen_ia") or e.get("analisis") or "Sin analisis detallado.")[:800],
        })

    if not records:
        log.info("Supabase sync: sin registros para insertar.")
        return

    # ── Batch INSERT (50 filas por lote para evitar payload limits) ──
    # Prefer: resolution=ignore-duplicates evita reventar el batch entero
    # si alguna fila choca con una constraint única existente; las demás
    # filas del lote se insertan igual. Esto reemplaza al viejo patrón de
    # "borrar todo y reinsertar todo" por uno de acumulación segura.
    BATCH = 50
    total_ok = 0
    headers_insert = {
        **_SB_HEADERS,
        "Prefer": "return=minimal,resolution=ignore-duplicates",
    }
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

    log.info("Supabase sync: %d/%d registros insertados en perovskite_leads (acumulativo, sin wipe).",
             total_ok, len(records))

# ── Build & Merge Database ────────────────────────────────────────
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

# ── Atomic Write ──────────────────────────────────────────────────
def write_database(db: dict):
    tmp = DB_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DB_FILE)
    m = db["meta"]
    log.info("database.json â€” %d art | %.3f GW | %.3f Ton I | LLM:%s | Anos:%s",
             m["article_count"], m["total_gw"], m["total_iodine_ton"],
             "ON" if m["llm_enabled"] else "OFF",
             ",".join(m.get("target_years", [])) or "-")



# â”€â”€ Hybrid Brain Tools â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
    if not q_emb: return "Error: No se pudo generar embedding para la bÃºsqueda."
    
    # 1. Intentar RPC match_knowledge
    url_rpc = f"{SUPABASE_URL}/rest/v1/rpc/match_knowledge"
    payload = {"query_embedding": q_emb, "match_count": 3, "similarity_threshold": 0.5}
    try:
        resp = requests.post(url_rpc, json=payload, headers=_SB_HEADERS, verify=False, timeout=10)
        if resp.ok:
            results = resp.json()
            if not results: return "No se encontrÃ³ informaciÃ³n en la base de datos corporativa."
            text_res = "\n".join([f"[Fuente: {r['fuente']}] {r['contenido']}" for r in results])
            return text_res
    except Exception as e:
        log.error("RPC Fallback: %s", e)
        
    # 2. Fallback local (simulaciÃ³n)
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
        if not scored: return "No se encontrÃ³ informaciÃ³n en la base de datos corporativa."
        text_res = "\n".join([f"[Fuente: {r[1]['fuente']}] {r[1]['contenido']}" for r in scored[:3]])
        return text_res
    except Exception as e:
        return f"Error en bÃºsqueda: {e}"

def tool_buscar_web(query: str) -> str:
    """Busca en DuckDuckGo en tiempo real."""
    if not DDGS: return "Error: Libreria duckduckgo_search no esta instalada."
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=3):
                url_str = r.get("href", "")
                title   = r.get("title", "")
                results.append(f"[Fuente: {url_str}] {title}")
        if not results: return "No se encontraron resultados en la web."
        return "\n".join(results)
    except Exception as e:
        return f"Error en busqueda web: {e}"

def tool_insertar_lead(empresa: str, capacidad_gw: float, target_year: str, fuente: str, fecha_publicacion: str = "", analisis: str = "") -> str:
    """Inserta un lead automÃ¡ticamente en Supabase."""
    if not SUPABASE_ENABLED: return "Error: Base de datos de leads no disponible."
    
    if not fecha_publicacion:
        fecha_publicacion = "Fecha Desconocida"
        
    if not analisis:
        analisis = f"Anuncio de capacidad de {capacidad_gw} GW por {empresa} para {target_year}."

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
        "nivel_riesgo": "Agente IA (AutomÃ¡tico)",
        "invest_proxy": False,
        "fecha_publicacion": fecha_publicacion[:10],
        "analisis": analisis[:500]
    }
    try:
        resp = requests.post(table_url, json=payload, headers={**_SB_HEADERS, "Prefer": "return=minimal"}, verify=False, timeout=10)
        if resp.ok:
            return f"Ã‰xito: Lead de {empresa} ({capacidad_gw} GW) insertado correctamente."
        else:
            return f"Error de inserciÃ³n: {resp.text}"
    except Exception as e:
        return f"Error al insertar: {e}"

TOOLS_DECLARATION = {
    "functionDeclarations": [
        {
            "name": "buscar_docs",
            "description": "Busca en la base de datos de conocimiento corporativo sobre perovskita (Supabase pgvector) usando similitud semÃ¡ntica. Obligatorio usar primero.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Consulta tÃ©cnica a buscar en la documentaciÃ³n interna."}
                },
                "required": ["query"]
            }
        },
        {
            "name": "buscar_web",
            "description": "Busca en la web en tiempo real informaciÃ³n reciente, noticias o datos faltantes. Usa esto si buscar_docs no tiene la respuesta.",
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
                    "target_year": {"type": "STRING", "description": "AÃ±o objetivo de producciÃ³n o 'TBD'"},
                    "fuente": {"type": "STRING", "description": "URL exacta o documento de origen del anuncio"},
                    "fecha_publicacion": {"type": "STRING", "description": "Fecha de publicaciÃ³n original de la noticia o anuncio (formato YYYY-MM-DD)."},
                    "analisis": {"type": "STRING", "description": "Resumen ejecutivo de 2 lÃ­neas sobre el lead."}
                },
                "required": ["empresa", "capacidad_gw", "target_year", "fuente", "fecha_publicacion", "analisis"]
            }
        }
    ]
}

# â”€â”€ Scan Cycle â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
def run_scan():
    log.info("=" * 65)
    log.info("SCAN ── %s | LLM: %s", datetime.now().strftime("%Y-%m-%d %H:%M"),
             f"Gemini Flash ✓ ({_RESOLVED_KEY[:8]}...)" if LLM_ENABLED else "OFF")
    log.info("=" * 65)



    raw = []

    for empresa in COMPANIES:
        import urllib.parse
        query = urllib.parse.quote(f"{empresa} perovskite solar news")
        feed_url = (
            f"https://news.google.com/rss/search"
            f"?q={query}&hl=en-US&gl=US&ceid=US:en"
        )
        log.info("Google News RSS: %s", empresa)

        try:
            import feedparser
            feed = feedparser.parse(feed_url)
            entries = feed.entries[:20]

            if not entries:
                log.info(" Sin resultados para %s", empresa)
                continue

            for entry in entries:
                link = getattr(entry, "link", "") or ""
                title = getattr(entry, "title", "Sin título") or "Sin título"
                summary = getattr(entry, "summary", "") or ""
                pub_raw = getattr(entry, "published", "") or ""

                if not link:
                    continue

                log.info(" Deep Scrape: %s", link)
                try:
                    ds = deep_scrape(link)
                except Exception as e:
                    log.warning(" deep_scrape falló para %s: %s", link[:60], e)
                    ds = {"fecha_publicacion": "Fecha Desconocida", "analisis": "", "titulo": ""}

                titulo_final = (ds.get("titulo") or title or "Sin título").strip()
                analisis_final = ds.get("analisis") or summary or ""
                fecha_final = ds.get("fecha_publicacion") or pub_raw or "Fecha Desconocida"

                raw.append({
                    "title": titulo_final[:160],
                    "link": link,
                    "url": link,
                    "summary": analisis_final[:300],
                    "pub_raw": fecha_final,
                    "full_text": empresa + " " + titulo_final + " " + analisis_final,
                    "source": "Google News",
                })

        except Exception as e:
            log.error("Error procesando RSS para %s: %s", empresa, e)

    log.info("Total raw: %d artículos", len(raw))
    entries = analyse(raw)

    log.info("Generando Informe Ejecutivo de Mercado...")
    market_report = generate_market_report(entries)

    db = build_database(entries, market_report)
    write_database(db)
    sync_to_supabase(db)



def schedule_scans():
    try:
        run_scan()
    except Exception as e:
        log.error("run_scan() falló por completo: %s -- se reintentará en el próximo ciclo.", e)
    t = threading.Timer(SCAN_INTERVAL_SEC, schedule_scans)
    t.daemon = True
    t.start()

# â”€â”€ HTTP Server â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
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
            result = self.handle_chat()
            status = result.pop("status", 200)
            self.send_response(status); self._cors(); self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
            return
        
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

    def handle_chat(self) -> dict:
        """Maneja el endpoint /api/chat con Function Calling para Gemini."""
        if not LLM_ENABLED:
            return {"error": "LLM API Key not configured.", "status": 503}
            
        try:
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            req_data = json.loads(body)
            user_msg = req_data.get("message", "")
            
            # Historial de conversaciÃ³n (si se implementara state)
            history = req_data.get("history", [])
            contents = history + [{"role": "user", "parts": [{"text": user_msg}]}]
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={_RESOLVED_KEY}"
            
            # EjecuciÃ³n en bucle para resolver Function Calls (max 3 iteraciones)
            MAX_ITERS = 3
            
            for iter_count in range(MAX_ITERS):
                payload = {
                    "systemInstruction": {"parts": [{"text": HYBRID_SYSTEM_PROMPT}]},
                    "contents": contents,
                    "tools": [TOOLS_DECLARATION]
                }
                
                resp = requests.post(url, json=payload, verify=False, timeout=30)
                if not resp.ok:
                    return {"error": f"API Error: {resp.text}", "status": 500}
                
                resp_json = resp.json()
                try:
                    candidate = resp_json["candidates"][0]
                    message = candidate["content"]
                    parts = message.get("parts", [])
                except KeyError:
                    return {"error": "Invalid response format from Gemini.", "status": 500}
                
                # Check for function call
                function_call = None
                for part in parts:
                    if "functionCall" in part:
                        function_call = part["functionCall"]
                        break
                        
                if function_call:
                    name = function_call["name"]
                    args = function_call.get("args", {})
                    log.info("Cerebro HÃ­brido invoca herramienta: %s(%s)", name, args)
                    
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
                            args.get("fecha_publicacion",""), args.get("analisis","")
                        )
                    else:
                        tool_res_text = "Error: Herramienta desconocida."
                        
                    log.info("Resultado %s: %s...", name, tool_res_text[:50])
                    
                    # AÃ±adir la respuesta del modelo (functionCall) y el result (functionResponse) al historial
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
                            
                    return {"reply": final_text, "status": 200}
                    
            # Si excede iteraciones
            return {"error": "Max tool loop iterations reached.", "status": 500}
            
        except Exception as e:
            log.error("POST /api/chat: %s", e)
            return {"error": str(e), "status": 400}

# â”€â”€ Entry Point â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-only", action="store_true")
    args = ap.parse_args()

    try:
        import feedparser, requests
        from bs4 import BeautifulSoup  # noqa: F401  (usado en deep_scrape)
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install",
                               "feedparser", "requests", "beautifulsoup4", "-q"])
        import feedparser, requests

    if not LLM_ENABLED:
        log.warning("â•”â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•—")
        log.warning("â•‘  GEMINI_API_KEY no configurado.                           â•‘")
        log.warning("â•‘  Edita la variable API_KEY en la lÃ­nea 18 del script.     â•‘")
        log.warning("â•‘  ObtÃ©n tu clave gratis en: https://aistudio.google.com   â•‘")
        log.warning("â•šâ•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•")
    else:
        log.info("âœ“ Gemini API Key configurada (%s...)", _RESOLVED_KEY[:8])

    if args.scan_only:
        run_scan(); sys.exit(0)

    log.info("SQM Perovskite Scout v6.0 | Supabase: %s | http://localhost:%d",
             "ON" if SUPABASE_ENABLED else "OFF", HTTP_PORT)
    threading.Thread(target=schedule_scans, daemon=True).start()
    time.sleep(2)

    server = HTTPServer(("0.0.0.0", HTTP_PORT), Handler)
    log.info("Servidor en puerto %d â€” Ctrl+C para detener.", HTTP_PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Detenido."); server.server_close()
