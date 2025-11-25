"""Utilities for slicing documents into numbered contract sections."""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from ..document.models import Block
from ..document.reader import blocks_to_prompt_lines_with_mapping
from ..schemas import DocumentSection, SpecificationResponse

_SECTION_HEADING_RE = re.compile(r"^(?P<number>\d{1,2})\.\s(?P<title>.+)")
_SECTION_BREAK_RE = re.compile(r"Приложение № 1")

@dataclass(slots=True)
class SectionChunk:
    """Extracted section text with optional numbering."""

    number: int | None
    title: str
    content: str


def split_into_sections(
    blocks: list[Block],
    *,
    max_section_number: int = 15,
) -> list[SectionChunk]:
    """Split document blocks into numbered sections and a header.

    Parameters
    ----------
    blocks:
        Parsed document blocks preserving original order.
    stop_before_index:
        Optional block index where section parsing should stop (useful to skip
        specification appendices).
    max_section_number:
        Upper bound for recognized section numbers. Content after that is ignored.
    """

    lines, mapping = blocks_to_prompt_lines_with_mapping(blocks)

    sections: list[SectionChunk] = []
    current_lines: list[str] = []
    current_number: int | None = None
    current_title = "Шапка"
    header_saved = False

    def flush_section() -> None:
        nonlocal current_lines, current_number, current_title, header_saved
        content = "\n".join(line for line in current_lines if line).strip()
        if content or (current_number is None and not header_saved):
            sections.append(
                SectionChunk(number=current_number, title=current_title, content=content)
            )
            if current_number is None:
                header_saved = True
        current_lines = []

    for line, (block_index, _) in zip(lines, mapping):
        
        if _SECTION_BREAK_RE.match(line):
            flush_section()
            break

        heading_match = _SECTION_HEADING_RE.match(line)
        if heading_match:
            number = int(heading_match.group("number"))
            

            flush_section()
            current_number = number
            raw_title = heading_match.group("title")
            current_title = raw_title.strip() or f"Раздел {number}"
            current_lines = [line]
            continue

        current_lines.append(line)

    flush_section()
    return sections


def _sanitize(value: str) -> str:
    sanitized = re.sub(r"[^0-9A-Za-zА-Яа-я_-]+", "_", value).strip("._")
    return sanitized or "section"


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

def _load_instruction_text(number: int | None) -> str | None:
    """Return predefined instruction text for a section number if available."""

    index = number or 0
    instructions_dir = Path(__file__).resolve().parent / "instractions"
    path = instructions_dir / f"{index}.txt"
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return None

def export_sections_to_txt(
    sections: list[SectionChunk],
    *,
    source_filename: str | None = None,
    export_dir: Path | None = None,
) -> list[tuple[SectionChunk, Path]]:
    """Persist each section into a standalone UTF-8 encoded text file."""

    if not sections:
        return []

    base_directory = _resolve_export_dir(export_dir)

    stem = Path(source_filename or "document").stem or "document"
    sanitized_stem = _sanitize(stem)

    exported: list[tuple[SectionChunk, Path]] = []
    for section in sections:
        suffix = "header" if section.number is None else f"section_{section.number:02d}"
        title_part = _sanitize(section.title)[:50]
        filename = f"{sanitized_stem}_{suffix}"
        if title_part:
            filename += f"_{title_part}"
        target = _next_available_path(base_directory, f"{filename}.txt")
        target.write_text(section.content, encoding="utf-8")
        exported.append((section, target))

    return exported


def build_sections_instruction(
    sections: list[SectionChunk], specification_text: str | None = None
) -> str:
    """Собирает все разделы и спецификацию в один текст по заданному шаблону."""

    parts: list[str] = []
    for section in sections:
        is_header = section.number is None
        instruction_label = "шапке" if is_header else f"разделу {section.number}"
        section_label = "Шапка" if is_header else f"Раздел {section.number}"
        # parts.append(f"Инструкция к {instruction_label}:")
        instruction_text = _load_instruction_text(section.number)
        if instruction_text:
            parts.append(instruction_text)
        parts.append(f"{section_label}:")
        parts.append(section.content or "(раздел пуст)")
        parts.append("")

    if specification_text:
        parts.append("Инструкция к спецификации:")
        instruction_text = _load_instruction_text(16)
        if instruction_text:
            parts.append(instruction_text)
        parts.append("TITLE: Приложение №1 Спецификация:")
        parts.append(specification_text)

    return "\n".join(parts).rstrip()


