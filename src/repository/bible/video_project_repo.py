import json
import sqlite3
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "app.db"


# =========================================================
# 공통 함수
# =========================================================
def convert_to_json_text(
    value: dict | list | str | None,
) -> str | None:
    """
    dict 또는 list는 JSON 문자열로 변환한다.
    문자열은 그대로 반환한다.
    """
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return json.dumps(
            value,
            ensure_ascii=False,
        )

    if isinstance(value, str):
        return value

    raise TypeError(
        "default_param은 dict, list, str, None만 가능합니다. "
        f"현재 타입: {type(value).__name__}"
    )


def parse_json_text(
    value: str | None,
) -> Any:
    """
    JSON 문자열을 Python 객체로 변환한다.

    JSON 변환에 실패하거나 값이 없으면 빈 딕셔너리를 반환한다.
    """
    if not value:
        return {}

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


# =========================================================
# INSERT
# =========================================================
def insert_video_project(
    project_no: int,
    project_name: str | None,
    project_en_word: str | None,
    project_desc: str | None,
    schedule_status: str,
    job_cron: str | None,
    default_param: dict | list | str | None,
) -> bool:
    """
    video_project 테이블에 프로젝트를 등록한다.

    created_at과 updated_at은 현재 시각으로 저장한다.

    Returns:
        True: 등록 성공
        False: 등록 실패
    """
    default_param_json = convert_to_json_text(
        default_param
    )

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO video_project (
                project_no,
                project_name,
                project_en_word,
                project_desc,
                schedule_status,
                job_cron,
                default_param_json,
                created_at,
                updated_at
            )
            VALUES (
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            )
            """,
            (
                project_no,
                project_name,
                project_en_word,
                project_desc,
                schedule_status,
                job_cron,
                default_param_json,
            ),
        )

        return cursor.rowcount > 0


# =========================================================
# SELECT
# =========================================================
def select_project(
    project_no: int | None = None,
) -> list[dict]:
    """
    video_project 데이터를 조회한다.

    project_no가 없으면:
        전체 프로젝트 조회

    project_no가 있으면:
        해당 프로젝트만 조회

    Returns:
        항상 list[dict] 형태로 반환
    """
    query = """
        SELECT
            project_no,
            project_name,
            project_en_word,
            project_desc,
            schedule_status,
            job_cron,
            default_param_json,
            created_at,
            updated_at
        FROM video_project
    """

    params: list[Any] = []

    if project_no is not None:
        query += " WHERE project_no = ?"
        params.append(project_no)

    query += " ORDER BY project_no ASC"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            query,
            tuple(params),
        )
        rows = cursor.fetchall()

    projects: list[dict] = []

    for row in rows:
        project = dict(row)

        project["default_param"] = parse_json_text(
            project.get("default_param_json")
        )

        projects.append(project)

    return projects


def select_project_one(
    project_no: int,
) -> dict | None:
    """
    project_no로 프로젝트 한 건을 조회한다.

    Returns:
        조회 성공: dict
        조회 결과 없음: None
    """
    projects = select_project(
        project_no=project_no,
    )

    if not projects:
        return None

    return projects[0]


# =========================================================
# UPDATE
# =========================================================
def update_video_project(
    project_no: int,
    project_name: str | None,
    project_en_word: str | None,
    project_desc: str | None,
    schedule_status: str,
    job_cron: str | None,
    default_param: dict | list | str | None,
) -> bool:
    """
    project_no를 기준으로 프로젝트 정보를 수정한다.

    updated_at은 현재 시각으로 변경한다.
    created_at은 변경하지 않는다.

    전달된 None 값은 실제 데이터베이스에 NULL로 저장된다.

    Returns:
        True: 수정 성공
        False: 해당 project_no 데이터가 없음
    """
    default_param_json = convert_to_json_text(
        default_param
    )

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE video_project
            SET
                project_name = ?,
                project_en_word = ?,
                project_desc = ?,
                schedule_status = ?,
                job_cron = ?,
                default_param_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE project_no = ?
            """,
            (
                project_name,
                project_en_word,
                project_desc,
                schedule_status,
                job_cron,
                default_param_json,
                project_no,
            ),
        )

        return cursor.rowcount > 0


def update_video_project_schedule(
    project_no: int,
    schedule_status: str,
    job_cron: str | None = None,
) -> bool:
    """
    프로젝트의 스케줄 상태와 크론 표현식만 수정한다.

    job_cron이 None이면 기존 job_cron 값을 유지한다.

    Returns:
        True: 수정 성공
        False: 해당 project_no 데이터가 없음
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE video_project
            SET
                schedule_status = ?,
                job_cron = COALESCE(?, job_cron),
                updated_at = CURRENT_TIMESTAMP
            WHERE project_no = ?
            """,
            (
                schedule_status,
                job_cron,
                project_no,
            ),
        )

        return cursor.rowcount > 0


# =========================================================
# DELETE
# =========================================================
def delete_video_project(
    project_no: int,
) -> bool:
    """
    project_no를 기준으로 video_project 데이터를 삭제한다.

    Returns:
        True: 삭제 성공
        False: 해당 project_no 데이터가 없음
    """
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            DELETE FROM video_project
            WHERE project_no = ?
            """,
            (project_no,),
        )

        return cursor.rowcount > 0


# =========================================================
# 실행 예시
# =========================================================
if __name__ == "__main__":
    # 프로젝트 등록
    inserted = insert_video_project(
        project_no=1,
        project_name="성경책 낭독",
        project_en_word="bible",
        project_desc=(
            "성경 음성을 생성하고 배경 이미지와 자막을 "
            "합성하여 영상으로 제작하는 프로젝트"
        ),
        job_cron="0 6 * * *",
        schedule_status="deactivate",
        default_param={
            "intro_bg_path": (
                "data/bible/images/start_img.png"
            ),
            "video_root": "data/bible/video",
            "width": 1920,
            "height": 1080,
            "fps": 30,
        },
    )

    print("등록 성공:", inserted)

    # 프로젝트 수정
    updated = update_video_project(
        project_no=1,
        project_name="성경책 자동 낭독 영상",
        project_en_word="bible",
        project_desc=(
            "성경 음성 및 자막 영상을 자동으로 생성하는 "
            "배치 프로젝트"
        ),
        schedule_status="activate",
        job_cron="30 3 * * *",
        default_param={
            "intro_bg_path": (
                "data/bible/images/start_img.png"
            ),
            "video_root": "data/bible/video",
            "width": 1920,
            "height": 1080,
            "fps": 30,
            "start_chapter": 1,
            "end_chapter": None,
        },
    )

    print("수정 성공:", updated)

    # 단건 조회
    project = select_project_one(
        project_no=1,
    )

    print("단건 조회:", project)

    # 전체 조회
    projects = select_project()

    for item in projects:
        print(item)