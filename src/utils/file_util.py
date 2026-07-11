import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

class FileUtil:

    @staticmethod
    def abspath(path):
        path = Path(path)
        if path.is_absolute():
            return str(path)
        return str((PROJECT_ROOT / path).resolve())

    # json파일 경로에서 json 데이터 조회하여 리턴
    @staticmethod
    def get_json_data(path: str | Path):
        json_path = Path(path)

        if not json_path.exists():
            raise FileNotFoundError(f"JSON 파일이 없습니다: {json_path}")

        with json_path.open("r", encoding="utf-8") as f:
            return json.load(f)