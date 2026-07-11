from pathlib import Path



"""
성경 파일 디렉토리의 한글명칭을 영문으로 변경

"""
# 한글 성경책명 -> 영문 폴더/파일명 매핑
BOOK_NAME_MAP = {
    "창세기": "genesis",
    "출애굽기": "exodus",
    "레위기": "leviticus",
    "민수기": "numbers",
    "신명기": "deuteronomy",
    "여호수아": "joshua",
    "사사기": "judges",
    "룻기": "ruth",
    "사무엘상": "samuel_1",
    "사무엘하": "samuel_2",
    "열왕기상": "kings_1",
    "열왕기하": "kings_2",
    "역대상": "chronicles_1",
    "역대하": "chronicles_2",
    "에스라": "ezra",
    "느헤미야": "nehemiah",
    "에스더": "esther",
    "욥기": "job",
    "시편": "psalms",
    "잠언": "proverbs",
    "전도서": "ecclesiastes",
    "아가": "song_of_songs",
    "이사야": "isaiah",
    "예레미야애가": "lamentations",
    "예레미야": "jeremiah",
    "에스겔": "ezekiel",
    "다니엘": "daniel",
    "호세아": "hosea",
    "요엘": "joel",
    "아모스": "amos",
    "오바댜": "obadiah",
    "요나": "jonah",
    "미가": "micah",
    "나훔": "nahum",
    "하박국": "habakkuk",
    "스바냐": "zephaniah",
    "학개": "haggai",
    "스가랴": "zechariah",
    "말라기": "malachi",
    "마태복음": "matthew",
    "마가복음": "mark",
    "루가복음": "luke",
    "누가복음": "luke",
    "요한복음": "john",
    "사도행전": "acts",
    "로마서": "romans",
    "고린도전서": "corinthians_1",
    "고린도후서": "corinthians_2",
    "갈라디아서": "galatians",
    "에베소서": "ephesians",
    "빌립보서": "philippians",
    "골로새서": "colossians",
    "데살로니가전서": "thessalonians_1",
    "데살로니가후서": "thessalonians_2",
    "디모데전서": "timothy_1",
    "디모데후서": "timothy_2",
    "디도서": "titus",
    "빌레몬서": "philemon",
    "히브리서": "hebrews",
    "야고보서": "james",
    "베드로전서": "peter_1",
    "베드로후서": "peter_2",
    "요한일서": "john_1",
    "요한이서": "john_2",
    "요한삼서": "john_3",
    "유다서": "jude",
    "요한계시록": "revelation",
}


def replace_korean_name(name: str) -> str:
    """
    파일명 또는 폴더명에 포함된 한글 성경책 이름을 영문명으로 변경한다.
    """

    new_name = name

    # 긴 이름을 먼저 치환해야 함
    # 예: 예레미야애가가 예레미야보다 먼저 처리되어야 함
    for ko_name, en_name in sorted(
        BOOK_NAME_MAP.items(),
        key=lambda item: len(item[0]),
        reverse=True
    ):
        new_name = new_name.replace(ko_name, en_name)

    return new_name


def rename_korean_bible_paths(root_dir: str = "data", dry_run: bool = True):
    """
    root_dir 하위 모든 폴더명과 파일명에 포함된 한글 성경책 이름을 영문명으로 변경한다.

    Args:
        root_dir (str): 변경 대상 루트 폴더
        dry_run (bool):
            True이면 실제 변경하지 않고 변경 예정 목록만 출력
            False이면 실제 파일명/폴더명을 변경
    """

    root_path = Path(root_dir)

    if not root_path.exists():
        raise FileNotFoundError(f"폴더가 존재하지 않습니다: {root_path}")

    # 하위 경로를 깊은 순서부터 처리해야 폴더명 변경 시 오류가 적음
    paths = sorted(
        root_path.rglob("*"),
        key=lambda p: len(p.parts),
        reverse=True
    )

    for old_path in paths:
        old_name = old_path.name
        new_name = replace_korean_name(old_name)

        # 변경할 내용이 없으면 건너뜀
        if old_name == new_name:
            continue

        new_path = old_path.with_name(new_name)

        print(f"[변경 예정] {old_path} -> {new_path}")

        if dry_run:
            continue

        if new_path.exists():
            print(f"[건너뜀] 이미 존재함: {new_path}")
            continue

        old_path.rename(new_path)
        print(f"[변경 완료] {old_path} -> {new_path}")


if __name__ == "__main__":
    # 1차 실행: 변경 예정 목록만 확인
    # rename_korean_bible_paths("data/openbible", dry_run=True)

    # 실제 변경하려면 위 줄을 주석 처리하고 아래 줄 사용
    rename_korean_bible_paths("data/bible/audio", dry_run=False)