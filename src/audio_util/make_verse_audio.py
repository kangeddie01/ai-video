# make_verse_audio.py

# data/bible_yohan1 파일을 읽어서 1~10절까지 음성파일 생성

# output: resources/audio/bible/yohan/yohan1_01.mp3, yohan1_02.mp3, yohan1_03.mp3

import os
import re
from openai import OpenAI

from src.audio_util.make_voice_openai import make_voice_openai

client = OpenAI()

INPUT_FILE = "data/bible_yohan1"
OUTPUT_DIR = "resources/audio/bible/yohan"

MODEL = "gpt-4o-mini-tts"
VOICE = "alloy"

os.makedirs(OUTPUT_DIR, exist_ok=True)


# 절넘버, 텍스트 분리
def parse_verse_line(line):
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
    text = match.group(2).strip()

    return verse_no, text


def make_speech(text, instructions, output_path):
    response = client.audio.speech.create(
        model=MODEL,
        voice=VOICE,
        input=text,
        intstructions=instructions
    )

    with open(output_path, "wb") as f:
        f.write(response.read())


def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    chapter = 1
    
    for index, line in enumerate(lines, start=1):


        if index > 1:
            break

        verse_no, verse_text = parse_verse_line(line)

        if not verse_text:
            continue

        if verse_no is None:
            verse_no = index

        output_path = os.path.join(
            OUTPUT_DIR,
            f"johan_{chapter}_{verse_no:02d}.mp3"
        )

        print(f"{verse_no}절 음성 생성 중...")

        make_voice_openai(
            text=verse_text,
            instructions="""
                Natural Korean pronunciation.
                살짝 근엄한 남자 톤으로.
            """,
            voice="alloy",
            output_path=output_path,
        )
        

    print("완료")


if __name__ == "__main__":
    main()