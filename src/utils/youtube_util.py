from __future__ import annotations

import random
import socket
import time
from pathlib import Path
from typing import Any

import httplib2
from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_httplib2 import AuthorizedHttp
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# =========================================================
# YouTube OAuth 설정
# =========================================================

# 영상 업로드에 필요한 최소 권한
YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

DEFAULT_CLIENT_SECRET_PATH = Path("credentials/youtube_client_secret.json")

DEFAULT_TOKEN_PATH = Path("credentials/youtube_token.json")


# =========================================================
# 업로드 설정
# =========================================================

# 8MB 단위 업로드
UPLOAD_CHUNK_SIZE = 8 * 1024 * 1024

# 재시도 가능한 HTTP 상태 코드
RETRIABLE_STATUS_CODES = {
    500,
    502,
    503,
    504,
}

MAX_RETRIES = 10

# 최대 재시도 대기 시간
MAX_RETRY_SLEEP_SECONDS = 60


# =========================================================
# OAuth 인증
# =========================================================
def get_youtube_credentials(
    client_secret_path: str | Path = DEFAULT_CLIENT_SECRET_PATH,
    token_path: str | Path = DEFAULT_TOKEN_PATH,
) -> Credentials:
    """
    YouTube OAuth 인증 정보를 가져온다.

    최초 실행:
        브라우저에서 Google 로그인 및 YouTube 권한 승인

    이후 실행:
        저장된 token JSON을 재사용한다.

    access token이 만료되면:
        refresh token으로 자동 갱신한다.
    """
    client_secret_path = Path(client_secret_path)
    token_path = Path(token_path)

    if not client_secret_path.is_file():
        raise FileNotFoundError(
            "YouTube OAuth 클라이언트 파일이 없습니다: " f"{client_secret_path}"
        )

    token_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    credentials: Credentials | None = None

    if token_path.is_file():
        try:
            credentials = Credentials.from_authorized_user_file(
                str(token_path),
                YOUTUBE_UPLOAD_SCOPE,
            )
        except (ValueError, OSError):
            # 토큰 파일 형식이 잘못되었거나 읽을 수 없는 경우
            token_path.unlink(missing_ok=True)
            credentials = None

    if credentials and credentials.expired and credentials.refresh_token:
        try:
            credentials.refresh(Request())

        except RefreshError:
            # 기존 토큰이 취소되었거나 사용할 수 없는 경우
            token_path.unlink(missing_ok=True)
            credentials = None

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path),
            scopes=YOUTUBE_UPLOAD_SCOPE,
        )

        credentials = flow.run_local_server(
            host="localhost",
            port=0,
            authorization_prompt_message=("브라우저에서 YouTube 계정을 승인해 주세요."),
            success_message=(
                "YouTube 인증이 완료되었습니다. " "브라우저 창을 닫아도 됩니다."
            ),
            open_browser=True,
        )

    token_path.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )

    return credentials


# =========================================================
# HTTP 308 처리
# =========================================================
def _create_youtube_http(
    credentials: Credentials,
    timeout: int = 300,
) -> AuthorizedHttp:
    """
    YouTube Data API에서 사용할 AuthorizedHttp를 생성한다.

    YouTube resumable upload 중 반환되는 HTTP 308은
    일반 리다이렉트가 아니라 Resume Incomplete 응답이다.

    따라서 httplib2가 308을 리다이렉트로 처리하지 않도록
    redirect_codes에서 308을 제거한다.
    """
    raw_http = httplib2.Http(
        timeout=timeout,
    )

    redirect_codes = getattr(
        raw_http,
        "redirect_codes",
        None,
    )

    if redirect_codes is None:
        raise RuntimeError(
            "httplib2.Http 객체에서 redirect_codes를 " "찾을 수 없습니다."
        )

    # httplib2 버전에 따라 set, frozenset, tuple일 수 있으므로
    # 기존 타입과 무관하게 set으로 변환한다.
    updated_redirect_codes = set(redirect_codes)
    updated_redirect_codes.discard(308)

    raw_http.redirect_codes = updated_redirect_codes

    if 308 in raw_http.redirect_codes:
        raise RuntimeError("HTTP 308 리다이렉트 제외 설정에 실패했습니다.")

    print(
        "[YouTube HTTP 설정] "
        "308 Resume Incomplete 응답을 "
        "리다이렉트 처리 대상에서 제외했습니다."
    )

    return AuthorizedHttp(
        credentials,
        http=raw_http,
    )


