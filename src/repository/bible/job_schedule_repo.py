import json
import sqlite3
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "app.db"


# =========================================================
# 공통 함수
# =========================================================
def get_connection() -> sqlite3.Connection:
    """
    SQLite 연결 객체를 생성한다.

    sqlite3.Row를 사용해 조회 결과를 딕셔너리처럼 접근할 수 있다.
    """
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )
    conn.row_factory = sqlite3.Row

    return conn


def convert_to_json_text(
    value: dict | list | str | None,
) -> str | None:
    """
    Python 객체를 DB 저장용 JSON 문자열로 변환한다.

    dict, list:
        JSON 문자열로 변환

    str:
        전달받은 문자열을 그대로 저장

    None:
        NULL 저장
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
        "param_json은 dict, list, str, None만 가능합니다. "
        f"현재 타입: {type(value).__name__}"
    )


def parse_json_text(
    value: str | None,
) -> Any:
    """
    DB에 저장된 JSON 문자열을 Python 객체로 변환한다.

    값이 없거나 올바른 JSON이 아니면 빈 딕셔너리를 반환한다.
    """
    if not value:
        return {}

    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return {}


def convert_row_to_dict(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """
    sqlite3.Row를 dict로 변환하고 param_json을 파싱한다.
    """
    schedule = dict(row)

    schedule["param"] = parse_json_text(
        schedule.get("param_json")
    )

    return schedule


# =========================================================
# INSERT
# =========================================================
def insert_job_schedule(
    project_no: int,
    run_status: str,
    run_type: str | None = None,
    job_param_1: str | None = None,
    job_param_2: str | None = None,
    job_param_3: str | None = None,
    param_json: dict | list | str | None = None,
    output_video_path: str | None = None,
) -> int:
    """
    job_schedule 테이블에 실행 이력을 등록한다.

    execution_id는 SQLite가 자동 생성한다.

    Returns:
        생성된 execution_id
    """
    param_json_text = convert_to_json_text(
        param_json
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO job_schedule (
                project_no,
                run_status,
                run_type,
                job_param_1,
                job_param_2,
                job_param_3,
                param_json,
                output_video_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_no,
                run_status.upper(),
                run_type,
                job_param_1,
                job_param_2,
                job_param_3,
                param_json_text,
                output_video_path,
            ),
        )

        execution_id = cursor.lastrowid

        if execution_id is None:
            raise RuntimeError(
                "job_schedule 등록 후 execution_id를 "
                "가져오지 못했습니다."
            )

        return execution_id


# =========================================================
# SELECT
# =========================================================
def select_job_schedule(
    execution_id: int | None = None,
    project_no: int | None = None,
    run_status: str | None = None,
    run_type: str | None = None,
    oldest_one: bool = False,
) -> list[dict[str, Any]]:
    """
    job_schedule 실행 이력을 조회한다.

    조회 조건:
        조건 없음:
            전체 실행 이력 조회

        execution_id:
            특정 실행 이력 조회

        project_no:
            특정 프로젝트의 전체 실행 이력 조회

        run_status:
            특정 상태의 실행 이력 조회

        run_type:
            특정 실행 유형의 실행 이력 조회

        oldest_one=True:
            조건에 맞는 가장 오래된 실행 이력 1건 조회

    Returns:
        항상 list[dict] 반환
    """
    query = """
        SELECT
            execution_id,
            project_no,
            run_status,
            run_type,
            job_param_1,
            job_param_2,
            job_param_3,
            param_json,
            output_video_path,
            created_at,
            started_at,
            finished_at,
            error_message
        FROM job_schedule
    """

    conditions: list[str] = []
    params: list[Any] = []

    if execution_id is not None:
        conditions.append("execution_id = ?")
        params.append(execution_id)

    if project_no is not None:
        conditions.append("project_no = ?")
        params.append(project_no)

    if run_status is not None:
        conditions.append("run_status = ?")
        params.append(run_status.upper())

    if run_type is not None:
        conditions.append("run_type = ?")
        params.append(run_type)

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if oldest_one:
        query += " ORDER BY execution_id ASC LIMIT 1"
    else:
        query += " ORDER BY execution_id DESC"

    with get_connection() as conn:
        cursor = conn.execute(
            query,
            tuple(params),
        )
        rows = cursor.fetchall()

    return [
        convert_row_to_dict(row)
        for row in rows
    ]


def select_job_schedule_one(
    execution_id: int,
) -> dict[str, Any] | None:
    """
    execution_id로 실행 이력 한 건을 조회한다.

    Returns:
        조회 성공: dict
        조회 결과 없음: None
    """
    schedules = select_job_schedule(
        execution_id=execution_id,
    )

    if not schedules:
        return None

    return schedules[0]


def select_next_waiting_job(
    project_no: int | None = None,
    run_status: str = "WAIT",
) -> dict[str, Any] | None:
    """
    지정된 상태의 가장 오래된 실행 이력 한 건을 조회한다.

    기본 상태는 WAIT이다.

    Returns:
        조회 성공: dict
        대기 작업 없음: None
    """
    schedules = select_job_schedule(
        project_no=project_no,
        run_status=run_status,
        oldest_one=True,
    )

    if not schedules:
        return None

    return schedules[0]


# =========================================================
# UPDATE
# =========================================================
def update_job_schedule(
    execution_id: int,
    project_no: int,
    run_status: str,
    run_type: str | None = None,
    job_param_1: str | None = None,
    job_param_2: str | None = None,
    job_param_3: str | None = None,
    param_json: dict | list | str | None = None,
    output_video_path: str | None = None,
    error_message: str | None = None,
) -> bool:
    """
    execution_id를 기준으로 실행 이력 전체를 수정한다.

    전달된 None 값은 DB 컬럼에 NULL로 저장된다.

    Returns:
        True: 수정 성공
        False: 대상 데이터 없음
    """
    param_json_text = convert_to_json_text(
        param_json
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                project_no = ?,
                run_status = ?,
                run_type = ?,
                job_param_1 = ?,
                job_param_2 = ?,
                job_param_3 = ?,
                param_json = ?,
                output_video_path = ?,
                error_message = ?
            WHERE execution_id = ?
            """,
            (
                project_no,
                run_status.upper(),
                run_type,
                job_param_1,
                job_param_2,
                job_param_3,
                param_json_text,
                output_video_path,
                error_message,
                execution_id,
            ),
        )

        return cursor.rowcount > 0


