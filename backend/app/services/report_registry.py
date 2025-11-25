"""YAML registry for cached section bundles and rendered HTML reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .section_splitter import _resolve_export_dir

_REGISTRY_FILENAME = "processed_files.yml"


@dataclass
class ReportRegistryEntry:
    file_hash: str
    sections_filename: str
    source_filename: str | None
    report_filename: str
    last_checked_at: str
    last_used_at: str
    overall_score: float | None = None
    inaccuracy: str | None = None
    red_flags: str | None = None


def _registry_path(export_dir: Path | None = None) -> Path:
    base_directory = _resolve_export_dir(export_dir)
    return base_directory / _REGISTRY_FILENAME


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_entry(raw: dict[str, Any]) -> ReportRegistryEntry | None:
    if not isinstance(raw, dict):
        return None

    required_fields = ("file_hash", "sections_filename", "report_filename")
    if not all(field in raw for field in required_fields):
        return None

    file_hash = str(raw.get("file_hash") or "").strip()
    sections_filename = str(raw.get("sections_filename") or "").strip()
    report_filename = str(raw.get("report_filename") or "").strip()

    if not file_hash or not sections_filename or not report_filename:
        return None

    source_filename = raw.get("source_filename")
    if source_filename is not None:
        source_filename = str(source_filename)

    last_checked_at = str(raw.get("last_checked_at") or "") or _now_iso()
    last_used_at = str(raw.get("last_used_at") or "") or last_checked_at

    overall_score = raw.get("overall_score")
    try:
        overall_score = float(overall_score) if overall_score is not None else None
    except (TypeError, ValueError):
        overall_score = None

    inaccuracy = raw.get("inaccuracy")
    if inaccuracy is not None:
        inaccuracy = str(inaccuracy)

    red_flags = raw.get("red_flags")
    if red_flags is not None:
        red_flags = str(red_flags)

    return ReportRegistryEntry(
        file_hash=file_hash,
        sections_filename=sections_filename,
        source_filename=source_filename,
        report_filename=report_filename,
        last_checked_at=last_checked_at,
        last_used_at=last_used_at,
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
    )


def load_registry(export_dir: Path | None = None) -> dict[str, ReportRegistryEntry]:
    path = _registry_path(export_dir)
    if not path.exists():
        return {}

    try:
        raw_content = path.read_text(encoding="utf-8")
    except OSError:
        return {}

    try:
        payload = yaml.safe_load(raw_content) or []
    except yaml.YAMLError:
        return {}

    entries: dict[str, ReportRegistryEntry] = {}
    if isinstance(payload, list):
        for item in payload:
            entry = _normalize_entry(item)
            if entry:
                entries[entry.file_hash] = entry

    return entries


def _dump_registry(entries: dict[str, ReportRegistryEntry], export_dir: Path | None = None) -> Path:
    path = _registry_path(export_dir)
    data = [
        {
            "file_hash": entry.file_hash,
            "sections_filename": entry.sections_filename,
            "source_filename": entry.source_filename,
            "report_filename": entry.report_filename,
            "last_checked_at": entry.last_checked_at,
            "last_used_at": entry.last_used_at,
            "overall_score": entry.overall_score,
            "inaccuracy": entry.inaccuracy,
            "red_flags": entry.red_flags,
        }
        for entry in sorted(entries.values(), key=lambda item: item.file_hash)
    ]
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return path


def record_report_generation(
    *,
    file_hash: str,
    sections_filename: str,
    source_filename: str | None,
    report_filename: str,
    overall_score: float | None = None,
    inaccuracy: str | None = None,
    red_flags: str | None = None,
    export_dir: Path | None = None,
) -> ReportRegistryEntry:
    entries = load_registry(export_dir)
    now = _now_iso()
    updated = ReportRegistryEntry(
        file_hash=file_hash,
        sections_filename=sections_filename,
        source_filename=source_filename,
        report_filename=report_filename,
        last_checked_at=now,
        last_used_at=now,
        overall_score=overall_score,
        inaccuracy=inaccuracy,
        red_flags=red_flags,
    )
    entries[file_hash] = updated
    _dump_registry(entries, export_dir)
    return updated


def update_last_used(
    *, file_hash: str, export_dir: Path | None = None
) -> ReportRegistryEntry | None:
    entries = load_registry(export_dir)
    if file_hash not in entries:
        return None

    entry = entries[file_hash]
    entry.last_used_at = _now_iso()
    entries[file_hash] = entry
    _dump_registry(entries, export_dir)
    return entry


def fetch_cached_report_html(
    *, file_hash: str, export_dir: Path | None = None
) -> tuple[str, ReportRegistryEntry] | None:
    entries = load_registry(export_dir)
    entry = entries.get(file_hash)
    if not entry:
        return None

    try:
        report_path = _resolve_export_dir(export_dir) / entry.report_filename
        if not report_path.exists():
            return None
        html = report_path.read_text(encoding="utf-8")
    except OSError:
        return None

    entry.last_used_at = _now_iso()
    entries[file_hash] = entry
    _dump_registry(entries, export_dir)
    return html, entry


__all__ = [
    "ReportRegistryEntry",
    "fetch_cached_report_html",
    "load_registry",
    "record_report_generation",
    "update_last_used",
]