import sys
import os
import json

# Agregamos la ruta principal del proyecto para poder importar scout_agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scout_agent import Handler
import scout_agent

class handler(Handler):
    def do_POST(self):
        """Vercel Serverless entrypoint for POST /api/chat"""
        try:
            # Inicializar credenciales dinámicamente en cada ejecución
            gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if gemini_key:
                scout_agent._RESOLVED_KEY = gemini_key
                scout_agent.LLM_ENABLED = True
                
            supa_url = os.environ.get("SUPABASE_URL", "").strip()
            supa_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            if supa_url and supa_key:
                scout_agent.SUPABASE_URL = supa_url
                scout_agent.SUPABASE_SERVICE_ROLE = supa_key
                scout_agent._SB_HEADERS["Authorization"] = f"Bearer {supa_key}"
                scout_agent._SB_HEADERS["apikey"] = supa_key
                scout_agent.SUPABASE_ENABLED = True

            self.handle_chat()
        except Exception as e:
            self.send_response(500)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        """CORS Preflight"""
        self.send_response(200)
        self._cors()
        self.end_headers()
