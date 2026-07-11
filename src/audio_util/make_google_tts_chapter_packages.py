"""
Google TTS로 성경 각 장별 음성 패키지를 생성합니다.

생성 결과:
- 절별 원본 mp3
- pause용 무음 mp3
- 장별 통합 음성 body_audio.mp3
- 장별 segments.json

실행 예:
cd C:\\project\\my-ai-video
.\\.venv\\Scripts\\python.exe -m src.audio_util.make_google_tts_chapter_packages
"""

import time
import os
import re
import json
import uuid
from pathlib import Path
from typing import Optional

from google.cloud import texttospeech

from src.utils.ffmpeg_util import get_ffmpeg_path, run_ffmpeg
from src.utils.audio_util import get_audio_duration


# ============================================================
# Google 인증 설정
# ============================================================

def configure_google_credentials() -> str:
    credential_path = (
        os.getenv("GOOGLE_KEY_FILE_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )

    if not credential_path:
        project_root = Path(__file__).resolve().parents[2]
        fallback_path = project_root / "data" / "google_key.json"

        if fallback_path.exists():
            credential_path = str(fallback_path)

    if credential_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path
        return credential_path

    raise RuntimeError(
        "Google credentials not found. "
        "Set GOOGLE_KEY_FILE_PATH or GOOGLE_APPLICATION_CREDENTIALS "
        "or place service-account json at data/google_key.json."
    )


configure_google_credentials()


# ============================================================
# 공통 유틸
# ============================================================

def parse_verse_line(line: str):
    """
    예:
    1 태초에 말씀이 계시니라...
    -> verse_no = 1
    -> text = 태초에 말씀이 계시니라...
    """
    line = line.strip()

    if not line:
        return None, None

    match = re.match(r"^(\d+)\s+(.*)$", line)

    if not match:
        return None, line

    verse_no = int(match.group(1))
    verse_text = match.group(2).strip()

    return verse_no, verse_text


def quote_concat_path(path: str) -> str:
    """
    FFmpeg concat list용 경로 처리.
    Windows에서도 안정적으로 동작하도록 / 로 변환.
    """
    return Path(path).resolve().as_posix().replace("'", r"'\''")


def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)


# ============================================================
# Google TTS
# ============================================================
def make_voice_google_with_retry(
    text: str,
    model_name: str,
    output_path: str | Path,
    speaking_rate: float = 0.9,
    sample_rate_hertz: int = 24000,
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> str:
    """
    Google TTS mp3 생성을 재시도한다.

    Args:
        text (str): 음성으로 변환할 텍스트
        model_name (str): Google TTS voice name
        output_path (str | Path): mp3 저장 경로
        speaking_rate (float): 말하기 속도
        sample_rate_hertz (int): 샘플레이트
        max_retries (int): 최대 재시도 횟수
        retry_delay (float): 재시도 전 대기 시간

    Returns:
        str: 생성된 mp3 파일 경로

    Raises:
        RuntimeError: 모든 재시도 실패 시 발생
    """
    output_path = Path(output_path)

    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[TTS TRY] {attempt}/{max_retries}: {output_path}")

            result_path = make_voice_google(
                text=text,
                model_name=model_name,
                output_path=output_path,
                speaking_rate=speaking_rate,
                sample_rate_hertz=sample_rate_hertz
            )

            # 파일이 실제로 생성되었는지 확인
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise RuntimeError(f"TTS 파일 생성 실패 또는 빈 파일: {output_path}")

            return result_path

        except Exception as e:
            last_error = e
            print(f"[TTS ERROR] {attempt}/{max_retries}: {output_path}")
            print(f"  error: {e}")

            # 실패한 빈 파일이 있으면 삭제
            if output_path.exists() and output_path.stat().st_size == 0:
                output_path.unlink()

            if attempt < max_retries:
                sleep_sec = retry_delay * attempt
                print(f"[TTS RETRY WAIT] {sleep_sec}초 대기 후 재시도")
                time.sleep(sleep_sec)

    raise RuntimeError(
        f"Google TTS 생성 최종 실패: {output_path}, error={last_error}"
    )

def make_voice_google(
    text: str,
    model_name: Optional[str] = None,
    output_path: Optional[str | Path] = None,
    speaking_rate: float = 0.9,
    sample_rate_hertz: int = 24000
) -> str:
    """
    Google TTS로 mp3 생성 후 파일 경로 반환.
    """
    client = texttospeech.TextToSpeechClient()

    synthesis_input = texttospeech.SynthesisInput(text=text)

    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR",
        name=model_name if model_name else None
    )

    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
        sample_rate_hertz=sample_rate_hertz
    )

    response = client.synthesize_speech(
        input=synthesis_input,
        voice=voice,
        audio_config=audio_config
    )

    if output_path is None:
        output_path = Path("output/audio/bible") / f"{uuid.uuid4().hex}.mp3"
    else:
        output_path = Path(output_path)

    ensure_dir(output_path.parent)

    with open(output_path, "wb") as out:
        out.write(response.audio_content)

    print(f"[TTS] 생성: {output_path}")

    return str(output_path)


