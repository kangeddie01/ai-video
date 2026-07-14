
"""
생성된 영상 조회 Repository.

generated_video와 video_project를 조인하여
프로젝트명을 포함한 생성 영상 정보를 조회한다.
"""

import sqlite3
from pathlib import Path
from typing import Any


# 프로젝트 실행 위치가 C:\\project\\my-ai-video인 경우 app.db를 사용한다.
DB_PATH = Path("app.db")


def select_generated_videos(
    project_no: int | None = None,
    execution_id: int | None = None,
    youtube_uploaded: bool | None = None,
) -> list[dict[str, Any]]:
    """
    생성된 영상 목록을 조회한다.

    Args:
        project_no:
            프로젝트 번호.
            None이면 전체 프로젝트를 조회한다.

        execution_id:
            영상 생성 실행 ID.
            None이면 실행 ID 조건 없이 조회한다.

        youtube_uploaded:
            유튜브 업로드 완료 여부.
            True이면 업로드 완료 영상만 조회한다.
            False이면 미업로드 영상만 조회한다.
            None이면 전체를 조회한다.

    Returns:
        프로젝트명을 포함한 생성 영상 목록.

    조회 결과 예:
        [
            {
                "project_no": 1,
                "project_name": "창세기 영상",
                "video_title": "창세기 1장",
                "execution_id": "execution-20260713-001",
                "video_url": "http://localhost:8000/videos/genesis_001.mp4",
                "youtube_uploaded": False,
                "duration_seconds": 325,
                "file_size_bytes": 52428800,
                "created_at": "2026-07-13 12:30:00"
            }
        ]
    """
    query = """
        SELECT
            gv.project_no,
            vp.project_name,
            gv.video_title,
            gv.execution_id,
            gv.video_url,
            gv.youtube_uploaded,
            gv.duration_seconds,
            gv.file_size_bytes,
            gv.created_at
        FROM generated_video AS gv
        LEFT JOIN video_project AS vp
            ON vp.project_no = gv.project_no
        WHERE 1 = 1
    """

    params: list[Any] = []

    if project_no is not None:
        query += """
            AND gv.project_no = ?
        """
        params.append(project_no)

    if execution_id is not None:
        query += """
            AND gv.execution_id = ?
        """
        params.append(execution_id)

    if youtube_uploaded is not None:
        query += """
            AND gv.youtube_uploaded = ?
        """
        params.append(1 if youtube_uploaded else 0)

    query += """
        ORDER BY
            gv.created_at DESC,
            gv.project_no ASC,
            gv.execution_id DESC
    """

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        cursor = conn.execute(
            query,
            tuple(params),
        )

        rows = cursor.fetchall()

    result: list[dict[str, Any]] = []

    for row in rows:
        video = dict(row)

        # SQLite에는 Boolean 타입이 없으므로
        # 0/1 값을 Python bool로 변환한다.
        video["youtube_uploaded"] = bool(
            video["youtube_uploaded"]
        )

        result.append(video)

    return result


def select_generated_video(
    project_no: int,
    execution_id: int,
) -> dict[str, Any] | None:
    """
    프로젝트 번호와 실행 ID로 생성 영상 한 건을 조회한다.

    Args:
        project_no:
            프로젝트 번호.

        execution_id:
            영상 생성 실행 ID.

    Returns:
        조회된 영상 정보.
        결과가 없으면 None.
    """
    videos = select_generated_videos(
        project_no=project_no,
        execution_id=execution_id,
    )

    if not videos:
        return None

    return videos[0]

