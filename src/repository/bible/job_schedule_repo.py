"""
job_schedule 테이블 Repository.

주요 기능:
- 작업 단건 등록
- 작업 일괄 등록
- 조건별 조회
- 가장 오래된 대기 작업 조회
- 대기 작업 선점
- 작업 전체 수정
- 작업 파라미터 수정
- 작업 상태 수정
- 작업 삭제

현재 job_schedule 테이블 구조:

    execution_id INTEGER PRIMARY KEY AUTOINCREMENT
    project_no INTEGER NOT NULL
    run_status TEXT NOT NULL
    run_type TEXT
    job_param_1 TEXT
    job_param_2 TEXT
    job_param_3 TEXT
    job_param_4 TEXT
    job_param_5 TEXT
    output_video_path TEXT
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    started_at TEXT
    finished_at TEXT
    error_message TEXT
"""

import sqlite3
from pathlib import Path
from typing import Any


# =========================================================
# DB 경로
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DB_PATH = PROJECT_ROOT / "app.db"


# =========================================================
# 공통 함수
# =========================================================

def get_connection() -> sqlite3.Connection:
    """
    SQLite 연결 객체를 생성한다.

    sqlite3.Row를 사용하여 조회 결과를
    딕셔너리처럼 접근할 수 있도록 설정한다.
    """
    conn = sqlite3.connect(
        DB_PATH,
        timeout=30,
    )

    conn.row_factory = sqlite3.Row

    return conn


def convert_row_to_dict(
    row: sqlite3.Row,
) -> dict[str, Any]:
    """
    sqlite3.Row 객체를 dict로 변환한다.
    """
    return dict(row)


def normalize_status(
    run_status: str,
) -> str:
    """
    작업 상태값을 소문자로 정규화한다.

    허용 상태:
        wait
        running
        completed
        failed

    Args:
        run_status:
            입력 상태값.

    Returns:
        소문자로 정규화된 상태값.
    """
    if not isinstance(run_status, str):
        raise TypeError(
            "run_status는 문자열이어야 합니다. "
            f"현재 타입: {type(run_status).__name__}"
        )

    normalized_status = run_status.strip().lower()

    if not normalized_status:
        raise ValueError(
            "run_status가 비어 있습니다."
        )

    allowed_statuses = {
        "wait",
        "running",
        "completed",
        "failed",
    }

    if normalized_status not in allowed_statuses:
        raise ValueError(
            "지원하지 않는 run_status입니다. "
            f"run_status={run_status}, "
            f"허용값={sorted(allowed_statuses)}"
        )

    return normalized_status


def normalize_optional_text(
    value: str | None,
) -> str | None:
    """
    선택 문자열 값의 앞뒤 공백을 제거한다.

    빈 문자열은 None으로 변환한다.
    """
    if value is None:
        return None

    if not isinstance(value, str):
        raise TypeError(
            "문자열 또는 None만 허용됩니다. "
            f"현재 타입: {type(value).__name__}"
        )

    normalized_value = value.strip()

    return normalized_value or None


# =========================================================
# INSERT
# =========================================================

