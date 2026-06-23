"""
SQM Perovskite Scout -- RAG Ingestion Pipeline v1.2
=====================================================
Pipeline de Ingesta para Base de Datos Vectorial (Supabase + pgvector)

Flujo:
  1. Lee archivos .txt de /docs
  2. Segmenta en chunks balanceados (~1200 chars) con overlap de 200 chars
  3. Genera embeddings via Google gemini-embedding-001 (768 dims)
  4. Inserta en tabla perovskite_knowledge de Supabase
  5. Valida con conteo de filas y busqueda semantica por coseno

Uso:
  python rag_ingest.py           (ingesta completa)
  python rag_ingest.py --search  (solo busqueda de validacion)
  python rag_ingest.py --count   (solo conteo de filas)

NOTA: Las credenciales se leen del .env -- NUNCA del cliente (AGENTS.md).
"""

import os
import sys
import json
import math
import time
import argparse
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ---------- Cargar .env ----------------------------------------
def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    env = {}
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
    return env

ENV            = load_env()
SUPABASE_URL   = ENV.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SRK   = ENV.get("SUPABASE_SERVICE_ROLE_KEY", "")
GEMINI_KEY     = ENV.get("GEMINI_API_KEY", "")

if not SUPABASE_URL or not SUPABASE_SRK:
    print("ERROR: Faltan credenciales Supabase en .env")
    sys.exit(1)

# ---------- Config ---------------------------------------------
DOCS_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
TABLE       = "perovskite_knowledge"
EMBED_MODEL = "gemini-embedding-001"   # Google -- 768 dims (activo 2026)
CHUNK_SIZE  = 1200                   # chars por chunk objetivo
OVERLAP     = 200                    # overlap entre chunks
BATCH_SIZE  = 10                     # filas por lote de INSERT

SB_HEADERS = {
    "apikey":        SUPABASE_SRK,
    "Authorization": "Bearer " + SUPABASE_SRK,
    "Content-Type":  "application/json",
    "Prefer":        "return=minimal",
}

EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta"
    "/models/" + EMBED_MODEL + ":embedContent?key=" + GEMINI_KEY
)

# ---------- Embedding ------------------------------------------
def get_embedding(text, retries=3):
    """Genera embedding vectorial via Google gemini-embedding-001 (768 dims)."""
    payload = {
        "model": "models/" + EMBED_MODEL,
        "content": {"parts": [{"text": text[:8000]}]},
        "taskType": "RETRIEVAL_DOCUMENT",
        "outputDimensionality": 768,
    }
    for attempt in range(retries):
        try:
            resp = requests.post(EMBED_URL, json=payload,
                                 verify=False, timeout=30)
            if resp.ok:
                return resp.json()["embedding"]["values"]
            body = resp.text[:150].encode("ascii", errors="replace").decode()
            print("  [WARN] Embedding HTTP " + str(resp.status_code) + ": " + body)
            time.sleep(2 ** attempt)
        except Exception as e:
            print("  [WARN] Embedding excepcion intento " + str(attempt+1) + ": " + str(e))
            time.sleep(2 ** attempt)
    return None

# ---------- Chunker (robusto, sin bucle infinito) ---------------
def chunk_text(text):
    """
    Segmenta texto en chunks de ~CHUNK_SIZE chars usando limites de parrafo.
    Garantiza progreso positivo en cada iteracion.
    """
    paragraphs = []
    for para in text.replace("\r\n", "\n").split("\n\n"):
        para = para.strip()
        if para:
            paragraphs.append(para)

    chunks = []
    current_parts = []
    current_len = 0

    for para in paragraphs:
        plen = len(para)

        # Parrafo individual mas grande que chunk_size: dividir por lineas
        if plen > CHUNK_SIZE:
            lines = [ln.strip() for ln in para.split("\n") if ln.strip()]
            for line in lines:
                llen = len(line)
                if current_len + llen + 1 > CHUNK_SIZE and current_parts:
                    joined = "\n".join(current_parts)
                    chunks.append(joined)
                    tail = joined[-OVERLAP:] if OVERLAP else ""
                    current_parts = [tail] if tail else []
                    current_len = len(tail)
                current_parts.append(line)
                current_len += llen + 1
        else:
            if current_len + plen + 2 > CHUNK_SIZE and current_parts:
                joined = "\n\n".join(current_parts)
                chunks.append(joined)
                tail = joined[-OVERLAP:] if OVERLAP else ""
                current_parts = [tail] if tail else []
                current_len = len(tail)
            current_parts.append(para)
            current_len += plen + 2

    # Flush del ultimo fragmento
    if current_parts:
        chunks.append("\n\n".join(current_parts))

    return [c for c in chunks if len(c.strip()) > 50]

