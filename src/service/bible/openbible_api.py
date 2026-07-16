import json
from pathlib import Path
from urllib.parse import quote

import requests

from src.utils.file_util import FileUtil

"""
    오픈바이블(openbible) API로부터 전체 성경책 내용 파일로 저장

    API URL : 
        https://api.openbible.uk/json/ko-KR/01.창세기/json/창세기-01.json

    저장 경로:
        data/openbible

    로컬실행: 
        .\\.venv\\Scripts\\python.exe -m src.service.bible.openbible_api

"""


def make_openbible_chapter_url(
    book_no: int,
    book_name_folder: str,
    book_name_finaname: str,
    chapter: int,
    lang: str = "ko-KR",
) -> str:
    book_folder = f"{book_no:02d}.{book_name_folder}"
    file_name = f"{book_name_finaname}-{chapter:02d}.json"

    url = (
        f"https://api.openbible.uk/json/{lang}/"
        + quote(book_folder)
        + "/json/"
        + quote(file_name)
    )

    return url


def fetch_openbible_chapter(
    book_no: int,
    book_name_folder: str,
    book_name_finaname: str,
    chapter: int,
    output_dir: str = "data/bible/openbible",
    lang: str = "ko-KR",
) -> dict:
    url = make_openbible_chapter_url(
        book_no=book_no,
        book_name_folder=book_name_folder,
        book_name_finaname=book_name_finaname,
        chapter=chapter,
        lang=lang,
    )

    print("[OpenBible URL]")
    print(url)

    headers = {"User-Agent": "Mozilla/5.0"}

    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    data = response.json()

    book_dir = Path(output_dir) / f"{book_no:02d}.{book_name_finaname}"
    book_dir.mkdir(parents=True, exist_ok=True)

    output_path = book_dir / f"{book_name_finaname}-{chapter:02d}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("[저장 완료]")
    print(output_path)

    return {"url": url, "output_path": str(output_path), "data": data}


def fetch_openbible_book(
    book_no: int,
    book_name_folder: str,
    book_name_finaname: str,
    chapter_count: int,
    output_dir: str = "data/bible/openbible",
    lang: str = "ko-KR",
) -> list[dict]:
    book_no = int(book_no)
    chapter_count = int(chapter_count)

    results = []

    for chapter in range(1, chapter_count + 1):
        result = fetch_openbible_chapter(
            book_no=book_no,
            book_name_folder=book_name_folder,
            book_name_finaname=book_name_finaname,
            chapter=chapter,
            output_dir=output_dir,
            lang=lang,
        )
        results.append(result)

    return results