def make_silent_mp3(
    output_path: str | Path,
    duration: float,
    force_recreate: bool = False
):
    """
    duration 초짜리 무음 mp3 파일을 생성한다.

    이미 파일이 존재하면 기본적으로 재생성하지 않는다.

    Args:
        output_path (str | Path): 생성할 무음 mp3 경로
        duration (float): 무음 길이
        force_recreate (bool): True이면 기존 파일이 있어도 다시 생성
    """
    output_path = Path(output_path)

    # 기존 파일이 있고, 파일 크기가 0보다 크면 재사용
    if output_path.exists() and output_path.stat().st_size > 0 and not force_recreate:
        print(f"[SKIP SILENCE] 기존 무음 mp3 사용: {output_path}")
        return str(output_path)

    ffmpeg = get_ffmpeg_path()

    ensure_dir(output_path.parent)

    cmd = [
        ffmpeg,
        "-y",
        "-f", "lavfi",
        "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
        "-t", str(duration),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        str(output_path)
    ]

    run_ffmpeg(cmd)

    print(f"[SILENCE 생성] {output_path}")

    return str(output_path)

def build_audio_list_with_pause(
    source_audio_files: list[str],
    silence_path: str,
    add_last_pause: bool = True
) -> list[str]:
    """
    절별 mp3 사이에 무음 mp3를 끼워 넣은 concat 목록을 만든다.

    Args:
        source_audio_files (list[str]): 절별 mp3 파일 목록
        silence_path (str): 무음 mp3 파일 경로
        add_last_pause (bool): 마지막 절 뒤에도 pause를 붙일지 여부

    Returns:
        list[str]: concat 대상 오디오 파일 목록
    """
    result = []

    for index, audio_file in enumerate(source_audio_files):
        result.append(audio_file)

        if add_last_pause:
            result.append(silence_path)
        else:
            if index < len(source_audio_files) - 1:
                result.append(silence_path)

    return result


def concat_mp3_files(
    audio_files: list[str],
    output_path: str | Path
):
    """
    여러 mp3 파일을 하나의 mp3 파일로 합친다.

    mp3 파일들의 포맷 차이로 인한 문제를 줄이기 위해 재인코딩한다.
    """
    if not audio_files:
        raise ValueError("합칠 mp3 파일이 없습니다.")

    ffmpeg = get_ffmpeg_path()

    output_path = Path(output_path)
    ensure_dir(output_path.parent)

    list_path = output_path.with_suffix(".txt")

    with open(list_path, "w", encoding="utf-8") as f:
        for file in audio_files:
            f.write(f"file '{quote_concat_path(file)}'\n")

    cmd = [
        ffmpeg,
        "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_path),
        "-vn",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "44100",
        "-ac", "2",
        str(output_path)
    ]

    run_ffmpeg(cmd)

    return str(output_path)

