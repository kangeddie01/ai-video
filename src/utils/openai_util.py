from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


def request_openai_free_json(
    prompt: str,
    model: str = "gpt-5.6",
) -> dict[str, Any]:
    """
    OpenAI API에 프롬프트를 전달하고 JSON 객체를 반환한다.
    """
    normalized_prompt = prompt.strip()

    if not normalized_prompt:
        raise ValueError("프롬프트가 비어 있습니다.")

    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")

    client = OpenAI(
        api_key=api_key,
    )

    response = client.responses.create(
        model=model,
        instructions=(
            "반드시 유효한 JSON 객체만 출력하세요. "
            "마크다운 코드 블록과 추가 설명은 출력하지 마세요. "
            "최상위 필드는 title과 desc만 사용하세요. "
            "title과 desc는 문자열이어야 합니다."
        ),
        input=normalized_prompt,
    )

    result_text = response.output_text.strip()

    try:
        result = json.loads(result_text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "OpenAI 응답이 유효한 JSON이 아닙니다.\n" f"응답 내용:\n{result_text}"
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError("OpenAI 응답의 최상위 구조가 JSON 객체가 아닙니다.")

    title = result.get("title")
    desc = result.get("desc")

    if not isinstance(title, str) or not title.strip():
        raise RuntimeError("OpenAI 응답에 유효한 title이 없습니다.")

    if not isinstance(desc, str) or not desc.strip():
        raise RuntimeError("OpenAI 응답에 유효한 desc가 없습니다.")

    if len(title) > 100:
        raise RuntimeError(
            "생성된 YouTube 제목이 100자를 초과했습니다. " f"현재 길이={len(title)}"
        )

    return {
        "title": title.strip(),
        "desc": desc.strip(),
    }


def make_youtube_metadata_prompt(
    video_content: str,
    response_language: str,
) -> str:
    """
    YouTube 영상 제목과 상세 설명을 생성하기 위한 프롬프트를 만든다.

    Args:
        video_content:
            영상 내용.
            예: "요한복음 1-21장 성경 낭독"

        response_language:
            응답 언어.
            예: "영어", "한국어"

    Returns:
        OpenAI API에 전달할 프롬프트 문자열.
    """
    video_content = video_content.strip()
    response_language = response_language.strip()

    if not video_content:
        raise ValueError("영상 내용이 비어 있습니다.")

    if not response_language:
        raise ValueError("응답 언어가 비어 있습니다.")

    prompt = f"""
        유튜브 업로드에 사용할 제목과 상세내용을
        아래 예시와 동일한 패턴으로 작성해줘.

        영상 내용: {video_content}
        응답 언어: {response_language}

        요구사항:
        - title은 유튜브 영상 제목으로 작성
        - title은 100자 이하
        - desc는 유튜브 영상 상세 설명으로 작성
        - desc의 각 문단 사이에는 개행문자 2개를 포함
        - 영상 내용으로 넘어온 텍스트를 언어에 맞게 제목과 설명에 반영
        - 영상 내용에 없는 성경 이야기나 인물을 임의로 추가하지 않기
        - 응답 언어에 맞춰 제목, 설명, 해시태그를 작성
        - 반드시 JSON 형식으로만 응답
        - JSON 필드는 title, desc만 사용

        아래 JSON과 동일한 문체와 패턴으로 작성해줘.

        {{
        "title": "Bible Reading | The Complete Book of Exodus | From Egypt to the Tabernacle",
        "desc": "This video presents a calm and peaceful reading of the entire Book of Genesis, the first book of the Bible.\\n\\nFrom Genesis Chapters 1 through 50, you can listen to the stories of Creation, Adam and Eve, Noah’s Ark, the Tower of Babel, Abraham and Isaac, Jacob, and Joseph—all in one complete video.\\n\\nListen when you want to meditate on God’s Word, relax with Scripture before going to sleep, or continue your Bible reading while driving or resting.\\n\\nMay your day be filled with peace and grace through the Word of God.\\n\\n※ This video contains a complete Bible reading of Genesis Chapters 1 through 50.\\n\\nYour subscription and support through likes are a great encouragement and help us continue creating Bible reading videos.\\n\\n#BibleReading #Genesis #ListenToTheBible #BibleStudy #AudioBible"
        }}
        """

    return prompt.strip()


def create_youtube_metadata(
    video_content: str,
    response_language: str,
    model: str = "gpt-5.6",
) -> dict[str, str]:
    """
    영상 내용과 응답 언어를 기준으로
    YouTube 제목과 상세 설명을 생성한다.
    제목은 100자 이내.
    Args:
        video_content:
            영상 내용.
            예: "요한복음 1-21장 성경 낭독"

        response_language:
            결과 언어.
            예: "영어", "한국어"

        model:
            사용할 OpenAI 모델명.

    Returns:
        {
            "title": "...",
            "desc": "..."
        }
    """
    prompt = make_youtube_metadata_prompt(
        video_content=video_content,
        response_language=response_language,
    )

    return request_openai_free_json(
        prompt=prompt,
        model=model,
    )


if __name__ == "__main__":
    result = create_youtube_metadata(
        video_content="요한복음 1-21장 성경 낭독",
        response_language="영어",
    )

    print(
        json.dumps(
            result,
            ensure_ascii=False,
            indent=2,
        )
    )

    print("\n[YouTube 제목]")
    print(result["title"])

    print("\n[YouTube 상세내용]")
    print(result["desc"])
