from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from src.scheduler.scheduler_manager import scheduler_manager
from src.fastapi.api.voice_api import router as voice_router
from src.fastapi.api.scheduler_api import router as scheduler_router
from src.fastapi.api.project_api import router as project_router
from src.fastapi.api.job_schedule_api import router as job_schedule_router
from src.fastapi.api.storage_api import router as storage_router
from src.fastapi.api.generated_video_api import ( router as generated_video_router, )
@asynccontextmanager
async def lifespan(app: FastAPI):

    print("=== Scheduler Start ===")

    scheduler_manager.start()
    scheduler_manager.restore_jobs()
    try:
        yield
    finally:
        scheduler_manager.shutdown()

app = FastAPI(lifespan=lifespan, title="AI 자동 영상제작 API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # 모든 Origin 허용
    allow_credentials=False,  # "*"와 함께 사용할 때는 False 권장
    allow_methods=["*"],      # 모든 HTTP 메서드 허용
    allow_headers=["*"],      # 모든 헤더 허용
)

down_path = "download"
static_root_dir = "output"

app.mount(f"/{down_path}", StaticFiles(directory=static_root_dir), name=down_path)

app.include_router(voice_router)
app.include_router(scheduler_router)
app.include_router(project_router)
app.include_router(job_schedule_router)
app.include_router(generated_video_router)
app.include_router(storage_router)