"""Unit tests for the specification extractor fallback."""

from __future__ import annotations

import pytest

from app.services.specification_extractor import SpecificationExtractor


class DummyClient:
    """Simple Ollama client stub that always fails."""

    def generate(self, *args, **kwargs):  # pragma: no cover - executed indirectly
        raise RuntimeError("Model should not be called in fallback test")


@pytest.fixture
def extractor() -> SpecificationExtractor:
    return SpecificationExtractor(
        ollama_client=DummyClient(),
        model="dummy",
        prompt_template="{contract_text}",
        enable_fallback=True,
    )


def test_heuristic_extracts_block(extractor: SpecificationExtractor) -> None:
    contract_text = (
        "ДОГОВОР ПОСТАВКИ\n"
        "Приложение №1 Спецификация\n"
        "№   Наименование   Кол-во   Цена\n"
        "1   Стул офисный   10       1500\n"
        "2   Стол рабочий   5        3200\n"
        "Подписи сторон\n"
    )

    result = extractor.extract_specification(contract_text, prefer_model=False)

    assert "Стол рабочий" in result.specification_text
    assert result.used_fallback is True
    assert any("Стул" in " ".join(row) for row in result.table_rows)


def test_empty_contract_raises_value_error(extractor: SpecificationExtractor) -> None:
    with pytest.raises(ValueError):
        extractor.extract_specification("   ", prefer_model=False)