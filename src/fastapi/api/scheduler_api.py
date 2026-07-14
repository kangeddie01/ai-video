from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.repository.bible.job_schedule_repo import (
    update_job_schedule_status,
)
from src.scheduler.scheduler_manager import scheduler_manager
from src.scheduler.job_registry import JOB_REGISTRY


# =========================================================
# 요청 모델
# =========================================================
class ScheduleSaveRequest(BaseModel):
    job_id: str
    project_en_word: str
    cron_expression: str
    enabled: bool = True
    args: list[Any] = Field(default_factory=list)
    kwargs: dict[str, Any] = Field(default_factory=dict)


class JobIdRequest(BaseModel):
    job_id: str


class JobStatusChangeRequest(BaseModel):
    execution_id: int
    run_status: str
    output_video_path: str | None = None
    error_message: str | None = None

class RunNowRequest(BaseModel):
    job_id: str
    execution_id: int
    project_no: int


# =========================================================
# Router
# =========================================================
router = APIRouter(
    prefix="/schedule",
    tags=["schedule"],
)


# =========================================================
# 스케줄 등록/수정
# =========================================================
@router.post("/save")
def save_schedule(req: ScheduleSaveRequest):
    func = JOB_REGISTRY.get(req.project_en_word)

    if func is None:
        raise HTTPException(
            status_code=400,
            detail=(
                "등록된 실행 함수를 찾을 수 없습니다. "
                f"project_en_word={req.project_en_word}"
            ),
        )

    try:
        scheduler_manager.save_job(
            job_id=req.job_id,
            func=func,
            cron_expression=req.cron_expression,
            enabled=req.enabled,
            args=req.args,
            kwargs=req.kwargs,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"잘못된 크론 표현식입니다: {exc}",
        ) from exc

    return {
        "success": True,
        "message": "스케줄이 저장되었습니다.",
        "job_id": req.job_id,
        "project_en_word": req.project_en_word,
        "cron_expression": req.cron_expression,
        "enabled": req.enabled,
        "args": req.args,
        "kwargs": req.kwargs,
    }


# =========================================================
# 스케줄 목록
# =========================================================
@router.get("/list")
def list_schedule():
    return scheduler_manager.list_jobs()


# =========================================================
# 즉시 실행
# =========================================================

@router.post("/run-now")
def run_now(req: RunNowRequest):
    result = scheduler_manager.run_now(
        job_id=req.job_id,
        project_no = req.project_no,
        execution_id = req.execution_id
    )

    if not result.get("success"):
        raise HTTPException(
            status_code=400,
            detail=result.get(
                "message",
                "스케줄 즉시 실행에 실패했습니다.",
            ),
        )

    return result



# =========================================================
# 스케줄 일시정지
# =========================================================
@router.post("/pause")
def pause(req: JobIdRequest):
    success = scheduler_manager.pause(req.job_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Job을 찾을 수 없습니다: {req.job_id}",
        )

    return {
        "success": True,
        "message": "스케줄 일시정지 완료",
        "job_id": req.job_id,
    }


# =========================================================
# 스케줄 재개
# =========================================================
@router.post("/resume")
def resume(req: JobIdRequest):
    success = scheduler_manager.resume(req.job_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Job을 찾을 수 없습니다: {req.job_id}",
        )

    return {
        "success": True,
        "message": "스케줄 재개 완료",
        "job_id": req.job_id,
    }


# =========================================================
# 스케줄 삭제
# =========================================================
@router.post("/remove")
def remove(req: JobIdRequest):
    success = scheduler_manager.remove(req.job_id)

    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Job을 찾을 수 없습니다: {req.job_id}",
        )

    return {
        "success": True,
        "message": "스케줄 삭제 완료",
        "job_id": req.job_id,
    }


# =========================================================
# 배치 서버에서 작업 상태 변경
# =========================================================
@router.post("/job-status")
def change_job_status(req: JobStatusChangeRequest):
    success = update_job_schedule_status(
        execution_id=req.execution_id,
        run_status=req.run_status,
        output_video_path=req.output_video_path,
        error_message=req.error_message,
    )

    if not success:
        raise HTTPException(
            status_code=404,
            detail=(
                "실행 이력을 찾을 수 없습니다. "
                f"execution_id={req.execution_id}"
            ),
        )

    return {
        "success": True,
        "message": "작업 상태가 변경되었습니다.",
        "execution_id": req.execution_id,
        "run_status": req.run_status.upper(),
        "output_video_path": req.output_video_path,
        "error_message": req.error_message,
    }