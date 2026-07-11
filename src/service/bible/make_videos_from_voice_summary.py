"""
Google TTS로 생성된 voice_package_summary.json을 기준으로
성경 장별 영상을 FFmpeg 방식으로 일괄 생성한다.

입력 예:
data/bible/audio/genesis/genesis_voice_package_summary.json

summary.json 내부 chapters 예:
{
    "chapter": 1,
    "body_audio": "data/bible/audio/genesis/01/genesis_01_body_audio.mp3",
    "segments_path": "data/bible/audio/genesis/01/genesis_01_segments.json",
    "body_audio_duration": 123.45,
    "segment_count": 31
}

출력 예:
data/bible/video/genesis_01_final.mp4
data/bible/video/genesis_02_final.mp4
...

실행 예:
cd C:\\project\\my-ai-video
.\\.venv\\Scripts\\python.exe -m src.service.bible.make_videos_from_voice_summary
"""

import json
from pathlib import Path


# ==============================
# 프로젝트 import
# ==============================
# 실제 프로젝트 파일 위치에 맞게 import 경로만 조정하세요.
from src.image_util.make_text_image import make_text_image
from src.model.video_basic import VideoBasic
from src.model.video_model import VideoModel
from src.model.text_style import TextStyle
from src.repository.bible.job_schedule_repo import select_job_schedule, update_job_schedule_status
from src.repository.bible.video_project_repo import select_project
from src.service.bible.concat_book_videos_from_summary import concat_book_videos_from_voice_summary
from src.utils.ffmpeg_util import get_ffmpeg_path, run_ffmpeg
from src.utils.file_util import FileUtil
from src.video_util.ffmpeg_make_video import make_body_video_ffmpeg


# ==============================
# 공통 유틸
# ==============================

def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)


def normalize_path(path: str | Path) -> Path:
    return Path(str(path).replace("\\", "/"))


# ==============================
# 출력 경로 생성
# ==============================
def build_output_video_path(
    output_root: str | Path,
    book_code: str,
    chapter: int
) -> Path:
    chapter_str = f"{chapter:02d}"
    return Path(output_root) / f"{book_code}_{chapter_str}_final.mp4"


# ==============================
# VideoBasic 생성
# ==============================
def create_video_basic(
    output_path: str | Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30
) -> VideoBasic:
    return VideoBasic(
        output_path=str(output_path),
        width=width,
        height=height,
        fps=fps
    )


# ==============================
# VideoModel 생성
# ==============================
def create_body_video_model(
    book_title: str,
    chapter: int,
    bg_images: list[str],
    textbox_image: str | None = None
) -> VideoModel:
    """
    장별 본문 영상에 사용할 VideoModel 생성.

    book_title:
        예: "창세기" 또는 "genesis"

    chapter:
        예: 1

    bg_images:
        배경 이미지 목록

    textbox_image:
        본문 텍스트 뒤에 깔 textbox 이미지가 있으면 경로 전달
    """

    return VideoModel(
        pause=0.4,
        bg_type="images",
        bg_images=bg_images,
        textbox_image=textbox_image,
        textbox_width=1400,

        title_txt=f"{book_title} {chapter}장",

        text_style=TextStyle(
            alignment=("center", "center"),
            text_position=("center", "center"),
            font_path="resources/font/H2MJRE.TTF",
            font_size=72,
            text_color=(0, 0, 0, 255),
            # text_effect=["shadow"],
            text_max_width=1500
        ),

        title_text_style=TextStyle(
            alignment=("center", "top"),
            text_position=(0, 80),
            font_path="resources/font/H2HDRM.TTF",
            font_size=70,
            text_color=(218, 223, 232, 255),
            text_effect=["shadow"]
        )
    )


