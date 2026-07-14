import os
from pathlib import Path
import uuid

from src.model.text_style import TextStyle
from src.model.video_basic import VideoBasic
from src.model.video_model import VideoModel
from src.repository.bible.generated_video_repo import insert_generated_video
from src.repository.bible.job_schedule_repo import (
    select_job_schedule,
    update_job_schedule_status,
)
from src.repository.bible.video_project_repo import (
    select_project,
)
from src.service.bible.concat_book_videos_from_summary import (
    concat_book_videos_from_voice_summary,
)
from src.service.bible.make_videos_from_voice_summary import (
    make_book_body_videos_from_voice_summary,
    make_simple_video_ffmpeg,
)
from src.utils.file_util import FileUtil
from src.utils.google_storage_util import (
    get_content_type,
    get_video_metadata,
    upload_file_to_gcs,
)


def start_bible_job(
    project_no: int = 1,
    execution_id: int | None = None,
):
    """
    성경 영상 생성 작업을 실행한다.

    execution_id가 전달된 경우:
        해당 execution_id의 job_schedule을 조회한다.

    execution_id가 전달되지 않은 경우:
        해당 프로젝트에서 가장 오래된 wait 작업 한 건을 조회한다.
    """

    job_schedule = None

    # =====================================================
    # 1. DB에서 프로젝트 기본 파라미터 조회
    # =====================================================
    project_rows = select_project(
        project_no=project_no,
    )

    if not project_rows:
        raise RuntimeError(
            "video_project 데이터가 없습니다. " f"project_no={project_no}"
        )

    video_project = project_rows[0]

    project_param = video_project.get(
        "default_param",
        {},
    )

    if not project_param:
        raise RuntimeError(
            "default_param_json이 비어 있습니다. " f"project_no={project_no}"
        )
    print("## execution_id : " + str(execution_id))
    # =====================================================
    # 2. 실행 대상 job_schedule 조회
    # =====================================================
    if execution_id is not None:
        job_rows = select_job_schedule(
            execution_id=execution_id,
            project_no=project_no,
        )

        if not job_rows:
            raise RuntimeError(
                "해당 실행 작업을 찾을 수 없습니다. "
                f"project_no={project_no}, "
                f"execution_id={execution_id}"
            )

        job_schedule = job_rows[0]

        current_status = (
            str(
                job_schedule.get(
                    "run_status",
                    "",
                )
            )
            .strip()
            .lower()
        )

        if current_status == "running":
            raise RuntimeError(
                "이미 실행 중인 작업입니다. " f"execution_id={execution_id}"
            )

        if current_status == "completed":
            raise RuntimeError(
                "이미 완료된 작업입니다. " f"execution_id={execution_id}"
            )

    else:
        job_rows = select_job_schedule(
            project_no=project_no,
            run_status="wait",
            oldest_one=True,
        )

        if not job_rows:
            raise RuntimeError(
                "실행할 대기 작업이 없습니다. " f"project_no={project_no}"
            )

        job_schedule = job_rows[0]

    selected_execution_id = int(job_schedule["execution_id"])

    # 기존 repository가 param_json_1을
    # param_1로 변환해서 반환하는 경우
    book_title_en = job_schedule.get("job_param_1", {})
    bg_image = job_schedule.get("job_param_2", {})
    start_chapter = job_schedule.get("job_param_3", {})
    end_chapter = job_schedule.get("job_param_4", {})

    if not book_title_en:
        raise RuntimeError(
            "job_schedule의 작업 파라미터가 비어 있습니다. "
            f"project_no={project_no}, "
            f"execution_id={selected_execution_id}"
        )

    # =====================================================
    # 3. 작업 상태를 running으로 변경
    # =====================================================
    updated = update_job_schedule_status(
        execution_id=selected_execution_id,
        run_status="running",
    )

    if not updated:
        raise RuntimeError(
            "작업 상태를 running으로 변경하지 못했습니다. "
            f"execution_id={selected_execution_id}"
        )

    try:
        # =====================================================
        # 4. 프로젝트 공통 파라미터
        # =====================================================
        video_root = project_param["video_root"]
        intro_bg_path = project_param["intro_bg_path"]
        width = int(
            project_param.get(
                "width",
                1920,
            )
        )
        height = int(
            project_param.get(
                "height",
                1080,
            )
        )
        fps = int(
            project_param.get(
                "fps",
                30,
            )
        )

        if start_chapter is not None:
            start_chapter = int(start_chapter)

        if end_chapter is not None:
            end_chapter = int(end_chapter)

        Path(video_root).mkdir(
            parents=True,
            exist_ok=True,
        )

        summary_json_path = f"data/bible/audio/{book_title_en}/{book_title_en}_voice_package_summary.json"

        bg_images = [bg_image]

        # =====================================================
        # 6. 음성 summary JSON 읽기
        # =====================================================
        summary = FileUtil.get_json_data(summary_json_path)

        chapter_count = int(summary.get("chapter_count") or 1)
        book_title = summary.get(
            "book_title",
            book_title_en,
        )
        book_code = summary.get(
            "book_code",
            book_title_en,
        )

        actual_start_chapter = start_chapter if start_chapter is not None else 1

        actual_end_chapter = (
            min(
                end_chapter,
                chapter_count,
            )
            if end_chapter is not None
            else chapter_count
        )

        if actual_start_chapter > actual_end_chapter:
            raise ValueError(
                "start_chapter가 "
                "end_chapter보다 큽니다. "
                f"start={actual_start_chapter}, "
                f"end={actual_end_chapter}"
            )

        # =====================================================
        # 7. 인트로 문구 생성
        # =====================================================
        if actual_start_chapter == actual_end_chapter:
            chapter_txt = f"{actual_start_chapter}장"
        else:
            chapter_txt = f"{actual_start_chapter}장 ~ " f"{actual_end_chapter}장"

        # =====================================================
        # 8. 인트로 영상 생성
        # =====================================================
        intro_video_path = make_simple_video_ffmpeg(
            video_basic=VideoBasic(
                output_path=f"{video_root}/{book_code}_intro.mp4",
                width=width,
                height=height,
                fps=fps,
            ),
            video_model=VideoModel(
                pause=0,
                bg_type="images",
                bg_images=[intro_bg_path],
                text_list=[
                    TextStyle(
                        text="성경 낭독",
                        alignment=("center", "center"),
                        text_position=("center", -100),
                        font_path="resources/font/H2HDRM.TTF",
                        font_size=160,
                        text_color=(214, 208, 92, 255),
                        # text_effect=["shadow"],
                    ),
                    TextStyle(
                        text=f"{book_title} {chapter_txt}",
                        alignment=("center", "center"),
                        text_position=("center", 100),
                        font_path="resources/font/H2HDRM.TTF",
                        font_size=120,
                        text_color=(218, 223, 232, 255),
                        text_effect=["shadow"],
                    ),
                ],
            ),
            duration=3,
            fadeout_duration=1,
        )

        # =====================================================
        # 9. 챕터별 영상 생성
        # =====================================================
        chapter_results = make_book_body_videos_from_voice_summary(
            summary=summary,
            output_root=video_root,
            bg_images=bg_images,
            textbox_image=None,
            width=width,
            height=height,
            fps=fps,
            start_chapter=(actual_start_chapter),
            end_chapter=(actual_end_chapter),
            force_recreate_video=False,
        )

        print("\n" + "=" * 70)
        print("[CHAPTER VIDEO RESULT]")
        print(f"[COUNT] " f"{len(chapter_results)}")
        print("=" * 70)

        # =====================================================
        # 10. 최종 영상 경로 생성
        # =====================================================
        if actual_start_chapter == 1 and actual_end_chapter == chapter_count:
            final_output_path = f"{video_root}/{book_title_en}_full_{uuid.uuid4()}.mp4"

        elif actual_start_chapter == actual_end_chapter:
            final_output_path = (
                f"{video_root}/"
                f"{book_title_en}_"
                f"{actual_start_chapter:02d}"
                f"_full_{uuid.uuid4()}.mp4"
            )

        else:
            final_output_path = (
                f"{video_root}/"
                f"{book_title_en}_"
                f"{actual_start_chapter:02d}_"
                f"{actual_end_chapter:02d}"
                f"_full_{uuid.uuid4()}.mp4"
            )

        # =====================================================
        # 11. 인트로 + 챕터 영상 합치기
        # =====================================================
        final_book_video_path = concat_book_videos_from_voice_summary(
            summary_json_path=(summary_json_path),
            video_root=video_root,
            output_path=(final_output_path),
            intro_video_path=(intro_video_path),
            start_chapter=(actual_start_chapter),
            end_chapter=(actual_end_chapter),
            force_recreate=True,
            reencode=False,
        )

        # google storage upload
        upload_result = upload_file_to_gcs(
            source_file_path=final_book_video_path,
            content_type=get_content_type(final_book_video_path),
        )

        metadata = get_video_metadata(final_book_video_path, os.getenv("FFPROBE_PATH"))

        print("## metadata.public_url : " + upload_result["public_url"])

        # insert generated_video
        insert_generated_video(
            project_no=project_no,
            execution_id=selected_execution_id,
            video_title="창세기 1장",
            video_url=upload_result["public_url"],
            youtube_uploaded=False,
            duration_seconds=metadata["duration_seconds"],
            file_size_bytes=metadata["file_size_bytes"],
        )

        # =====================================================
        # 12. 성공 상태 변경
        # =====================================================
        updated = update_job_schedule_status(
            execution_id=(selected_execution_id),
            run_status="completed",
            output_video_path=(final_book_video_path),
        )

        # TODO # youtube upload
        # if(youtube_upload_yn == "Y"):

        # 임시 파일들 삭제
        FileUtil.delete_directory_contents("output/temp_ffmpeg")
        FileUtil.delete_directory_contents("data/bible/video")

        if not updated:
            raise RuntimeError(
                "작업 완료 상태를 저장하지 "
                "못했습니다. "
                f"execution_id="
                f"{selected_execution_id}"
            )

    except Exception as exc:
        update_job_schedule_status(
            execution_id=(selected_execution_id),
            run_status="failed",
            error_message=str(exc),
        )

        raise

    print("\n" + "=" * 70)
    print("[FINAL BOOK VIDEO DONE]")
    print(f"[PROJECT NO] {project_no}")
    print(f"[EXECUTION ID] " f"{selected_execution_id}")
    print(f"[OUTPUT] " f"{final_book_video_path}")
    print("=" * 70)

    return {
        "project_no": project_no,
        "execution_id": (selected_execution_id),
        "output_video_path": (final_book_video_path),
    }


if __name__ == "__main__":
    start_bible_job()
