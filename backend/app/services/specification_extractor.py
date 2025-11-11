"""Service for extracting specification blocks from contract text."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.services.ollama_client import OllamaClient, OllamaError

logger = logging.getLogger(__name__)


@dataclass
class SpecificationExtractionResult:
    """Normalized result returned by the extraction service."""

    specification_text: str
    table_rows: List[List[str]]
    used_fallback: bool
    raw_model_output: Optional[str] = None
    reasoning: Optional[str] = None


class SpecificationExtractor:
    """Extract the specification (table with product positions) from contracts."""

    STOP_WORDS = (
        "подпис",  # подписи сторон
        "реквизит",
        "условия",
        "порядок",
        "гарантии",
        "оплата",
        "ответственность",
        "заключительн",
    )

    def __init__(
        self,
        ollama_client: OllamaClient,
        *,
        model: str,
        prompt_template: str,
        enable_fallback: bool = True,
    ) -> None:
        self._ollama = ollama_client
        self._model = model
        self._prompt_template = prompt_template
        self._enable_fallback = enable_fallback

    # ------------------------------------------------------------------
    def extract_specification(self, text: str, *, prefer_model: bool = True) -> SpecificationExtractionResult:
        """Extract the specification block from the provided contract text."""

        text = text.strip()
        if not text:
            raise ValueError("Contract text is empty")

        model_output: Optional[str] = None
        reasoning: Optional[str] = None

        if prefer_model:
            prompt = self._prompt_template.replace("{contract_text}", text)
            logger.debug("Sending prompt to model '%s'", self._model)
            try:
                response = self._ollama.generate(
                    model=self._model,
                    prompt=prompt,
                    options={"temperature": 0.1},
                )
                model_output = response.response
                parsed = self._parse_model_response(model_output)
                if parsed:
                    sections = parsed.get("specification_sections") or []
                    if not isinstance(sections, list):
                        sections = [str(sections)]
                    cleaned_sections = [str(section).strip() for section in sections if str(section).strip()]
                    if cleaned_sections:
                        reasoning = parsed.get("notes") if reasoning is None else reasoning
                        logger.info("Specification extracted via LLM")
                        return SpecificationExtractionResult(
                            specification_text="\n\n".join(cleaned_sections),
                            table_rows=self._flatten_tables(parsed.get("tables", [])),
                            used_fallback=False,
                            raw_model_output=model_output,
                            reasoning=reasoning,
                        )
                    logger.warning("Model returned empty specification sections")
                logger.warning("Model returned an unexpected payload; falling back to heuristics")
            except OllamaError as exc:
                logger.warning("Model call failed: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive branch
                logger.warning("Unexpected error during model call: %s", exc)

        if not self._enable_fallback:
            raise OllamaError("Model response could not be parsed and heuristic fallback is disabled")

        logger.info("Running heuristic fallback extraction")
        block = self._heuristic_extract(text)
        table_rows = self._extract_table_rows(block)
        return SpecificationExtractionResult(
            specification_text=block,
            table_rows=table_rows,
            used_fallback=True,
            raw_model_output=model_output,
            reasoning=reasoning,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _parse_model_response(raw: str) -> Optional[Dict[str, Any]]:
        """Parse the JSON response returned by the model."""

        raw = raw.strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Model response is not a valid JSON: %s", raw)
            return None
        if not isinstance(parsed, dict):
            return None
        sections = parsed.get("specification_sections")
        if not sections:
            return parsed
        if isinstance(sections, list):
            parsed["specification_sections"] = [str(section).strip() for section in sections if str(section).strip()]
        return parsed

    @staticmethod
    def _flatten_tables(tables: Any) -> List[List[str]]:
        """Convert nested table definitions into a flat list of rows."""

        if not tables:
            return []
        flattened: List[List[str]] = []
        for table in tables:
            if isinstance(table, dict):
                rows = table.get("rows")
                if isinstance(rows, list):
                    for row in rows:
                        flattened.append([str(cell).strip() for cell in row if str(cell).strip()])
            elif isinstance(table, list):
                flattened.extend(
                    [[str(cell).strip() for cell in row if str(cell).strip()] for row in table]
                )
        return [row for row in flattened if row]

    def _heuristic_extract(self, text: str) -> str:
        """A deterministic fallback extractor based on simple patterns."""

        lines = [line.rstrip() for line in text.splitlines()]
        start_index = self._locate_start(lines)
        if start_index is None:
            logger.debug("Failed to locate specification start; returning empty string")
            return ""
        end_index = self._locate_end(lines, start_index)
        block = "\n".join(lines[start_index:end_index]).strip()
        logger.debug("Heuristic block extracted with length %s", len(block))
        return block

    def _locate_start(self, lines: List[str]) -> Optional[int]:
        pattern = re.compile(r"спецификац", re.IGNORECASE)
        for idx, line in enumerate(lines):
            if pattern.search(line):
                logger.debug("Found specification start at line %s", idx)
                return idx
        return None

    def _locate_end(self, lines: List[str], start_index: int) -> int:
        stop_pattern = re.compile("|".join(self.STOP_WORDS), re.IGNORECASE)
        for idx in range(start_index + 1, len(lines)):
            current = lines[idx].strip().lower()
            if not current:
                continue
            if stop_pattern.search(current) and idx - start_index > 5:
                logger.debug("Detected stop keyword at line %s", idx)
                return idx
        return len(lines)

    def _extract_table_rows(self, block: str) -> List[List[str]]:
        """Extract table-like rows from the heuristic block."""

        rows: List[List[str]] = []
        for line in block.splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            if "|" in cleaned:
                cells = [cell.strip() for cell in cleaned.split("|") if cell.strip()]
            else:
                cells = re.split(r"\s{3,}|\t", cleaned)
                cells = [cell.strip() for cell in cells if cell.strip()]
            digit_count = sum(char.isdigit() for char in cleaned)
            if len(cells) >= 2 and digit_count >= 2:
                rows.append(cells)
        return rows