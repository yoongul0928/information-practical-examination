import json
import re
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup, Tag


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_URL = "https://chobopark.tistory.com/540"
QUESTION_START_RE = re.compile(r"^([1-9]|1[0-9]|20)\.\s*")
TITLE_INFO_RE = re.compile(r"\[(\d{4})년\s+(\d+)회\]")


def fetch_html(url: str) -> str:
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/135.0.0.0 Safari/537.36"
            )
        },
    )
    response.raise_for_status()
    return response.text


def find_article_body(soup: BeautifulSoup) -> Tag:
    selectors = [
        "div.tt_article_useless_p_margin",
        "div.article-view",
        "article",
        "div.entry-content",
    ]
    for selector in selectors:
        node = soup.select_one(selector)
        if node:
            return node
    raise ValueError("본문 영역을 찾지 못했습니다.")


def extract_exam_info(soup: BeautifulSoup) -> tuple[str, str]:
    title_text = ""

    if soup.title and soup.title.string:
        title_text = soup.title.string.strip()

    if not title_text:
        heading = soup.select_one("h1")
        if heading:
            title_text = heading.get_text(" ", strip=True)

    match = TITLE_INFO_RE.search(title_text)
    if not match:
        raise ValueError(f"제목에서 연도/회차를 추출하지 못했습니다: {title_text}")

    year = match.group(1)
    round_no = match.group(2).zfill(2)
    return year, round_no


def normalize_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def normalize_code_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")
    return text.rstrip()


def is_empty_block(tag: Tag) -> bool:
    text = normalize_text(tag.get_text(" ", strip=True))
    has_image = tag.find("img") is not None
    has_iframe = tag.find("iframe") is not None
    return not text and not has_image and not has_iframe


def cleaned_html(tag: Tag) -> str:
    copied = BeautifulSoup(str(tag), "html.parser")

    for inner in list(copied.find_all(True)):
        if inner.name in {"img", "iframe"}:
            continue

        text = normalize_text(inner.get_text(" ", strip=True))
        has_image = inner.find("img") is not None
        has_iframe = inner.find("iframe") is not None
        if not text and not has_image and not has_iframe:
            inner.decompose()

    return str(copied).strip()


def is_question_start(tag: Tag) -> int | None:
    bold = tag.find("b")
    if not bold:
        return None

    bold_text = normalize_text(bold.get_text(" ", strip=True))
    match = QUESTION_START_RE.match(bold_text)
    if not match:
        return None

    return int(match.group(1))


def collect_question_blocks(article: Tag) -> dict[int, list[str]]:
    question_blocks = {number: [] for number in range(1, 21)}
    current_number = None

    # article 바로 아래 블록을 순서대로 읽으면서
    # <b> 안의 `1.` ~ `20.`를 문제 시작점으로 사용한다.
    for child in article.children:
        if not isinstance(child, Tag):
            continue

        question_number = is_question_start(child)
        if question_number is not None:
            current_number = question_number

        if current_number is None or current_number > 20:
            continue

        if is_empty_block(child):
            continue

        block_html = cleaned_html(child)
        if block_html:
            question_blocks[current_number].append(block_html)
            if current_number == 20 and 'data-ke-type="moreLess"' in block_html:
                break

    return question_blocks


def html_to_text(html_blocks: list[str]) -> str:
    text_parts = []
    for html in html_blocks:
        soup = BeautifulSoup(html, "html.parser")
        text = normalize_text(soup.get_text("\n", strip=True))
        if text:
            text_parts.append(text)
    return "\n".join(text_parts).strip()


def extract_code_from_colorscripter(code_block: Tag) -> str:
    line_nodes = code_block.select("td:nth-of-type(2) > div > div")
    lines = []

    for node in line_nodes:
        line = normalize_code_text(node.get_text("", strip=False))
        lines.append(line)

    return "\n".join(lines).strip("\n")


