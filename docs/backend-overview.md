# Backend architecture overview

This document summarises the key pieces of the backend after the refactor that
separates internal document processing from neural processing.

## API surface

The FastAPI application exposes the following relevant endpoints:

| Endpoint | Description |
| --- | --- |
| `POST /api/chat` | General chat endpoint that forwards the full conversation history to the configured LLM. |
| `POST /api/chat/simple` | Convenience endpoint that sends a single user message (optionally with a system prompt) to the LLM. |
| `POST /api/specification/ai` | Extracts specification anchors by delegating to the neural model. Returns both the parsed result and debug information with the exact prompt and model response. |
| `POST /api/specification/internal` | Extracts specification anchors using the internal parser without involving the LLM. |
| `GET /api/health` | Verifies Ollama connectivity and that the target model is available. |

Both chat endpoints include structured debug information so that the frontend can
show the raw prompt and the unmodified LLM reply.

## Module layout

- `api/` — domain-specific routers for chat, specification extraction, section
  review, and health checks.
- `core/` — application settings, logging bootstrap, and shared exceptions.
- `document/` — shared document models, readers, utils, and the specification
  extractor used by internal flows.
- `services/` — higher-level business logic including LLM-based specification
  detection, section reviews, and export helpers.
- `llm/` — Ollama client wrapper, response utilities, and prompt assets.
- `schemas/` — Pydantic models grouped by domain (chat, sections,
  specification, and shared types).
- `main.py` — FastAPI application with middleware and router wiring.

## Debug payloads

Both neural specification extraction and regular chat responses return
`LlmDebugInfo`. The object contains:

- `prompt` — raw JSON that is sent to the model.
- `prompt_formatted` — the same payload formatted with indentation for easier
  reading.
- `response` — the LLM response as received.
- `response_formatted` — pretty-printed representation used for logging and UI
  display.

This data is logged server-side and returned to the frontend so that developers
can inspect prompts during debugging.