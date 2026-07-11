
# '장(chapter)' 별로 영상 생성
import json
from pathlib import Path
from src.service.bible.openbible_api import change_json_to_txt


"""
    성경책 영상 생성 서비스

    로컬실행: 
        .\\.venv\\Scripts\\python.exe -m src.service.bible_service

"""
               
def start_bible_job():

    """
    사전작업1) 성경 구절 조회 (data/openbible/01.창세기/창세기-01.txt)
    사전작업2) 각 절별로 음성파일 및 세그먼트 생성 (google-tts AI, output/audio/bible/창세기/01/창세기_01_001_sadachbia.mp3)
    사전작업3) 배경이미지

    1. DB에서 이번 스케쥴의 파라메터 조회 ( json )
    2. 음성파일, 세그먼트 파일로 영상 생성 ( 챕터별로 mp4 생성 하여 ffmpeg 로 concat )
    3. youtube 업로드   
    """

    print("proc_bible() start ~~")


if __name__ == "__main__":
    start_bible_job()