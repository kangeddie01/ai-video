"""Synthesizes speech from the input string of text or ssml.
Make sure to be working in a virtual environment.

Note: ssml must be well-formed according to:
    https://www.w3.org/TR/speech-synthesis/
"""

from pathlib import Path
import re
import os
import uuid
from pyexpat import model
from google.cloud import texttospeech

from src.utils.file_util import FileUtil


def _configure_google_credentials():
    credential_path = os.getenv("GOOGLE_KEY_FILE_PATH") or os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )

    if not credential_path:
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        fallback_path = os.path.join(project_root, "data", "google_key.json")
        if os.path.exists(fallback_path):
            credential_path = fallback_path

    if credential_path:
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path
        return credential_path

    raise RuntimeError(
        "Google credentials not found. Set GOOGLE_KEY_FILE_PATH or GOOGLE_APPLICATION_CREDENTIALS to your service-account JSON file."
    )


_configure_google_credentials()


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


def make_voice_google(
    text, model_name=None, book_en_name="", chapter=1, file_name=None, lang="en-GB"
):
    # Instantiates a client
    client = texttospeech.TextToSpeechClient()

    # Set the text input to be synthesized
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-US") and the ssml
    # voice gender ("neutral")
    voice = texttospeech.VoiceSelectionParams(
        language_code="ko-KR", name=model_name if model_name else None
    )

    # Select the type of audio file you want returned
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=0.9,  # Adjust the speaking rate (1.0 is normal speed)
        #  pitch = -3.0,          # Adjust the pitch (0.0 is default pitch)
        sample_rate_hertz=24000,
    )

    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    root_folder = "data"
    sub_folder = f"bible/audio/{lang}/{book_en_name}/{chapter:02d}"
    # The response's audio_content is binary.

    if not file_name:
        file_name = f"{uuid.uuid4()}.mp3"
    output_path = f"{root_folder}/{sub_folder}/{file_name}"
    Path(output_path).parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with open(output_path, "wb") as out:
        # Write the response to the output file.
        out.write(response.audio_content)
        print(f'Audio content written to file "{output_path}"')

    audio_url = f"http://localhost:8000/files/{sub_folder}/{file_name}"
    return [audio_url, output_path]


if __name__ == "__main__":

    # text = "요한이 그에 대하여 증언하여 외쳐 이르되 내가 전에 말하기를 내 뒤에 오시는 이가 나보다 앞선 것은 나보다 먼저 계심이라 한 것이 이 사람을 가리킴이라 하니라"

    # 사용 가능한 한국어 목소리 목록 출력
    # client = texttospeech.TextToSpeechClient()
    # voices = client.list_voices(language_code="ko-KR")
    # for voice in voices.voices:
    #    # Chirp 모델이 포함된 이름만 필터링하여 출력
    #    if "Chirp" in voice.name:
    #        print(f"사용 가능한 모델명: {voice.name}")

    # file_path = r"C:\project\my-ai-video\data\google_tts_all_model.txt"

    book = "johan"
    chapter = "1"
    model = "sadachbia"
    lang = "en-GB"

    book_list = FileUtil.get_json_data("data/bible/openbible/book_list.json")

    for book_index, book in enumerate(book_list):
        # 앞의 2권만 실행
        if book_index >= 2:
            break

        book_no = book.get("bookNo")
        book_en_name = book.get("bookNmEn2")
        chapter_count = book.get("chapterCount")

        if not book_no:
            raise ValueError(f"bookNo가 없습니다: {book}")

        if not book_en_name:
            raise ValueError(f"bookNmEn2가 없습니다: {book}")

        if not chapter_count:
            raise ValueError(f"chapterCount가 없습니다: {book}")

        for chapter in range(1, chapter_count + 1):
            input_path = (
                f"data/bible/openbible/{lang}/"
                f"{book_no:02d}.{book_en_name}/"
                f"{book_en_name}-{chapter:02d}.txt"
            )

            with open(
                input_path,
                "r",
                encoding="utf-8",
            ) as f:
                lines = f.readlines()

            for verse_index, text in enumerate(
                lines,
                start=1,
            ):
                verse_no, verse_text = parse_verse_line(text)

                file_name = (
                    f"{book_en_name}_"
                    f"{chapter:02d}_"
                    f"{verse_no:02d}_"
                    f"{lang}_"
                    f"{model.strip()}.mp3"
                )

                result = make_voice_google(
                    verse_text,
                    f"ko-KR-Chirp3-HD-{model.strip()}",
                    book_en_name,
                    chapter,
                    file_name,
                    lang,
                )

                print(
                    f"[음성 생성 완료] "
                    f"{book_en_name} "
                    f"{chapter}장 "
                    f"{verse_no}절: {result}"
                )

    # def check_voice_info():
    #     client = texttospeech.TextToSpeechClient()
    #     voices = client.list_voices(language_code="ko-KR")
    #     for v in voices.voices:
    #         print(f" {v.name}")

    # check_voice_info()
