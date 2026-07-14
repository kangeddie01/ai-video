import json
from pathlib import Path
import shutil

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
        
    # 지정한 디렉토리의 하위 모든 파일 삭제
    @staticmethod
    def delete_directory_contents(directory_path: str | Path) -> bool:
        """
        디렉토리는 유지하고, 디렉토리 하위의 모든 파일과 폴더를 삭제한다.

        Args:
            directory_path: 하위 내용을 삭제할 디렉토리 경로

        Returns:
            삭제 성공 여부
        """
        directory = Path(directory_path)

        if not directory.exists():
            print(f"[디렉토리 없음] {directory}")
            return False

        if not directory.is_dir():
            print(f"[디렉토리가 아님] {directory}")
            return False

        for child in directory.iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()

        print(f"[디렉토리 하위 전체 삭제 완료] {directory}")
        return True        