# ==============================
# chapter 1개 영상 생성
# ==============================
def make_chapter_body_video_from_summary_item(
    book_code:str,
    book_title:str,
    bg_images: list[str],
    chapter_item: dict,
    output_root: str | Path,
    textbox_image: str | None = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    force_recreate_video: bool = False
) -> dict:
    """
    summary.json의 chapters 항목 1개를 기준으로
    make_body_video_ffmpeg()를 호출한다.
    """
    chapter = int(chapter_item["chapter"])

    body_audio_path = normalize_path(chapter_item["body_audio"])
    segments_json_path = normalize_path(chapter_item["segments_path"])

    if not body_audio_path.exists():
        raise FileNotFoundError(f"body_audio 파일이 없습니다: {body_audio_path}")

    if not segments_json_path.exists():
        raise FileNotFoundError(f"segments.json 파일이 없습니다: {segments_json_path}")

    output_path = build_output_video_path(
        output_root=output_root,
        book_code=book_code,
        chapter=chapter
    )

    ensure_dir(output_path.parent)

    if output_path.exists() and not force_recreate_video:
        print(f"[SKIP VIDEO] 기존 영상 사용: {output_path}")

        return {
            "chapter": chapter,
            "status": "skipped",
            "output_path": str(output_path).replace("\\", "/"),
            "body_audio": str(body_audio_path).replace("\\", "/"),
            "segments_path": str(segments_json_path).replace("\\", "/")
        }

    print("\n" + "=" * 70)
    print(f"[VIDEO START] {book_code} {chapter}장")
    print(f"[BODY AUDIO] {body_audio_path}")
    print(f"[SEGMENTS] {segments_json_path}")
    print(f"[OUTPUT] {output_path}")
    print("=" * 70)

    video_basic = create_video_basic(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps
    )

    video_body = create_body_video_model(
        book_title=book_title,
        chapter=chapter,
        bg_images=bg_images,
        textbox_image=textbox_image
    )

    make_body_video_ffmpeg(
        video_basic=video_basic,
        video_model=video_body,
        body_audio_path=str(body_audio_path),
        segments_json_path=str(segments_json_path),
        output_path=str(output_path)
    )

    print(f"[VIDEO DONE] {output_path}")

    return {
        "chapter": chapter,
        "status": "created",
        "output_path": str(output_path).replace("\\", "/"),
        "body_audio": str(body_audio_path).replace("\\", "/"),
        "segments_path": str(segments_json_path).replace("\\", "/")
    }


# ==============================
# summary 기준 전체 영상 생성
# ==============================
def make_book_body_videos_from_voice_summary(
    summary,
    output_root: str | Path = "data/bible/video",
    bg_images: list[str] | None = None,
    textbox_image: str | None = None,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    start_chapter: int | None = None,
    end_chapter: int | None = None,
    force_recreate_video: bool = False
) -> list[dict]:
    """
    genesis_voice_package_summary.json 같은 파일을 읽어서
    장별 최종 mp4를 일괄 생성한다.

    Args:
        summary_json_path:
            data/bible/audio/genesis/genesis_voice_package_summary.json

        output_root:
            최종 mp4 저장 폴더

        textbox_image:
            본문 텍스트 박스 이미지

        start_chapter:
            특정 장부터 생성하고 싶을 때 사용

        end_chapter:
            특정 장까지만 생성하고 싶을 때 사용

        force_recreate_video:
            True면 기존 mp4가 있어도 다시 생성
    """

    # summary = FileUtil.get_json_data(summary_json_path)

    book_code = summary["book_code"]
    book_title = summary["book_title"]
    chapters = summary.get("chapters", [])

    if bg_images is None:
        raise ValueError("bg_images가 비어 있습니다. 배경 이미지 경로를 1개 이상 전달하세요.")
    
    if not chapters:
        raise RuntimeError(f"summary에 chapters가 없습니다: {summary}")

    results = []

    for chapter_item in chapters:
        chapter = int(chapter_item["chapter"])

        if start_chapter is not None and chapter < start_chapter:
            continue

        if end_chapter is not None and chapter > end_chapter:
            continue

        result = make_chapter_body_video_from_summary_item(
            book_code = book_code,
            book_title = book_title,
            bg_images = bg_images,
            chapter_item=chapter_item,
            output_root=output_root,
            textbox_image=textbox_image,
            width=width,
            height=height,
            fps=fps,
            force_recreate_video=force_recreate_video
        )

        results.append(result)

    print("\n" + "=" * 70)
    print("[ALL VIDEO DONE]")
    print(f"[BOOK] {book_code}")
    print(f"[COUNT] {len(results)}")
    print("=" * 70)

    return results