def insert_job_schedule(
    project_no: int,
    run_status: str = "wait",
    run_type: str | None = "batch",
    job_param_1: str | None = None,
    job_param_2: str | None = None,
    job_param_3: str | None = None,
    job_param_4: str | None = None,
    job_param_5: str | None = None,
    output_video_path: str | None = None,
) -> int:
    """
    job_schedule 테이블에 실행 작업 한 건을 등록한다.

    execution_id는 SQLite AUTOINCREMENT로 자동 생성된다.

    Args:
        project_no:
            프로젝트 번호.

        run_status:
            작업 상태.
            기본값은 wait.

        run_type:
            작업 유형.
            기본값은 batch.

        job_param_1 ~ job_param_5:
            작업 실행 파라미터.

        output_video_path:
            생성된 영상 파일 경로.

    Returns:
        생성된 execution_id.
    """
    if not isinstance(project_no, int):
        raise TypeError(
            "project_no는 int 타입이어야 합니다."
        )

    if project_no <= 0:
        raise ValueError(
            "project_no는 1 이상의 값이어야 합니다."
        )

    normalized_status = normalize_status(
        run_status
    )

    normalized_run_type = normalize_optional_text(
        run_type
    )

    normalized_job_params = [
        normalize_optional_text(job_param_1),
        normalize_optional_text(job_param_2),
        normalize_optional_text(job_param_3),
        normalize_optional_text(job_param_4),
        normalize_optional_text(job_param_5),
    ]

    normalized_output_path = normalize_optional_text(
        output_video_path
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
                job_param_4,
                job_param_5,
                output_video_path
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                project_no,
                normalized_status,
                normalized_run_type,
                normalized_job_params[0],
                normalized_job_params[1],
                normalized_job_params[2],
                normalized_job_params[3],
                normalized_job_params[4],
                normalized_output_path,
            ),
        )

        execution_id = cursor.lastrowid

        if execution_id is None:
            raise RuntimeError(
                "job_schedule 등록 후 execution_id를 "
                "가져오지 못했습니다."
            )

        return int(execution_id)