# =========================================================
# YouTube API 서비스
# =========================================================
def get_youtube_service(
    client_secret_path: str | Path = DEFAULT_CLIENT_SECRET_PATH,
    token_path: str | Path = DEFAULT_TOKEN_PATH,
) -> Resource:
    """
    YouTube Data API 서비스 객체를 생성한다.
    """
    credentials = get_youtube_credentials(
        client_secret_path=client_secret_path,
        token_path=token_path,
    )

    authorized_http = _create_youtube_http(
        credentials=credentials,
        timeout=300,
    )

    youtube = build(
        serviceName="youtube",
        version="v3",
        http=authorized_http,
        cache_discovery=False,
    )

    return youtube


# =========================================================
# 재시도 처리
# =========================================================
def _get_retry_sleep_seconds(
    retry_count: int,
) -> float:
    """
    지수 백오프 방식의 재시도 대기 시간을 반환한다.
    """
    max_sleep = min(
        MAX_RETRY_SLEEP_SECONDS,
        2**retry_count,
    )

    return random.uniform(
        0,
        max_sleep,
    )


def _execute_resumable_upload(
    request,
) -> dict[str, Any]:
    """
    대용량 영상 업로드를 resumable upload 방식으로 실행한다.

    다음 오류가 발생하면 지수 백오프 방식으로 재시도한다.

    - HTTP 500
    - HTTP 502
    - HTTP 503
    - HTTP 504
    - 네트워크 연결 오류
    - 소켓 타임아웃
    - httplib2 임시 오류
    """
    response: dict[str, Any] | None = None
    retry_count = 0

    while response is None:
        error_message: str | None = None

        try:
            upload_status, response = request.next_chunk(
                num_retries=0,
            )

            if upload_status is not None:
                progress_percent = int(upload_status.progress() * 100)

                print("[YouTube 업로드 진행률] " f"{progress_percent}%")

        except HttpError as exc:
            status_code = getattr(
                exc.resp,
                "status",
                None,
            )

            if status_code not in RETRIABLE_STATUS_CODES:
                error_content = getattr(
                    exc,
                    "content",
                    b"",
                )

                if isinstance(error_content, bytes):
                    error_content = error_content.decode(
                        "utf-8",
                        errors="replace",
                    )

                raise RuntimeError(
                    "YouTube API 요청에 실패했습니다.\n"
                    f"HTTP 상태 코드: {status_code}\n"
                    f"오류 내용: {error_content}"
                ) from exc

            error_message = "YouTube 서버 임시 오류: " f"HTTP {status_code}"

        except httplib2.error.RedirectMissingLocation as exc:
            # 308 제외 설정이 정상이라면 일반적으로 발생하지 않는다.
            # 프록시나 보안 프로그램이 응답을 변경하는 경우를 대비해
            # 재시도 가능한 오류로 처리한다.
            error_message = "HTTP 리다이렉트 응답에 Location 헤더가 없습니다: " f"{exc}"

        except (
            httplib2.HttpLib2Error,
            socket.timeout,
            TimeoutError,
            ConnectionResetError,
            ConnectionAbortedError,
            ConnectionError,
            OSError,
        ) as exc:
            error_message = (
                "YouTube 업로드 네트워크 오류: " f"{type(exc).__name__}: {exc}"
            )

        if response is not None:
            if "id" not in response:
                raise RuntimeError(
                    "YouTube 업로드 응답에 video ID가 없습니다. " f"response={response}"
                )

            return response

        if error_message is None:
            # 정상적인 308 Resume Incomplete 처리 후
            # 다음 청크를 계속 업로드한다.
            continue

        retry_count += 1

        if retry_count > MAX_RETRIES:
            raise RuntimeError(
                "YouTube 영상 업로드 재시도 횟수를 "
                "초과했습니다.\n"
                f"마지막 오류: {error_message}"
            )

        sleep_seconds = _get_retry_sleep_seconds(
            retry_count=retry_count,
        )

        print("[YouTube 업로드 오류] " f"{error_message}")

        print(
            "[YouTube 업로드 재시도] "
            f"{sleep_seconds:.1f}초 후 재시도 "
            f"({retry_count}/{MAX_RETRIES})"
        )

        time.sleep(sleep_seconds)

    raise RuntimeError("YouTube 업로드 결과를 확인할 수 없습니다.")


