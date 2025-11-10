import requests

class OllamaClient:
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url.rstrip("/")

    def check_connection(self):
        """Проверка состояния Ollama через его API."""
        url = f"{self.base_url}/api/tags"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            return "connected"
        else:
            return f"failed ({response.status_code})"
