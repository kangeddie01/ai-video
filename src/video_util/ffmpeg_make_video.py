from pathlib import Path
from src.utils.file_util import FileUtil
from src.image_util.make_text_image import make_text_image
from src.model.text_style import TextStyle
from src.model.video_auto_req import VideoAutoRequest
from src.model.video_basic import VideoBasic
from src.model.video_model import VideoModel
from src.utils.ffmpeg_util import get_ffmpeg_path, run_ffmpeg
from src.utils.audio_util import get_audio_duration
from pathlib import Path


def validate_body_video_inputs(
    body_audio_path: str | Path, segments_json_path: str | Path
) -> tuple[Path, Path]:
    """
    body_audio.mp3와 segments.json 파일 존재 여부를 확인한다.
    """
    body_audio_path = Path(body_audio_path)
    segments_json_path = Path(segments_json_path)

    if not body_audio_path.exists():
        raise FileNotFoundError(f"body_audio 파일이 없습니다: {body_audio_path}")

    if not segments_json_path.exists():
        raise FileNotFoundError(f"segments.json 파일이 없습니다: {segments_json_path}")

    return body_audio_path, segments_json_path


def load_segments(segments_json_path: str | Path) -> list[dict]:
    """
    segments.json 파일에서 segments 목록을 읽어온다.
    """
    data = FileUtil.get_json_data(segments_json_path)
    segments = data.get("segments", [])

    if not segments:
        raise ValueError(f"segments 정보가 비어 있습니다: {segments_json_path}")

    return segments


def get_textbox_width(video_model) -> int:
    """
    텍스트 이미지 생성 시 사용할 최대 너비를 계산한다.
    """
    textbox_w = 1920

    if video_model.text_style.text_max_width > 0:
        textbox_w = video_model.textbox_width

    return textbox_w


def create_segment_text_images(
    segments: list[dict], video_basic, video_model
) -> list[str]:
    """
    segments의 text 값을 이용해 절별 텍스트 이미지를 생성한다.

    Returns:
        list[str]: 생성된 텍스트 이미지 파일 경로 목록
    """
    text_image_files = []
    textbox_w = get_textbox_width(video_model)

    for seg in segments:
        verse = seg.get("verse", "")
        text = seg.get("text", "")

        print(video_model.text_style)
        text_result = make_text_image(
            str(verse) + "." + text,
            video_basic,
            video_model.text_style,
            max_width=textbox_w,
        )

        text_image_files.append(text_result["path"])

    return text_image_files


def build_ffmpeg_base_inputs(
    ffmpeg: str, video_model, body_audio_path: Path, content_duration: float
) -> tuple[list[str], int]:
    """
    FFmpeg 기본 입력을 구성한다.

    입력 번호:
    - 0번: 배경 이미지
    - 1번: body_audio.mp3

    Returns:
        tuple[list[str], int]: FFmpeg cmd 리스트, 다음 입력 index
    """
    bg_image = FileUtil.abspath(video_model.bg_images[0])

    cmd = [
        ffmpeg,
        "-y",
        # 0번 입력: 배경 이미지
        "-loop",
        "1",
        "-t",
        str(content_duration),
        "-i",
        bg_image,
        # 1번 입력: body_audio.mp3
        "-i",
        str(body_audio_path),
    ]

    input_index = 2

    return cmd, input_index


def add_overlay_inputs(
    cmd: list[str],
    input_index: int,
    video_basic,
    video_model,
    text_image_files: list[str],
) -> tuple[int | None, int | None, list[int]]:
    """
    FFmpeg 입력에 텍스트박스, 제목, 절별 텍스트 이미지를 추가한다.

    Returns:
        textbox_input_index: 텍스트박스 이미지 입력 번호
        title_input_index: 제목 이미지 입력 번호
        text_input_indexes: 절별 텍스트 이미지 입력 번호 목록
    """
    textbox_input_index = None
    title_input_index = None

    # 텍스트 박스 이미지 입력
    if video_model.textbox_image:
        textbox_input_index = input_index
        cmd.extend(["-i", FileUtil.abspath(video_model.textbox_image)])
        input_index += 1

    # 제목 이미지 입력
    if video_model.title_txt:
        title_result = make_text_image(
            video_model.title_txt,
            video_basic,
            video_model.title_text_style,
            max_width=1920,
        )

        title_input_index = input_index
        cmd.extend(["-i", title_result["path"]])
        input_index += 1

    # 절별 텍스트 이미지 입력
    text_input_indexes = []

    for text_img in text_image_files:
        text_input_indexes.append(input_index)
        cmd.extend(["-i", text_img])
        input_index += 1

    return textbox_input_index, title_input_index, text_input_indexes


