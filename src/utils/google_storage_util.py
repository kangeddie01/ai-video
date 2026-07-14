import mimetypes
import os
from pathlib import Path

from google.cloud import storage


BUCKET_NAME = os.getenv("BUCKET_NAME")
BUCKET_ROOT = os.getenv("BUCKET_ROOT")

import json
import subprocess
from pathlib import Path


def get_content_type(file_path: str | Path) -> str:
    path = Path(file_path)

    content_type, _ = mimetypes.guess_type(path.name)

    return content_type or "application/octet-stream"

def get_video_metadata(
    video_path: str | Path,
    ffprobe_path: str = "ffprobe",
) -> dict:
    """
    영상 파일의 재생 시간과 파일 크기를 조회한다.

    Returns:
        {
            "duration_seconds": 325.4,
            "file_size_bytes": 52428800,
        }
    """
    path = Path(video_path)

    if not path.exists():
        raise FileNotFoundError(
            f"영상 파일을 찾을 수 없습니다: {path}"
        )

    if not path.is_file():
        raise ValueError(
            f"파일 경로가 아닙니다: {path}"
        )

    command = [
        ffprobe_path,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "영상 길이 조회에 실패했습니다.\n"
            f"{completed.stderr}"
        )

    probe_result = json.loads(
        completed.stdout
    )

    duration_value = (
        probe_result
        .get("format", {})
        .get("duration")
    )

    if duration_value is None:
        raise RuntimeError(
            "FFprobe 결과에서 영상 길이를 찾을 수 없습니다."
        )

    return {
        "duration_seconds": float(duration_value),
        "file_size_bytes": path.stat().st_size,
    }

def upload_file_to_gcs(
    source_file_path: str | Path,
    # destination_blob_name: str,
    content_type: str | None = None,
) -> dict:
    """
    로컬 파일을 Google Cloud Storage에 업로드한다.

    Args:
        bucket_name:
            GCS 버킷 이름
            예: my-ai-video-bucket

        source_file_path:
            업로드할 로컬 파일 경로
            예: data/bible/video/genesis_001_final.mp4

        destination_blob_name:
            버킷 내부에 저장할 객체 경로
            예: videos/bible/genesis_001_final.mp4

        content_type:
            MIME 타입
            예: video/mp4

    Returns:
        업로드된 객체 정보
    """
    source_path = Path(source_file_path)

    if not source_path.exists():
        raise FileNotFoundError(
            f"업로드할 파일을 찾을 수 없습니다: {source_path}"
        )

    if not source_path.is_file():
        raise ValueError(
            f"파일 경로가 아닙니다: {source_path}"
        )
    
    normalized_blob_name = source_file_path.replace("data", BUCKET_ROOT).replace("\\", "/").lstrip("/")

    print("normalized_blob_name : " + normalized_blob_name )

    if not normalized_blob_name:
        raise ValueError("GCS 객체 경로가 비어 있습니다.")

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(normalized_blob_name)

    blob.upload_from_filename(
        filename=str(source_path),
        content_type=content_type,
    )

    return {
        "bucket_name": BUCKET_NAME,
        "blob_name": normalized_blob_name,
        "gs_uri": f"gs://{BUCKET_NAME}/{normalized_blob_name}",
        "public_url": blob.public_url,
        "file_size_bytes": source_path.stat().st_size,
    }