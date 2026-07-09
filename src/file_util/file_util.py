from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

def abspath(path):
    path = Path(path)
    if path.is_absolute():
        return str(path)
    return str((PROJECT_ROOT / path).resolve())