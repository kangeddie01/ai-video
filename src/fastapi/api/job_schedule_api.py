from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.repository.bible.job_schedule_repo import (
    claim_next_waiting_job,
    delete_job_schedule,
    delete_job_schedules_by_project,
    insert_job_schedule,
    select_job_schedule,
    select_job_schedule_one,
    select_next_waiting_job,
    update_job_schedule,
    update_job_schedule_params,
    update_job_schedule_status,
)


router = APIRouter(
    prefix="/job-schedules",
    tags=["job-schedules"],
)


# =========================================================
# Request Model
# =========================================================
class JobScheduleCreateRequest(BaseModel):
    project_no: int = Field(
        ge=1,
        description="프로젝트 번호",
    )
    run_status: str = "WAIT"
    run_type: str | None = None
    job_param_1: str | None = None
    job_param_2: str | None = None
    job_param_3: str | None = None
    param_json: dict[str, Any] | list[Any] | str | None = None
    output_video_path: str | None = None


class JobScheduleUpdateRequest(BaseModel):
    project_no: int = Field(
        ge=1,
        description="프로젝트 번호",
    )
    run_status: str
    run_type: str | None = None
    job_param_1: str | None = None
    job_param_2: str | None = None
    job_param_3: str | None = None
    param_json: dict[str, Any] | list[Any] | str | None = None
    output_video_path: str | None = None
    error_message: str | None = None


class JobScheduleStatusRequest(BaseModel):
    run_status: str
    output_video_path: str | None = None
    error_message: str | None = None


class JobScheduleParamRequest(BaseModel):
    job_param_1: str | None = None
    job_param_2: str | None = None
    job_param_3: str | None = None
    param_json: dict[str, Any] | list[Any] | str | None = None


class ClaimJobRequest(BaseModel):
    project_no: int | None = Field(
        default=None,
        ge=1,
    )
    waiting_status: str = "WAIT"


# =========================================================
# 공통 함수
# =========================================================
def normalize_status(run_status: str) -> str:
    """
    작업 상태 문자열을 대문자로 정규화한다.
    """
    normalized = run_status.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=400,
            detail="run_status는 필수입니다.",
        )

    return normalized


# =========================================================
# INSERT
# =========================================================
@router.post("")
def create_job_schedule(
    req: JobScheduleCreateRequest,
):
    """
    새로운 배치 실행 이력을 등록한다.
    """
    try:
        execution_id = insert_job_schedule(
            project_no=req.project_no,
            run_status=normalize_status(req.run_status),
            run_type=req.run_type,
            job_param_1=req.job_param_1,
            job_param_2=req.job_param_2,
            job_param_3=req.job_param_3,
            param_json=req.param_json,
            output_video_path=req.output_video_path,
        )

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"작업 이력 등록 중 오류가 발생했습니다: {exc}",
        ) from exc

    created_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    return {
        "success": True,
        "message": "작업 실행 이력이 등록되었습니다.",
        "execution_id": execution_id,
        "data": created_job,
    }


# =========================================================
# SELECT LIST
# =========================================================
@router.get("")
def get_job_schedules(
    execution_id: int | None = Query(
        default=None,
        ge=1,
    ),
    project_no: int | None = Query(
        default=None,
        ge=1,
    ),
    run_status: str | None = Query(
        default=None,
    ),
    run_type: str | None = Query(
        default=None,
    ),
    oldest_one: bool = Query(
        default=False,
    ),
):
    """
    작업 실행 이력 목록을 조회한다.

    사용 예:
        GET /job-schedules
        GET /job-schedules?project_no=1
        GET /job-schedules?run_status=WAIT
        GET /job-schedules?project_no=1&run_status=WAIT
        GET /job-schedules?run_status=WAIT&oldest_one=true
    """
    schedules = select_job_schedule(
        execution_id=execution_id,
        project_no=project_no,
        run_status=run_status,
        run_type=run_type,
        oldest_one=oldest_one,
    )

    return {
        "success": True,
        "count": len(schedules),
        "data": schedules,
    }


# =========================================================
# SELECT ONE
# =========================================================
@router.get("/{execution_id}")
def get_job_schedule(
    execution_id: int,
):
    """
    execution_id로 작업 실행 이력 한 건을 조회한다.
    """
    schedule = select_job_schedule_one(
        execution_id=execution_id,
    )

    if schedule is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "작업 실행 이력을 찾을 수 없습니다. "
                f"execution_id={execution_id}"
            ),
        )

    return {
        "success": True,
        "data": schedule,
    }


# =========================================================
# 다음 대기 작업 조회
# =========================================================
@router.get("/waiting/next")
def get_next_waiting_job(
    project_no: int | None = Query(
        default=None,
        ge=1,
    ),
    run_status: str = Query(
        default="WAIT",
    ),
):
    """
    가장 오래된 대기 작업 한 건을 조회한다.

    상태를 변경하지 않고 조회만 한다.
    """
    job = select_next_waiting_job(
        project_no=project_no,
        run_status=normalize_status(run_status),
    )

    if job is None:
        return {
            "success": True,
            "message": "대기 중인 작업이 없습니다.",
            "data": None,
        }

    return {
        "success": True,
        "data": job,
    }