def load_book_list(json_path: str) -> list[dict]:
    path = Path(json_path)

    if not path.exists():
        raise FileNotFoundError(f"파일이 없습니다: {json_path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("book_list.json 형식은 list 여야 합니다.")

    return data


def fetch_all_books_from_list(
    json_path: str = "data/bible/book_list.json",
    output_dir: str = "data/openbible",
    lang: str = "ko-KR",
    gubun_filter: str | None = None,
    start_book_no: int = 1,
    end_book_no: int | None = None,
):
    print("json_path : " + json_path)
    book_list = load_book_list(json_path)

    results = []

    for index, book_info in enumerate(book_list, start=1):
        raw_book_no = book_info.get("bookNo")
        book_folder_name = book_info.get("bookNmEn1")
        book_filename = book_info.get("bookNmEn2")
        raw_chapter_count = book_info.get("chapterCount")
        gubun = book_info.get("gubun")

        if raw_book_no is None:
            raise ValueError(f"{index}번째 항목에 bookNo 값이 없습니다.")

        if not book_folder_name:
            raise ValueError(f"{index}번째 항목에 book 값이 없습니다.")

        if raw_chapter_count is None:
            raise ValueError(f"{book_folder_name} 항목에 chapterCount 값이 없습니다.")

        book_no = int(raw_book_no)
        chapter_count = int(raw_chapter_count)

        if gubun_filter and gubun != gubun_filter:
            continue

        if book_no < start_book_no:
            continue

        if end_book_no is not None and book_no > end_book_no:
            continue

        print("\n" + "=" * 70)
        print(
            f"[BOOK START] {book_no:02d}. {book_folder_name} / {chapter_count}장 / {gubun}"
        )
        print("=" * 70)

        try:
            book_results = fetch_openbible_book(
                book_no=book_no,
                book_name_folder=book_folder_name,
                book_name_finaname=book_filename,
                chapter_count=chapter_count,
                output_dir=output_dir,
                lang=lang,
            )

            results.append(
                {
                    "bookNo": book_no,
                    "bookFolderName": book_folder_name,
                    "bookFilename": book_filename,
                    "chapterCount": chapter_count,
                    "gubun": gubun,
                    "success": True,
                    "resultCount": len(book_results),
                }
            )

            print(f"[BOOK DONE] {book_no:02d}. {book_folder_name}")

        except Exception as e:
            print(f"[BOOK ERROR] {book_no:02d}. {book_folder_name}: {e}")

            results.append(
                {
                    "bookNo": book_no,
                    "bookFolderName": book_folder_name,
                    "bookFilename": book_filename,
                    "chapterCount": chapter_count,
                    "gubun": gubun,
                    "success": False,
                    "error": str(e),
                }
            )

    summary_path = Path(output_dir) / "fetch_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)

    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("[전체 완료]")
    print("summary:", summary_path)
    print("=" * 70)

    return results


# 오픈 바이블 (https://www.openbible.uk/ko-KR/) 에서 다움받은 json 형식의 성경글을 txt 형태로 변환한다.
def change_json_to_txt(bookNo=None, lang="en-GB"):
    """
    오픈 바이블 (https://www.openbible.uk/ko-KR/) 에서 제공한 json 형식의 성경글을 txt 형태로 변환한다.

    입력 json : data/openbible/{book_no}.{book_name}/{book_name}-{chapter}.json
    출력 txt : data/openbible/{book_no}.{book_name}/{book_name}-{chapter}.txt

    args:
        bookNo: 변환할 대상 bookNo

    실행:
        .\\.venv\\Scripts\\python.exe -m src.service.bible_service

    """
    print("change_json_to_txt!!!")
    book_list = FileUtil.get_json_data(f"data/bible/openbible/book_list.json")

    for index, book_info in enumerate(book_list, start=1):  # book loop
        print(book_info.get("bookNo"))
        if bookNo is not None and book_info.get("bookNo") != bookNo:
            continue

        book_no = int(book_info.get("bookNo", index))
        book_en_name = book_info.get("bookNmEn2")
        chapter_count = int(book_info.get("chapterCount"))

        for chapter in range(1, chapter_count + 1):  # chapter loop
            # if chapter > 1:
            #     break

            json_path = Path(
                f"data/bible/openbible/{lang}/{book_no:02d}.{book_en_name}/{book_en_name}-{chapter:02d}.json"
            )

            if not json_path.exists():
                print(f"[파일 없음] {json_path}")
                continue

            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            verses = data.get("verses", [])

            chapter_verses = ""

            for verse_info in verses:  # 절 loop
                verse_no = verse_info.get("verse")
                verse_text = verse_info.get("text")

                if verse_no is None or verse_text is None:
                    continue
                if isinstance(verse_text, list):
                    verse_text = " ".join(verse_text)
                chapter_verses += f"{verse_no} {verse_text}\n"

            txt_path = Path(
                f"data/bible/openbible/{lang}/{book_no:02d}.{book_en_name}/{book_en_name}-{chapter:02d}.txt"
            )
            txt_path.parent.mkdir(parents=True, exist_ok=True)

            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(chapter_verses)

            print(f"[TXT 저장 완료] {txt_path}")


if __name__ == "__main__":
    print("main start!! ")
    # 오픈바이블에서 전체 성경 다운로드 (json)
    lang = "en-GB"
    # fetch_all_books_from_list(
    #     json_path="data/bible/openbible/book_list.json",
    #     output_dir=f"data/bible/openbible/{lang}",
    #     lang=lang,
    #     # 전체 다운로드
    #     gubun_filter=None,
    # )

    # 다운받은 json을 txt로 변경
    change_json_to_txt()

    # 단일 책 테스트용. 전체 다운로드할 때는 주석 유지.
    # fetch_openbible_book(
    #     book_no=1,
    #     book_name_folder="Genesis",
    #     book_name_finaname="genesis",
    #     chapter_count=50,
    #     output_dir="data/bible/openbible/en",
    #     lang="en-GB",
    # )
