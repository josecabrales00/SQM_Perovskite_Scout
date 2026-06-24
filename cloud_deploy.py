import os
import requests
import base64
import json

def _load_dotenv():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
_load_dotenv()

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
VERCEL_TOKEN = os.environ.get("VERCEL_TOKEN", "")
REPO_NAME = "SQM_Perovskite_Scout"

def deploy():
    print("Iniciando despliegue en la nube...")
    # 1. GITHUB DEPLOY
    gh_headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"}
    
    user_res = requests.get("https://api.github.com/user", headers=gh_headers)
    if not user_res.ok:
        print("Error getting GitHub user:", user_res.text)
        return
        
    username = user_res.json().get("login")
    
    ignore_dirs = ['.git', '__pycache__', '.gemini']
    ignore_files = ['.env', 'cloud_deploy.py']
    
    print(f"Autenticado en GitHub como: {username}")

    # Create Repo
    repo_res = requests.post("https://api.github.com/user/repos", headers=gh_headers, json={"name": REPO_NAME, "private": False, "auto_init": True})
    import time
    time.sleep(3) # Wait for auto_init
    
    print("Subiendo archivos principales a GitHub...")
    files_to_upload = ['index.html', 'app.js', 'AGENTS.md', 'scout_agent.py', 'database.json', 'rag_ingest.py', 'migrate_knowledge.sql', 'rls_patch.sql', 'cloud_deploy.py', 'requirements.txt', 'api/chat.py', 'logo.png']
    
    for f in files_to_upload:
        if not os.path.exists(f): continue
        with open(f, "rb") as file_obj:
            content = file_obj.read()
        
        # Check if file exists to get its SHA (in case of updates)
        file_url = f"https://api.github.com/repos/{username}/{REPO_NAME}/contents/{f}"
        file_res = requests.get(file_url, headers=gh_headers)
        payload = {
            "message": f"v1.3.5 - Anti-Ban Rate Limit - {f}",
            "content": base64.b64encode(content).decode('utf-8')
        }
        if file_res.ok:
            payload["sha"] = file_res.json()["sha"]
            
        put_res = requests.put(file_url, headers=gh_headers, json=payload)
        if put_res.ok:
            print(f"Archivo {f} subido correctamente.")
        else:
            print(f"Error subiendo {f}: {put_res.text}")
            
    gh_url = f"https://github.com/{username}/{REPO_NAME}"
    print(f"\\n[GITHUB] Repositorio configurado y código subido: {gh_url}")

    # 2. VERCEL DEPLOY
    print("\\nIniciando despliegue en Vercel...")
    v_headers = {"Authorization": f"Bearer {VERCEL_TOKEN}"}
    
    vercel_files = []
    # Deploy only code files for frontend/backend (no docs or binaries to avoid payload limits)
    allowed_exts = [".html", ".js", ".json", ".css", ".md", ".py", ".sql", ".txt", ".png"]
    
    for root, dirs, files in os.walk("."):
        if any(ig in root for ig in ignore_dirs + ["docs", "tmp"]):
            continue
        for f in files:
            if f in ignore_files:
                continue
            if not any(f.endswith(ext) for ext in allowed_exts):
                continue
                
            filepath = os.path.join(root, f)
            relpath = os.path.relpath(filepath, ".").replace("\\", "/")
            
            with open(filepath, "rb") as file_obj:
                content = file_obj.read()
            
            if filepath.endswith('.png'):
                vercel_files.append({"file": relpath, "data": base64.b64encode(content).decode('utf-8'), "encoding": "base64"})
            else:
                try:
                    decoded_content = content.decode('utf-8')
                    vercel_files.append({"file": relpath, "data": decoded_content})
                except UnicodeDecodeError:
                    pass
            
    v_payload = {
        "name": "sqm-perovskite-scout",
        "projectSettings": {"framework": None},
        "files": vercel_files
    }
    
    v_res = requests.post("https://api.vercel.com/v13/deployments", headers=v_headers, json=v_payload)
    if v_res.status_code in [200, 201]:
        v_url = v_res.json()["url"]
        print(f"[VERCEL] Despliegue exitoso: https://{v_url}")
    else:
        print(f"[VERCEL] Error de despliegue: {v_res.text}")

if __name__ == "__main__":
    deploy()
