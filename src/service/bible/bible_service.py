import json
import os
from pathlib import Path
import uuid

from src.model.text_style import TextStyle
from src.model.video_basic import VideoBasic
from src.model.video_model import VideoModel
from src.repository.bible.generated_video_repo import insert_generated_video
from src.repository.bible.job_schedule_repo import (
    claim_next_waiting_job,
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
from src.utils.ffmpeg_util import create_thumbnail_from_video
from src.utils.file_util import FileUtil
from src.utils.google_storage_util import (
    get_content_type,
    get_video_metadata,
    upload_file_to_gcs,
)
from src.utils.make_google_tts_chapter_packages import create_book_voice_packages
from src.utils.openai_util import create_youtube_metadata
from src.utils.youtube_util import add_video_to_playlist, upload_video_to_youtube


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

        # if current_status == "completed":
        #     raise RuntimeError(
        #         "이미 완료된 작업입니다. " f"execution_id={execution_id}"
        #     )

    else:
        job_schedule = claim_next_waiting_job(
            project_no=project_no,
            waiting_status="wait",
        )

        if job_schedule is None:
            raise RuntimeError(
                "실행할 대기 작업이 없습니다. " f"project_no={project_no}"
            )

    selected_execution_id = int(job_schedule["execution_id"])

    try:
        bg_image = project_param.get("body_bg_path")
        voice_model = project_param.get("voice")
        lang = project_param.get("lang")

        book_no = int(job_schedule.get("job_param_1"))
        book_code = job_schedule.get("job_param_2")
        start_chapter = int(job_schedule.get("job_param_3"))
        end_chapter = int(job_schedule.get("job_param_4"))
        chapter_count = 1

        book_list_path = Path("data/bible/openbible/book_list.json")
        with open(book_list_path, "r", encoding="utf-8") as f:
            book_list = json.load(f)
        book_info = book_list[book_no - 1]

        # book_title_ko = book_info.get("bookNmKo")
        chapter_count = book_info.get("chapterCount")

        actual_start_chapter = start_chapter if start_chapter is not None else 1
        actual_end_chapter = (
            min(
                end_chapter,
                chapter_count,
            )
            if end_chapter is not None
            else chapter_count
        )

        if not book_code:
            raise RuntimeError(
                "job_schedule의 작업 파라미터가 비어 있습니다. "
                f"project_no={project_no}, "
                f"execution_id={selected_execution_id}"
            )

        # =====================================================
        # 3. 작업 상태를 running으로 변경
        # =====================================================
        # execution_id를 직접 전달한 즉시실행인 경우에만 running으로 변경
        if execution_id is not None:
            updated = update_job_schedule_status(
                execution_id=selected_execution_id,
                run_status="running",
            )

            if not updated:
                raise RuntimeError(
                    "작업 상태를 running으로 변경하지 못했습니다. "
                    f"execution_id={selected_execution_id}"
                )

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

        Path(video_root).mkdir(
            parents=True,
            exist_ok=True,
        )

        audio_root_path = f"data/bible/audio/{lang}"
        book_title = book_info.get("bookNmEn1" if lang == "en-GB" else "bookNmKo")
        chapter_count = int(book_info.get("chapterCount"))

        summary_json_path = (
            f"{audio_root_path}/{book_code}/{book_code}_voice_package_summary.json"
        )

        if not Path(summary_json_path).exists():

            create_book_voice_packages(
                book_code=book_code,
                book_title=book_title,
                chapter_count=chapter_count,
                input_pattern=(
                    f"data/bible/openbible/{lang}/{book_no:02d}.{book_code}/"
                    f"{book_code}-{{chapter:02d}}.txt"
                ),
                model=voice_model,
                lang=lang,
                create_default_path=audio_root_path,
                pause=0.4,
                force_recreate_tts=False,
                speaking_rate=1.0,
                sample_rate_hertz=24000,
                start_chapter=actual_start_chapter,
                end_chapter=actual_end_chapter,
            )

        bg_images = [bg_image]

        # =====================================================
        # 6. 음성 summary JSON 읽기
        # =====================================================
        summary = FileUtil.get_json_data(summary_json_path)

        chapter_count = int(summary.get("chapter_count") or 1)

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
        if lang == "en-GB":
            if actual_start_chapter == actual_end_chapter:
                chapter_txt = f"Chapter {actual_start_chapter}"
            else:
                chapter_txt = (
                    f"Chapters {actual_start_chapter}" f"~{actual_end_chapter}"
                )
        else:
            if actual_start_chapter == actual_end_chapter:
                chapter_txt = f"{actual_start_chapter}장"
            else:
                chapter_txt = f"{actual_start_chapter}장" f"~{actual_end_chapter}장"

        video_title = f"{book_title} {chapter_txt}"

        # =====================================================
        # 8. 인트로 영상 생성
        # =====================================================
        if lang == "en-GB":
            intro_title = "Bible Reading"
        else:
            intro_title = "성경 낭독"

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
                        text=intro_title,
                        alignment=("center", "center"),
                        text_position=("center", -140),
                        font_path="resources/font/HMKMRHD.TTF",
                        font_size=170,
                        text_color=(255, 242, 0, 255),
                        # text_effect=["shadow"],
                    ),
                    TextStyle(
                        text=video_title,
                        alignment=("center", "center"),
                        text_position=("center", 110),
                        font_path="resources/font/H2HDRM.TTF",
                        font_size=170,
                        text_color=(255, 255, 255, 255),
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
            final_output_path = f"{video_root}/{book_code}_full_{uuid.uuid4()}.mp4"

        elif actual_start_chapter == actual_end_chapter:
            final_output_path = (
                f"{video_root}/"
                f"{book_code}_"
                f"{actual_start_chapter:02d}"
                f"_full_{uuid.uuid4()}.mp4"
            )

        else:
            final_output_path = (
                f"{video_root}/"
                f"{book_code}_"
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

        # 썸네일 생성
        thumbnail_path = f"data/bible/temp/{uuid.uuid4()}.jpg"
        create_thumbnail_from_video(final_book_video_path, thumbnail_path, 1)

        print("thumbnail_path : " + thumbnail_path)

        thumbnail_result = upload_file_to_gcs(
            source_file_path=thumbnail_path,
            content_type="image/jpeg",
        )

        # openAI로 제목, 상세내용 요청
        youtube_meta = create_youtube_metadata(
            video_title, ("영어" if lang == "en-GB" else "한국어")
        )

        print(youtube_meta)

        # 유튜브로 업로드
        youtube_result = upload_video_to_youtube(
            video_path=final_book_video_path,
            title=youtube_meta["title"],
            description=youtube_meta["desc"],
            tags=[],
            category_id="22",
            privacy_status="public",
            made_for_kids=False,
            thumbnail_path=thumbnail_path,
        )

        print(youtube_result)

        # insert generated_video
        insert_generated_video(
            project_no=project_no,
            execution_id=selected_execution_id,
            video_title=video_title,
            video_url=upload_result["public_url"],
            thumbnail_url=thumbnail_result["public_url"],
            youtube_uploaded=bool(youtube_result.get("video_id")),
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

        # # # 임시 파일들 삭제
        FileUtil.delete_directory_contents("output/temp_ffmpeg")
        FileUtil.delete_directory_contents("data/bible/video")
        FileUtil.delete_directory_contents("data/bible/temp")

        # if not updated:
        #     raise RuntimeError(
        #         "작업 완료 상태를 저장하지 "
        #         "못했습니다. "
        #         f"execution_id="
        #         f"{selected_execution_id}"
        #     )

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
    start_bible_job(project_no=1, execution_id=17)