def resolve_overlay_position(pos):
    """
    TextStyle의 text_position 값을 FFmpeg overlay 좌표로 변환한다.

    사용 예:
        ("center", "center") -> 화면 정중앙
        ("center", 50)       -> 상단에서 50px, 가로 중앙
        (50, 50)             -> x=50, y=50
    """

    if pos == ("center", "center"):
        return "(W-w)/2", "(H-h)/2"

    if isinstance(pos, tuple):
        x, y = pos

        if x == "center":
            x = "(W-w)/2"

        if y == "center":
            y = "(H-h)/2"

        if x == "left":
            x = "0"

        if x == "right":
            x = "W-w"

        if y == "top":
            y = "0"

        if y == "bottom":
            y = "H-h"

        return str(x), str(y)

    return "(W-w)/2", "(H-h)/2"


def build_filter_complex(
    video_basic,
    video_model,
    segments: list[dict],
    text_input_indexes: list[int],
    textbox_input_index: int | None,
    title_input_index: int | None,
    content_duration: float,
) -> tuple[str, str]:
    """
    FFmpeg filter_complex 문자열을 생성한다.

    Returns:
        filter_complex: FFmpeg filter_complex 값
        final_video_label: 최종 비디오 label
    """
    filter_parts = []

    # 배경 이미지를 영상 크기에 맞춤
    filter_parts.append(
        f"[0:v]scale={video_basic.width}:{video_basic.height},setsar=1[base]"
    )

    current = "base"
    overlay_count = 0

    # 텍스트 박스는 본문 전체 시간 표시
    if textbox_input_index is not None:
        next_label = f"v{overlay_count}"

        filter_parts.append(
            f"[{current}][{textbox_input_index}:v]"
            f"overlay=(W-w)/2:(H-h)/2:enable='between(t,0,{content_duration})'"
            f"[{next_label}]"
        )

        current = next_label
        overlay_count += 1

    # 제목은 본문 전체 시간 표시
    if title_input_index is not None:
        x, y = resolve_overlay_position(video_model.title_text_style.text_position)

        next_label = f"v{overlay_count}"

        filter_parts.append(
            f"[{current}][{title_input_index}:v]"
            f"overlay={x}:{y}:enable='between(t,0,{content_duration})'"
            f"[{next_label}]"
        )

        current = next_label
        overlay_count += 1

    # 절별 텍스트 overlay
    for seg, text_idx in zip(segments, text_input_indexes):
        start = float(seg.get("start", 0))
        end = float(seg.get("end", start))

        # end가 body_audio보다 살짝 길면 잘라줌
        if end > content_duration:
            end = content_duration

        x, y = resolve_overlay_position(video_model.text_style.text_position)

        next_label = f"v{overlay_count}"

        filter_parts.append(
            f"[{current}][{text_idx}:v]"
            f"overlay={x}:{y}:enable='between(t,{start},{end})'"
            f"[{next_label}]"
        )

        current = next_label
        overlay_count += 1

    filter_complex = ";".join(filter_parts)

    return filter_complex, current


