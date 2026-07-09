from pathlib import Path
import subprocess
import tempfile
import shutil


def concat_videos_ffmpeg(
    input_files,
    output_path,
    ffmpeg_path=r"C:\\ffmpeg-8.1.2\\bin\\ffmpeg.exe"
):
    if len(input_files) == 0:
        raise ValueError("input_files가 비어 있습니다.")

    ffmpeg_path = str(ffmpeg_path)

    if ffmpeg_path.lower() == "ffmpeg":
        if shutil.which("ffmpeg") is None:
            raise FileNotFoundError(
                "ffmpeg를 찾을 수 없습니다. PATH에 ffmpeg를 등록하거나 "
                "ffmpeg_path에 전체 경로를 넣어주세요."
            )
    else:
        if not Path(ffmpeg_path).exists():
            raise FileNotFoundError(ffmpeg_path)

    input_files = [Path(f).resolve() for f in input_files]
    output_file = Path(output_path).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)

    for file in input_files:
        if not file.exists():
            raise FileNotFoundError(file)

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".txt",
        delete=False,
        encoding="utf-8"
    )

    concat_path = Path(temp_file.name)

    try:
        for file in input_files:
            temp_file.write(f"file '{file.as_posix()}'\n")

        temp_file.close()

        cmd = [
            ffmpeg_path,
            "-hide_banner",
            "-y",

            "-fflags", "+genpts",

            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_path),

            # -c copy 금지: 재인코딩
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",

            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            "-ac", "2",

            str(output_file)
        ]

        print("FFmpeg command:")
        print(" ".join(cmd))

        subprocess.run(cmd, check=True)

        return output_file

    finally:
        if concat_path.exists():
            concat_path.unlink()