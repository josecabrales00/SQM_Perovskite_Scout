import sys
import os

# Agregamos la ruta principal del proyecto para poder importar scout_agent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scout_agent import Handler

class handler(Handler):
    def do_POST(self):
        """Vercel Serverless entrypoint for POST /api/chat"""
        self.handle_chat()

    def do_OPTIONS(self):
        """CORS Preflight"""
        self.send_response(200)
        self._cors()
        self.end_headers()
