Setup and run:

1. Install dependencies:

```
pip install -r requirements.txt
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

3. Run the script:

```
python src/ai_image_create.py
```