def update_job_schedule_status(
    execution_id: int,
    run_status: str,
    output_video_path: str | None = None,
    error_message: str | None = None,
) -> bool:
    """
    execution_id를 기준으로 실행 상태를 변경한다.

    상태별 시간 처리:

        RUNNING:
            started_at을 현재 시각으로 설정
            finished_at과 error_message 초기화

        SUCCESS, FAILED, CANCELLED:
            finished_at을 현재 시각으로 설정

        WAIT, QUEUED 및 기타 상태:
            상태 및 전달받은 컬럼만 변경

    output_video_path가 None이면 기존 값을 유지한다.

    FAILED가 아닌 상태에서 error_message가 None이면
    기존 오류 메시지를 유지한다.
    """
    normalized_status = run_status.strip().upper()

    with get_connection() as conn:
        if normalized_status == "RUNNING":
            cursor = conn.execute(
                """
                UPDATE job_schedule
                SET
                    run_status = ?,
                    started_at = CURRENT_TIMESTAMP,
                    finished_at = NULL,
                    error_message = NULL,
                    output_video_path = COALESCE(
                        ?,
                        output_video_path
                    )
                WHERE execution_id = ?
                """,
                (
                    normalized_status,
                    output_video_path,
                    execution_id,
                ),
            )

        elif normalized_status == "SUCCESS":
            cursor = conn.execute(
                """
                UPDATE job_schedule
                SET
                    run_status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    error_message = NULL,
                    output_video_path = COALESCE(
                        ?,
                        output_video_path
                    )
                WHERE execution_id = ?
                """,
                (
                    normalized_status,
                    output_video_path,
                    execution_id,
                ),
            )

        elif normalized_status in {
            "FAILED",
            "CANCELLED",
        }:
            cursor = conn.execute(
                """
                UPDATE job_schedule
                SET
                    run_status = ?,
                    finished_at = CURRENT_TIMESTAMP,
                    output_video_path = COALESCE(
                        ?,
                        output_video_path
                    ),
                    error_message = COALESCE(
                        ?,
                        error_message
                    )
                WHERE execution_id = ?
                """,
                (
                    normalized_status,
                    output_video_path,
                    error_message,
                    execution_id,
                ),
            )

        else:
            cursor = conn.execute(
                """
                UPDATE job_schedule
                SET
                    run_status = ?,
                    output_video_path = COALESCE(
                        ?,
                        output_video_path
                    ),
                    error_message = COALESCE(
                        ?,
                        error_message
                    )
                WHERE execution_id = ?
                """,
                (
                    normalized_status,
                    output_video_path,
                    error_message,
                    execution_id,
                ),
            )

        return cursor.rowcount > 0


