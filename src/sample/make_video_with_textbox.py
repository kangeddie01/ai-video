# make_video_with_textbox.py
from src.file_util.file_util import abspath
from moviepy.video.fx import FadeOut
from genericpath import exists

from pathlib import Path
import numpy as np
from moviepy import (
    AudioClip,
    CompositeAudioClip,
    AudioFileClip,
    ImageClip,
    CompositeVideoClip,
    concatenate_videoclips
)

from src.image_util.make_text_image import make_text_image
from src.model.text_style import TextStyle
from src.model.video_auto_req import VideoAutoRequest
from src.model.video_basic import VideoBasic
from src.service.clip_service import make_intro_clip, repeat_background, repeat_images_by_audio_clips
from src.video_util.ffmpeg_concat_video import concat_videos_ffmpeg


# Run this module from the project root with:
# python -m src.sample.make_video_with_textbox
from ..model.video_model import VideoModel


def format_two_digit_index(index: int) -> str:
    """10 이하일 때 앞에 0을 붙여 두 자리 문자열을 반환합니다."""
    return f"{index:02d}"


def make_video(video_basic, video_model, intro_clip, items = None):


    if items is None:
        items = []
    audio_clips = []
    source_audio_clips = []
    overlay_clips = []
    intro_duration = intro_clip.duration if intro_clip and intro_clip.duration else 0;
    timeline = intro_duration
    content_duration = 0
    textbox_w = 1920
    textbox_base = None
    silent_audio = None
    final_audio = None
    if video_model.textbox_image and video_model.textbox_width:
        textbox_base = ImageClip(abspath(video_model.textbox_image)).resized(width=video_model.textbox_width)
        textbox_w = textbox_base.size[0]

    print("textbox_w : " + str(textbox_w));

    audio_durations = []

    for item in items:
        voice = None
        duration = video_model.pause

        if item.get("voice"):
            voice = AudioFileClip(abspath(item["voice"]))
            source_audio_clips.append(voice)
            duration = voice.duration + video_model.pause

        audio_durations.append(duration)



        if video_model.textbox_image:
            textbox_clip = (
                ImageClip(abspath(video_model.textbox_image))
                .resized(width=video_model.textbox_width)
                .with_start(timeline)
                .with_duration(duration)
                .with_position(("center","center"))
            )
            overlay_clips.append(textbox_clip)

        text_img = make_text_image(
            item["text"],
            video_basic,
            video_model.text_style,
            max_width=textbox_w
        )

        text_clip = (
            ImageClip(text_img)
            .with_start(timeline)
            .with_duration(duration)
            .with_position(video_model.text_style.text_position)
        )

   
        overlay_clips.append(text_clip)

        # title 이 있는 경우에만 title_clip을 생성하고 overlay_clips에 추가
        if video_model.title_txt:
            title_img = make_text_image(
                video_model.title_txt,
                video_basic,
                video_model.title_text_style,
                max_width=1920
            )

            print("text_position")
            print(video_model.title_text_style.text_position)

            title_clip = (
                ImageClip(title_img)
                .with_start(timeline)
                .with_duration(duration)
                .with_position(video_model.title_text_style.text_position)
            )
            overlay_clips.append(title_clip)


        if voice is not None:
            audio_clips.append(
                voice.with_start(timeline)
            )

        timeline += duration
        content_duration += duration
    
    background = None
    background_clips = []

    print("timeline : " + str(timeline))
    print(video_model.bg_images)

    if video_model.bg_type == 'video' :
        background, background_clips = repeat_background(
            video_model.bg_video,
            content_duration,
            video_basic.width,
            video_basic.height
        )
    elif video_model.bg_type == 'images':
        background, background_clips = repeat_images_by_audio_clips(
            video_model.bg_images, audio_durations, video_basic.width, video_basic.height, 2, video_basic.fps
        )
    else:
        raise ValueError(f"지원하지 않는 bg_type입니다: {video_model.bg_type}")
    
    background = background.with_start(intro_duration)


    composite_clips = []

    if intro_clip is not None:
        composite_clips.append(intro_clip)

    composite_clips.append(background)
    composite_clips.extend(overlay_clips)


    final = (
        CompositeVideoClip(
            composite_clips,
            size=(video_basic.width, video_basic.height)
        ).with_duration(timeline)
    )

    if audio_clips:
        final_audio = CompositeAudioClip(audio_clips).with_duration(timeline)
        final = final.with_audio(final_audio)
    else:
        silent_audio = AudioClip(
            frame_function=lambda t: np.zeros((2,)),
            duration=timeline,
            fps=44100
        )
        final = final.with_audio(silent_audio)

    if getattr(video_model, "fadeout_duration", 0) > 0:
        final = final.with_effects([
            FadeOut(video_model.fadeout_duration)
        ])

    # temp_dir = Path("output/temp")
    # temp_dir.mkdir(parents=True, exist_ok=True)
    # output_path = str(temp_dir / f"{uuid.uuid4()}.mp4")

    output_path = video_basic.output_path
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        final.write_videofile(
            output_path,
            fps=video_basic.fps,
            codec="libx264",
            preset="ultrafast",
            threads=4,
            # audio=False
            audio_codec="aac"
        )
    finally:
        try:
            final.close()
        except Exception:
            pass
        try:
            background.close()
        except Exception:
            pass
        for clip in background_clips:
            try:
                clip.close()
            except Exception:
                pass
        if textbox_base is not None:
            try:
                textbox_base.close()
            except Exception:
                pass
        if silent_audio is not None:
            try:
                silent_audio.close()
            except Exception:
                pass            
        for clip in audio_clips + source_audio_clips:
            try:
                clip.close()
            except Exception:
                pass
        if final_audio is not None:
            try:
                final_audio.close()
            except Exception:
                pass            
        if intro_clip is not None:
            try:
                intro_clip.close()
            except Exception:
                pass
        for clip in overlay_clips:
            try:
                clip.close()
            except Exception:
                pass            
    return output_path

