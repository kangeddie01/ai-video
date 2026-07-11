import json
import sqlite3
from pathlib import Path


DB_PATH = Path("app.db")


def insert_video_project(
    project_no: int,
    project_name: str | None,
    project_en_word: str | None,
    schedule_status: str,
    job_cron: str | None,
    default_param: dict | None,
) -> bool:
    """
    video_project 테이블에 프로젝트를 등록한다.

    Returns:
        True: 등록 성공
        False: 등록 실패
    """
    default_param_json = (
        json.dumps(default_param, ensure_ascii=False)
        if default_param is not None
        else None
    )

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO video_project (
                project_no,
                project_name,
                project_en_word,
                schedule_status,
                job_cron,
                default_param_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                project_no,
                project_name,
                project_en_word,
                schedule_status,
                job_cron,
                default_param_json,
            ),
        )

        return cursor.rowcount > 0


def delete_video_project(project_no: int) -> bool:
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


def select_project(
    project_no: int | None = None,
) -> list[dict]:
    """
    project_no가 없으면 전체 조회한다.
    project_no가 있으면 해당 프로젝트만 조회한다.

    Returns:
        항상 list[dict] 형태로 반환한다.
    """
    query = """
        SELECT
            project_no,
            project_name,
            project_en_word,
            schedule_status,
            job_cron,
            default_param_json
        FROM video_project
    """

    params: tuple = ()

    if project_no is not None:
        query += " WHERE project_no = ?"
        params = (project_no,)

    query += " ORDER BY project_no"

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

    projects: list[dict] = []

    for row in rows:
        project = dict(row)

        default_param_json = project.get("default_param_json")

        if default_param_json:
            try:
                project["default_param"] = json.loads(
                    default_param_json
                )
            except json.JSONDecodeError:
                project["default_param"] = {}
        else:
            project["default_param"] = {}

        projects.append(project)

    return projects


if __name__ == "__main__":
    inserted = insert_video_project(
        project_no=1,
        project_name="성경책 낭독",
        project_en_word="bible",
        job_cron="0 6 * * *",
        schedule_status="deactivate",
        default_param={
            "intro_bg_path": "data/bible/images/start_img.png",
            "video_root": "data/bible/video",
            "width": 1920,
            "height": 1080,
            "fps": 30,
        },
    )

    print("등록 성공:", inserted)

    projects = select_project(project_no=1)

    for project in projects:
        print(project)