# ==============================
# segments가 없는 단순 영상 제작 ( 배경 : 이미지 or video)
# ==============================
def make_intro_video_ffmpeg(
    video_basic,
    video_model,
    text_list: list[str],
    output_path: str,
    duration: float = 3.0,
    fadeout_duration: float = 0
):
    """
    배경 이미지/영상 + intro 텍스트로 3초짜리 intro mp4를 생성한다.
    """

    if not text_list:
        raise ValueError("intro 텍스트가 비어 있습니다.")

    ffmpeg = get_ffmpeg_path()

    bg_image = FileUtil.abspath(video_model.bg_images[0])

    # 일단 text는 한개만 처리.. 
    text_result = make_text_image(
        text_list[0],
        video_basic,
        video_model.text_style,
        max_width=video_basic.width
    )

    text_image_path = text_result["path"]

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fade_start = max(0, duration - fadeout_duration)
    cmd = [
        ffmpeg,
        "-y",

        # 0번 입력: 배경 이미지
        "-loop", "1",
        "-t", str(duration),
        "-i", bg_image,

        # 1번 입력: 텍스트 이미지
        "-i", text_image_path,

        # 2번 입력: 무음 오디오
        "-f", "lavfi",
        "-t", str(duration),
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",

        "-filter_complex",
        (
            f"[0:v]scale={video_basic.width}:{video_basic.height},setsar=1[base];"
            f"[base][1:v]overlay=(W-w)/2:(H-h)/2[overlaid];"
            f"[overlaid]fade=t=out:st={fade_start}:d={fadeout_duration}[v]"
        ),

        "-map", "[v]",
        "-map", "2:a",

        "-t", str(duration),
        "-r", str(video_basic.fps),

        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-pix_fmt", "yuv420p",

        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",

        output_path
    ]

    run_ffmpeg(cmd)

    return output_path


# 이미지를 배경으로 텍스트를 출력하는 정적 영상 생성
def make_simple_video(
    bg_images: list[str],
    text_list: list[str],
    output_path: str,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
) -> str:
    intro_video_basic = VideoBasic(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
    )

    intro_video_model = VideoModel(
        pause=0,
        bg_type="images",
        bg_images=bg_images,
        text_style=TextStyle(
            alignment=("center", "center"),
            text_position=("center", "center"),
            font_path="resources/font/H2HDRM.TTF",
            font_size=120,
            text_color=(218, 223, 232, 255),
            text_effect=["shadow"],
        ),
    )

    return make_intro_video_ffmpeg(
        video_basic=intro_video_basic,
        video_model=intro_video_model,
        text_list=text_list,
        output_path=output_path,
        duration=3,
        fadeout_duration=1,
    )