# =========================================================
# 대기 작업 가져오기
# =========================================================
@router.post("/claim")
def claim_job(
    req: ClaimJobRequest,
):
    """
    가장 오래된 대기 작업을 가져오면서 RUNNING 상태로 변경한다.

    배치 서버 또는 Worker에서 작업을 가져갈 때 사용한다.
    """
    job = claim_next_waiting_job(
        project_no=req.project_no,
        waiting_status=normalize_status(
            req.waiting_status
        ),
    )

    if job is None:
        return {
            "success": True,
            "message": "처리할 대기 작업이 없습니다.",
            "data": None,
        }

    return {
        "success": True,
        "message": "작업을 가져왔습니다.",
        "data": job,
    }


# =========================================================
# UPDATE ALL
# =========================================================
@router.put("/{execution_id}")
def modify_job_schedule(
    execution_id: int,
    req: JobScheduleUpdateRequest,
):
    """
    execution_id 기준으로 실행 이력 전체 정보를 수정한다.
    """
    existing_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    if existing_job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "수정할 작업 실행 이력을 찾을 수 없습니다. "
                f"execution_id={execution_id}"
            ),
        )

    try:
        success = update_job_schedule(
            execution_id=execution_id,
            project_no=req.project_no,
            run_status=normalize_status(req.run_status),
            run_type=req.run_type,
            job_param_1=req.job_param_1,
            job_param_2=req.job_param_2,
            job_param_3=req.job_param_3,
            param_json=req.param_json,
            output_video_path=req.output_video_path,
            error_message=req.error_message,
        )

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if not success:
        raise HTTPException(
            status_code=500,
            detail="작업 실행 이력 수정에 실패했습니다.",
        )

    updated_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    return {
        "success": True,
        "message": "작업 실행 이력이 수정되었습니다.",
        "data": updated_job,
    }


# =========================================================
# UPDATE STATUS
# =========================================================
@router.patch("/{execution_id}/status")
def modify_job_schedule_status(
    execution_id: int,
    req: JobScheduleStatusRequest,
):
    """
    실행 상태, 결과 경로, 오류 메시지를 수정한다.

    상태별 시간 처리:
        RUNNING:
            started_at 설정

        SUCCESS, FAILED, CANCELLED:
            finished_at 설정
    """
    existing_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    if existing_job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "작업 실행 이력을 찾을 수 없습니다. "
                f"execution_id={execution_id}"
            ),
        )

    success = update_job_schedule_status(
        execution_id=execution_id,
        run_status=normalize_status(req.run_status),
        output_video_path=req.output_video_path,
        error_message=req.error_message,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="작업 상태 변경에 실패했습니다.",
        )

    updated_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    return {
        "success": True,
        "message": "작업 상태가 변경되었습니다.",
        "data": updated_job,
    }


# =========================================================
# UPDATE PARAM
# =========================================================
@router.patch("/{execution_id}/params")
def modify_job_schedule_params(
    execution_id: int,
    req: JobScheduleParamRequest,
):
    """
    작업 실행 파라미터만 수정한다.
    """
    existing_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    if existing_job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "작업 실행 이력을 찾을 수 없습니다. "
                f"execution_id={execution_id}"
            ),
        )

    try:
        success = update_job_schedule_params(
            execution_id=execution_id,
            job_param_1=req.job_param_1,
            job_param_2=req.job_param_2,
            job_param_3=req.job_param_3,
            param_json=req.param_json,
        )

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if not success:
        raise HTTPException(
            status_code=500,
            detail="작업 파라미터 수정에 실패했습니다.",
        )

    updated_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    return {
        "success": True,
        "message": "작업 파라미터가 수정되었습니다.",
        "data": updated_job,
    }


# =========================================================
# DELETE ONE
# =========================================================
@router.delete("/{execution_id}")
def remove_job_schedule(
    execution_id: int,
):
    """
    execution_id에 해당하는 작업 실행 이력 한 건을 삭제한다.
    """
    existing_job = select_job_schedule_one(
        execution_id=execution_id,
    )

    if existing_job is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "삭제할 작업 실행 이력을 찾을 수 없습니다. "
                f"execution_id={execution_id}"
            ),
        )

    success = delete_job_schedule(
        execution_id=execution_id,
    )

    if not success:
        raise HTTPException(
            status_code=500,
            detail="작업 실행 이력 삭제에 실패했습니다.",
        )

    return {
        "success": True,
        "message": "작업 실행 이력이 삭제되었습니다.",
        "execution_id": execution_id,
    }


# =========================================================
# DELETE BY PROJECT
# =========================================================
@router.delete("/project/{project_no}")
def remove_job_schedules_by_project(
    project_no: int,
):
    """
    특정 프로젝트의 모든 작업 실행 이력을 삭제한다.
    """
    deleted_count = delete_job_schedules_by_project(
        project_no=project_no,
    )

    return {
        "success": True,
        "message": "프로젝트 실행 이력이 삭제되었습니다.",
        "project_no": project_no,
        "deleted_count": deleted_count,
    }
