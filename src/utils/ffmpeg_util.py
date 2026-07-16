from pathlib import Path
import subprocess
import shutil

import imageio_ffmpeg


def get_ffmpeg_path() -> str:
    """
    1. 시스템 PATH에 설치된 ffmpeg 우선 사용
    2. 없으면 imageio_ffmpeg에 포함된 ffmpeg 사용
    """
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg

    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass

    raise RuntimeError(
        "ffmpeg를 찾을 수 없습니다. ffmpeg를 설치하거나 imageio-ffmpeg를 설치하세요."
    )


import subprocess


def run_ffmpeg(cmd: list):
    """
    FFmpeg 명령어 실행.
    cmd 안에 Path 객체가 섞여 있어도 str로 변환해서 처리한다.
    """

    # WindowsPath, Path 객체가 들어오는 문제 방지
    cmd = [str(item) for item in cmd]

    print("\n[FFmpeg 실행]")
    print(" ".join(cmd))

    subprocess.run(cmd, check=True)


# 영상에서 썸네일 생성
def create_thumbnail_from_video(
    video_path: str | Path,
    output_path: str | Path,
    capture_time: float = 1.0,
) -> str:
    """
    FFmpeg를 사용하여 영상의 특정 시점 프레임을 썸네일 이미지로 저장한다.

    Args:
        video_path:
            원본 영상 파일 경로

        output_path:
            생성할 썸네일 경로
            예: data/bible/video/genesis_thumbnail.jpg

        capture_time:
            캡처할 영상 시점(초)
            기본값은 1초

    Returns:
        생성된 썸네일 파일 경로
    """
    video_path = Path(video_path)
    output_path = Path(output_path)

    if not video_path.exists():
        raise FileNotFoundError(f"영상 파일이 없습니다: {video_path}")

    if capture_time < 0:
        raise ValueError("capture_time은 0 이상이어야 합니다.")

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

    command = [
        ffmpeg_path,
        "-y",
        "-ss",
        str(capture_time),
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output_path),
    ]

    print("\n[썸네일 생성]")
    print(" ".join(command))

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    if result.returncode != 0:
        raise RuntimeError("썸네일 생성에 실패했습니다.\n" f"{result.stderr}")

    if not output_path.exists():
        raise RuntimeError(f"썸네일 파일이 생성되지 않았습니다: " f"{output_path}")

    print(f"[썸네일 생성 완료] {output_path}")

    return str(output_path)
