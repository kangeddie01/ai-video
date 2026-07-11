# 영상을 무한반복하는 배경clip 생성
from genericpath import exists
import math
from PIL import Image
from moviepy import CompositeVideoClip, ImageClip, VideoClip, VideoFileClip, concatenate_videoclips
import numpy as np
from moviepy.video.fx import FadeOut
from src.utils.file_util import abspath
from src.image_util.make_text_image import make_text_image

def repeat_background(video_path, duration, width, height):
    video_path = abspath(video_path)
    first_bg = VideoFileClip(video_path).resized((width, height))
    count = math.ceil(duration / first_bg.duration)
    bg_clips = [first_bg] + [VideoFileClip(video_path).resized((width, height)) for _ in range(count - 1)]

    repeated = concatenate_videoclips(bg_clips)
    return repeated.subclipped(0, duration), bg_clips

# n개의 이미지를 s개의 음성클립마다 변경되게하는 배경 클립 생성
def repeat_images_by_audio_clips(
    image_paths: list[str],
    audio_durations: list[float],
    width: int,
    height: int,
    change_every_n_audio: int = 2,
    fps: int = 30
):
    """
    음성 클립 단위로 이미지를 변경하는 배경 VideoClip 생성.

    예:
        change_every_n_audio=2 이면
        음성 1,2번 동안 이미지1
        음성 3,4번 동안 이미지2
        음성 5,6번 동안 이미지3

    Args:
        image_paths: 배경 이미지 경로 리스트
        audio_durations: 각 음성 클립의 길이 리스트. 예: [7.2, 8.5, 6.1]
        width: 출력 영상 너비
        height: 출력 영상 높이
        change_every_n_audio: 음성 몇 개마다 이미지 변경할지
        fps: 출력 FPS

    Returns:
        background_clip: 최종 배경 VideoClip
        close_clips: close용 리스트. 이 방식에서는 빈 리스트 반환
    """

    if not image_paths:
        raise ValueError("image_paths가 비어 있습니다.")

    if not audio_durations:
        raise ValueError("audio_durations가 비어 있습니다.")

    if change_every_n_audio <= 0:
        raise ValueError("change_every_n_audio는 1 이상이어야 합니다.")

    for path in image_paths:
        if not exists(path):
            raise FileNotFoundError(f"이미지 파일을 찾을 수 없습니다: {path}")

    # 전체 영상 길이 = 모든 음성 클립 길이 합
    total_duration = sum(audio_durations)

    if total_duration <= 0:
        raise ValueError("전체 음성 길이가 0보다 커야 합니다.")

    # 이미지를 메모리에 미리 로드
    frames = []

    for path in image_paths:
        img = Image.open(abspath(path)).convert("RGB")
        img = img.resize((width, height))
        frames.append(np.array(img))

    # 각 음성 클립의 시작/끝 시간 계산
    audio_ranges = []
    current_time = 0.0

    for index, audio_duration in enumerate(audio_durations):
        start = current_time
        end = current_time + audio_duration

        image_index = (index // change_every_n_audio) % len(frames)

        audio_ranges.append({
            "start": start,
            "end": end,
            "image_index": image_index
        })

        current_time = end

    def make_frame(t):
        for item in audio_ranges:
            if item["start"] <= t < item["end"]:
                return frames[item["image_index"]]

        # 마지막 프레임 보정
        return frames[audio_ranges[-1]["image_index"]]

    background_clip = (
        VideoClip(frame_function=make_frame, duration=total_duration)
        .with_fps(fps)
    )

    return background_clip, []



def make_intro_clip(video_basic, intro, title_text=None):
    if intro is None:
        return None

    intro_duration = intro.pause

    if intro_duration <= 0:
        return None

    if not intro.bg_images:
        raise ValueError("intro.bg_images가 비어 있습니다.")

    intro_clips = []

    intro_bg = (
        ImageClip(abspath(intro.bg_images[0]))
        .resized((video_basic.width, video_basic.height))
        .with_start(0)
        .with_duration(intro_duration)
    )

    intro_clips.append(intro_bg)

    display_text = title_text or intro.title_txt

    if display_text:
        text_img = make_text_image(
            display_text,
            video_basic,
            intro.text_style,
            max_width=int(video_basic.width * 0.8)
        )

        intro_text_clip = (
            ImageClip(text_img)
            .with_start(0)
            .with_duration(intro_duration)
            .with_position(intro.text_style.text_position)
        )

        intro_clips.append(intro_text_clip)

    intro_clip = (
        CompositeVideoClip(
            intro_clips,
            size=(video_basic.width, video_basic.height)
        )
        .with_start(0)
        .with_duration(intro_duration)
    )

    if getattr(intro, "fadeout_duration", 0) > 0:
        intro_clip = intro_clip.with_effects([
            FadeOut(intro.fadeout_duration)
        ])

    return intro_clip