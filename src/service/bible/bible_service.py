
from pathlib import Path
from src.service.bible.make_videos_from_voice_summary import make_book_body_videos_from_voice_summary, make_simple_video
from src.service.bible.openbible_api import change_json_to_txt
from src.image_util.make_text_image import make_text_image
from src.repository.bible.job_schedule_repo import select_job_schedule, update_job_schedule_status
from src.repository.bible.video_project_repo import select_project
from src.service.bible.concat_book_videos_from_summary import concat_book_videos_from_voice_summary
from src.utils.ffmpeg_util import get_ffmpeg_path, run_ffmpeg
from src.utils.file_util import FileUtil
from src.video_util.ffmpeg_make_video import make_body_video_ffmpeg


"""
    성경책 영상 생성 서비스

    로컬실행: 
        .\\.venv\\Scripts\\python.exe -m src.service.bible_service

"""               
def start_bible_job(project_no:int = 1):



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
    
    try:

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


if __name__ == "__main__":
    start_bible_job()