-- Parche de Seguridad (MVP)
-- Habilitar lectura pública para que el cliente (app.js) pueda renderizar los KPIs y la tabla sin login.

ALTER TABLE public.perovskite_leads ENABLE ROW LEVEL SECURITY;

-- Política para permitir SELECT a usuarios anónimos
CREATE POLICY "Permitir lectura pública a anon"
ON public.perovskite_leads
FOR SELECT
TO anon
USING (true);
