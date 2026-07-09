import argparse
from pathlib import Path
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.video.compositing.CompositeVideoClip import concatenate_videoclips


def append_videos(input_files, output_file, fps=30, codec="libx264", audio_codec="aac"):
    """Append multiple MP4 files into one output video.

    기능:
    - 여러 MP4 파일을 순서대로 이어붙여 하나의 출력 파일로 만듭니다.
    - 출력 동영상에 오디오를 함께 유지합니다.

    사용 라이브러리:
    - moviepy.video.io.VideoFileClip.VideoFileClip
    - moviepy.video.compositing.CompositeVideoClip.concatenate_videoclips
    - pathlib.Path
    - argparse (스크립트 실행용)
    """
    clips = []
    for file_path in input_files:
        clip = VideoFileClip(str(file_path))
        clips.append(clip)

    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip.write_videofile(str(output_file), fps=fps, codec=codec, audio_codec=audio_codec)

    final_clip.close()
    for clip in clips:
        clip.close()


if __name__ == "__main__":
    # 고정된 MP4 파일 목록을 배열로 전달하여 이어붙입니다.
    input_paths = [
        Path("resources/videos/bible/yohan1_final6.mp4"),
        Path("resources/videos/bible/yohan1_final8.mp4"),
    ]
    output_path = Path("resources/videos/bible/yohan1_final_combined.mp4")

    append_videos(input_paths, output_path, fps=30)
