from pathlib import Path
import os
import sys
from openai import OpenAI

def load_api_key() -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key

    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, value = line.split("=", 1)
            if key.strip() == "OPENAI_API_KEY":
                value = value.strip().strip('"').strip("'")
                os.environ["OPENAI_API_KEY"] = value
                return value

    return None

def check_api_key(api_key):
    if not api_key:
        sys.exit(
        "ERROR: OPENAI_API_KEY not set. "
        "Set it in Windows Environment Variables, restart the terminal, "
        "or create a .env file with OPENAI_API_KEY=... and retry."
    )
        
def getOpenAIClient():
    api_key = load_api_key()
    check_api_key(api_key)
    return OpenAI(api_key=api_key)        