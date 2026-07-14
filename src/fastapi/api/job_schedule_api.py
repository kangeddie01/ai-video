"""
job_schedule FastAPI Router.

지원 기능:
- 작업 단건 등록
- 작업 일괄 등록
- 작업 목록 조회
- 작업 단건 조회
- 다음 대기 작업 조회
- 대기 작업 선점
- 작업 전체 수정
- 작업 상태 수정
- 작업 파라미터 수정
- 작업 단건 삭제
- 프로젝트별 작업 전체 삭제

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

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Query
from pydantic import BaseModel
from pydantic import Field

from src.repository.bible.job_schedule_repo import (
    claim_next_waiting_job,
    delete_job_schedule,
    delete_job_schedules_by_project,
    insert_job_schedule,
    insert_job_schedules_batch,
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
    """
    작업 단건 등록 요청.
    """

    project_no: int = Field(
        ge=1,
        description="프로젝트 번호",
    )

    run_status: str = Field(
        default="wait",
        description=(
            "작업 상태. "
            "wait, running, completed, failed"
        ),
    )

    run_type: str | None = Field(
        default="batch",
        description="작업 실행 유형",
    )

    job_param_1: str | None = None
    job_param_2: str | None = None
    job_param_3: str | None = None
    job_param_4: str | None = None
    job_param_5: str | None = None

    output_video_path: str | None = None


class JobScheduleUpdateRequest(BaseModel):
    """
    작업 전체 수정 요청.
    """

    project_no: int = Field(
        ge=1,
        description="프로젝트 번호",
    )

    run_status: str = Field(
        description=(
            "작업 상태. "
            "wait, running, completed, failed"
        ),
    )

    run_type: str | None = None

    job_param_1: str | None = None
    job_param_2: str | None = None
    job_param_3: str | None = None
    job_param_4: str | None = None
    job_param_5: str | None = None

    output_video_path: str | None = None
    error_message: str | None = None


class JobScheduleStatusRequest(BaseModel):
    """
    작업 상태 변경 요청.
    """

    run_status: str = Field(
        description=(
            "작업 상태. "
            "wait, running, completed, failed"
        ),
    )

    output_video_path: str | None = None
    error_message: str | None = None


class JobScheduleParamRequest(BaseModel):
    """
    작업 파라미터 변경 요청.
    """

    job_param_1: str | None = None
    job_param_2: str | None = None
    job_param_3: str | None = None
    job_param_4: str | None = None
    job_param_5: str | None = None


class ClaimJobRequest(BaseModel):
    """
    다음 대기 작업 선점 요청.
    """

    project_no: int | None = Field(
        default=None,
        ge=1,
        description="프로젝트 번호",
    )

    waiting_status: str = Field(
        default="wait",
        description="선점할 대기 상태",
    )


class JobScheduleBatchCreateRequest(BaseModel):
    """
    작업 일괄 등록 요청.
    """

    project_no: int = Field(
        ge=1,
        description="프로젝트 번호",
    )

    job_params: list[str] = Field(
        min_length=1,
        description=(
            "작업 파라미터 목록. "
            "각 항목은 "
            "param1|param2|param3|param4|param5 형식"
        ),
    )

    run_type: str = Field(
        default="batch",
        description="작업 실행 유형",
    )


# =========================================================
# INSERT ONE
# =========================================================

@router.post("")
def create_job_schedule(
    req: JobScheduleCreateRequest,
):
    """
    새로운 작업 실행 이력 한 건을 등록한다.

    요청 예:

        {
            "project_no": 1,
            "run_status": "wait",
            "run_type": "batch",
            "job_param_1": "genesis",
            "job_param_2": "data/bible/images/bg.png",
            "job_param_3": "1",
            "job_param_4": "10",
            "job_param_5": null
        }
    """
    try:
        execution_id = insert_job_schedule(
            project_no=req.project_no,
            run_status=req.run_status,
            run_type=req.run_type,
            job_param_1=req.job_param_1,
            job_param_2=req.job_param_2,
            job_param_3=req.job_param_3,
            job_param_4=req.job_param_4,
            job_param_5=req.job_param_5,
            output_video_path=req.output_video_path,
        )

        created_job = select_job_schedule_one(
            execution_id=execution_id,
        )

        return {
            "success": True,
            "message": "작업 실행 이력이 등록되었습니다.",
            "execution_id": execution_id,
            "data": created_job,
        }

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 실행 이력 등록 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# INSERT BATCH
# =========================================================

@router.post("/batch")
def create_job_schedules_batch(
    req: JobScheduleBatchCreateRequest,
):
    """
    여러 작업 실행 이력을 한 번에 등록한다.

    job_params 항목 형식:

        param1|param2|param3|param4|param5

    요청 예:

        {
            "project_no": 1,
            "job_params": [
                "genesis|data/bible/images/bg1.png|1|10|",
                "exodus|data/bible/images/bg2.png|1|5|"
            ],
            "run_type": "batch"
        }
    """
    try:
        inserted_jobs = insert_job_schedules_batch(
            project_no=req.project_no,
            job_params=req.job_params,
            run_type=req.run_type,
        )

        return {
            "success": True,
            "message": (
                f"{len(inserted_jobs)}건의 "
                "작업 실행 이력이 등록되었습니다."
            ),
            "project_no": req.project_no,
            "inserted_count": len(inserted_jobs),
            "data": inserted_jobs,
        }

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 실행 이력 일괄 등록 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# SELECT LIST
# =========================================================

@router.get("")
def get_job_schedules(
    execution_id: int | None = Query(
        default=None,
        ge=1,
        description="Job 실행 ID",
    ),
    project_no: int | None = Query(
        default=None,
        ge=1,
        description="프로젝트 번호",
    ),
    run_status: str | None = Query(
        default=None,
        description="작업 상태",
    ),
    oldest_one: bool = Query(
        default=False,
        description="가장 오래된 한 건만 조회",
    ),
):
    """
    작업 실행 이력 목록을 조회한다.

    사용 예:

        GET /job-schedules

        GET /job-schedules?execution_id=10

        GET /job-schedules?project_no=1

        GET /job-schedules?run_status=wait

        GET /job-schedules?project_no=1&run_status=wait

        GET /job-schedules
            ?project_no=1
            &run_status=wait
            &oldest_one=true
    """
    try:
        schedules = select_job_schedule(
            execution_id=execution_id,
            project_no=project_no,
            run_status=run_status,
            oldest_one=oldest_one,
        )

        return {
            "success": True,
            "count": len(schedules),
            "data": schedules,
        }

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 실행 이력 조회 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# NEXT WAITING JOB
# =========================================================

@router.get("/waiting/next")
def get_next_waiting_job(
    project_no: int | None = Query(
        default=None,
        ge=1,
        description="프로젝트 번호",
    ),
    run_status: str = Query(
        default="wait",
        description="조회할 작업 상태",
    ),
):
    """
    가장 오래된 대기 작업 한 건을 조회한다.

    이 API는 조회만 하며 상태는 변경하지 않는다.
    """
    try:
        job = select_next_waiting_job(
            project_no=project_no,
            run_status=run_status,
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

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "대기 작업 조회 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# CLAIM WAITING JOB
# =========================================================

@router.post("/claim")
def claim_job(
    req: ClaimJobRequest,
):
    """
    가장 오래된 대기 작업을 조회한 뒤
    running 상태로 변경하여 반환한다.

    배치 서버 또는 Worker에서 다음 처리할 작업을
    가져갈 때 사용한다.
    """
    try:
        job = claim_next_waiting_job(
            project_no=req.project_no,
            waiting_status=req.waiting_status,
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

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "대기 작업 선점 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


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
    try:
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

    except HTTPException:
        raise

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 실행 이력 조회 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# UPDATE ALL
# =========================================================

@router.put("/{execution_id}")
def modify_job_schedule(
    execution_id: int,
    req: JobScheduleUpdateRequest,
):
    """
    execution_id 기준으로 작업 실행 이력 전체를 수정한다.
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
            run_status=req.run_status,
            run_type=req.run_type,
            job_param_1=req.job_param_1,
            job_param_2=req.job_param_2,
            job_param_3=req.job_param_3,
            job_param_4=req.job_param_4,
            job_param_5=req.job_param_5,
            output_video_path=req.output_video_path,
            error_message=req.error_message,
        )

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

    except HTTPException:
        raise

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 실행 이력 수정 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# UPDATE STATUS
# =========================================================

