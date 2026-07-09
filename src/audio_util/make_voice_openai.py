import uuid

from openai import OpenAI


def make_voice_openai(text, instructions, voice, output_path=None):
    client = OpenAI()
    if not output_path: 
        filename = f"{uuid.uuid4()}.mp3"
        root_folder = "output"
        sub_folder = "audio"
        output_path = f"{root_folder}/{sub_folder}/{filename}"
    #print(f"Generating voice for instructions: {instructions}")
    with client.audio.speech.with_streaming_response.create(
        model="gpt-4o-mini-tts",
        voice=voice,
        input=text,
        instructions=instructions
    ) as response:
        response.stream_to_file(output_path)

    audio_url = f"http://localhost:8000/files/{sub_folder}/{filename}"
    return [audio_url, output_path]
