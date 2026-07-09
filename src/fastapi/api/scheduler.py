import datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from src.scheduler import scheduler_manager
from src.scheduler.job_registry import JOB_REGISTRY

# scheduler = BackgroundScheduler()
# scheduler.start()

class ScheduleRequest(BaseModel):
    action: str
    job_id: str
    func: str
    hour: int
    minute: int
    enabled: bool = True
    args: list
    kwargs: dict[str, Any]


def create_daily_video():
    print("영상 생성 시작")
    # 1. 이미지 생성
    # 2. 음성 생성
    # 3. 영상 생성
    # 4. 유튜브 업로드

router = APIRouter(
    prefix="/schedule",
    tags=["schedule"]
)

job_status = {}


@router.post("/save")
def save_schedule(req: ScheduleRequest):

        # job_id: str,
        # func: Callable,
        # hour: int,
        # minute: int,
        # enabled: bool = True,
        # args: list[Any] | None = None,
        # kwargs: dict[str, Any] | None = None,

    scheduler_manager.save_job(req.job_id, JOB_REGISTRY.get(req.func), req.hour, req.minute, req.enabled)

    return {
        "success": True,
        "message": "스케줄이 저장되었습니다.",
        "job_id": req.job_id,
        "hour": req.hour,
        "minute": req.minute,
        "enabled": req.enabled,
    }


@router.get("/list")
def list_schedule():
    jobs = scheduler_manager.list_jobs()
    return [
        {
            "job_id": job.id,
            "next_run_time": str(job.next_run_time),
            "trigger": str(job.trigger),
            "running": job.running,
            "enabled": job.enabled
        }
        for job in jobs
    ]


@router.post("/run-now")
def run_now(req:ScheduleRequest):
    return scheduler_manager.run_now(req.job_id)    

@router.post("/pause")
def pause(req:ScheduleRequest):
    scheduler_manager.pause(req.job_id)
    return {"success": True, "message": "중지 완료"}

@router.post("/resume")
def resume(req:ScheduleRequest):
    scheduler_manager.resume(req.job_id)
    return {"success": True, "message": "스케쥴 재개 완료"}

@router.post("/remove")
def remove(req:ScheduleRequest):
    scheduler_manager.remove(req.job_id)
    return {"success": True, "message": "스케쥴 삭제 완료"}