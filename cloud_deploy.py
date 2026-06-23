import os
import requests
import base64
import json

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
    files_to_upload = ['index.html', 'app.js', 'AGENTS.md', 'scout_agent.py', 'database.json', 'rag_ingest.py', 'migrate_knowledge.sql', 'rls_patch.sql', 'cloud_deploy.py']
    
    for f in files_to_upload:
        if not os.path.exists(f): continue
        with open(f, "rb") as file_obj:
            content = file_obj.read()
        
        # Check if file exists to get its SHA (in case of updates)
        file_url = f"https://api.github.com/repos/{username}/{REPO_NAME}/contents/{f}"
        file_res = requests.get(file_url, headers=gh_headers)
        payload = {
            "message": f"Add {f} - v1.0 SQM Enterprise Release",
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

    # 2. VERCEL DEPLOY (Skipped per user request)
    print("\\nDespliegue Vercel omitido en esta ejecución.")

if __name__ == "__main__":
    deploy()