def create_chapter_voice_package(
    input_text_path: str | Path,
    create_default_path: Path,
    book_code: str,
    chapter: int,
    model: str,
    pause: float = 0.4,
    force_recreate_tts: bool = False,
    speaking_rate: float = 0.9,
    sample_rate_hertz: int = 24000
):
    """
    한 장에 대한 음성 패키지를 생성한다.

    처리 흐름:
    - 절별 mp3 생성
    - 공백 mp3 생성
    - 절별 mp3 + 공백 mp3 방식으로 장별 body_audio.mp3 생성
    - segments.json 생성

    입력:
        data/openbible/{book_no}.{book_code}/{book_code}-{chapter}.txt

    출력:
        output/bible/audio/{book_code}/{chapter_str}/{book_code}_{chapter_str}_{verse_str}_{model}.mp3
        output/bible/audio/{book_code}/{chapter_str}/silence_{pause}.mp3
        output/bible/audio/{book_code}/{chapter_str}/{book_code}_{chapter_str}_body_audio.mp3
        output/bible/audio/{book_code}/{chapter_str}/{book_code}_{chapter_str}_segments.json
    """
    chapter_str = f"{chapter:03d}"
    model = model.strip()
    google_voice_name = f"ko-KR-Chirp3-HD-{model}"

    input_text_path = Path(input_text_path)

    if not input_text_path.exists():
        raise FileNotFoundError(f"입력 텍스트 파일이 없습니다: {input_text_path}")

    chapter_dir = create_default_path / book_code / chapter_str

    ensure_dir(chapter_dir)

    segments = []
    source_audio_files = []
    timeline = 0.0

    print("\n" + "=" * 70)
    print(f"[CHAPTER START] {book_code} {chapter}장")
    print(f"[INPUT] {input_text_path}")
    print(f"[VOICE] {google_voice_name}")
    print("=" * 70)

    with open(input_text_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    for line_index, line in enumerate(lines, start=1):
        verse_no, verse_text = parse_verse_line(line)

        if not verse_text:
            continue

        if verse_no is None:
            verse_no = line_index

        verse_str = f"{verse_no:03d}"

        source_audio_path = (
            chapter_dir / f"{book_code}_{chapter_str}_{verse_str}_{model}.mp3"
        )

        audio_url = (
            f"http://localhost:8000/files/audio/bible/"
            f"{book_code}/{chapter_str}/{source_audio_path.name}"
        )

        if source_audio_path.exists() and not force_recreate_tts:
            print(f"[SKIP TTS] 기존 mp3 사용: {source_audio_path}")
        else:

            time.sleep(0.5)  # API 호출 DELAY

            make_voice_google_with_retry(
                text=verse_text,
                model_name=google_voice_name,
                output_path=source_audio_path,
                speaking_rate=speaking_rate,
                sample_rate_hertz=sample_rate_hertz,
                max_retries=3,
                retry_delay=2.0
            )

        voice_duration = get_audio_duration(str(source_audio_path))

        start = timeline
        end = start + voice_duration + pause

        segment = {
            "chapter": chapter,
            "verse": verse_no,
            "text": verse_text,
            "source_audio": str(source_audio_path).replace("\\", "/"),
            "audio_url": audio_url,
            "start": round(start, 3),
            "end": round(end, 3),
            "voice_duration": round(voice_duration, 3),
            "duration": round(voice_duration + pause, 3),
            "pause": pause
        }

        segments.append(segment)
        source_audio_files.append(str(source_audio_path))

        print(
            f"[SEGMENT] {chapter}:{verse_no} "
            f"start={start:.3f}, "
            f"end={end:.3f}, "
            f"voice_duration={voice_duration:.3f}, "
            f"pause={pause:.3f}"
        )

        timeline = end

    if not segments:
        raise RuntimeError(f"생성된 segment가 없습니다: {input_text_path}")

    body_audio_path = chapter_dir / f"{book_code}_{chapter_str}_body_audio.mp3"

    if pause > 0:
        silence_name = f"silence_{str(pause).replace('.', '_')}.mp3"
        silence_path = create_default_path / silence_name

        make_silent_mp3(
            output_path=silence_path,
            duration=pause
        )

        concat_files = build_audio_list_with_pause(
            source_audio_files=source_audio_files,
            silence_path=str(silence_path),
            add_last_pause=True
        )
    else:
        silence_path = None
        concat_files = source_audio_files

    concat_mp3_files(
        audio_files=concat_files,
        output_path=body_audio_path
    )

    body_audio_duration = get_audio_duration(str(body_audio_path))

    segments_path = chapter_dir / f"{book_code}_{chapter_str}_segments.json"

    result = {
        "book_code": book_code,
        "chapter": chapter,
        "chapter_str": chapter_str,
        "model": model,
        "voice_name": google_voice_name,
        "pause": pause,
        "input_text_path": str(input_text_path).replace("\\", "/"),
        "body_audio": str(body_audio_path).replace("\\", "/"),
        "body_audio_duration": round(body_audio_duration, 3),
        "timeline_duration": round(timeline, 3),
        "silence_audio": (
            str(silence_path).replace("\\", "/")
            if silence_path is not None
            else None
        ),
        "segment_count": len(segments),
        "segments": segments
    }

    with open(segments_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"[CHAPTER DONE] {book_code} {chapter}장")
    print(f"[BODY AUDIO] {body_audio_path}")
    print(f"[SEGMENTS] {segments_path}")
    print(f"[DURATION] {body_audio_duration:.3f} sec")

    return {
        "chapter": chapter,
        "body_audio": str(body_audio_path),
        "segments_path": str(segments_path),
        "body_audio_duration": body_audio_duration,
        "segment_count": len(segments)
    }




# 구글tts에서 음성 생성 하는 시작 함수
def create_book_voice_packages(
    book_code: str,
    book_title: str,
    chapter_count: int,
    input_pattern: str,
    model: str,
    pause: float = 0.4,
    force_recreate_tts: bool = False,
    speaking_rate: float = 0.9,
    sample_rate_hertz: int = 24000,
    start_chapter:int = 1
):
    summary = []

    for chapter in range(start_chapter, chapter_count + 1):
        
        file_path = input_pattern.format(chapter=chapter)

        result = create_chapter_voice_package(
            input_text_path=file_path,
            create_default_path = Path("data/bible/audio"),
            book_code=book_code,
            chapter=chapter,
            model=model,
            pause=pause,
            force_recreate_tts=force_recreate_tts,
            speaking_rate=speaking_rate,
            sample_rate_hertz=sample_rate_hertz
        )

        summary.append(result)

    summary_path = Path("data/bible/audio") / book_code / f"{book_code}_voice_package_summary.json"
    ensure_dir(summary_path.parent)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "book_code": book_code,
                "book_title": book_title,
                "chapter_count": chapter_count,
                "model": model,
                "pause": pause,
                "chapters": summary
            },
            f,
            ensure_ascii=False,
            indent=2
        )

    print("\n" + "=" * 70)
    print("[BOOK DONE]")
    print(f"[SUMMARY] {summary_path}")
    print("=" * 70)

    return summary


# ============================================================
# 실행부
# ============================================================

if __name__ == "__main__":


    path = Path("data/bible/book_list.json")
    with open(path, "r", encoding="utf-8") as f:
        book_list = json.load(f)

    target_book_no = 1

    for index, book_info in enumerate(book_list, start=1):

        book_no = int(book_info.get("bookNo"))
        book_name_en = book_info.get("bookNmEn")
        book_name_ko = book_info.get("bookNmko")
        chapter_count = int(book_info.get("chapterCount"))

        if book_no != target_book_no:
            continue

        create_book_voice_packages(
            book_code=book_name_en,
            book_title=book_name_ko,
            chapter_count=chapter_count,
            input_pattern = (
                f"data/bible/openbible/{book_no:02d}.{book_name_en}/"
                f"{book_name_en}-{{chapter:03d}}.txt"
            ),
            model="sadachbia",
            pause=0.4,

            # True면 기존 mp3가 있어도 Google TTS 다시 호출
            # False면 기존 mp3 재사용
            force_recreate_tts=False,

            speaking_rate=0.9,
            sample_rate_hertz=24000
        )