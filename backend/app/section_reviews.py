"""Helpers for evaluating section instructions via LLM and building HTML reports."""
from __future__ import annotations

import html
import json
import math
import re
from typing import Iterable

import httpx

from .llm_utils import build_debug_info, extract_reply
from .ollama import client
from .schemas import LlmDebugInfo, SectionReview


def _parse_titles(source: str) -> list[str]:
    """Extract section titles from the combined instruction file."""

    pattern = re.compile(r"^(Шапка|Раздел\s+\d+|Спецификация):", re.MULTILINE)
    titles: list[str] = []
    for match in pattern.finditer(source):
        titles.append(match.group(1))
    return titles


def _coerce_to_list(payload: object) -> list[dict]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        return [payload]
    return []


def _extract_response_payload(text: str) -> tuple[list[dict], str | None]:
    """Parse model response into section items and optional red flags."""

    try:
        parsed = json.loads(text)
        inaccuracy = _coerce_inaccuracy(parsed)
        red_flags = _coerce_red_flags(parsed)
        items = _extract_items_from_parsed(parsed)
        filtered = [item for item in items if _looks_like_section(item)]
        if filtered:
            return filtered, inaccuracy, red_flags
    except json.JSONDecodeError:
        pass

    matches = re.findall(r"\{[^{}]*\}", text, flags=re.DOTALL)
    items: list[dict] = []
    inaccuracy: str | None = None
    red_flags: str | None = None
    for chunk in matches:
        try:
            parsed = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            possible_inaccuracy = _coerce_inaccuracy(parsed)
            inaccuracy = inaccuracy or possible_inaccuracy
            possible_flags = _coerce_red_flags(parsed)
            red_flags = red_flags or possible_flags
            if _looks_like_section(parsed):
                items.append(parsed)
    return items, inaccuracy, red_flags


def _extract_items_from_parsed(parsed: object) -> list[dict]:
    if isinstance(parsed, dict):
        if "sections" in parsed and isinstance(parsed["sections"], list):
            return _coerce_to_list(parsed["sections"])
        if "items" in parsed and isinstance(parsed["items"], list):
            return _coerce_to_list(parsed["items"])
        if "reviews" in parsed and isinstance(parsed["reviews"], list):
            return _coerce_to_list(parsed["reviews"])
        return _coerce_to_list(parsed)
    return _coerce_to_list(parsed)


def _coerce_red_flags(parsed: object) -> str | None:
    if isinstance(parsed, dict):
        for key in ("red_flags", "RED_FLAGS"):
            if key in parsed and parsed[key]:
                value = parsed[key]
                if isinstance(value, list):
                    return "; ".join(str(item) for item in value if str(item).strip()).strip() or None
                return str(value).strip() or None
    return None

def _coerce_inaccuracy(parsed: object) -> str | None:
    if isinstance(parsed, dict):
        for key in ("inaccuracy", "INACCURACY"):
            if key in parsed and parsed[key]:
                value = parsed[key]
                if isinstance(value, list):
                    return "; ".join(str(item) for item in value if str(item).strip()).strip() or None
                return str(value).strip() or None
    return None


def _looks_like_section(item: dict) -> bool:
    return any(key in item for key in ("title", "resume", "risks", "score"))


def _normalize_reviews(raw_items: Iterable[dict], titles: list[str]) -> list[SectionReview]:
    normalized: list[SectionReview] = []
    padded_items = list(raw_items)
    if titles and len(padded_items) < len(titles):
        padded_items.extend({} for _ in range(len(titles) - len(padded_items)))

    for index, item in enumerate(padded_items):
        fallback_title = titles[index] if index < len(titles) else f"Раздел {index + 1}"
        title = str(item.get("title") or fallback_title)
        resume = str(item.get("resume") or "").strip()
        risks = str(item.get("risks") or "").strip()
        score = str(item.get("score") or "").strip()
        normalized.append(
            SectionReview(
                title=title or f"Раздел {index + 1}",
                resume=resume,
                risks=risks,
                score=score,
            )
        )
    return normalized


def _extract_numeric_score(score: str) -> float | None:
    match = re.search(r"([0-9]+(?:[\.,][0-9]+)?)", score)
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _calculate_average_score(reviews: list[SectionReview]) -> float | None:
    values = [value for review in reviews if (value := _extract_numeric_score(review.score)) is not None]
    if not values:
        return None
    return round(sum(values) / len(values), 2)


def _score_to_color(score: float | None) -> str:
    if score is None or math.isnan(score):
        return "#f3f4f6"
    clamped = max(1.0, min(10.0, score))
    hue = 0 + (120 * (clamped - 1) / 9)
    return f"hsl({hue:.0f}, 75%, 90%)"