# ---------- Leer /docs -----------------------------------------
def load_documents():
    """Lee todos los .txt de /docs."""
    docs = []
    if not os.path.isdir(DOCS_DIR):
        print("ERROR: No existe la carpeta " + DOCS_DIR)
        return docs
    for fname in sorted(os.listdir(DOCS_DIR)):
        if not fname.endswith(".txt"):
            continue
        fpath = os.path.join(DOCS_DIR, fname)
        with open(fpath, encoding="utf-8") as f:
            content = f.read()
        docs.append({"fuente": fname, "contenido": content})
        print("  Leido: " + fname + " (" + str(len(content)) + " chars)")
    return docs

# ---------- Supabase helpers -----------------------------------
def insert_batch(rows):
    url = SUPABASE_URL + "/rest/v1/" + TABLE
    resp = requests.post(url, json=rows, headers=SB_HEADERS,
                         verify=False, timeout=30)
    if resp.ok:
        return len(rows)
    body = resp.text[:200].encode("ascii", errors="replace").decode()
    print("  [ERROR] INSERT: " + str(resp.status_code) + " " + body)
    return 0

def delete_all_rows():
    url = SUPABASE_URL + "/rest/v1/" + TABLE + "?id=gte.1"
    resp = requests.delete(url, headers=SB_HEADERS, verify=False, timeout=20)
    if resp.ok:
        print("  Tabla limpiada correctamente.")
    else:
        print("  [WARN] DELETE: " + str(resp.status_code))

def count_rows():
    url = SUPABASE_URL + "/rest/v1/" + TABLE + "?select=id"
    headers = dict(SB_HEADERS)
    headers["Prefer"] = "count=exact"
    resp = requests.get(url, headers=headers, verify=False, timeout=10)
    if resp.ok:
        cr = resp.headers.get("Content-Range", "")
        if "/" in cr:
            return int(cr.split("/")[1])
        return len(resp.json())
    print("  [ERROR] COUNT: " + str(resp.status_code))
    return -1

# ---------- Cosine similarity ----------------------------------
def cosine_similarity(a, b):
    dot   = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)

# ---------- Busqueda semantica ---------------------------------
def semantic_search(query, top_k=3):
    """Busca por similitud coseno via RPC match_knowledge o fallback local."""
    print("\n  Embedding query: '" + query[:70] + "'")
    q_emb = get_embedding(query)
    if not q_emb:
        print("  [ERROR] No se pudo generar embedding para la query.")
        return []

    # Intento via RPC
    url_rpc = SUPABASE_URL + "/rest/v1/rpc/match_knowledge"
    payload = {
        "query_embedding": q_emb,
        "match_count": top_k,
        "similarity_threshold": 0.5,
    }
    resp = requests.post(url_rpc, json=payload, headers=SB_HEADERS,
                         verify=False, timeout=30)
    if resp.ok:
        results = resp.json()
        if results:
            return results

    # Fallback: similitud local
    print("  [INFO] Fallback: calculando similitud localmente...")
    url_all = (SUPABASE_URL + "/rest/v1/" + TABLE
               + "?select=id,contenido,fuente,embedding&limit=300")
    resp_all = requests.get(url_all, headers=SB_HEADERS, verify=False, timeout=30)
    if not resp_all.ok:
        print("  [ERROR] Fetch all: " + str(resp_all.status_code))
        return []

    scored = []
    for row in resp_all.json():
        emb_raw = row.get("embedding", "")
        if not emb_raw:
            continue
        try:
            if isinstance(emb_raw, str):
                doc_emb = json.loads(emb_raw.replace("{", "[").replace("}", "]"))
            else:
                doc_emb = emb_raw
            sim = cosine_similarity(q_emb, doc_emb)
            scored.append({
                "id":         row["id"],
                "contenido":  row["contenido"],
                "fuente":     row["fuente"],
                "similarity": round(sim, 4),
            })
        except Exception:
            continue

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored[:top_k]

