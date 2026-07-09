from datetime import datetime
from typing import Callable, Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger


class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")
        self.job_status = {}

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    def _job_wrapper(self, job_id: str, func: Callable, *args, **kwargs):
        self.job_status[job_id] = {
            **self.job_status.get(job_id, {}),
            "running": True,
            "last_start": datetime.now().isoformat(),
            "last_end": None,
            "last_error": None,
        }

        try:
            result = func(*args, **kwargs)

            self.job_status[job_id]["last_result"] = "success"
            return result

        except Exception as e:
            self.job_status[job_id]["last_result"] = "error"
            self.job_status[job_id]["last_error"] = str(e)
            raise

        finally:
            self.job_status[job_id]["running"] = False
            self.job_status[job_id]["last_end"] = datetime.now().isoformat()

    def save_job(
        self,
        job_id: str,
        func: Callable,
        hour: int,
        minute: int,
        enabled: bool = True,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ):
        args = args or []
        kwargs = kwargs or {}

        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        self.scheduler.add_job(
            self._job_wrapper,
            trigger=CronTrigger(hour=hour, minute=minute),
            id=job_id,
            args=[job_id, func, *args],
            kwargs=kwargs,
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

        self.job_status[job_id] = {
            "running": False,
            "enabled": enabled,
            "last_start": None,
            "last_end": None,
            "last_result": None,
            "last_error": None,
        }

        if not enabled:
            self.scheduler.pause_job(job_id)

    def pause(self, job_id: str):
        job = self.scheduler.get_job(job_id)
        if not job:
            return False

        self.scheduler.pause_job(job_id)
        self.job_status.setdefault(job_id, {})["enabled"] = False
        return True

    def resume(self, job_id: str):
        job = self.scheduler.get_job(job_id)
        if not job:
            return False

        self.scheduler.resume_job(job_id)
        self.job_status.setdefault(job_id, {})["enabled"] = True
        return True

    def remove(self, job_id: str):
        job = self.scheduler.get_job(job_id)
        if not job:
            return False

        self.scheduler.remove_job(job_id)
        self.job_status.pop(job_id, None)
        return True

    def is_running(self, job_id: str) -> bool:
        return self.job_status.get(job_id, {}).get("running", False)

    def run_now(self, job_id: str):
        job = self.scheduler.get_job(job_id)
        if not job:
            return {
                "success": False,
                "message": "Job을 찾을 수 없습니다.",
            }

        if self.is_running(job_id):
            return {
                "success": False,
                "message": "이미 실행 중입니다.",
            }

        func = job.args[1]
        args = list(job.args[2:])
        kwargs = job.kwargs or {}

        self._job_wrapper(job_id, func, *args, **kwargs)

        return {
            "success": True,
            "message": "즉시 실행 완료",
        }
    
    def list_jobs(self):
        result = []

        for job in self.scheduler.get_jobs():
            status = self.job_status.get(job.id, {})

            result.append({
                "id": job.id,
                "name": job.name,
                "running": status.get("running", False),
                "enabled": job.next_run_time is not None,
                "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
                "last_start": status.get("last_start"),
                "last_end": status.get("last_end"),
                "last_result": status.get("last_result"),
                "last_error": status.get("last_error"),
            })

        return result


scheduler_manager = SchedulerManager()