def export_sections_bundle(
    sections: list[SectionChunk],
    *,
    source_filename: str | None = None,
    export_dir: Path | None = None,
    specification_text: str | None = None,
) -> tuple[Path, str] | None:
    """Сохраняет все разделы в один txt-файл и возвращает путь и содержимое."""

    if not sections:
        return None

    base_directory = _resolve_export_dir(export_dir)

    stem = Path(source_filename or "document").stem or "document"
    sanitized_stem = _sanitize(stem)
    content = build_sections_instruction(sections, specification_text)
    target = _next_available_path(base_directory, f"{sanitized_stem}_sections.txt")
    target.write_text(content, encoding="utf-8")

    return target, content

def _resolve_export_dir(export_dir: Path | None) -> Path:
    base_directory = Path(
        export_dir
        or os.getenv("SECTIONS_EXPORT_DIR")
        or Path(__file__).resolve().parent / "exports"
    )
    base_directory.mkdir(parents=True, exist_ok=True)
    return base_directory

def export_sections_with_specification(
    *,
    sections: list[DocumentSection] | list[SectionChunk] | None,
    specification: SpecificationResponse | None,
    source_filename: str | None = None,
    export_dir: Path | None = None,
    filename_hash: str | None = None,
) -> Path | None:
    """Persist sections and specification into a single JSON file.

    The resulting file name is based on the provided ``filename_hash`` when supplied
    (``<hash>.json``). Otherwise, it falls back to a sanitized source stem with a
    ``_sections.json`` suffix. Content is stored in UTF-8 inside the export
    directory, which is created if missing.
    """

    if not sections and not specification:
        return None

    base_directory = _resolve_export_dir(export_dir)

    def _normalize_section(item: DocumentSection | SectionChunk) -> dict[str, object]:
        return {
            "number": getattr(item, "number", None),
            "title": getattr(item, "title", ""),
            "content": getattr(item, "content", ""),
        }

    payload = {
        "source_filename": source_filename,
        "sections": [_normalize_section(item) for item in sections or []],
        "specification": specification.dict() if specification else None,
    }

    if filename_hash:
        filename = f"{filename_hash}.json"
        target = base_directory / filename
    else:
        stem = Path(source_filename or "document").stem or "document"
        sanitized_stem = _sanitize(stem)
        target = _next_available_path(base_directory, f"{sanitized_stem}_sections.json")

    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target

def import_sections_with_specification(
    *,
    filename_hash: str,
    export_dir: Path | None = None,
) -> tuple[list[DocumentSection], SpecificationResponse | None, str] | None:
    """Load cached sections/specification bundle by hash if it exists."""

    if not filename_hash:
        return None

    base_directory = _resolve_export_dir(export_dir)
    candidate = base_directory / f"{filename_hash}.json"
    if not candidate.exists():
        return None

    try:
        raw_payload = candidate.read_text(encoding="utf-8")
        data = json.loads(raw_payload)
    except (OSError, json.JSONDecodeError):
        return None

    sections_data = data.get("sections") or []
    specification_data = data.get("specification")

    sections = [
        DocumentSection(
            number=item.get("number"),
            title=item.get("title", ""),
            content=item.get("content", ""),
            filename=None,
        )
        for item in sections_data
        if isinstance(item, dict)
    ]

    specification = None
    if isinstance(specification_data, dict):
        try:
            specification = SpecificationResponse.parse_obj(specification_data)
        except Exception:  # pragma: no cover - defensive parsing
            specification = None

    return sections, specification, raw_payload

__all__ = [
    "SectionChunk",
    "split_into_sections",
    "export_sections_to_txt",
    "export_sections_bundle",
    "export_sections_with_specification",
    "import_sections_with_specification",
    "build_sections_instruction",
]