# =========================================================
# 영상 업로드
# =========================================================
def upload_video_to_youtube(
    video_path: str | Path,
    title: str,
    description: str = "",
    tags: list[str] | None = None,
    category_id: str = "22",
    privacy_status: str = "private",
    made_for_kids: bool = False,
    thumbnail_path: str | Path | None = None,
    client_secret_path: str | Path = DEFAULT_CLIENT_SECRET_PATH,
    token_path: str | Path = DEFAULT_TOKEN_PATH,
) -> dict[str, Any]:
    """
    동영상 파일을 YouTube에 업로드한다.

    Args:
        video_path:
            업로드할 영상 파일 경로.

        title:
            YouTube 영상 제목.

        description:
            YouTube 영상 설명.

        tags:
            영상 태그 목록.

        category_id:
            YouTube 카테고리 ID.
            기본값 "22"는 People & Blogs.

        privacy_status:
            공개 범위.

            - private
            - unlisted
            - public

        made_for_kids:
            아동용 콘텐츠 여부.

        client_secret_path:
            Google OAuth 클라이언트 JSON 경로.

        token_path:
            OAuth 인증 토큰 저장 경로.

    Returns:
        {
            "video_id": "...",
            "video_url": "...",
            "title": "...",
            "privacy_status": "...",
            "raw_response": {...}
        }
    """
    video_path = Path(video_path)

    if not video_path.is_file():
        raise FileNotFoundError(f"업로드할 영상 파일이 없습니다: {video_path}")

    normalized_title = title.strip()

    if not normalized_title:
        raise ValueError("YouTube 영상 제목이 비어 있습니다.")

    if len(normalized_title) > 100:
        raise ValueError(
            "YouTube 영상 제목은 100자를 초과할 수 없습니다. "
            f"현재 길이={len(normalized_title)}"
        )

    allowed_privacy_statuses = {
        "private",
        "unlisted",
        "public",
    }

    if privacy_status not in allowed_privacy_statuses:
        raise ValueError(
            "privacy_status는 private, unlisted, public 중 " "하나여야 합니다."
        )

    youtube = get_youtube_service(
        client_secret_path=client_secret_path,
        token_path=token_path,
    )

    snippet = {
        "title": normalized_title,
        "description": description.strip(),
        "categoryId": str(category_id),
    }

    if tags:
        snippet["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]

    request_body = {
        "snippet": snippet,
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": made_for_kids,
        },
    }

    media = MediaFileUpload(
        filename=str(video_path),
        mimetype="video/mp4",
        chunksize=UPLOAD_CHUNK_SIZE,
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=request_body,
        media_body=media,
    )

    file_size_bytes = video_path.stat().st_size
    file_size_mb = file_size_bytes / 1024 / 1024

    print(
        "[YouTube 업로드 시작]\n"
        f"파일: {video_path}\n"
        f"크기: {file_size_mb:.2f} MB\n"
        f"제목: {normalized_title}\n"
        f"공개 상태: {privacy_status}"
    )

    response = _execute_resumable_upload(
        request=request,
    )

    video_id = response["id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    result = {
        "video_id": video_id,
        "video_url": video_url,
        "title": normalized_title,
        "privacy_status": privacy_status,
        "raw_response": response,
    }

    print("[YouTube 업로드 완료]\n" f"video_id={video_id}\n" f"video_url={video_url}")

    video_id = result["video_id"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"

    thumbnail_response = None
    # thumbnail_path = "data/bible/video/genesis_thumbnail_en.jpg"
    if thumbnail_path is not None:
        thumbnail_response = upload_youtube_thumbnail(
            youtube=youtube,
            video_id=video_id,
            thumbnail_path=thumbnail_path,
        )

    playlist_id = "PLAzRzDnXj_8o"
    playlist_response = None

    if playlist_id and not is_video_in_playlist(
        youtube=youtube,
        playlist_id=playlist_id,
        video_id=video_id,
    ):
        playlist_response = add_video_to_playlist(
            playlist_id=playlist_id,
            youtube=youtube,
            video_id=video_id,
        )

    result["playlist_response"] = playlist_response
    result["thumbnail_response"] = thumbnail_response
    return result


# 썸네일 업로드
def upload_youtube_thumbnail(
    youtube: Resource,
    video_id: str,
    thumbnail_path: str | Path,
) -> dict[str, Any]:
    """
    업로드된 YouTube 영상에 사용자 지정 썸네일을 설정한다.

    Args:
        youtube:
            인증된 YouTube Data API 서비스 객체.

        video_id:
            썸네일을 적용할 YouTube 영상 ID.

        thumbnail_path:
            JPG 또는 PNG 썸네일 파일 경로.

    Returns:
        YouTube thumbnails.set API 응답.
    """
    thumbnail_path = Path(thumbnail_path)

    if not thumbnail_path.is_file():
        raise FileNotFoundError(f"썸네일 파일이 없습니다: {thumbnail_path}")

    file_size_bytes = thumbnail_path.stat().st_size
    max_file_size_bytes = 2 * 1024 * 1024

    if file_size_bytes > max_file_size_bytes:
        raise ValueError(
            "YouTube 썸네일 파일은 2MB 이하여야 합니다. "
            f"현재 크기={file_size_bytes / 1024 / 1024:.2f}MB"
        )

    extension = thumbnail_path.suffix.lower()

    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
    }

    mimetype = mime_types.get(extension)

    if mimetype is None:
        raise ValueError(
            "썸네일은 JPG, JPEG, PNG 파일만 가능합니다. " f"현재 확장자={extension}"
        )

    media_body = MediaFileUpload(
        filename=str(thumbnail_path),
        mimetype=mimetype,
        resumable=False,
    )

    print(
        "[YouTube 썸네일 업로드 시작]\n"
        f"video_id={video_id}\n"
        f"thumbnail={thumbnail_path}"
    )

    response = (
        youtube.thumbnails()
        .set(
            videoId=video_id,
            media_body=media_body,
        )
        .execute(num_retries=5)
    )

    print("[YouTube 썸네일 업로드 완료]\n" f"video_id={video_id}")

    return response


