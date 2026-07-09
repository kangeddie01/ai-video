import sys
from pathlib import Path

from generate_video_with_voice import generate_video_with_voice
import src.audio_util.make_voice_openai as make_voice_openai

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from image_util.ai_image_create import generate_image
from image_util.image_text_merge_new import merge_text_to_image
from file_util.load_json_data import load_bible_json_data
from image_util.resize_image import resize_image




data = load_bible_json_data()


#print(data["verses"][0]["image_prompt"])
#generate_image(data["verses"][0]["image_prompt"], "resources/images/scene2.png")

size = (1920, 1080);
clip_list = []

for verse in data["verses"]:
    print(f"Verse: {verse['script']}")
    print(f"Image Prompt: {verse['image_prompt']}")
    image_path = f"resources/images/bible/scene{data['verses'].index(verse) + 1}.png"
    output_path = f"resources/images/bible/scene{data['verses'].index(verse) + 1}_text.png"

    # 배경 이미지 생성

    if not Path(output_path).exists():
        print(f"Generating image for verse: {verse['script']}")
        generate_image(verse["image_prompt"], image_path, size)
        resize_image(image_path, output_path, size) #해상도 조정(16:9)
        
        #배경 이미지에 텍스트를 합성
        merge_text_to_image(
            image_path=output_path,
            output_path=output_path,
            text=verse["script"]
        )        
    else:
        print(f"Using existing image: {output_path}")


    #음성파일 생성
    audio_path = f"resources/audio/bible/scene{data['verses'].index(verse) + 1}.mp3"    

    prompt_instructions = """    
        Natural Korean pronunciation.    
        살짝 근엄한 남자 톤으로.
        """
    if not Path(audio_path).exists():
        print(f"Generating voice for verse: {verse['script']}")

        make_voice_openai.make_voice_openai(verse["script"], prompt_instructions, "alloy", audio_path)


    clip_list.append({"image": output_path, "audio": audio_path})


# 이미지에 음성을 더해서 mp4 비디오로 생성
output_video_path = "resources/videos/bible/bible_video.mp4"
generate_video_with_voice(clip_list, output_path=output_video_path)