@router.patch("/{execution_id}/status")
def modify_job_schedule_status(
    execution_id: int,
    req: JobScheduleStatusRequest,
):
    """
    작업 상태와 실행 결과 정보를 수정한다.

    상태별 처리:

        wait:
            started_at = NULL
            finished_at = NULL
            error_message = NULL

        running:
            started_at = CURRENT_TIMESTAMP
            finished_at = NULL
            error_message = NULL

        completed:
            finished_at = CURRENT_TIMESTAMP

        failed:
            finished_at = CURRENT_TIMESTAMP
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
        success = update_job_schedule_status(
            execution_id=execution_id,
            run_status=req.run_status,
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

    except HTTPException:
        raise

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 상태 변경 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


# =========================================================
# UPDATE PARAMS
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
            job_param_4=req.job_param_4,
            job_param_5=req.job_param_5,
        )

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

    except HTTPException:
        raise

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 파라미터 수정 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


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
    try:
        deleted_count = delete_job_schedules_by_project(
            project_no=project_no,
        )

        return {
            "success": True,
            "message": "프로젝트 실행 이력이 삭제되었습니다.",
            "project_no": project_no,
            "deleted_count": deleted_count,
        }

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "프로젝트 실행 이력 삭제 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc


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

    try:
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

    except HTTPException:
        raise

    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                "작업 실행 이력 삭제 중 "
                f"오류가 발생했습니다: {exc}"
            ),
        ) from exc
