import json
from datetime import datetime
from typing import Any, Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.repository.bible.video_project_repo import select_project
from src.scheduler.job_registry import JOB_REGISTRY


class SchedulerManager:
    def __init__(self):
        self.scheduler = BackgroundScheduler(timezone="Asia/Seoul")

        # 서버 메모리에만 저장되는 최근 실행 상태
        self.job_status: dict[str, dict[str, Any]] = {}

    # =========================================================
    # Scheduler 시작/종료
    # =========================================================
    def start(self) -> None:
        if not self.scheduler.running:
            self.scheduler.start()

    def shutdown(self, wait: bool = False) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=wait)

    # =========================================================
    # 실제 Job 실행 Wrapper
    # =========================================================
    def _job_wrapper(
        self,
        job_id: str,
        func: Callable,
        *args,
        **kwargs,
    ):
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

        except Exception as exc:
            self.job_status[job_id]["last_result"] = "error"
            self.job_status[job_id]["last_error"] = str(exc)
            raise

        finally:
            self.job_status[job_id]["running"] = False
            self.job_status[job_id]["last_end"] = datetime.now().isoformat()

    # =========================================================
    # Job 등록/수정
    # =========================================================
    def save_job(
        self,
        job_id: str,
        func: Callable,
        cron_expression: str,
        enabled: bool = True,
        args: list[Any] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        args = args or []
        kwargs = kwargs or {}

        trigger = CronTrigger.from_crontab(
            cron_expression,
            timezone="Asia/Seoul",
        )

        self.scheduler.add_job(
            self._job_wrapper,
            trigger=trigger,
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

    # =========================================================
    # Job 일시정지
    # =========================================================
    def pause(self, job_id: str) -> bool:
        job = self.scheduler.get_job(job_id)

        if job is None:
            return False

        self.scheduler.pause_job(job_id)

        self.job_status.setdefault(
            job_id,
            {},
        )["enabled"] = False

        return True

    # =========================================================
    # Job 재개
    # =========================================================
    def resume(self, job_id: str) -> bool:
        job = self.scheduler.get_job(job_id)

        if job is None:
            return False

        self.scheduler.resume_job(job_id)

        self.job_status.setdefault(
            job_id,
            {},
        )["enabled"] = True

        return True

    # =========================================================
    # Job 제거
    # =========================================================
    def remove(self, job_id: str) -> bool:
        job = self.scheduler.get_job(job_id)

        if job is None:
            return False

        self.scheduler.remove_job(job_id)
        self.job_status.pop(job_id, None)

        return True

    # =========================================================
    # Job 실행 여부 확인
    # =========================================================
    def is_running(self, job_id: str) -> bool:
        return self.job_status.get(
            job_id,
            {},
        ).get(
            "running",
            False,
        )

    # =========================================================
    # Job 즉시 실행
    # =========================================================
    def run_now(
        self,
        job_id: str,
        execution_id: int,
        project_no: int,
    ) -> dict:
        job = self.scheduler.get_job(job_id)

        if job is None:
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

        execute_kwargs = {
            **(job.kwargs or {}),
            "project_no": project_no,
            "execution_id": execution_id,
        }

        self._job_wrapper(
            job_id,
            func,
            *args,
            **execute_kwargs,
        )

        return {
            "success": True,
            "message": "즉시 실행 완료",
        }

    # =========================================================
    # Job 목록 조회
    # =========================================================
    def list_jobs(self) -> list[dict]:
        result: list[dict] = []

        for job in self.scheduler.get_jobs():
            status = self.job_status.get(
                job.id,
                {},
            )

            result.append(
                {
                    "id": job.id,
                    "name": job.name,
                    "running": status.get(
                        "running",
                        False,
                    ),
                    "enabled": (job.next_run_time is not None),
                    "next_run_time": (
                        str(job.next_run_time) if job.next_run_time else None
                    ),
                    "trigger": str(job.trigger),
                    "last_start": status.get("last_start"),
                    "last_end": status.get("last_end"),
                    "last_result": status.get("last_result"),
                    "last_error": status.get("last_error"),
                }
            )

        return result

    # =========================================================
    # DB에 저장된 프로젝트 스케줄 복원
    # =========================================================
    def restore_jobs(self) -> dict:
        projects = select_project()

        restored_count = 0
        skipped_count = 0
        errors: list[dict] = []

        for project in projects:
            project_no = project.get("project_no")
            project_en_word = project.get("project_en_word")
            job_cron = project.get("job_cron")
            schedule_status = project.get("schedule_status")
            default_param = project.get("default_param")

            # repository가 default_param_json만 반환하는 경우
            if default_param is None:
                default_param = self._parse_default_param(
                    project.get("default_param_json")
                )

            job_id = f"video-project-{project_no}"

            # JOB_REGISTRY의 key는 프로젝트 영문 코드
            func = JOB_REGISTRY.get(project_en_word)

            if func is None:
                skipped_count += 1

                errors.append(
                    {
                        "project_no": project_no,
                        "job_id": job_id,
                        "message": (
                            "JOB_REGISTRY에서 실행 함수를 "
                            f"찾을 수 없습니다: {project_en_word}"
                        ),
                    }
                )
                continue

            if not job_cron:
                skipped_count += 1

                errors.append(
                    {
                        "project_no": project_no,
                        "job_id": job_id,
                        "message": "job_cron 값이 없습니다.",
                    }
                )
                continue

            enabled = self._is_schedule_enabled(schedule_status)

            try:
                self.save_job(
                    job_id=job_id,
                    func=func,
                    cron_expression=job_cron,
                    enabled=enabled,
                    kwargs={
                        "project_no": project_no,
                        "execution_id": None,
                    },
                )

                restored_count += 1

            except (ValueError, TypeError) as exc:
                skipped_count += 1

                errors.append(
                    {
                        "project_no": project_no,
                        "job_id": job_id,
                        "message": str(exc),
                    }
                )

        return {
            "restored_count": restored_count,
            "skipped_count": skipped_count,
            "errors": errors,
        }

    # =========================================================
    # schedule_status → enabled 변환
    # =========================================================
    @staticmethod
    def _is_schedule_enabled(
        schedule_status: str | bool | int | None,
    ) -> bool:
        if isinstance(schedule_status, bool):
            return schedule_status

        if isinstance(schedule_status, int):
            return schedule_status == 1

        if schedule_status is None:
            return False

        return str(schedule_status).strip().upper() in {
            "Y",
            "YES",
            "TRUE",
            "1",
            "ENABLE",
            "ENABLED",
            "ACTIVE",
            "ACTIVATE",
            "RUN",
        }

    # =========================================================
    # default_param_json 변환
    # =========================================================
    @staticmethod
    def _parse_default_param(
        value: dict | str | None,
    ) -> dict[str, Any]:
        if value is None:
            return {}

        if isinstance(value, dict):
            return value

        if isinstance(value, str):
            if not value.strip():
                return {}

            try:
                parsed_value = json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "default_param_json이 올바른 " f"JSON이 아닙니다: {exc}"
                ) from exc

            if not isinstance(parsed_value, dict):
                raise ValueError(
                    "default_param_json의 최상위 값은 " "JSON 객체(dict)여야 합니다."
                )

            return parsed_value

        raise TypeError(
            "default_param_json은 dict, str, None만 "
            f"가능합니다: {type(value).__name__}"
        )


scheduler_manager = SchedulerManager()
