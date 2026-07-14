from datetime import timedelta
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from google.cloud import storage
from pydantic import BaseModel


router = APIRouter(
    prefix="/api/storage",
    tags=["storage"],
)


BUCKET_NAME = os.getenv("BUCKET_NAME")

class SignedUploadUrlRequest(BaseModel):
    file_name: str
    content_type: str
    folder: str | None = "uploads"


class SignedUploadUrlResponse(BaseModel):
    upload_url: str
    object_name: str
    gs_path: str


def sanitize_file_name(file_name: str) -> str:
    """
    클라이언트에서 전달된 파일명에서 경로 부분을 제거한다.

    예:
        C:\\temp\\video.mp4 -> video.mp4
        ../../video.mp4    -> video.mp4
    """
    normalized_name = file_name.replace("\\", "/")
    return Path(normalized_name).name


@router.post(
    "/signed-upload-url",
    response_model=SignedUploadUrlResponse,
)
def create_signed_upload_url(
    request: SignedUploadUrlRequest,
) -> SignedUploadUrlResponse:
    file_name = sanitize_file_name(request.file_name)

    if not file_name:
        raise HTTPException(
            status_code=400,
            detail="파일명이 필요합니다.",
        )

    if not request.content_type:
        raise HTTPException(
            status_code=400,
            detail="content_type이 필요합니다.",
        )

    folder = (request.folder or "uploads").strip("/")
    unique_file_name = f"{uuid4().hex}_{file_name}"
    object_name = f"{folder}/{unique_file_name}"

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(object_name)

        upload_url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=15),
            method="PUT",
            content_type=request.content_type,
        )

        return SignedUploadUrlResponse(
            upload_url=upload_url,
            object_name=object_name,
            gs_path=f"gs://{BUCKET_NAME}/{object_name}",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Signed URL 생성 실패: {exc}",
        ) from exc