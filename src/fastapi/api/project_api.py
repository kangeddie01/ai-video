from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.repository.bible.video_project_repo import (
    delete_video_project,
    insert_video_project,
    select_project,
    select_project_one,
    update_video_project,
    update_video_project_schedule,
)


router = APIRouter(
    prefix="/projects",
    tags=["projects"],
)


# =========================================================
# Request Model
# =========================================================
class ProjectCreateRequest(BaseModel):
    project_no: int = Field(
        ge=1,
        description="프로젝트 번호",
    )
    project_name: str | None = None
    project_en_word: str | None = None
    project_desc: str | None = None
    schedule_status: str = "deactivate"
    job_cron: str | None = None
    default_param: dict[str, Any] | list[Any] | str | None = None


class ProjectUpdateRequest(BaseModel):
    project_name: str | None = None
    project_en_word: str | None = None
    project_desc: str | None = None
    schedule_status: str
    job_cron: str | None = None
    default_param: dict[str, Any] | list[Any] | str | None = None


class ProjectScheduleUpdateRequest(BaseModel):
    schedule_status: str
    job_cron: str | None = None


# =========================================================
# Response helper
# =========================================================
def validate_schedule_status(
    schedule_status: str,
) -> str:
    """
    스케줄 상태값을 소문자로 정규화하고 검증한다.
    """
    normalized_status = schedule_status.strip().lower()

    allowed_statuses = {
        "activate",
        "deactivate",
    }

    if normalized_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                "schedule_status는 activate 또는 "
                "deactivate만 가능합니다."
            ),
        )

    return normalized_status


# =========================================================
# INSERT
# =========================================================
@router.post("")
def create_project(
    req: ProjectCreateRequest,
):
    """
    신규 프로젝트를 등록한다.
    """
    existing_project = select_project_one(
        project_no=req.project_no,
    )

    if existing_project is not None:
        raise HTTPException(
            status_code=409,
            detail=(
                "이미 존재하는 project_no입니다. "
                f"project_no={req.project_no}"
            ),
        )

    schedule_status = validate_schedule_status(
        req.schedule_status
    )

    try:
        success = insert_video_project(
            project_no=req.project_no,
            project_name=req.project_name,
            project_en_word=req.project_en_word,
            project_desc=req.project_desc,
            schedule_status=schedule_status,
            job_cron=req.job_cron,
            default_param=req.default_param,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"프로젝트 등록 중 오류가 발생했습니다: {exc}",
        ) from exc

    if not success:
        raise HTTPException(
            status_code=500,
            detail="프로젝트 등록에 실패했습니다.",
        )

    created_project = select_project_one(
        project_no=req.project_no,
    )

    return {
        "success": True,
        "message": "프로젝트가 등록되었습니다.",
        "data": created_project,
    }


# =========================================================
# SELECT LIST
# =========================================================
@router.get("")
def get_projects(
    project_no: int | None = Query(
        default=None,
        ge=1,
        description="프로젝트 번호",
    ),
):
    """
    프로젝트 목록을 조회한다.

    project_no가 없으면 전체 조회하고,
    project_no가 있으면 해당 프로젝트만 조회한다.
    """
    projects = select_project(
        project_no=project_no,
    )

    return {
        "success": True,
        "count": len(projects),
        "data": projects,
    }


# =========================================================
# SELECT ONE
# =========================================================
@router.get("/{project_no}")
def get_project(
    project_no: int,
):
    """
    프로젝트 한 건을 조회한다.
    """
    project = select_project_one(
        project_no=project_no,
    )

    if project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "프로젝트를 찾을 수 없습니다. "
                f"project_no={project_no}"
            ),
        )

    return {
        "success": True,
        "data": project,
    }


# =========================================================
# UPDATE
# =========================================================
@router.put("/{project_no}")
def modify_project(
    project_no: int,
    req: ProjectUpdateRequest,
):
    """
    프로젝트 전체 정보를 수정한다.
    """
    existing_project = select_project_one(
        project_no=project_no,
    )

    if existing_project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "수정할 프로젝트를 찾을 수 없습니다. "
                f"project_no={project_no}"
            ),
        )

    schedule_status = validate_schedule_status(
        req.schedule_status
    )

    try:
        success = update_video_project(
            project_no=project_no,
            project_name=req.project_name,
            project_en_word=req.project_en_word,
            project_desc=req.project_desc,
            schedule_status=schedule_status,
            job_cron=req.job_cron,
            default_param=req.default_param,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"프로젝트 수정 중 오류가 발생했습니다: {exc}",
        ) from exc

    if not success:
        raise HTTPException(
            status_code=500,
            detail="프로젝트 수정에 실패했습니다.",
        )

    updated_project = select_project_one(
        project_no=project_no,
    )

    return {
        "success": True,
        "message": "프로젝트가 수정되었습니다.",
        "data": updated_project,
    }


# =========================================================
# UPDATE SCHEDULE
# =========================================================
@router.patch("/{project_no}/schedule")
def modify_project_schedule(
    project_no: int,
    req: ProjectScheduleUpdateRequest,
):
    """
    프로젝트의 스케줄 상태와 크론 표현식만 수정한다.

    job_cron이 None이면 기존 크론 표현식을 유지한다.
    """
    existing_project = select_project_one(
        project_no=project_no,
    )

    if existing_project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "프로젝트를 찾을 수 없습니다. "
                f"project_no={project_no}"
            ),
        )

    schedule_status = validate_schedule_status(
        req.schedule_status
    )

    success = update_video_project_schedule(
        project_no=project_no,
        schedule_status=schedule_status,
        job_cron=req.job_cron,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="프로젝트 스케줄 수정에 실패했습니다.",
        )

    updated_project = select_project_one(
        project_no=project_no,
    )

    return {
        "success": True,
        "message": "프로젝트 스케줄이 수정되었습니다.",
        "data": updated_project,
    }


# =========================================================
# DELETE
# =========================================================
@router.delete("/{project_no}")
def remove_project(
    project_no: int,
):
    """
    프로젝트를 삭제한다.
    """
    existing_project = select_project_one(
        project_no=project_no,
    )

    if existing_project is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "삭제할 프로젝트를 찾을 수 없습니다. "
                f"project_no={project_no}"
            ),
        )

    success = delete_video_project(
        project_no=project_no,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="프로젝트 삭제에 실패했습니다.",
        )

    return {
        "success": True,
        "message": "프로젝트가 삭제되었습니다.",
        "project_no": project_no,
    }
