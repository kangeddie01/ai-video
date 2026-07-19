"""
voice_package_summary 데이터를 기준으로 성경 장별 영상과
segments가 없는 단순 영상을 FFmpeg로 생성한다.
"""

from pathlib import Path
from typing import Any

from src.image_util.make_text_image import make_text_image
from src.model.text_style import TextStyle
from src.model.video_basic import VideoBasic
from src.model.video_model import VideoModel
from src.utils.ffmpeg_util import get_ffmpeg_path, run_ffmpeg
from src.utils.file_util import FileUtil
from src.video_util.ffmpeg_make_video import make_body_video_ffmpeg

DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080
DEFAULT_FPS = 30
DEFAULT_AUDIO_SAMPLE_RATE = 44100
TEXTBOX_MAX_WIDTH = 1600
BODY_FONT_COLOR = (255, 255, 255, 255)
BODY_FONT_PATH = "resources/font/GULIM.TTC"  # c:\WINDOWS\Fonts\H2HDRM.TTF ( 굴림 )
TITLE_FONT_PATH = "resources/font/H2HDRM.TTF"


# =====================================================
# 공통 유틸
# =====================================================
def ensure_dir(path: str | Path) -> Path:
    """디렉토리를 생성하고 Path 객체를 반환한다."""
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def normalize_path(path: str | Path) -> Path:
    """Windows/Unix 구분자와 관계없이 Path 객체로 변환한다."""
    return Path(str(path).replace("\\", "/"))


def to_posix_path(path: str | Path) -> str:
    """응답 및 로그에 사용할 슬래시 경로 문자열로 변환한다."""
    return Path(path).as_posix()


def validate_existing_file(
    path: str | Path,
    description: str,
) -> Path:
    """파일 존재 여부를 검사하고 Path 객체를 반환한다."""
    file_path = normalize_path(path)

    if not file_path.is_file():
        raise FileNotFoundError(f"{description} 파일이 없습니다: {file_path}")

    return file_path


def validate_video_size(
    width: int,
    height: int,
    fps: int,
) -> None:
    if width <= 0:
        raise ValueError("width는 0보다 커야 합니다.")

    if height <= 0:
        raise ValueError("height는 0보다 커야 합니다.")

    if fps <= 0:
        raise ValueError("fps는 0보다 커야 합니다.")


def build_output_video_path(
    output_root: str | Path,
    book_code: str,
    chapter: int,
) -> Path:
    """장별 본문 영상 출력 경로를 생성한다."""
    return Path(output_root) / f"{book_code}_{chapter:02d}_final.mp4"


def build_chapter_result(
    *,
    chapter: int,
    status: str,
    output_path: str | Path,
    body_audio_path: str | Path,
    segments_json_path: str | Path,
) -> dict[str, Any]:
    return {
        "chapter": chapter,
        "status": status,
        "output_path": to_posix_path(output_path),
        "body_audio": to_posix_path(body_audio_path),
        "segments_path": to_posix_path(segments_json_path),
    }


def print_chapter_start(
    *,
    book_code: str,
    chapter: int,
    body_audio_path: Path,
    segments_json_path: Path,
    output_path: Path,
) -> None:
    print("\n" + "=" * 70)
    print(f"[VIDEO START] {book_code} {chapter}장")
    print(f"[BODY AUDIO] {body_audio_path}")
    print(f"[SEGMENTS] {segments_json_path}")
    print(f"[OUTPUT] {output_path}")
    print("=" * 70)


# =====================================================
# 모델 생성
# =====================================================
def create_video_basic(
    output_path: str | Path,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
) -> VideoBasic:
    validate_video_size(width, height, fps)

    return VideoBasic(
        output_path=str(output_path),
        width=width,
        height=height,
        fps=fps,
    )


def create_body_text_style() -> TextStyle:
    return TextStyle(
        text="",
        alignment=("center", "center"),
        text_position=("center", 100),
        font_path=BODY_FONT_PATH,
        font_size=100,
        text_color=BODY_FONT_COLOR,
        text_max_width=1700,
    )


def create_title_text_style() -> TextStyle:
    return TextStyle(
        text="",
        alignment=("center", "top"),
        text_position=(0, 80),
        font_path=TITLE_FONT_PATH,
        font_size=70,
        text_color=(218, 223, 232, 255),
        text_effect=["shadow"],
    )


def create_body_video_model(
    title_txt: str,
    bg_images: list[str],
    textbox_image: str | None = None,
) -> VideoModel:
    """장별 본문 영상용 VideoModel을 생성한다."""
    if not bg_images:
        raise ValueError("bg_images가 비어 있습니다.")

    return VideoModel(
        pause=0.4,
        bg_type="images",
        bg_images=bg_images,
        textbox_image=textbox_image,
        textbox_width=TEXTBOX_MAX_WIDTH,
        title_txt=f"{title_txt}",
        text_style=create_body_text_style(),
        title_text_style=create_title_text_style(),
    )