def extract_code_from_html(html_blocks: list[str]) -> tuple[list[str], str]:
    cleaned_blocks = []
    code_parts = []

    for html in html_blocks:
        soup = BeautifulSoup(html, "html.parser")

        for code_block in soup.select("div.colorscripter-code"):
            code_text = extract_code_from_colorscripter(code_block)
            if code_text:
                code_parts.append(code_text)
            code_block.decompose()

        for pre_block in soup.find_all("pre"):
            code_text = normalize_code_text(pre_block.get_text("\n", strip=False))
            if code_text:
                code_parts.append(code_text)
            pre_block.decompose()

        cleaned_html = str(soup).strip()
        if cleaned_html and normalize_text(soup.get_text(" ", strip=True)):
            cleaned_blocks.append(cleaned_html)

    return cleaned_blocks, "\n\n".join(part for part in code_parts if part).strip()


def collect_images(html_blocks: list[str]) -> list[str]:
    images = []
    for html in html_blocks:
        soup = BeautifulSoup(html, "html.parser")
        for image in soup.find_all("img"):
            src = image.get("src")
            if src and src not in images:
                images.append(src)
    return images


def split_moreless_block(block_html: str) -> tuple[str, str]:
    soup = BeautifulSoup(block_html, "html.parser")
    moreless = soup.select_one('div[data-ke-type="moreLess"]')
    if moreless is None:
        return block_html.strip(), ""

    answer_parts = []
    content = moreless.select_one(".moreless-content")
    if content is not None:
        for child in content.contents:
            if isinstance(child, Tag):
                child_html = cleaned_html(child)
                if child_html:
                    answer_parts.append(child_html)

    moreless.decompose()
    question_html = str(soup).strip()
    answer_html = "\n".join(answer_parts).strip()
    return question_html, answer_html


def split_question_and_answer(blocks: list[str]) -> tuple[list[str], list[str]]:
    question_html = []
    answer_html = []

    for block_html in blocks:
        question_part, answer_part = split_moreless_block(block_html)
        if question_part:
            question_html.append(question_part)
        if answer_part:
            answer_html.append(answer_part)

    return question_html, answer_html


def build_question_record(number: int, blocks: list[str]) -> dict:
    question_html, answer_html = split_question_and_answer(blocks)
    question_html, code = extract_code_from_html(question_html)

    return {
        "number": number,
        "text": html_to_text(question_html),
        "question_html": "\n".join(question_html).strip(),
        "options": "",
        "images": collect_images(question_html),
        "code": code or None,
        "answer": html_to_text(answer_html),
        "answer_html": "\n".join(answer_html).strip(),
    }


def parse_questions(article: Tag) -> list[dict]:
    question_blocks = collect_question_blocks(article)
    questions = []

    for number in range(1, 21):
        blocks = question_blocks[number]
        if not blocks:
            continue
        questions.append(build_question_record(number, blocks))

    return questions


def build_payload(questions: list[dict], source_url: str) -> dict:
    return {
        "metadata": {
            "crawl_time": datetime.now().isoformat(),
            "source": source_url,
            "total_questions": len(questions),
        },
        "questions": questions,
    }


def save_payload(payload: dict, year: str, round_no: str) -> Path:
    output_dir = BASE_DIR / "questions"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"questions_{year}_{round_no}.json"
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def crawl_url(url = DEFAULT_URL) -> None:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")
    year, round_no = extract_exam_info(soup)
    article = find_article_body(soup)
    questions = parse_questions(article)
    payload = build_payload(questions, url)
    output_path = save_payload(payload, year, round_no)

    print(f"saved: {output_path}")
    print(f"questions: {len(questions)}")
    print(f"exam: {year}-{round_no}")


if __name__ == "__main__":
    urls = [
        "https://chobopark.tistory.com/540",
        "https://chobopark.tistory.com/554",
        "https://chobopark.tistory.com/558",
        "https://chobopark.tistory.com/476",
        "https://chobopark.tistory.com/483",
        "https://chobopark.tistory.com/495",
        "https://chobopark.tistory.com/372",
        "https://chobopark.tistory.com/420",
        "https://chobopark.tistory.com/453",
        "https://chobopark.tistory.com/271",
        "https://chobopark.tistory.com/423",
        "https://chobopark.tistory.com/424",
        "https://chobopark.tistory.com/191",
        "https://chobopark.tistory.com/210",
        "https://chobopark.tistory.com/217",
        "https://chobopark.tistory.com/196",
        "https://chobopark.tistory.com/195",
        "https://chobopark.tistory.com/194"
    ]
    for url in urls:
        crawl_url(url)
