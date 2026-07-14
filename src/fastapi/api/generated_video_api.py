"""
생성된 영상 조회 FastAPI.

지원 API:
    GET /videos
    GET /videos/{project_no}/{execution_id}
"""

import sqlite3

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from fastapi import status


from src.repository.bible.generated_video_repo import (
    select_generated_video,
    select_generated_videos,
)


router = APIRouter(
    prefix="/videos",
    tags=["Generated Videos"],
)


@router.get("")
def get_generated_videos(
    project_no: int | None = Query(
        default=None,
        ge=1,
        description="프로젝트 번호",
    ),
    execution_id: int | None = Query(
        default=None,
        description="영상 생성 실행 ID",
    ),
    youtube_uploaded: bool | None = Query(
        default=None,
        description="유튜브 업로드 완료 여부",
    ),
) -> dict:
    """
    생성된 영상 목록을 조회한다.

    요청 예:
        GET /videos

        GET /videos?project_no=1

        GET /videos?project_no=1&youtube_uploaded=false

        GET /videos?execution_id=execution-20260713-001
    """
    try:
        videos = select_generated_videos(
            project_no=project_no,
            execution_id=execution_id,
            youtube_uploaded=youtube_uploaded,
        )

        return {
            "data": videos,
            "count": len(videos),
        }

    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "생성된 영상 목록을 조회하는 중 "
                f"데이터베이스 오류가 발생했습니다: {error}"
            ),
        ) from error


@router.get("/{project_no}/{execution_id}")
def get_generated_video(
    project_no: int,
    execution_id: int,
) -> dict:
    """
    프로젝트 번호와 실행 ID로 생성 영상 한 건을 조회한다.

    요청 예:
        GET /videos/1/execution-20260713-001
    """
    try:
        video = select_generated_video(
            project_no=project_no,
            execution_id=execution_id,
        )

        if video is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "생성된 영상 정보를 찾을 수 없습니다. "
                    f"project_no={project_no}, "
                    f"execution_id={execution_id}"
                ),
            )

        return {
            "data": video,
        }

    except HTTPException:
        raise

    except sqlite3.Error as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "생성된 영상 정보를 조회하는 중 "
                f"데이터베이스 오류가 발생했습니다: {error}"
            ),
        ) from error