def _build_html_report(
    reviews: list[SectionReview],
    overall_score: float | None,
    inaccuracy: str | None,
    red_flags: str | None,
    document_html: str | None = None,
) -> str:
    cards = []
    for review in reviews:
        score_numeric = _extract_numeric_score(review.score)
        bg_color = _score_to_color(score_numeric)
        card = f"""
        <section class=\"section-card\" style=\"background:{bg_color}\">
            <h2>{html.escape(review.title)}</h2>
            <div class=\"section-card__score\">Оценка: {html.escape(review.score) or "-"}</div>
            <div class=\"section-card__block\">
                <h3>Резюме</h3>
                <p>{html.escape(review.resume) or "(пусто)"}</p>
            </div>
            <div class=\"section-card__block\">
                <h3>Риски</h3>
                <p>{html.escape(review.risks) or "(пусто)"}</p>
            </div>
        </section>
        """
        cards.append(card)

    cards_html = "\n".join(cards)

    inaccuracy_block = ""
    if inaccuracy:
        inaccuracy_block = f"""
        <section class=\"red-flags\">
            <h2>INACCURACY</h2>
            <p>{html.escape(inaccuracy)}</p>
        </section>
        """

    red_flags_block = ""
    if red_flags:
        red_flags_block = f"""
        <section class=\"red-flags\">
            <h2>RED_FLAGS</h2>
            <p>{html.escape(red_flags)}</p>
        </section>
        """

    document_section = ""
    if document_html:
        document_section = f"""
        <details class=\"document-panel\">
            <summary>Текст документа</summary>
            <div class=\"document-panel__content\">{document_html}</div>
        </details>
        """

    overall_display = (
        f"{overall_score:.2f}" if overall_score is not None else "нет данных"
    )
    overall_bg = _score_to_color(overall_score if overall_score is not None else None)
    return f"""
<!doctype html>
<html lang=\"ru\">
<head>
    <meta charset=\"utf-8\" />
    <title>Отчет по разделам</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Helvetica', sans-serif;
            background: #f5f7fa;
            margin: 0;
            padding: 24px;
        }}
        h1 {{
            margin: 0 0 16px;
            font-size: 24px;
        }}
        .layout {{
            max-width: 960px;
            margin: 0 auto;
        }}
        .overall-score {{
            background: {overall_bg};
            border-radius: 12px;
            padding: 16px;
            border: 1px solid #e5e7eb;
            margin-bottom: 20px;
            font-weight: 700;
            font-size: 18px;
        }}
        .document-panel {{
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 12px 16px;
            margin: 12px 0 20px;
            background: #fff;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }}
        .document-panel summary {{
            cursor: pointer;
            font-weight: 700;
            outline: none;
        }}
        .document-panel__content {{
            margin-top: 12px;
            max-height: 420px;
            overflow: auto;
            padding: 12px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            background: #f9fafb;
        }}
        .document-panel__content p {{
            margin: 0 0 10px;
            line-height: 1.5;
        }}
        .document-panel__content table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 10px;
            background: #fff;
        }}
        .document-panel__content td {{
            border: 1px solid #d1d5db;
            padding: 6px 8px;
        }}
        .section-card {{
            border: 1px solid #e5e7eb;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 16px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
        }}
        .section-card__score {{
            display: inline-block;
            padding: 4px 10px;
            margin: 6px 0 12px;
            border-radius: 20px;
            background: rgba(0,0,0,0.08);
            color: #111827;
            font-weight: 600;
        }}
        .section-card__block h3 {{
            margin: 0 0 6px;
            font-size: 16px;
        }}
        .section-card__block p {{
            margin: 0 0 12px;
            line-height: 1.5;
            white-space: pre-line;
        }}
        .red-flags {{
            margin-top: 24px;
            padding: 16px;
            border-radius: 12px;
            border: 1px solid #f87171;
            background: #fef2f2;
            color: #991b1b;
        }}
        .debug {{
            margin-top: 24px;
            padding: 12px;
            border-radius: 12px;
            background: #0f172a;
            color: #e2e8f0;
        }}
        .debug pre {{
            white-space: pre-wrap;
            background: rgba(255,255,255,0.05);
            padding: 12px;
            border-radius: 8px;
            color: #e2e8f0;
        }}
    </style>
</head>
<body>
    <div class=\"layout\">
        <h1>Отчет по оценке разделов</h1>
        <div class=\"overall-score\">Средняя оценка: {overall_display}</div>
        {document_section}
        {cards_html}
        {inaccuracy_block}
        {red_flags_block}
    </div>
</body>
</html>
""".strip()


async def evaluate_section_file(
    content: str,
    document_html: str | None = None,
) -> tuple[list[SectionReview], float | None, str | None, str, LlmDebugInfo | None]:
    """Send the combined instruction file to LLM and build an HTML report."""

    titles = _parse_titles(content)
    system_prompt = (
        "Ты юрист. Проанализируй шапку, каждый раздел документа и спецификацию после строки 'Инструкция'. "
        "Верни JSON с ключом sections (массив объектов со свойствами title, resume, risks, score, "
        "где score — целое число от 1 до 10) и опциональными ключами INACCURACY (строка или массив), "
        "который содержит перечень ключевых несоответствий по всему документу. RED_FLAGS (строка или массив),"
        "который выводит только ошибку по общей сумме, если она разная на протяжении документа, и ошибку по Сторонам (Покупатель и Поставщик)"
        "если они разные на протяжении документа, в противном случае оставь данный пункт пустым." 
        "Внимание: RED_FLAGS заполнять только если есть ошибки! Если ошибок нет, оставить пустым. Если есть любые другие замечания, кроме суммы и сторон - игнорируй их."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": content},
    ]

    try:
        raw = await client.chat(messages)
    except httpx.HTTPStatusError as exc:  # pragma: no cover - defensive logging
        raise
    debug = build_debug_info(messages, raw)
    reply = extract_reply(raw)
    raw_items, inaccuracy, red_flags = _extract_response_payload(reply)
    if not raw_items and titles:
        raw_items = [{} for _ in titles]
    reviews = _normalize_reviews(raw_items, titles)
    average_score = _calculate_average_score(reviews)
    html_report = _build_html_report(
        reviews,
        average_score,
        inaccuracy,
        red_flags,
        document_html,
    )
    return reviews, average_score, inaccuracy, red_flags, html_report, debug


__all__ = ["evaluate_section_file"]