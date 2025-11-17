"""Utilities for exporting specification tables into standalone JSON files."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .schemas import SpecificationResponse, SpecificationTable

_DEFAULT_EXPORT_DIR = Path(__file__).resolve().parent / "exports"

_KEYWORDS = {
    "name": ("наимен", "описан", "товар", "продук", "предмет", "работ"),
    "qty": ("кол", "кол-во", "колич"),
    "unit": ("ед", "изм"),
    "price": ("цена", "за 1 ед"),
    "amount": ("сумма", "всего"),
    "country": ("страна", "происх", "изгот", "завод"),
    "period": ("срок", "постав", "период", "достав"),
}

_WHITESPACE_RE = re.compile(r"\s+")
_NUMERIC_RE = re.compile(r"[^0-9,.-]")


def _sanitize_stem(value: str) -> str:
    """Превращает имя файла в безопасное(без пробелов)."""

    sanitized = re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "_", value).strip("._")
    return sanitized or "specification"


def _ensure_export_dir(path: Path | None) -> Path:
    """Создает папку, если ее нет."""
    export_dir = Path(path or _DEFAULT_EXPORT_DIR)
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def _normalize(text: str | None) -> str:
    """Очищение строки от пробелов."""
    if not text:
        return ""
    return _WHITESPACE_RE.sub(" ", text).strip()


def _parse_decimal(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = _NUMERIC_RE.sub("", value.replace("\u00A0", " "))
    cleaned = cleaned.replace(" ", "").replace(",", ".").strip()
    if not cleaned or cleaned in {"-", ".", "+"}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def _normalize_number(value: float | None) -> float | int | None:
    if value is None:
        return None
    rounded = round(value, 2)
    if abs(rounded - round(rounded)) < 1e-6:
        return int(round(rounded))
    return rounded


def _infer_columns(header: list[str]) -> dict[str, int]:
    columns: dict[str, int] = {}
    for index, cell in enumerate(header):
        normalized = _normalize(cell).casefold()
        for field, keywords in _KEYWORDS.items():
            if field in columns:
                continue
            if any(keyword in normalized for keyword in keywords):
                columns[field] = index
    return columns

def _is_merged_row(row: list[str]) -> bool:
    """
    Строка считается объединённой (merged row), если:
    - Все непустые ячейки одинаковые после нормализации.
    """
    normalized = [_normalize(cell) for cell in row if cell and _normalize(cell)]
    if not normalized:
        return False

    # Все ячейки одинаковые → merged row
    return len(set(normalized)) == 1


def _is_summary_row(row: list[str]) -> bool:
    text = " ".join(_normalize(cell).casefold() for cell in row)
    return (
        "итого" in text
        or "всего" in text
        or "ндс" in text
        or "налог" in text
        or text.startswith("итог")
    )


def _split_body_and_summary(rows: list[list[str]]) -> tuple[list[list[str]], list[list[str]]]:
    if not rows:
        return [], []

    body = list(rows)
    summary: list[list[str]] = []

    while body:
        candidate = body[-1]
        row_text = " ".join(_normalize(cell).casefold() for cell in candidate)
        if not row_text:
            body.pop()
            continue
        if "итого" in row_text or "ндс" in row_text:
            summary.insert(0, body.pop())
            continue
        break

    return body, summary


def _extract_summary_value(row: list[str]) -> float | None:
    for cell in reversed(row):
        value = _parse_decimal(cell)
        if value is not None:
            return value
    return None


def _extract_total(summary_rows: Iterable[list[str]]) -> float | None:
    for row in summary_rows:
        row_text = " ".join(_normalize(cell).casefold() for cell in row)
        if "итого" in row_text:
            return _extract_summary_value(row)
    return None


def _extract_vat_percent(summary_rows: Iterable[list[str]]) -> int | None:
    for row in summary_rows:
        text = " ".join(_normalize(cell).casefold() for cell in row)

        if "ндс" not in text:
            continue

        # Ищем число сразу после слова НДС
        match = re.search(r"ндс[^0-9]{0,10}(\d{1,3})\s*%?", text)
        if match:
            return int(match.group(1))

    return None

def _find_vat_percent_anywhere(rows: list[list[str]]) -> int | None:
    """
    Ищет процент НДС в любой строке таблицы.
    """
    for row in rows:
        text = " ".join(_normalize(cell).casefold() for cell in row)

        if "ндс" not in text:
            continue

        match = re.search(r"ндс[^0-9]{0,10}(\d{1,3})\s*%?", text)
        if match:
            return int(match.group(1))

    return None

def _count_itogo_rows(rows: list[list[str]]) -> int:
    """
    Считает количество строк в таблице, где встречается 'итого'.
    """
    count = 0
    for row in rows:
        text = " ".join(_normalize(cell).casefold() for cell in row)
        if "итого" in text:
            count += 1
    return count

def _extract_items(table: SpecificationTable) -> tuple[list[dict[str, object]], float | None, int | None]:
    rows = table.rows or []
    if not rows:
        return [], None, None

    body, summary = _split_body_and_summary(rows)
    if not body:
        return [], _extract_total(summary), _extract_vat_percent(summary)

    header, *data_rows = body
    columns = _infer_columns(header)
    items: list[dict[str, object]] = []

    for row in data_rows:
        if _is_merged_row(row):
            continue
        if _is_summary_row(row):
            continue
        name_index = columns.get("name")
        name = _normalize(row[name_index]) if name_index is not None and name_index < len(row) else ""
        if not name:
            continue

        item: dict[str, object] = {"name": name}

        qty_index = columns.get("qty")
        if qty_index is not None and qty_index < len(row):
            qty_value = _normalize_number(_parse_decimal(row[qty_index]))
            if qty_value is not None:
                item["qty"] = qty_value

        unit_index = columns.get("unit")
        if unit_index is not None and unit_index < len(row):
            unit_value = _normalize(row[unit_index])
            if unit_value:
                item["unit"] = unit_value

        price_index = columns.get("price")
        if price_index is not None and price_index < len(row):
            price_value = _normalize_number(_parse_decimal(row[price_index]))
            if price_value is not None:
                item["price"] = price_value

        amount_index = columns.get("amount")
        if amount_index is not None and amount_index < len(row):
            amount_value = _normalize_number(_parse_decimal(row[amount_index]))
            if amount_value is not None:
                item["amount"] = amount_value

        country_index = columns.get("country")
        if country_index is not None and country_index < len(row):
            country_value = _normalize(row[country_index])
            if country_value:
                item["country"] = country_value

        period_index = columns.get("period")
        if period_index is not None and period_index < len(row):
            period_value = _normalize(row[period_index])
            if period_value:
                item["period"] = period_value

        items.append(item)

    total = _extract_total(summary)
    vat_percent = _extract_vat_percent(summary)
    if vat_percent is None:
        vat_percent = _find_vat_percent_anywhere(rows)

    if _count_itogo_rows(rows) > 1:
        total = None
        vat_percent = None
    return items, total, vat_percent


def _pick_filename(source_name: str | None, stem_fallback: str) -> str:
    stem = Path(source_name or "").stem or stem_fallback
    sanitized = _sanitize_stem(stem)
    return f"{sanitized}_specification.json"


def _next_available_path(directory: Path, filename: str) -> Path:
    candidate = directory / filename
    if not candidate.exists():
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 1
    while True:
        updated = directory / f"{stem}_{counter}{suffix}"
        if not updated.exists():
            return updated
        counter += 1


def export_specification_to_json(
    specification: SpecificationResponse,
    *,
    source_filename: str | None = None,
    export_dir: Path | None = None,
) -> tuple[Path, bytes] | None:
    """Create a JSON document containing only the extracted specification tables."""

    if not specification.tables:
        return None

    all_items: list[dict[str, object]] = []
    total_values: list[float] = []
    vat_values: list[int] = []

    for table in specification.tables:
        items, total, vat_percent = _extract_items(table)
        all_items.extend(items)
        if total is not None:
            total_values.append(total)
        if vat_percent is not None:
            vat_values.append(vat_percent)

    if not all_items and not total_values and not vat_values:
        return None    

    payload = {
        "items": all_items,
        "total": None if not total_values else _normalize_number(sum(total_values)),
        "vat": None if not vat_values else vat_values[0],
    }

    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

    export_directory = _ensure_export_dir(export_dir)
    filename = _pick_filename(source_filename, specification.heading or "specification")
    target_path = _next_available_path(export_directory, filename)
    target_path.write_bytes(data)

    return target_path, data

__all__ = ["export_specification_to_json"]