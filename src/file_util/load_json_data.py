import json
from pathlib import Path


def load_bible_json_data(path: str | None = None) -> dict:
    if path is None:
        data_path = Path(__file__).resolve().parents[1] / "data" / "bible_json"
    else:
        data_path = Path(path)

    with data_path.open("r", encoding="utf-8") as f:
        return json.load(f)