# 플레이리스트에 동영상 추가
def add_video_to_playlist(
    youtube: Any,
    playlist_id: str,
    video_id: str,
    position: int | None = None,
) -> dict:
    """
    유튜브 영상을 지정한 재생목록에 추가한다.

    Args:
        youtube:
            googleapiclient.discovery.build()로 생성한
            YouTube API 클라이언트

        playlist_id:
            영상을 추가할 유튜브 재생목록 ID

        video_id:
            유튜브 업로드 후 반환받은 영상 ID

        position:
            재생목록 내 삽입 위치
            None이면 기본적으로 재생목록 끝에 추가

    Returns:
        생성된 playlistItem 리소스
    """
    if not playlist_id.strip():
        raise ValueError("playlist_id가 비어 있습니다.")

    if not video_id.strip():
        raise ValueError("video_id가 비어 있습니다.")

    snippet = {
        "playlistId": playlist_id,
        "resourceId": {
            "kind": "youtube#video",
            "videoId": video_id,
        },
    }

    if position is not None:
        snippet["position"] = position

    response = (
        youtube.playlistItems()
        .insert(
            part="snippet",
            body={
                "snippet": snippet,
            },
        )
        .execute()
    )

    print(
        "[유튜브 재생목록 추가 완료] "
        f"playlist_id={playlist_id}, "
        f"video_id={video_id}"
    )

    return response


# 플레이리스트에 비디오가 있는지 체크
def is_video_in_playlist(
    youtube,
    playlist_id: str,
    video_id: str,
) -> bool:
    next_page_token = None

    while True:
        response = (
            youtube.playlistItems()
            .list(
                part="contentDetails",
                playlistId=playlist_id,
                maxResults=50,
                pageToken=next_page_token,
            )
            .execute()
        )

        for item in response.get("items", []):
            current_video_id = item.get("contentDetails", {}).get("videoId")

            if current_video_id == video_id:
                return True

        next_page_token = response.get("nextPageToken")

        if not next_page_token:
            return False


# =========================================================
# 직접 실행 테스트
# =========================================================
if __name__ == "__main__":
    result = upload_video_to_youtube(
        video_path=("data/bible/video/" "exodus_05_final.mp4"),
        title=("테스트 입니다."),
        description=(
            "This video presents a calm and peaceful reading "
            "of Genesis Chapter 1.\n\n"
            "Listen when you want to meditate on God's Word, "
            "relax with Scripture before going to sleep, "
            "or continue your Bible reading while driving "
            "or resting.\n\n"
            "May your day be filled with peace and grace "
            "through the Word of God.\n\n"
            "#BibleReading #Genesis #AudioBible "
            "#ListenToTheBible"
        ),
        tags=[
            "Bible Reading",
            "Listen to the Bible",
            "Genesis",
            "Genesis Chapter 1",
            "Audio Bible",
        ],
        category_id="22",
        privacy_status="private",
        made_for_kids=False,
        thumbnail_path="data/bible/video/genesis_thumbnail_en.jpg",
    )

    print(result)
