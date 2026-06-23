# Proyecto: SQM Perovskite Scout - Business Analytics

## Reglas de Desarrollo
- El stack tecnológico frontend debe ser HTML5 nativo, CSS3 mediante Tailwind CSS (vía CDN o compilado local) y JavaScript plano (Vanilla JS). No uses frameworks pesados como React o Vue.
- Toda la visualización de datos de la interfaz debe implementarse mediante la librería Chart.js.
- Se prohíbe de forma estricta escribir secretos, API keys o la service_role key de Supabase directamente en los archivos del cliente (frontend). Toda credencial debe inyectarse mediante variables de entorno en el backend corporativo.
- Mantén una estética "premium" corporativa con diseño mobile-first: aplica una paleta de colores basada en la identidad de SQM (Morado institucional, Verde tecnológico y tonos Grises oscuros de fondo para el modo oscuro con efectos de glassmorphism).

## Workflows y Skills Reutilizables
- Define el comando personalizado `/verificar`. Cuando invoque este comando, debes abrir de forma automática el archivo `index.html` en el entorno de pruebas del navegador integrado, validar que el diseño no esté roto, constatar el correcto renderizado de Chart.js y desplegar una captura de pantalla como evidencia técnica obligatoria antes de declarar la tarea por terminada.