def add_output_options(
    cmd: list[str],
    filter_complex: str,
    final_video_label: str,
    content_duration: float,
    video_basic,
    output_path: str,
):
    """
    FFmpeg 출력 옵션을 cmd에 추가한다.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    cmd.extend(
        [
            "-filter_complex",
            filter_complex,
            # 최종 비디오
            "-map",
            f"[{final_video_label}]",
            # body_audio.mp3
            "-map",
            "1:a",
            "-t",
            str(content_duration),
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
            "44100",
            "-ac",
            "2",
            output_path,
        ]
    )


def make_body_video_ffmpeg(
    video_basic,
    video_model,
    body_audio_path: str | Path,
    segments_json_path: str | Path,
    output_path: str,
):
    """
    body_audio.mp3와 segments.json을 이용해서 본문 영상을 생성한다.

    처리 흐름:
    1. 입력 파일 검증
    2. segments.json 읽기
    3. body_audio.mp3 길이 계산
    4. 절별 텍스트 이미지 생성
    5. FFmpeg 입력 구성
    6. overlay filter_complex 생성
    7. 출력 옵션 추가
    8. FFmpeg 실행
    """
    ffmpeg = get_ffmpeg_path()

    body_audio_path, segments_json_path = validate_body_video_inputs(
        body_audio_path=body_audio_path, segments_json_path=segments_json_path
    )

    segments = load_segments(segments_json_path)

    # 영상 길이는 실제 body_audio 길이를 기준으로 잡는 것이 안전함
    content_duration = get_audio_duration(str(body_audio_path))

    text_image_files = create_segment_text_images(
        segments=segments, video_basic=video_basic, video_model=video_model
    )

    cmd, input_index = build_ffmpeg_base_inputs(
        ffmpeg=ffmpeg,
        video_model=video_model,
        body_audio_path=body_audio_path,
        content_duration=content_duration,
    )

    textbox_input_index, title_input_index, text_input_indexes = add_overlay_inputs(
        cmd=cmd,
        input_index=input_index,
        video_basic=video_basic,
        video_model=video_model,
        text_image_files=text_image_files,
    )

    filter_complex, final_video_label = build_filter_complex(
        video_basic=video_basic,
        video_model=video_model,
        segments=segments,
        text_input_indexes=text_input_indexes,
        textbox_input_index=textbox_input_index,
        title_input_index=title_input_index,
        content_duration=content_duration,
    )

    add_output_options(
        cmd=cmd,
        filter_complex=filter_complex,
        final_video_label=final_video_label,
        content_duration=content_duration,
        video_basic=video_basic,
        output_path=output_path,
    )

    run_ffmpeg(cmd)

    return output_path


def concat_videos_ffmpeg(input_files: list[str], output_path: str):
    ffmpeg = get_ffmpeg_path()

    if len(input_files) != 2:
        raise ValueError("현재 함수는 intro + body 2개 파일 기준입니다.")

    intro_path = input_files[0]
    body_path = input_files[1]

    cmd = [
        ffmpeg,
        "-y",
        "-i",
        intro_path,
        "-i",
        body_path,
        "-filter_complex",
        (
            "[0:v]setpts=PTS-STARTPTS,setsar=1[v0];"
            "[1:v]setpts=PTS-STARTPTS,setsar=1[v1];"
            "[0:a]asetpts=PTS-STARTPTS,aresample=44100,"
            "aformat=sample_fmts=fltp:channel_layouts=stereo[a0];"
            "[1:a]asetpts=PTS-STARTPTS,aresample=44100,"
            "aformat=sample_fmts=fltp:channel_layouts=stereo[a1];"
            "[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
        ),
        "-map",
        "[v]",
        "-map",
        "[a]",
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
        "44100",
        "-ac",
        "2",
        output_path,
    ]

    run_ffmpeg(cmd)

    return output_path


if __name__ == "__main__":

    book_en_name = "genesis"
    book_ko_name = "창세기"
    chapter = 1
    chapter_str = f"{chapter:03d}"

    request = VideoAutoRequest(
        video_basic=VideoBasic(
            output_path=f"data/bible/video/{book_en_name}_{chapter_str}_final.mp4",
            width=1920,
            height=1080,
            fps=30,
        ),
        video_intro=VideoModel(
            pause=3,
            bg_type="images",
            bg_images=["data/bible/images/start_img.png"],
            text_style=TextStyle(
                text="",
                alignment=("center", "center"),
                text_position=("center", "center"),
                font_path="resources/font/H2HDRM.TTF",
                font_size=120,
                text_color=(218, 223, 232, 255),
                text_effect=["shadow"],
            ),
            fadeout_duration=1,
        ),
        video_body=VideoModel(
            pause=0.4,
            bg_type="images",
            bg_images=["data/bible/images/bg_bible_9.png"],
            text_style=TextStyle(
                text="",
                alignment=("center", "center"),
                text_position=("center", "center"),
                font_path="resources/font/H2MJRE.TTF",
                font_size=72,
                text_color=(0, 0, 0, 255),
            ),
            title_text_style=TextStyle(
                text="",
                text_position=(50, 50),
                alignment=("left", "top"),
                font_path="resources/font/H2HDRM.TTF",
                font_size=70,
                text_color=(218, 223, 232, 255),
                text_effect=["shadow"],
            ),
            title_txt=f"{book_ko_name} {chapter_str}장",
        ),
    )

    body_audio_path = (
        f"data/bible/audio/{book_en_name}/{chapter_str}/"
        f"{book_en_name}_{chapter_str}_body_audio.mp3"
    )

    segments_json_path = (
        f"data/bible/audio/{book_en_name}/{chapter_str}/"
        f"{book_en_name}_{chapter_str}_segments.json"
    )

    output_path = make_body_video_ffmpeg(
        video_basic=request.video_basic,
        video_model=request.video_body,
        body_audio_path=body_audio_path,
        segments_json_path=segments_json_path,
        output_path=request.video_basic.output_path,
    )

    print("최종 영상 경로:", output_path)
