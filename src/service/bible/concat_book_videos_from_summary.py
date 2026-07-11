"""
voice_package_summary.json을 기준으로
챕터별 생성된 mp4 파일들을 하나의 book 최종 mp4로 합친다.

입력 예:
data/bible/audio/genesis/genesis_voice_package_summary.json

챕터별 영상 예:
data/bible/video/genesis_01_final.mp4
data/bible/video/genesis_02_final.mp4
...

최종 출력 예:
data/bible/video/genesis_final.mp4

실행 예:
cd C:\\project\\my-ai-video
.\\.venv\\Scripts\\python.exe -m src.sample.concat_book_videos_from_summary
"""

from pathlib import Path

from src.utils.file_util import FileUtil
from src.utils.ffmpeg_util import get_ffmpeg_path, run_ffmpeg


# ==============================
# 공통 유틸
# ==============================
def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)


def normalize_path(path: str | Path) -> Path:
    return Path(str(path).replace("\\", "/"))


def quote_concat_path(path: str | Path) -> str:
    """
    FFmpeg concat list용 경로 처리.
    Windows에서도 안정적으로 동작하도록 / 로 변환.
    """
    return Path(path).resolve().as_posix().replace("'", r"'\''")


# ==============================
# 챕터별 영상 경로 생성
# ==============================
def build_chapter_video_path(
    video_root: str | Path,
    book_code: str,
    chapter: int
) -> Path:
    chapter_str = f"{chapter:02d}"
    return Path(video_root) / f"{book_code}_{chapter_str}_final.mp4"


# ==============================
# book 최종 영상 경로 생성
# ==============================
def build_book_final_video_path(
    video_root: str | Path,
    book_code: str
) -> Path:
    return Path(video_root) / f"{book_code}_final.mp4"


# ==============================
# concat list 파일 생성
# ==============================
def create_concat_list_file(
    video_files: list[Path],
    list_path: str | Path
) -> Path:
    """
    FFmpeg concat demuxer에서 사용할 txt 파일 생성.

    파일 내용 예:
    file 'C:/project/my-ai-video/data/bible/video/genesis_01_final.mp4'
    file 'C:/project/my-ai-video/data/bible/video/genesis_02_final.mp4'
    """
    list_path = Path(list_path)
    ensure_dir(list_path.parent)

    with open(list_path, "w", encoding="utf-8") as f:
        for video_file in video_files:
            f.write(f"file '{quote_concat_path(video_file)}'\n")

    return list_path


# ==============================
# MP4 concat
# ==============================
def concat_mp4_files_ffmpeg(
    video_files: list[str | Path],
    output_path: str | Path,
    force_recreate: bool = False,
    reencode: bool = False
) -> str:
    """
    여러 mp4 파일을 하나의 mp4로 합친다.

    Args:
        video_files:
            합칠 mp4 파일 목록

        output_path:
            최종 mp4 경로

        force_recreate:
            False이면 기존 output_path가 있을 때 스킵

        reencode:
            False:
                - 빠름
                - 모든 챕터 mp4의 코덱/해상도/fps/오디오 포맷이 같아야 안정적
                - -c copy 사용

            True:
                - 느림
                - 포맷 차이 문제가 있을 때 안정적
                - libx264/aac로 재인코딩
    """
    if not video_files:
        raise ValueError("합칠 mp4 파일이 없습니다.")

    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    if output_path.exists() and not force_recreate:
        print(f"[SKIP BOOK VIDEO] 기존 최종 영상 사용: {output_path}")
        return str(output_path)

    normalized_files = [normalize_path(file) for file in video_files]

    missing_files = [
        str(file)
        for file in normalized_files
        if not file.exists()
    ]

    if missing_files:
        raise FileNotFoundError(
            "존재하지 않는 챕터 영상 파일이 있습니다:\n"
            + "\n".join(missing_files)
        )

    ffmpeg = get_ffmpeg_path()

    list_path = output_path.with_suffix(".concat.txt")
    create_concat_list_file(
        video_files=normalized_files,
        list_path=list_path
    )

    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
    ]

    if reencode:
        cmd += [
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-c:a", "aac",
            "-b:a", "192k",
            "-movflags", "+faststart",
            str(output_path)
        ]
    else:
        cmd += [
            "-c", "copy",
            "-movflags", "+faststart",
            str(output_path)
        ]

    print("\n" + "=" * 70)
    print("[BOOK CONCAT START]")
    print(f"[COUNT] {len(normalized_files)}")
    print(f"[OUTPUT] {output_path}")
    print(f"[REENCODE] {reencode}")
    print("=" * 70)

    run_ffmpeg(cmd)

    print(f"[BOOK CONCAT DONE] {output_path}")

    return str(output_path)


# ==============================
# summary 기준 book 최종 영상 생성
# ==============================
def concat_book_videos_from_voice_summary(
    summary_json_path: str | Path,
    video_root: str | Path = "data/bible/video",
    output_path: str | Path | None = None,
    intro_video_path: str | Path | None = None,
    start_chapter: int | None = None,
    end_chapter: int | None = None,
    force_recreate: bool = False,
    reencode: bool = False
) -> str:
    """
    voice_package_summary.json의 chapters 목록을 기준으로
    챕터별 mp4를 찾아 하나의 book mp4로 합친다.
    """

    summary = FileUtil.get_json_data(summary_json_path)

    book_code = summary["book_code"]
    chapters = summary.get("chapters", [])

    if not chapters:
        raise RuntimeError(f"summary에 chapters가 없습니다: {summary_json_path}")

    video_files = []
    if intro_video_path is not None:
        video_files.append(intro_video_path)
        
    for chapter_item in chapters:
        chapter = int(chapter_item["chapter"])

        if start_chapter is not None and chapter < start_chapter:
            continue

        if end_chapter is not None and chapter > end_chapter:
            continue

        chapter_video_path = build_chapter_video_path(
            video_root=video_root,
            book_code=book_code,
            chapter=chapter
        )

        video_files.append(chapter_video_path)

    if not video_files:
        raise RuntimeError("합칠 챕터 영상이 없습니다.")

    if output_path is None:
        output_path = build_book_final_video_path(
            video_root=video_root,
            book_code=book_code
        )

    return concat_mp4_files_ffmpeg(
        video_files=video_files,
        output_path=output_path,
        force_recreate=force_recreate,
        reencode=reencode
    )


# ==============================
# 실행부
# ==============================
if __name__ == "__main__":

    concat_book_videos_from_voice_summary(
        summary_json_path="data/bible/audio/genesis/genesis_voice_package_summary.json",

        # 챕터별 mp4가 있는 폴더
        video_root="data/bible/video",

        # None이면 data/bible/video/genesis_final.mp4 로 생성
        output_path=None,

        # 일부 장만 합치고 싶으면 사용
        # 예: 1장부터 3장까지만 합치기
        start_chapter=1,
        end_chapter=3,

        # True면 기존 genesis_final.mp4가 있어도 다시 생성
        force_recreate=False,

        # False 추천: 빠름
        # 만약 concat 후 재생 오류가 있으면 True로 변경
        reencode=False
    )