def update_job_schedule_params(
    execution_id: int,
    job_param_1: str | None = None,
    job_param_2: str | None = None,
    job_param_3: str | None = None,
    param_json: dict | list | str | None = None,
) -> bool:
    """
    실행 이력의 파라미터만 수정한다.

    주의:
        None을 전달하면 해당 컬럼에 NULL이 저장된다.

    Returns:
        True: 수정 성공
        False: 대상 데이터 없음
    """
    param_json_text = convert_to_json_text(
        param_json
    )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                job_param_1 = ?,
                job_param_2 = ?,
                job_param_3 = ?,
                param_json = ?
            WHERE execution_id = ?
            """,
            (
                job_param_1,
                job_param_2,
                job_param_3,
                param_json_text,
                execution_id,
            ),
        )

        return cursor.rowcount > 0


# =========================================================
# 작업 가져오기
# =========================================================
def claim_next_waiting_job(
    project_no: int | None = None,
    waiting_status: str = "WAIT",
) -> dict[str, Any] | None:
    """
    가장 오래된 대기 작업을 조회한 뒤 RUNNING으로 변경한다.

    BEGIN IMMEDIATE를 사용하여 동시에 여러 요청이 들어왔을 때
    동일한 작업이 중복 선택되는 가능성을 줄인다.

    단일 SQLite DB와 단일 Worker 또는 소수 Worker 환경에 적합하다.

    Returns:
        가져온 작업: dict
        대기 작업 없음: None
    """
    normalized_waiting_status = waiting_status.strip().upper()

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")

        query = """
            SELECT
                execution_id,
                project_no,
                run_status,
                run_type,
                job_param_1,
                job_param_2,
                job_param_3,
                param_json,
                output_video_path,
                created_at,
                started_at,
                finished_at,
                error_message
            FROM job_schedule
            WHERE run_status = ?
        """

        params: list[Any] = [
            normalized_waiting_status,
        ]

        if project_no is not None:
            query += " AND project_no = ?"
            params.append(project_no)

        query += " ORDER BY execution_id ASC LIMIT 1"

        row = conn.execute(
            query,
            tuple(params),
        ).fetchone()

        if row is None:
            return None

        execution_id = row["execution_id"]

        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                run_status = 'RUNNING',
                started_at = CURRENT_TIMESTAMP,
                finished_at = NULL,
                error_message = NULL
            WHERE execution_id = ?
              AND run_status = ?
            """,
            (
                execution_id,
                normalized_waiting_status,
            ),
        )

        if cursor.rowcount == 0:
            return None

        updated_row = conn.execute(
            """
            SELECT
                execution_id,
                project_no,
                run_status,
                run_type,
                job_param_1,
                job_param_2,
                job_param_3,
                param_json,
                output_video_path,
                created_at,
                started_at,
                finished_at,
                error_message
            FROM job_schedule
            WHERE execution_id = ?
            """,
            (execution_id,),
        ).fetchone()

        if updated_row is None:
            return None

        return convert_row_to_dict(
            updated_row
        )


# =========================================================
# DELETE
# =========================================================
def delete_job_schedule(
    execution_id: int,
) -> bool:
    """
    execution_id에 해당하는 실행 이력 한 건을 삭제한다.

    Returns:
        True: 삭제 성공
        False: 대상 데이터 없음
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM job_schedule
            WHERE execution_id = ?
            """,
            (execution_id,),
        )

        return cursor.rowcount > 0


def delete_job_schedules_by_project(
    project_no: int,
) -> int:
    """
    특정 프로젝트의 모든 실행 이력을 삭제한다.

    Returns:
        삭제된 행 개수
    """
    with get_connection() as conn:
        cursor = conn.execute(
            """
            DELETE FROM job_schedule
            WHERE project_no = ?
            """,
            (project_no,),
        )

        return cursor.rowcount


# =========================================================
# 사용 예시
# =========================================================
if __name__ == "__main__":
    execution_id = insert_job_schedule(
        project_no=1,
        run_status="WAIT",
        run_type="BATCH",
        job_param_1="genesis",
        job_param_2="1",
        job_param_3="3",
        param_json={
            "book_title_en": "genesis",
            "bg_image": (
                "data/bible/images/"
                "bg_bible_03.png"
            ),
            "start_chapter": 1,
            "end_chapter": 3,
        },
    )

    print(
        "생성된 execution_id:",
        execution_id,
    )

    schedules = select_job_schedule(
        project_no=1,
    )

    for schedule in schedules:
        print(schedule)

    waiting_job = select_next_waiting_job(
        project_no=1,
    )

    print(
        "대기 작업:",
        waiting_job,
    )

    claimed_job = claim_next_waiting_job(
        project_no=1,
    )

    print(
        "실행할 작업:",
        claimed_job,
    )

    if claimed_job is not None:
        update_job_schedule_status(
            execution_id=claimed_job["execution_id"],
            run_status="SUCCESS",
            output_video_path=(
                "data/bible/video/"
                "genesis_final.mp4"
            ),
        )