def insert_job_schedules_batch(
    project_no: int,
    job_params: list[str],
    run_type: str = "batch",
) -> list[dict[str, Any]]:
    """
    job_schedule 테이블에 작업 목록을 일괄 등록한다.

    job_params 항목 형식:
        param1|param2|param3|param4|param5

    입력 예:
        project_no=1

        job_params=[
            "genesis|data/bible/images/bg.png|1|10|",
            "exodus|data/bible/images/bg2.png|1|5|",
        ]

    저장 결과:
        job_param_1 = genesis
        job_param_2 = data/bible/images/bg.png
        job_param_3 = 1
        job_param_4 = 10
        job_param_5 = NULL

    모든 작업 등록이 성공한 경우에만 commit한다.
    한 건이라도 실패하면 전체 rollback한다.

    Returns:
        등록된 작업 정보 목록.
    """
    if not isinstance(project_no, int):
        raise TypeError(
            "project_no는 int 타입이어야 합니다."
        )

    if project_no <= 0:
        raise ValueError(
            "project_no는 1 이상의 값이어야 합니다."
        )

    if not isinstance(job_params, list):
        raise TypeError(
            "job_params는 list 타입이어야 합니다."
        )

    if not job_params:
        raise ValueError(
            "job_params가 비어 있습니다."
        )

    normalized_run_type = normalize_optional_text(
        run_type
    )

    inserted_jobs: list[dict[str, Any]] = []

    insert_sql = """
        INSERT INTO job_schedule (
            project_no,
            run_status,
            run_type,
            job_param_1,
            job_param_2,
            job_param_3,
            job_param_4,
            job_param_5,
            output_video_path,
            started_at,
            finished_at,
            error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    with get_connection() as conn:
        cursor = conn.cursor()

        try:
            for index, job_param in enumerate(
                job_params,
                start=1,
            ):
                if not isinstance(job_param, str):
                    raise ValueError(
                        "job_params의 각 항목은 "
                        "문자열이어야 합니다. "
                        f"index={index}, "
                        f"value={job_param!r}"
                    )

                normalized_job_param = (
                    job_param.strip()
                )

                if not normalized_job_param:
                    raise ValueError(
                        "job_params에 빈 문자열이 "
                        "포함되어 있습니다. "
                        f"index={index}"
                    )

                split_params = [
                    value.strip()
                    for value
                    in normalized_job_param.split("|")
                ]

                if len(split_params) > 5:
                    raise ValueError(
                        "job_param은 최대 5개의 값만 "
                        "허용합니다. "
                        "'param1|param2|param3|"
                        "param4|param5' 형식으로 "
                        "입력하세요. "
                        f"index={index}, "
                        f"value={normalized_job_param}"
                    )

                while len(split_params) < 5:
                    split_params.append("")

                normalized_params = [
                    value or None
                    for value in split_params
                ]

                cursor.execute(
                    insert_sql,
                    (
                        project_no,
                        "wait",
                        normalized_run_type,
                        normalized_params[0],
                        normalized_params[1],
                        normalized_params[2],
                        normalized_params[3],
                        normalized_params[4],
                        None,
                        None,
                        None,
                        None,
                    ),
                )

                execution_id = cursor.lastrowid

                if execution_id is None:
                    raise RuntimeError(
                        "일괄 등록 중 execution_id를 "
                        "가져오지 못했습니다. "
                        f"index={index}"
                    )

                inserted_jobs.append(
                    {
                        "execution_id": int(
                            execution_id
                        ),
                        "project_no": project_no,
                        "run_status": "wait",
                        "run_type": normalized_run_type,
                        "job_param_1": (
                            normalized_params[0]
                        ),
                        "job_param_2": (
                            normalized_params[1]
                        ),
                        "job_param_3": (
                            normalized_params[2]
                        ),
                        "job_param_4": (
                            normalized_params[3]
                        ),
                        "job_param_5": (
                            normalized_params[4]
                        ),
                        "output_video_path": None,
                    }
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

    return inserted_jobs


# =========================================================
# SELECT
# =========================================================

def select_job_schedule(
    execution_id: int | None = None,
    project_no: int | None = None,
    run_status: str | None = None,
    oldest_one: bool = False,
) -> list[dict[str, Any]]:
    """
    job_schedule 실행 이력 목록을 조회한다.

    조회 조건:
        execution_id만 전달:
            해당 실행 ID 조회.

        project_no만 전달:
            해당 프로젝트의 전체 실행 이력 조회.

        run_status만 전달:
            해당 상태의 전체 실행 이력 조회.

        project_no와 run_status 전달:
            해당 프로젝트의 지정 상태 작업 조회.

        조건을 전달하지 않음:
            전체 실행 이력 조회.

    oldest_one=True:
        조회 조건에 해당하는 가장 오래된 한 건만 반환한다.
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
            job_param_4,
            job_param_5,
            output_video_path,
            created_at,
            started_at,
            finished_at,
            error_message
        FROM job_schedule
        WHERE 1 = 1
    """

    params: list[Any] = []

    if execution_id is not None:
        query += """
            AND execution_id = ?
        """
        params.append(execution_id)

    if project_no is not None:
        query += """
            AND project_no = ?
        """
        params.append(project_no)

    if run_status is not None:
        query += """
            AND LOWER(run_status) = LOWER(?)
        """
        params.append(run_status.strip())

    query += """
        ORDER BY
            created_at ASC,
            execution_id ASC
    """

    if oldest_one:
        query += """
            LIMIT 1
        """

    with get_connection() as conn:
        rows = conn.execute(
            query,
            tuple(params),
        ).fetchall()

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
        조회 성공:
            실행 이력 dict.

        조회 결과 없음:
            None.
    """
    schedules = select_job_schedule(
        execution_id=execution_id,
        oldest_one=True,
    )

    if not schedules:
        return None

    return schedules[0]


def select_next_waiting_job(
    project_no: int | None = None,
    run_status: str = "wait",
) -> dict[str, Any] | None:
    """
    지정된 상태의 가장 오래된 작업 한 건을 조회한다.

    기본 상태는 wait이다.

    주의:
        조회만 수행하며 상태를 running으로 변경하지 않는다.

    Returns:
        조회된 작업 또는 None.
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
    job_param_4: str | None = None,
    job_param_5: str | None = None,
    output_video_path: str | None = None,
    error_message: str | None = None,
) -> bool:
    """
    execution_id를 기준으로 작업 정보 전체를 수정한다.

    전달된 None 값은 DB에 NULL로 저장된다.

    Returns:
        True:
            수정 성공.

        False:
            execution_id에 해당하는 데이터 없음.
    """
    if execution_id <= 0:
        raise ValueError(
            "execution_id는 1 이상의 값이어야 합니다."
        )

    if project_no <= 0:
        raise ValueError(
            "project_no는 1 이상의 값이어야 합니다."
        )

    normalized_status = normalize_status(
        run_status
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
                job_param_4 = ?,
                job_param_5 = ?,
                output_video_path = ?,
                error_message = ?
            WHERE execution_id = ?
            """,
            (
                project_no,
                normalized_status,
                normalize_optional_text(run_type),
                normalize_optional_text(job_param_1),
                normalize_optional_text(job_param_2),
                normalize_optional_text(job_param_3),
                normalize_optional_text(job_param_4),
                normalize_optional_text(job_param_5),
                normalize_optional_text(
                    output_video_path
                ),
                normalize_optional_text(
                    error_message
                ),
                execution_id,
            ),
        )

        return cursor.rowcount > 0


