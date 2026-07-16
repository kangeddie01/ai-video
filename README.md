Setup and run:

1. Install dependencies:

```
pip install -r requirements.txt
```

If FastAPI is not installed in your environment yet, also install:

```
pip install fastapi uvicorn
```

2. Set your OpenAI API key.

You can use one of these methods:

- PowerShell (for the current terminal only):

```
$env:OPENAI_API_KEY = "sk-..."
```

- Windows Environment Variables (persists across terminals, but you must restart VS Code / the terminal after changing it)

- Project-local .env file (recommended for this project): create a file named .env in the project root with:

```
OPENAI_API_KEY=sk-...
```

3. Run the FastAPI server:

```
uvicorn src.fastapi.app:app --reload --host 0.0.0.0 --port 8000
```

Then open:

- API docs: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

Example request:

```
curl -X POST "http://127.0.0.1:8000/generate/voice" -H "Content-Type: application/json" -d "{\"vender\":\"google-tts\",\"text\":\"Hello world\",\"voice\":\"en-US-Neural2-A\"}"
```

4. Run the script (if you want to use the non-API workflow):

```
python src/ai_image_create.py
python -m src.ai_image_create.py
```

5. 가상환경 접속
```
.\.venv\Scripts\Activate.ps1
```
