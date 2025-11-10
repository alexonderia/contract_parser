from fastapi import FastAPI, HTTPException
from app.ollama_client import OllamaClient

app = FastAPI(title="Contract Parser")

ollama = OllamaClient(base_url="http://ollama:11434")  # контейнер ollama по имени

@app.get("/")
def root():
    return {"message": "Ollama API connection service is running."}

@app.get("/status")
def check_status():
    try:
        status = ollama.check_connection()
        return {"status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
