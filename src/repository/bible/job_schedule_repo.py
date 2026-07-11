import json
import sqlite3
from pathlib import Path
from typing import Any


DB_PATH = Path("app.db")


# =========================================================
# 공통 함수
# =========================================================
def convert_to_json_text(value: dict | list | str | None) -> str | None:
    """
    dict 또는 list는 JSON 문자열로 변환한다.
    문자열은 그대로 반환한다.
    """
    if value is None:
        return None

    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    if isinstance(value, str):
        return value

    raise TypeError(
        f"JSON 파라미터는 dict, list, str, None만 가능합니다. "
        f"현재 타입: {type(value).__name__}"
    )


def parse_json_text(value: str | None) -> Any:
    """
    JSON 문자열을 dict 또는 list로 변환한다.
    잘못된 JSON이거나 값이 없으면 빈 딕셔너리를 반환한다.
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
def insert_job_schedule(
    project_no: int,
    job_seq: int,
    run_status: str,
    run_type: str | None = None,
    param_json_1: dict | list | str | None = None,
    param_json_2: dict | list | str | None = None,
    param_json_3: dict | list | str | None = None,
    output_video_path: str | None = None,
) -> bool:
    """
    job_schedule 테이블에 작업 스케줄을 추가한다.

    Returns:
        True: 추가 성공
    """
    param_json_text_1 = convert_to_json_text(param_json_1)
    param_json_text_2 = convert_to_json_text(param_json_2)
    param_json_text_3 = convert_to_json_text(param_json_3)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO job_schedule (
                project_no,
                job_seq,
                run_status,
                run_type,
                param_json_1,
                param_json_2,
                param_json_3,
                output_video_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_no,
                job_seq,
                run_status,
                run_type,
                param_json_text_1,
                param_json_text_2,
                param_json_text_3,
                output_video_path,
            ),
        )

        return cursor.rowcount > 0


# =========================================================
# SELECT
# =========================================================
def select_job_schedule(
    project_no: int | None = None,
    job_seq: int | None = None,
    run_status: str | None = None,
) -> list[dict]:
    """
    조회 조건:
        조건 없음:
            전체 조회

        project_no만 있음:
            해당 project_no의 모든 행 조회

        project_no + run_status:
            조건에 맞는 행 중 job_seq가 가장 낮은 1건 조회

        project_no + job_seq:
            특정 작업 조회

        run_status만 있음:
            해당 상태의 모든 행 조회

    Returns:
        항상 list[dict] 반환
    """
    query = """
        SELECT
            project_no,
            job_seq,
            run_status,
            run_type,
            param_json_1,
            param_json_2,
            param_json_3,
            output_video_path
        FROM job_schedule
    """

    conditions: list[str] = []
    params: list = []

    if project_no is not None:
        conditions.append("project_no = ?")
        params.append(project_no)

    if job_seq is not None:
        conditions.append("job_seq = ?")
        params.append(job_seq)

    if run_status is not None:
        conditions.append("run_status = ?")
        params.append(run_status)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    # project_no와 run_status만 넘긴 경우
    # job_seq가 가장 낮은 행 1건 조회
    if (
        project_no is not None
        and run_status is not None
        and job_seq is None
    ):
        query += " ORDER BY job_seq ASC LIMIT 1"
    else:
        # project_no만 넘긴 경우를 포함해 전체 결과 정렬
        query += " ORDER BY project_no ASC, job_seq ASC"

    print("[QUERY]")
    print(query)
    print("[PARAMS]", params)

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(query, tuple(params))
        rows = cursor.fetchall()

    schedules: list[dict] = []

    for row in rows:
        schedule = dict(row)

        schedule["param_1"] = parse_json_text(
            schedule.get("param_json_1")
        )
        schedule["param_2"] = parse_json_text(
            schedule.get("param_json_2")
        )
        schedule["param_3"] = parse_json_text(
            schedule.get("param_json_3")
        )

        schedules.append(schedule)

    if schedule :
        print(schedule)
    else :
        print("no selected data!!")    
        
    return schedules


# =========================================================
# UPDATE
# =========================================================
def update_job_schedule(
    project_no: int,
    job_seq: int,
    run_status: str,
    run_type: str | None = None,
    param_json_1: dict | list | str | None = None,
    param_json_2: dict | list | str | None = None,
    param_json_3: dict | list | str | None = None,
    output_video_path: str | None = None,
) -> bool:
    """
    project_no와 job_seq를 기준으로 작업 스케줄을 수정한다.

    Returns:
        True: 수정 성공
        False: 대상 데이터 없음
    """
    param_json_text_1 = convert_to_json_text(param_json_1)
    param_json_text_2 = convert_to_json_text(param_json_2)
    param_json_text_3 = convert_to_json_text(param_json_3)

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                run_status = ?,
                run_type = ?,
                param_json_1 = ?,
                param_json_2 = ?,
                param_json_3 = ?,
                output_video_path = ?
            WHERE project_no = ?
              AND job_seq = ?
            """,
            (
                run_status,
                run_type,
                param_json_text_1,
                param_json_text_2,
                param_json_text_3,
                output_video_path,
                project_no,
                job_seq,
            ),
        )

        return cursor.rowcount > 0


def update_job_schedule_status(
    project_no: int,
    job_seq: int,
    run_status: str,
    output_video_path: str | None = None,
) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                run_status = ?,
                output_video_path = COALESCE(?, output_video_path)
            WHERE project_no = ?
              AND job_seq = ?
            """,
            (
                run_status,
                output_video_path,
                project_no,
                job_seq,
            ),
        )

        return cursor.rowcount > 0
    
# =========================================================
# DELETE
# =========================================================
def delete_job_schedule(
    project_no: int,
    job_seq: int | None = None,
) -> int:
    """
    job_schedule 데이터를 삭제한다.

    job_seq가 있으면:
        특정 작업 1건 삭제

    job_seq가 없으면:
        해당 project_no의 모든 작업 삭제

    Returns:
        삭제된 데이터 개수
    """
    with sqlite3.connect(DB_PATH) as conn:
        if job_seq is None:
            cursor = conn.execute(
                """
                DELETE FROM job_schedule
                WHERE project_no = ?
                """,
                (project_no,),
            )
        else:
            cursor = conn.execute(
                """
                DELETE FROM job_schedule
                WHERE project_no = ?
                  AND job_seq = ?
                """,
                (project_no, job_seq),
            )

        return cursor.rowcount
    

# insert_job_schedule(
#     project_no = 1,
#     job_seq = 1,
#     run_status = "wait",
#     run_type = "batch",
#     param_json_1 = { 
#         "book_title_en": "genesis",                
#         "bg_image": "data/bible/images/bg_bible_03.png",
#         "start_chapter" : 1,
#         "end_chapter" : 3 ,
#         "output_video_path": ""}
# )    

select_job_schedule(project_no=1, run_status="wait")
# select_job_schedule()