if __name__ == "__main__":
    try:
        project_no = 1

        # =====================================================
        # 1. DB에서 프로젝트 기본 파라미터 조회
        # =====================================================
        project_rows = select_project(project_no=project_no)

        if not project_rows:
            raise RuntimeError(
                f"video_project 데이터가 없습니다. project_no={project_no}"
            )

        video_project = project_rows[0]
        project_param = video_project.get("default_param", {})

        if not project_param:
            raise RuntimeError(
                f"default_param_json이 비어 있습니다. project_no={project_no}"
            )

        # =====================================================
        # 2. 실행 대기 중인 가장 낮은 job_seq 조회
        # =====================================================
        job_rows = select_job_schedule(
            project_no=project_no,
            run_status="wait",
        )

        if not job_rows:
            raise RuntimeError(
                f"실행할 대기 작업이 없습니다. project_no={project_no}"
            )

        job_schedule = job_rows[0]
        book_param = job_schedule.get("param_1", {})

        if not book_param:
            raise RuntimeError(
                "job_schedule.param_json_1이 비어 있습니다. "
                f"project_no={project_no}, "
                f"job_seq={job_schedule['job_seq']}"
            )


        # 스케쥴 상태 변경
        update_job_schedule_status(
            project_no=project_no,
            job_seq=job_schedule["job_seq"],
            run_status="running",
        )


        # =====================================================
        # 3. 프로젝트 공통 파라미터
        # =====================================================
        video_root = project_param["video_root"]
        intro_bg_path = project_param["intro_bg_path"]
        width = int(project_param.get("width", 1920))
        height = int(project_param.get("height", 1080))
        fps = int(project_param.get("fps", 30))

        # =====================================================
        # 4. Book별 파라미터
        # =====================================================
        book_title_en = book_param["book_title_en"]
        bg_image = book_param["bg_image"]

        start_chapter = book_param.get("start_chapter")
        end_chapter = book_param.get("end_chapter")

        if start_chapter is not None:
            start_chapter = int(start_chapter)

        if end_chapter is not None:
            end_chapter = int(end_chapter)

        Path(video_root).mkdir(
            parents=True,
            exist_ok=True,
        )

        summary_json_path = (
            f"data/bible/audio/{book_title_en}/"
            f"{book_title_en}_voice_package_summary.json"
        )

        bg_images = [bg_image]

        # =====================================================
        # 5. 음성 summary JSON 읽기
        # =====================================================
        summary = FileUtil.get_json_data(summary_json_path)

        chapter_count = int(
            summary.get("chapter_count") or 1
        )

        book_title = summary.get(
            "book_title",
            book_title_en,
        )

        book_code = summary.get(
            "book_code",
            book_title_en,
        )

        # start_chapter가 없으면 1장부터
        actual_start_chapter = (
            start_chapter
            if start_chapter is not None
            else 1
        )

        # end_chapter가 없으면 마지막 장까지
        actual_end_chapter = (
            min(end_chapter, chapter_count)
            if end_chapter is not None
            else chapter_count
        )

        if actual_start_chapter > actual_end_chapter:
            raise ValueError(
                "start_chapter가 end_chapter보다 큽니다. "
                f"start={actual_start_chapter}, "
                f"end={actual_end_chapter}"
            )

        # =====================================================
        # 6. 인트로 문구 생성
        # =====================================================
        if actual_start_chapter == actual_end_chapter:
            chapter_txt = f"{actual_start_chapter}장"
        else:
            chapter_txt = (
                f"{actual_start_chapter}장 ~ "
                f"{actual_end_chapter}장"
            )

        intro_title = (
            "성경 낭독\n"
            "━━━━━━━━━━━━\n\n\n\n"
            f"{book_title} {chapter_txt}"
        )

        intro_output_path = (
            f"{video_root}/{book_code}_intro.mp4"
        )

        # =====================================================
        # 7. 인트로 영상 생성
        # =====================================================
        intro_video_path = make_simple_video(
            bg_images=[intro_bg_path],
            text_list=[intro_title],
            output_path=intro_output_path,
            width=width,
            height=height,
            fps=fps,
        )
        # =====================================================
        # 8. 챕터별 영상 생성
        # =====================================================
        chapter_results = (
            make_book_body_videos_from_voice_summary(
                summary=summary,
                output_root=video_root,
                bg_images=bg_images,
                textbox_image=None,
                width=width,
                height=height,
                fps=fps,
                start_chapter=actual_start_chapter,
                end_chapter=actual_end_chapter,
                force_recreate_video=False,
            )
        )

        print("\n" + "=" * 70)
        print("[CHAPTER VIDEO RESULT]")
        print(f"[COUNT] {len(chapter_results)}")
        print("=" * 70)

        # =====================================================
        # 9. 최종 영상 경로 생성
        # =====================================================
        if (
            actual_start_chapter == 1
            and actual_end_chapter == chapter_count
        ):
            final_output_path = (
                f"{video_root}/{book_title_en}_full.mp4"
            )
        elif actual_start_chapter == actual_end_chapter:
            final_output_path = (
                f"{video_root}/"
                f"{book_title_en}_"
                f"{actual_start_chapter:02d}_full.mp4"
            )
        else:
            final_output_path = (
                f"{video_root}/"
                f"{book_title_en}_"
                f"{actual_start_chapter:02d}_"
                f"{actual_end_chapter:02d}_full.mp4"
            )

        # =====================================================
        # 10. 인트로 + 챕터 영상 합치기
        # =====================================================
        final_book_video_path = (
            concat_book_videos_from_voice_summary(
                summary_json_path=summary_json_path,
                video_root=video_root,
                output_path=final_output_path,
                intro_video_path=intro_video_path,
                start_chapter=actual_start_chapter,
                end_chapter=actual_end_chapter,
                force_recreate=True,
                reencode=False,
            )
        )

        # 성공한경우
        update_job_schedule_status(
            project_no=project_no,
            job_seq=job_schedule["job_seq"],
            run_status="completed",
            output_video_path=final_book_video_path,
        )
    except Exception:
        if job_schedule is not None:
            update_job_schedule_status(
                project_no=project_no,
                job_seq=job_schedule["job_seq"],
                run_status="failed",
            )

        raise

    print("\n" + "=" * 70)
    print("[FINAL BOOK VIDEO DONE]")
    print(f"[PROJECT NO] {project_no}")
    print(f"[JOB SEQ] {job_schedule['job_seq']}")
    print(f"[OUTPUT] {final_book_video_path}")
    print("=" * 70)