# =====================================================
# 장별 본문 영상 생성
# =====================================================
def make_chapter_body_video_from_summary_item(
    book_code: str,
    book_title: str,
    bg_images: list[str],
    chapter_item: dict[str, Any],
    output_root: str | Path,
    textbox_image: str | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    force_recreate_video: bool = False,
) -> dict[str, Any]:
    """summary의 chapter 항목 하나를 기준으로 본문 영상을 생성한다."""
    chapter = int(chapter_item["chapter"])
    chapter_txt = chapter_item["chapter_txt"]
    body_audio_path = validate_existing_file(
        chapter_item["body_audio"],
        "body_audio",
    )
    segments_json_path = validate_existing_file(
        chapter_item["segments_path"],
        "segments.json",
    )

    output_path = build_output_video_path(
        output_root=output_root,
        book_code=book_code,
        chapter=chapter,
    )
    ensure_dir(output_path.parent)

    if output_path.is_file() and not force_recreate_video:
        print(f"[SKIP VIDEO] 기존 영상 사용: {output_path}")

        return build_chapter_result(
            chapter=chapter,
            status="skipped",
            output_path=output_path,
            body_audio_path=body_audio_path,
            segments_json_path=segments_json_path,
        )

    print_chapter_start(
        book_code=book_code,
        chapter=chapter,
        body_audio_path=body_audio_path,
        segments_json_path=segments_json_path,
        output_path=output_path,
    )

    video_basic = create_video_basic(
        output_path=output_path,
        width=width,
        height=height,
        fps=fps,
    )
    video_model = create_body_video_model(
        title_txt=f"{book_title} {chapter_txt}",
        bg_images=bg_images,
        textbox_image=textbox_image,
    )

    make_body_video_ffmpeg(
        video_basic=video_basic,
        video_model=video_model,
        body_audio_path=str(body_audio_path),
        segments_json_path=str(segments_json_path),
        output_path=str(output_path),
    )

    print(f"[VIDEO DONE] {output_path}")

    return build_chapter_result(
        chapter=chapter,
        status="created",
        output_path=output_path,
        body_audio_path=body_audio_path,
        segments_json_path=segments_json_path,
    )


def is_chapter_in_range(
    chapter: int,
    start_chapter: int | None,
    end_chapter: int | None,
) -> bool:
    if start_chapter is not None and chapter < start_chapter:
        return False

    if end_chapter is not None and chapter > end_chapter:
        return False

    return True


def validate_summary(
    summary: dict[str, Any],
    bg_images: list[str] | None,
) -> tuple[str, str, list[dict[str, Any]], list[str]]:
    if not isinstance(summary, dict):
        raise TypeError("summary는 dict여야 합니다.")

    book_code = str(summary.get("book_code", "")).strip()
    book_title = str(summary.get("book_title", "")).strip()
    chapters = summary.get("chapters", [])

    if not book_code:
        raise ValueError("summary의 book_code가 비어 있습니다.")

    if not book_title:
        raise ValueError("summary의 book_title이 비어 있습니다.")

    if not isinstance(chapters, list) or not chapters:
        raise RuntimeError("summary의 chapters가 비어 있습니다.")

    if not bg_images:
        raise ValueError(
            "bg_images가 비어 있습니다. " "배경 이미지 경로를 1개 이상 전달하세요."
        )

    return book_code, book_title, chapters, bg_images


def make_book_body_videos_from_voice_summary(
    summary: dict[str, Any],
    output_root: str | Path = "data/bible/video",
    bg_images: list[str] | None = None,
    textbox_image: str | None = None,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: int = DEFAULT_FPS,
    start_chapter: int | None = None,
    end_chapter: int | None = None,
    force_recreate_video: bool = False,
) -> list[dict[str, Any]]:
    """voice summary를 기준으로 선택 범위의 장별 영상을 생성한다."""
    validate_video_size(width, height, fps)

    if (
        start_chapter is not None
        and end_chapter is not None
        and start_chapter > end_chapter
    ):
        raise ValueError("start_chapter가 end_chapter보다 큽니다.")

    (
        book_code,
        book_title,
        chapters,
        validated_bg_images,
    ) = validate_summary(summary, bg_images)

    results: list[dict[str, Any]] = []

    for chapter_item in chapters:
        chapter = int(chapter_item["chapter"])

        if not is_chapter_in_range(
            chapter,
            start_chapter,
            end_chapter,
        ):
            continue

        result = make_chapter_body_video_from_summary_item(
            book_code=book_code,
            book_title=book_title,
            bg_images=validated_bg_images,
            chapter_item=chapter_item,
            output_root=output_root,
            textbox_image=textbox_image,
            width=width,
            height=height,
            fps=fps,
            force_recreate_video=force_recreate_video,
        )
        results.append(result)

    print("\n" + "=" * 70)
    print("[ALL VIDEO DONE]")
    print(f"[BOOK] {book_code}")
    print(f"[COUNT] {len(results)}")
    print("=" * 70)

    return results