if __name__ == "__main__":
  
    book = "요한복음"
    chapter = 1

    request = VideoAutoRequest(

        video_basic=VideoBasic(
            output_path="output/yohan1_final_7.mp4",
            width=1920,
            height=1080,
            fps=24
        ),
        video_intro=VideoModel(
            pause=3,
            bg_type="images",
            bg_images=[
                "resources/images/bible/start_img.png"
            ],

            text_style=TextStyle(
                alignment=("center", "center"),
                text_position= ("center", "center"),
                font_path="c:\\WINDOWS\\Fonts\\H2HDRM.TTF",
                font_size=120,
                text_color=(218, 223, 232, 255),
                text_effect=["shadow"]
            ),

            fadeout_duration=1
        ),

        video_body=VideoModel(
            pause=0.4,
            bg_type="images",
            bg_images=[
                "resources/images/bg_bible_9.png"
            ],
            # title_position=("center", "center"),
            text_style=TextStyle(
                alignment=("center", "center"),              
                text_position=("center", "center"),                
                font_path="c:\\WINDOWS\\Fonts\\H2MJRE.TTF",
                font_size=72,
                text_color=(0, 0, 0, 255)
            ),
            title_text_style=TextStyle(
                text_position=(50, 50), # 텍스트 박스(clip)의 위치
                alignment=("left", "top"), # clip에서의 정렬
                font_path="c:\\WINDOWS\\Fonts\\H2HDRM.TTF",
                font_size=70,
                text_color=(218, 223, 232, 255),
                text_effect=["shadow"]                
            ),

            title_txt="요한복음 1장",

        )
    )

    items = []  

    with open("data/bible_yohan1", "r", encoding="utf-8") as f:
        lines = f.readlines()

    # max_files = 5  # 최대 생성할 파일 수
    

    # 시작영상 제작
    # intro_video_path = make_video(request.video_basic, request.video_intro, [{"text" : "신약성경 낭독 \n\n 요한복음 1장"}]);

    intro_clip = make_intro_clip(request.video_basic, request.video_intro, "신약성경 낭독 \n\n 요한복음 1장")

    #n개의 절을 한번에 영상 생성
    for index, text in enumerate(lines, start=1):
        # if index < 2:
        item = {"text": text.strip(), "voice": f"output/audio/bible/johan_1_{index}_sadachbia.mp3"}
        items.append(item)
    body_video_path = make_video(request.video_basic, request.video_body, intro_clip, items=items)

    print("최종 영상 경로 : " + body_video_path)

    # 시작화면 붙이기
    # concat_videos_ffmpeg(
    #     [Path(intro_video_path), Path(body_video_path)], request.video_basic.output_path
    # )




    # 각 절마다 개별 동영상 생성
    # for index, text in enumerate(lines, start=1):
    #     if index > max_files:
    #         break
    #     item = {
    #         "text": text.strip(),
    #         "voice": f"resources/audio/bible/yohan/yohan1_{index:02d}.mp3"
    #     }
    #     items = [item]
    #     config.output_video = f"output/yohan_{chapter}_{index:02d}.mp4"
    #     config.title_txt = f"{book} {chapter}장 {index}절"
    #     make_video(config, items=items)
    # 각 파일 합치기
    # input_files = []
    # output_path = "output/johan_final_combined.mp4"
    # for index in range(1, max_files + 1):
    #     file_path = Path(f"output/johan_{chapter}_{index:02d}.mp4")
    #     input_files.append(file_path)
    #     if not file_path.exists():
    #         print(f"파일이 존재하지 않습니다: {file_path}")
    #         continue
    # output_path = concat_videos_ffmpeg(
    #     input_files, output_path
    # )
    # print(f"생성된 파일: {output_path}")