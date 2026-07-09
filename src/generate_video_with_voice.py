# 각 항목에 담긴 이미지 파일과 오디오 파일을 합성하여 하나의 비디오 파일을 생성

from pathlib import Path
from moviepy import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips
)
from moviepy.audio.fx.AudioFadeIn import AudioFadeIn
from moviepy.audio.fx.AudioFadeOut import AudioFadeOut
from moviepy.video.fx.CrossFadeIn import CrossFadeIn

def generate_video_with_voice(clips, output_path, width=1920, height=1080, fps=30, transition=1.0):
    """
    이미지/오디오 객체 리스트로 비디오를 생성합니다.
    clips: [{"image": "path/to/image.png", "audio": "path/to/audio.mp3"}, ...]
    output_path: 생성할 비디오 파일 경로
    width, height: 출력 해상도
    fps: 프레임 속도
    transition: 장면 전환 페이드 시간(초)
    """
    if not isinstance(clips, list) or len(clips) == 0:
        raise ValueError("clips must be a non-empty list of {'image':..., 'audio':...} dictionaries")

    video_clips = []
    for item in clips:
        if not isinstance(item, dict) or 'image' not in item or 'audio' not in item:
            raise ValueError("Each clip item must be a dict with 'image' and 'audio' keys")

        image_path = item['image']
        audio_path = item['audio']

        audio = AudioFileClip(audio_path)

        clip = (
            ImageClip(image_path)
            .resized((width, height))
            .with_duration(audio.duration + 2)
            .with_audio(audio)
        )
        video_clips.append(clip)

    if len(video_clips) == 0:
        raise ValueError("No valid clips provided")

    if len(video_clips) > 1 and transition > 0:
        for i in range(1, len(video_clips)):
            effect = CrossFadeIn(transition)
            video_clips[i] = video_clips[i].with_effects([effect])

    video = concatenate_videoclips(
        video_clips,
        method="compose",
        padding=-transition if transition > 0 else 0
    )

    output_dir = Path(output_path).resolve().parent
    output_dir.mkdir(parents=True, exist_ok=True)

    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac"
    )