# =====================================================
# 단순 영상 생성
# =====================================================
def _resolve_axis_position(
    position: str | int | float,
    *,
    center_expression: str,
    end_expression: str,
    is_vertical: bool,
    center_offset: bool = False,
) -> str:
    if position == "center":
        return center_expression

    if position in {"left", "top"}:
        return "0"

    if position in {"right", "bottom"}:
        return end_expression

    if isinstance(position, (int, float)):
        if is_vertical and center_offset:
            return f"{center_expression}+({position})"

        return str(position)

    return center_expression


def _make_overlay_position(
    text_style: TextStyle,
) -> tuple[str, str]:
    """
    TextStyle.text_position을 FFmpeg overlay 좌표로 변환한다.

    ("center", -100)은 화면 중앙에서 위로 100px 이동한다.
    (100, 200)은 영상 좌측 상단 기준 절대 좌표다.
    """
    position = getattr(text_style, "text_position", None)

    if not isinstance(position, tuple) or len(position) != 2:
        return "(W-w)/2", "(H-h)/2"

    position_x, position_y = position

    overlay_x = _resolve_axis_position(
        position_x,
        center_expression="(W-w)/2",
        end_expression="W-w",
        is_vertical=False,
    )
    overlay_y = _resolve_axis_position(
        position_y,
        center_expression="(H-h)/2",
        end_expression="H-h",
        is_vertical=True,
        center_offset=position_x == "center",
    )

    return overlay_x, overlay_y


def _create_simple_text_items(
    video_basic: VideoBasic,
    video_model: VideoModel,
) -> list[dict[str, Any]]:
    text_items: list[dict[str, Any]] = []

    for text_style in video_model.text_list or []:
        text = text_style.text

        if not text or not text.strip():
            continue

        max_width = (
            text_style.text_max_width
            if getattr(text_style, "text_max_width", None)
            else video_basic.width
        )

        text_result = make_text_image(
            text=text,
            video_basic=video_basic,
            text_style=text_style,
            max_width=max_width,
        )
        text_image_path = validate_existing_file(
            FileUtil.abspath(text_result["path"]),
            "텍스트 이미지",
        )

        text_items.append(
            {
                "path": str(text_image_path),
                "style": text_style,
            }
        )

    return text_items


def _build_simple_video_inputs(
    ffmpeg: str,
    bg_image: str,
    text_items: list[dict[str, Any]],
    duration: float,
) -> tuple[list[str], int]:
    cmd = [
        ffmpeg,
        "-y",
        "-loop",
        "1",
        "-t",
        str(duration),
        "-i",
        bg_image,
    ]

    for text_item in text_items:
        cmd.extend(["-i", text_item["path"]])

    audio_input_index = len(text_items) + 1

    cmd.extend(
        [
            "-f",
            "lavfi",
            "-t",
            str(duration),
            "-i",
            (
                "anullsrc=channel_layout=stereo:"
                f"sample_rate={DEFAULT_AUDIO_SAMPLE_RATE}"
            ),
        ]
    )

    return cmd, audio_input_index


def _build_simple_video_filter(
    video_basic: VideoBasic,
    text_items: list[dict[str, Any]],
    duration: float,
    fadeout_duration: float,
) -> str:
    filter_parts = [
        f"[0:v]scale={video_basic.width}:{video_basic.height}," "setsar=1[base]"
    ]
    previous_label = "base"

    for index, text_item in enumerate(text_items):
        input_index = index + 1
        output_label = f"overlay_{index}"
        overlay_x, overlay_y = _make_overlay_position(text_item["style"])

        filter_parts.append(
            f"[{previous_label}][{input_index}:v]"
            f"overlay=x={overlay_x}:y={overlay_y}"
            f"[{output_label}]"
        )
        previous_label = output_label

    applied_fadeout_duration = min(
        fadeout_duration,
        duration,
    )

    if applied_fadeout_duration > 0:
        fade_start = duration - applied_fadeout_duration
        filter_parts.append(
            f"[{previous_label}]"
            f"fade=t=out:st={fade_start}:"
            f"d={applied_fadeout_duration}[v]"
        )
    else:
        filter_parts.append(f"[{previous_label}]null[v]")

    return ";".join(filter_parts)


