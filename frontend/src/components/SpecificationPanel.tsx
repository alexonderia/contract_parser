import { type ChangeEvent, useState } from "react";
import {
  uploadSpecificationDocument,
  type SpecificationExtractionResponse,
  type SpecificationMode,
  type SpecificationResponse,
  type LlmDebugInfo,
  type DocumentSection,
} from "../api/specification";
import SpecificationPreview from "./SpecificationPreview";
import DebugDetails from "./DebugDetails";

interface SpecificationResult {
  id: string;
  filename: string;
  summary: string;
  specification: SpecificationResponse;
  prompt?: string | null;
  debug?: LlmDebugInfo | null;
  exportedJsonName?: string | null;
  exportedJsonBase64?: string | null;
  sections?: DocumentSection[];
  combinedSectionsName?: string | null;
  combinedSectionsBase64?: string | null;
  combinedSectionsText?: string | null;
}

function formatSpecificationReply(
  result: SpecificationResponse,
  filename: string,
  mode: SpecificationMode,
  sections?: DocumentSection[],
): string {
  const parts = [
    `🔍 Найдена спецификация в документе «${filename}».`,
    `Режим: ${mode === "ai" ? "ИИ" : "встроенный анализ"}.`,
    `Таблиц: ${result.tables.length}.`,
  ];

  const firstAnchor = result.start_anchor;
  parts.push(
    `Начало: блок #${firstAnchor.index + 1} (${firstAnchor.type}). ` +
      `Конец: блок #${result.end_anchor.index + 1} (${result.end_anchor.type}).`,
  );

  if (sections && sections.length > 0) {
    const headerCount = sections.some((section) => section.number === null) ? 1 : 0;
    const numbered = sections.length - headerCount;
    parts.push(`Разделов: ${numbered} + шапка.`);
  }

  return parts.join(" ");
}

export default function SpecificationPanel() {
  const [specMode, setSpecMode] = useState<SpecificationMode>("ai");
  const [specPrompt, setSpecPrompt] = useState("");
  const [selectedSpecFile, setSelectedSpecFile] = useState<File | null>(null);
  const [results, setResults] = useState<SpecificationResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handlePromptFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    setSelectedSpecFile(file);
  };

  const handlePromptAndFileSubmit = async () => {
    if (!selectedSpecFile || isLoading) {
      if (!selectedSpecFile) {
        setError("Прикрепите документ для обработки промта");
      }
      return;
    }

    const promptText = specPrompt.trim();
    const file = selectedSpecFile;
    setIsLoading(true);
    setError(null);

    try {
      const result: SpecificationExtractionResponse = await uploadSpecificationDocument(
        file,
        specMode,
        promptText,
      );

      const summary = formatSpecificationReply(
        result.specification,
        file.name,
        specMode,
        result.sections,
      );

      const entry: SpecificationResult = {
        id: `${file.name}-${Date.now()}`,
        filename: file.name,
        summary,
        specification: result.specification,
        prompt: promptText || null,
        debug: result.debug,
        exportedJsonName: result.exported_json_name,
        exportedJsonBase64: result.exported_json_base64,
        sections: result.sections,
        combinedSectionsName: result.combined_sections_name,
        combinedSectionsBase64: result.combined_sections_base64,
        combinedSectionsText: result.combined_sections_text,
      };

      setResults((prev) => [entry, ...prev]);
      setSpecPrompt("");
      setSelectedSpecFile(null);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Не удалось обработать документ";
      setError(description);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="panel specification-panel">
      <h2>Извлечение спецификации</h2>
      <div className="spec-mode">
        <label htmlFor="spec-mode-select">Способ извлечения спецификации:</label>
        <select
          id="spec-mode-select"
          value={specMode}
          onChange={(event) => setSpecMode(event.target.value as SpecificationMode)}
          disabled={isLoading}
        >
          <option value="ai">ИИ (через модель)</option>
          <option value="internal">Внутренняя обработка</option>
        </select>
      </div>
      <div className="spec-request">
        <label htmlFor="spec-prompt">Промт для анализа документа:</label>
        <textarea
          id="spec-prompt"
          className="spec-request__input"
          placeholder="Опишите, что нужно найти в документе"
          value={specPrompt}
          onChange={(event) => setSpecPrompt(event.target.value)}
          rows={4}
          disabled={isLoading}
        />
        <label className={`file-uploader${isLoading ? " file-uploader--disabled" : ""}`}>
          <input
            type="file"
            accept=".docx,.txt,.md,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
            onChange={handlePromptFileChange}
            disabled={isLoading}
          />
          <span>
            {isLoading
              ? "Обработка файла..."
              : selectedSpecFile
              ? `📎 Файл: ${selectedSpecFile.name}`
              : "📎 Прикрепить документ"}
          </span>
        </label>
        <button
          className="button spec-request__submit"
          type="button"
          onClick={handlePromptAndFileSubmit}
          disabled={isLoading || !selectedSpecFile}
        >
          {isLoading ? "Отправка..." : "Отправить промт и файл"}
        </button>
      </div>
      {error && <p className="panel__error">{error}</p>}
      <div className="specification-panel__results">
        {results.length === 0 ? (
          <p className="specification-panel__placeholder">
            После отправки запроса сюда будет выведена найденная спецификация.
          </p>
        ) : (
          results.map((result) => (
            <article key={result.id} className="specification-panel__result">
              <p className="chat-message__summary">{result.summary}</p>
              {result.prompt ? (
                <div className="chat-message__prompt">
                  <span className="chat-message__prompt-label">Промт:</span>
                  <p className="chat-message__prompt-value">{result.prompt}</p>
                </div>
              ) : null}
              <SpecificationPreview
                filename={result.filename}
                specification={result.specification}
                exportedJsonName={result.exportedJsonName}
                exportedJsonBase64={result.exportedJsonBase64}
                sections={result.sections}
                combinedSectionsName={result.combinedSectionsName}
                combinedSectionsBase64={result.combinedSectionsBase64}
                combinedSectionsText={result.combinedSectionsText}
              />
              <DebugDetails debug={result.debug} />
            </article>
          ))
        )}
      </div>
    </div>
  );
}