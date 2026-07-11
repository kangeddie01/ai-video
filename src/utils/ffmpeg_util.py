from pathlib import Path
import subprocess
import shutil


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