def update_job_schedule_params(
    execution_id: int,
    job_param_1: str | None = None,
    job_param_2: str | None = None,
    job_param_3: str | None = None,
    job_param_4: str | None = None,
    job_param_5: str | None = None,
) -> bool:
    """
    execution_id를 기준으로 작업 파라미터만 수정한다.

    주의:
        None을 전달하면 해당 컬럼에 NULL이 저장된다.

    Returns:
        True:
            수정 성공.

        False:
            execution_id에 해당하는 데이터 없음.
    """
    if execution_id <= 0:
        raise ValueError(
            "execution_id는 1 이상의 값이어야 합니다."
        )

    with get_connection() as conn:
        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                job_param_1 = ?,
                job_param_2 = ?,
                job_param_3 = ?,
                job_param_4 = ?,
                job_param_5 = ?
            WHERE execution_id = ?
            """,
            (
                normalize_optional_text(job_param_1),
                normalize_optional_text(job_param_2),
                normalize_optional_text(job_param_3),
                normalize_optional_text(job_param_4),
                normalize_optional_text(job_param_5),
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
    execution_id를 기준으로 작업 상태를 변경한다.

    상태별 처리:

        wait:
            started_at을 NULL로 변경.
            finished_at을 NULL로 변경.
            error_message를 NULL로 변경.

        running:
            started_at을 현재 시간으로 변경.
            finished_at을 NULL로 변경.
            error_message를 NULL로 변경.

        completed:
            finished_at을 현재 시간으로 변경.
            output_video_path를 선택적으로 저장.

        failed:
            finished_at을 현재 시간으로 변경.
            error_message를 선택적으로 저장.

    Returns:
        True:
            수정 성공.

        False:
            execution_id에 해당하는 데이터 없음.
    """
    if execution_id <= 0:
        raise ValueError(
            "execution_id는 1 이상의 값이어야 합니다."
        )

    normalized_status = normalize_status(
        run_status
    )

    set_clauses = [
        "run_status = ?",
    ]

    params: list[Any] = [
        normalized_status,
    ]

    if normalized_status == "wait":
        set_clauses.extend(
            [
                "started_at = NULL",
                "finished_at = NULL",
                "error_message = NULL",
            ]
        )

    elif normalized_status == "running":
        set_clauses.extend(
            [
                "started_at = CURRENT_TIMESTAMP",
                "finished_at = NULL",
                "error_message = NULL",
            ]
        )

    elif normalized_status in {
        "completed",
        "failed",
    }:
        set_clauses.append(
            "finished_at = CURRENT_TIMESTAMP"
        )

    if output_video_path is not None:
        set_clauses.append(
            "output_video_path = ?"
        )

        params.append(
            normalize_optional_text(
                output_video_path
            )
        )

    if error_message is not None:
        set_clauses.append(
            "error_message = ?"
        )

        params.append(
            normalize_optional_text(
                error_message
            )
        )

    query = f"""
        UPDATE job_schedule
        SET
            {", ".join(set_clauses)}
        WHERE execution_id = ?
    """

    params.append(execution_id)

    with get_connection() as conn:
        cursor = conn.execute(
            query,
            tuple(params),
        )

        return cursor.rowcount > 0


# =========================================================
# 작업 선점
# =========================================================

