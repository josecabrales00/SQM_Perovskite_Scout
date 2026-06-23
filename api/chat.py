import sys
import os
import json

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scout_agent import Handler
import scout_agent

class handler(Handler):
    def send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

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

            result = self.handle_chat()
            status = result.pop("status", 200)
            self.send_json(status, result)
            
        except Exception as e:
            self.send_json(500, {"error": str(e)})

    def do_OPTIONS(self):
        """CORS Preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization, apikey')
        self.end_headers()
