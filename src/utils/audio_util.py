from moviepy import AudioFileClip

# ============================================================
# 오디오 파일로부터 전체 길이 조회
# ============================================================
def get_audio_duration(audio_path: str) -> float:
    clip = AudioFileClip(audio_path)
    try:
        return float(clip.duration)
    finally:
        clip.close()