-- ══════════════════════════════════════════════════════════════════
--  SQM Perovskite Scout — Migración RAG v1.0
--  Tabla: perovskite_knowledge
--  PEGAR EN: https://supabase.com/dashboard/project/rpibprkdzoxfizssvtuf/sql/new
-- ══════════════════════════════════════════════════════════════════

-- 1. Habilitar pgvector (ya debe estar habilitado de la migración anterior)
CREATE EXTENSION IF NOT EXISTS vector SCHEMA extensions;

-- 2. Tabla de conocimiento vectorial
CREATE TABLE IF NOT EXISTS public.perovskite_knowledge (
    id         bigint   GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contenido  text     NOT NULL,
    fuente     text     NOT NULL,
    embedding  extensions.vector(768)  -- Google text-embedding-004
);

-- Índice HNSW para búsqueda ANN de alta velocidad (coseno)
CREATE INDEX IF NOT EXISTS idx_perovskite_knowledge_embedding
    ON public.perovskite_knowledge
    USING hnsw (embedding extensions.vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- Índice de fuente para filtrado por documento
CREATE INDEX IF NOT EXISTS idx_perovskite_knowledge_fuente
    ON public.perovskite_knowledge (fuente);

-- 3. RLS: INSERT anónimo (agente Python), SELECT autenticado
ALTER TABLE public.perovskite_knowledge ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "insert_anon_knowledge" ON public.perovskite_knowledge;
CREATE POLICY "insert_anon_knowledge"
    ON public.perovskite_knowledge FOR INSERT TO anon
    WITH CHECK (true);

DROP POLICY IF EXISTS "select_auth_knowledge" ON public.perovskite_knowledge;
CREATE POLICY "select_auth_knowledge"
    ON public.perovskite_knowledge FOR SELECT TO authenticated
    USING (true);

-- También permitir DELETE para service_role (para limpiar en re-ingestas)
DROP POLICY IF EXISTS "delete_service_knowledge" ON public.perovskite_knowledge;
CREATE POLICY "delete_service_knowledge"
    ON public.perovskite_knowledge FOR DELETE TO service_role
    USING (true);

-- 4. Función de búsqueda semántica por similitud coseno
CREATE OR REPLACE FUNCTION match_knowledge(
    query_embedding  extensions.vector(768),
    match_count      int  DEFAULT 5,
    similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
    id          bigint,
    contenido   text,
    fuente      text,
    similarity  float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pk.id,
        pk.contenido,
        pk.fuente,
        1 - (pk.embedding <=> query_embedding) AS similarity
    FROM public.perovskite_knowledge pk
    WHERE 1 - (pk.embedding <=> query_embedding) > similarity_threshold
    ORDER BY pk.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Comentarios de documentación
COMMENT ON TABLE  public.perovskite_knowledge IS
    'Base de datos vectorial RAG: fragmentos de conocimiento científico sobre perovskita y yodo.';
COMMENT ON COLUMN public.perovskite_knowledge.embedding IS
    'Vector 768 dims — Google text-embedding-004. Índice HNSW para búsqueda semántica.';
COMMENT ON FUNCTION match_knowledge IS
    'Búsqueda semántica por similitud coseno. Umbral default=0.5, top-k default=5.';