def _add_simple_video_output_options(
    cmd: list[str],
    *,
    filter_complex: str,
    audio_input_index: int,
    video_basic: VideoBasic,
    duration: float,
    output_path: str,
) -> None:
    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            "-map",
            "[v]",
            "-map",
            f"{audio_input_index}:a",
            "-t",
            str(duration),
            "-r",
            str(video_basic.fps),
            "-c:v",
            "libx264",
            "-preset",
            "ultrafast",
            "-crf",
            "28",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-ar",
            str(DEFAULT_AUDIO_SAMPLE_RATE),
            "-ac",
            "2",
            "-shortest",
            output_path,
        ]
    )


def make_simple_video_ffmpeg(
    video_basic: VideoBasic,
    video_model: VideoModel,
    duration: float = 3.0,
    fadeout_duration: float = 0,
) -> str:
    """
    배경 이미지 한 장과 여러 텍스트 이미지를 합성해
    무음 오디오가 포함된 MP4 영상을 생성한다.
    """
    if not video_model.bg_images:
        raise ValueError("배경 이미지가 설정되지 않았습니다.")

    if video_model.bg_type != "images":
        raise ValueError(
            "현재 make_simple_video_ffmpeg는 " "bg_type='images'만 지원합니다."
        )

    if duration <= 0:
        raise ValueError("duration은 0보다 커야 합니다.")

    if fadeout_duration < 0:
        raise ValueError("fadeout_duration은 0 이상이어야 합니다.")

    validate_video_size(
        video_basic.width,
        video_basic.height,
        video_basic.fps,
    )

    ffmpeg = get_ffmpeg_path()
    bg_image = str(
        validate_existing_file(
            FileUtil.abspath(video_model.bg_images[0]),
            "배경 이미지",
        )
    )
    output_path = FileUtil.abspath(video_basic.output_path)
    ensure_dir(Path(output_path).parent)

    text_items = _create_simple_text_items(
        video_basic,
        video_model,
    )
    cmd, audio_input_index = _build_simple_video_inputs(
        ffmpeg=ffmpeg,
        bg_image=bg_image,
        text_items=text_items,
        duration=duration,
    )
    filter_complex = _build_simple_video_filter(
        video_basic=video_basic,
        text_items=text_items,
        duration=duration,
        fadeout_duration=fadeout_duration,
    )
    _add_simple_video_output_options(
        cmd,
        filter_complex=filter_complex,
        audio_input_index=audio_input_index,
        video_basic=video_basic,
        duration=duration,
        output_path=output_path,
    )

    run_ffmpeg(cmd)

    return output_path


if __name__ == "__main__":
    # =====================================================
    # 1. 영상 기본 설정
    # =====================================================
    video_basic = VideoBasic(
        output_path="data/bible/video/simple_intro.mp4",
        width=1920,
        height=1080,
        fps=30,
    )

    # =====================================================
    # 2. 첫 번째 텍스트
    # =====================================================
    # c:\WINDOWS\Fonts\HMKMRHD.TTF
    title_text = TextStyle(
        text="성경 낭독",
        font_path="resources/font/HMKMRHD.TTF",
        font_size=170,
        text_color=(255, 242, 0, 255),
        alignment=("center", "center"),
        text_position=("center", -140),
        text_max_width=1600,
        # text_effect=["shadow"],
    )

    # =====================================================
    # 3. 두 번째 텍스트
    # =====================================================
    chapter_text = TextStyle(
        text="창세기 1장",
        font_path="resources/font/H2HDRM.TTF",
        font_size=170,
        text_color=(255, 255, 255, 255),
        alignment=("center", "center"),
        text_position=("center", 110),
        text_max_width=1600,
        text_effect=["shadow"],
    )

    # =====================================================
    # 4. 영상 모델
    # =====================================================
    video_model = VideoModel(
        text_list=[
            title_text,
            chapter_text,
        ],
        bg_type="images",
        bg_images=[
            "data/bible/images/bg_bible_01.png",
        ],
        textbox_image=None,
        textbox_width=1600,
        title_txt=None,
        text_style=None,
        title_text_style=None,
        pause=0.4,
        fadeout_duration=0,
    )

    # =====================================================
    # 5. 단순 영상 생성
    # =====================================================
    output_path = make_simple_video_ffmpeg(
        video_basic=video_basic,
        video_model=video_model,
        duration=5.0,
        fadeout_duration=1.0,
    )

    print("\n영상 생성 완료")
    print(f"출력 경로: {output_path}")