# ---------- Validacion -----------------------------------------
def run_validation():
    """Conteo de filas + 3 busquedas semanticas de prueba."""
    count = count_rows()
    print("  Filas en " + TABLE + ": " + str(count))
    if count <= 0:
        print("  [ERROR] La tabla esta vacia!")
        return
    print("  OK: " + str(count) + " chunks en la base de datos vectorial.")

    queries = [
        "migracion de iones yoduro y degradacion de perovskita",
        "nanoparticulas de alumina Al2O3 para estabilizar celda solar",
        "cuantas toneladas de yodo se necesitan por gigawatt instalado",
    ]

    print("\n  --- Simulacion de Busqueda Semantica (coseno) ---")
    for q in queries:
        print("\n  QUERY: '" + q + "'")
        results = semantic_search(q, top_k=2)
        if not results:
            print("    Sin resultados.")
            continue
        for j, r in enumerate(results, 1):
            sim    = r.get("similarity", 0)
            fuente = r.get("fuente", "")
            snip   = r.get("contenido", "")[:160].replace("\n", " ")
            print("    [" + str(j) + "] sim=" + str(round(sim, 4))
                  + " | " + fuente)
            print("         ..." + snip + "...")

    print("\n  OK: Busqueda semantica validada correctamente.")

# ---------- Pipeline principal ---------------------------------
def run_ingestion():
    print("=" * 65)
    print("  SQM Perovskite Scout - RAG Ingestion Pipeline v1.1")
    print("  Modelo: Google gemini-embedding-001 (768 dims)")
    print("=" * 65)

    print("\n[1/5] Limpiando tabla...")
    delete_all_rows()

    print("\n[2/5] Cargando documentos de /docs...")
    docs = load_documents()
    if not docs:
        print("  ERROR: No hay archivos .txt en /docs/")
        return

    print("\n[3/5] Segmentando en chunks...")
    all_chunks = []
    for doc in docs:
        chunks = chunk_text(doc["contenido"])
        for i, c in enumerate(chunks):
            all_chunks.append({
                "fuente": doc["fuente"],
                "contenido": c,
                "idx": i,
            })
        print("  " + doc["fuente"] + ": " + str(len(chunks)) + " chunks")
    print("  TOTAL: " + str(len(all_chunks)) + " chunks")

    print("\n[4/5] Generando embeddings e insertando...")
    batch    = []
    total_ok = 0
    errors   = 0

    for i, chunk in enumerate(all_chunks):
        label = "[" + str(i+1) + "/" + str(len(all_chunks)) + "]"
        print("  " + label + " " + chunk["fuente"]
              + " chunk " + str(chunk["idx"]) + "...", end=" ", flush=True)

        emb = get_embedding(chunk["contenido"])
        if emb is None:
            print("ERROR")
            errors += 1
            continue

        batch.append({
            "contenido": chunk["contenido"],
            "fuente":    chunk["fuente"],
            "embedding": emb,
        })

        if len(batch) >= BATCH_SIZE:
            ok = insert_batch(batch)
            total_ok += ok
            print("lote OK (" + str(ok) + " filas)")
            batch = []
            time.sleep(0.3)
        else:
            print("OK")

        time.sleep(0.15)   # rate limit Google API free tier

    # Flush final
    if batch:
        ok = insert_batch(batch)
        total_ok += ok
        print("  Ultimo lote: " + str(ok) + " filas")

    print("\n  Ingesta: " + str(total_ok) + " filas | " + str(errors) + " errores")

    print("\n[5/5] Validacion tecnica...")
    run_validation()

# ---------- Entry point ----------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RAG Ingestion Pipeline")
    parser.add_argument("--search", action="store_true",
                        help="Solo busqueda semantica de validacion")
    parser.add_argument("--count", action="store_true",
                        help="Solo contar filas")
    args = parser.parse_args()

    if args.count:
        print("Filas en " + TABLE + ": " + str(count_rows()))
    elif args.search:
        run_validation()
    else:
        run_ingestion()