def insert_generated_video(
    project_no: int,
    execution_id: int,
    video_title: str,
    video_url: str,
    youtube_uploaded: bool = False,
    duration_seconds: float | None = None,
    file_size_bytes: int | None = None,
    created_at: str | None = None,
) -> int:
    """
    generated_video 테이블에 생성 영상 정보를 등록하거나 수정한다.

    동작:
        - 동일한 project_no, execution_id 데이터가 없으면 INSERT
        - 동일한 project_no, execution_id 데이터가 있으면 UPDATE

    Args:
        project_no:
            프로젝트 번호.

        execution_id:
            영상 생성 실행 ID.

        video_title:
            생성된 영상 제목.

        video_url:
            영상 파일 URL 또는 저장 경로.

        youtube_uploaded:
            유튜브 업로드 완료 여부.

        duration_seconds:
            영상 길이(초).

        file_size_bytes:
            영상 파일 크기(byte).

        created_at:
            생성 일시.

            신규 등록이고 None인 경우:
                SQLite 현재 시간을 사용한다.

            기존 데이터 수정이고 None인 경우:
                기존 created_at 값을 유지한다.

            값이 전달된 경우:
                INSERT 또는 UPDATE 시 전달된 값으로 저장한다.

    Returns:
        INSERT 또는 UPDATE된 행의 rowid.
    """
    if project_no < 1:
        raise ValueError(
            "project_no는 1 이상의 정수여야 합니다."
        )

    if execution_id < 1:
        raise ValueError(
            "execution_id는 1 이상의 정수여야 합니다."
        )

    if not video_title or not video_title.strip():
        raise ValueError(
            "video_title이 비어 있습니다."
        )

    if not video_url or not video_url.strip():
        raise ValueError(
            "video_url이 비어 있습니다."
        )

    if (
        duration_seconds is not None
        and duration_seconds < 0
    ):
        raise ValueError(
            "duration_seconds는 0 이상이어야 합니다."
        )

    if (
        file_size_bytes is not None
        and file_size_bytes < 0
    ):
        raise ValueError(
            "file_size_bytes는 0 이상이어야 합니다."
        )

    params = {
        "project_no": project_no,
        "execution_id": execution_id,
        "video_title": video_title.strip(),
        "video_url": video_url.strip(),
        "youtube_uploaded": (
            1 if youtube_uploaded else 0
        ),
        "duration_seconds": duration_seconds,
        "file_size_bytes": file_size_bytes,
        "created_at": created_at,
    }

    if created_at is None:
        # 신규 등록:
        #   created_at을 현재 시간으로 입력
        #
        # 기존 데이터 수정:
        #   created_at은 변경하지 않음
        query = """
            INSERT INTO generated_video (
                project_no,
                execution_id,
                video_title,
                video_url,
                youtube_uploaded,
                duration_seconds,
                file_size_bytes,
                created_at
            )
            VALUES (
                :project_no,
                :execution_id,
                :video_title,
                :video_url,
                :youtube_uploaded,
                :duration_seconds,
                :file_size_bytes,
                datetime('now', 'localtime')
            )
            ON CONFLICT (
                project_no,
                execution_id
            )
            DO UPDATE SET
                video_title = excluded.video_title,
                video_url = excluded.video_url,
                youtube_uploaded = excluded.youtube_uploaded,
                duration_seconds = excluded.duration_seconds,
                file_size_bytes = excluded.file_size_bytes
        """
    else:
        # created_at이 전달되면
        # INSERT 및 UPDATE 모두 해당 값으로 저장
        query = """
            INSERT INTO generated_video (
                project_no,
                execution_id,
                video_title,
                video_url,
                youtube_uploaded,
                duration_seconds,
                file_size_bytes,
                created_at
            )
            VALUES (
                :project_no,
                :execution_id,
                :video_title,
                :video_url,
                :youtube_uploaded,
                :duration_seconds,
                :file_size_bytes,
                :created_at
            )
            ON CONFLICT (
                project_no,
                execution_id
            )
            DO UPDATE SET
                video_title = excluded.video_title,
                video_url = excluded.video_url,
                youtube_uploaded = excluded.youtube_uploaded,
                duration_seconds = excluded.duration_seconds,
                file_size_bytes = excluded.file_size_bytes,
                created_at = excluded.created_at
        """
    print(query)
    print(params)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            query,
            params,
        )

        # INSERT와 UPDATE 모두 정확한 rowid를 반환하기 위해
        # project_no, execution_id로 다시 조회한다.
        cursor = conn.execute(
            """
            SELECT rowid
            FROM generated_video
            WHERE project_no = ?
              AND execution_id = ?
            """,
            (
                project_no,
                execution_id,
            ),
        )

        row = cursor.fetchone()

        if row is None:
            raise RuntimeError(
                "generated_video 저장 후 데이터를 찾을 수 없습니다. "
                f"project_no={project_no}, "
                f"execution_id={execution_id}"
            )

        conn.commit()

        saved_row_id = int(row[0])

    return saved_row_id




if __name__ == "__main__":
    generated_videos = select_generated_videos()

    for generated_video in generated_videos:
        print(generated_video)