def claim_next_waiting_job(
    project_no: int | None = None,
    waiting_status: str = "wait",
) -> dict[str, Any] | None:
    """
    가장 오래된 대기 작업 한 건을 조회하고
    running 상태로 변경한 뒤 반환한다.

    BEGIN IMMEDIATE를 사용하여 여러 요청이 동시에
    접근할 때 동일 작업이 중복 선택되는 가능성을 줄인다.

    Args:
        project_no:
            프로젝트 번호.
            None이면 전체 프로젝트에서 조회한다.

        waiting_status:
            조회할 대기 상태.
            기본값은 wait.

    Returns:
        선점한 작업 정보 또는 None.
    """
    normalized_waiting_status = (
        waiting_status.strip().lower()
    )

    with get_connection() as conn:
        conn.execute(
            "BEGIN IMMEDIATE"
        )

        query = """
            SELECT
                execution_id,
                project_no,
                run_status,
                run_type,
                job_param_1,
                job_param_2,
                job_param_3,
                job_param_4,
                job_param_5,
                output_video_path,
                created_at,
                started_at,
                finished_at,
                error_message
            FROM job_schedule
            WHERE LOWER(run_status) = LOWER(?)
        """

        params: list[Any] = [
            normalized_waiting_status,
        ]

        if project_no is not None:
            query += """
                AND project_no = ?
            """
            params.append(project_no)

        query += """
            ORDER BY
                created_at ASC,
                execution_id ASC
            LIMIT 1
        """

        row = conn.execute(
            query,
            tuple(params),
        ).fetchone()

        if row is None:
            conn.rollback()
            return None

        execution_id = int(
            row["execution_id"]
        )

        cursor = conn.execute(
            """
            UPDATE job_schedule
            SET
                run_status = 'running',
                started_at = CURRENT_TIMESTAMP,
                finished_at = NULL,
                error_message = NULL
            WHERE execution_id = ?
              AND LOWER(run_status) = LOWER(?)
            """,
            (
                execution_id,
                normalized_waiting_status,
            ),
        )

        if cursor.rowcount == 0:
            conn.rollback()
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
                job_param_4,
                job_param_5,
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
            conn.rollback()
            return None

        conn.commit()

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
    execution_id에 해당하는 작업 한 건을 삭제한다.

    Returns:
        True:
            삭제 성공.

        False:
            삭제 대상 없음.
    """
    if execution_id <= 0:
        raise ValueError(
            "execution_id는 1 이상의 값이어야 합니다."
        )

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
    특정 프로젝트의 모든 작업 이력을 삭제한다.

    Returns:
        삭제된 행 개수.
    """
    if project_no <= 0:
        raise ValueError(
            "project_no는 1 이상의 값이어야 합니다."
        )

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
    new_execution_id = insert_job_schedule(
        project_no=1,
        run_status="wait",
        run_type="batch",
        job_param_1="genesis",
        job_param_2=(
            "data/bible/images/"
            "bg_bible_03.png"
        ),
        job_param_3="1",
        job_param_4="3",
        job_param_5=None,
    )

    print(
        "생성된 execution_id:",
        new_execution_id,
    )

    schedules = select_job_schedule(
        project_no=1,
    )

    print("\n[프로젝트 작업 목록]")

    for schedule in schedules:
        print(schedule)

    waiting_job = select_next_waiting_job(
        project_no=1,
    )

    print(
        "\n[다음 대기 작업]",
        waiting_job,
    )

    claimed_job = claim_next_waiting_job(
        project_no=1,
    )

    print(
        "\n[선점한 작업]",
        claimed_job,
    )

    if claimed_job is not None:
        update_job_schedule_status(
            execution_id=(
                claimed_job["execution_id"]
            ),
            run_status="completed",
            output_video_path=(
                "data/bible/video/"
                "genesis_final.mp4"
            ),
        )

        completed_job = (
            select_job_schedule_one(
                execution_id=(
                    claimed_job["execution_id"]
                )
            )
        )

        print(
            "\n[완료된 작업]",
            completed_job,
        )
