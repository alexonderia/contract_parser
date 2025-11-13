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

- `document_models.py` — shared data structures representing document blocks.
- `document_processing.py` — helper functions that turn DOCX/TXT files into
  normalised blocks or plain text lines for prompting.
- `document_parser.py` — rule-based detector that locates specification tables
  inside the parsed document.
- `specification_builder.py` — converts the parser result into Pydantic
  responses.
- `neural_specification.py` — prepares prompts for the LLM, validates its JSON
  response and emits debug metadata.
- `llm_utils.py` — utilities for extracting the textual answer from the LLM and
  assembling debug payloads.
- `ollama.py` — asynchronous HTTP client used by the backend.
- `main.py` — FastAPI application with middleware and endpoint wiring.

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