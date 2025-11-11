import { type ChangeEvent, type FormEvent, useState } from "react";
import axios from "axios";
import { resolveApiUrl } from "../api/client";

interface ExtractionResponse {
  specification_text: string;
  table_rows: string[][];
  used_fallback: boolean;
  reasoning?: string | null;
}

function SpecificationExtractorPanel() {
  const [text, setText] = useState("");
  const [fileName, setFileName] = useState<string | null>(null);
  const [result, setResult] = useState<ExtractionResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!text.trim()) {
      setError("Пожалуйста, вставьте текст договора или загрузите файл.");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post(resolveApiUrl("/api/specification/extract"), {
        text,
        prefer_model: true,
      });
      setResult(response.data);
    } catch (err) {
      console.error(err);
      setError("Не удалось извлечь спецификацию. Проверьте подключение к серверу.");
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setFileName(file.name);
    const formData = new FormData();
    formData.append("file", file);
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await axios.post(resolveApiUrl("/api/specification/extract-file"), formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setResult(response.data);
      setText(response.data.specification_text ?? "");
    } catch (err) {
      console.error(err);
      setError("Не удалось обработать файл.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel">
      <h2>Извлечение спецификации</h2>
      <form className="form" onSubmit={handleSubmit}>
        <label className="form__label">
          Текст договора
          <textarea
            className="form__textarea"
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="Вставьте текст договора..."
            rows={10}
          />
        </label>
        <label className="form__label form__label--file">
          Загрузить файл
          <input type="file" accept=".txt" onChange={handleFileUpload} />
          {fileName && <span className="form__filename">Выбран: {fileName}</span>}
        </label>
        <button className="button" type="submit" disabled={loading}>
          {loading ? "Обработка..." : "Извлечь спецификацию"}
        </button>
      </form>
      {error && <p className="panel__error">{error}</p>}
      {result && (
        <div className="result">
          <h3>Найденный фрагмент</h3>
          <pre className="result__text">{result.specification_text || "Спецификация не найдена"}</pre>
          <div className="result__meta">
            <span>Источник: {result.used_fallback ? "эвристика" : "LLM"}</span>
            {result.reasoning && <span>Комментарий модели: {result.reasoning}</span>}
          </div>
          {result.table_rows.length > 0 && (
            <table className="result__table">
              <tbody>
                {result.table_rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((cell, cellIndex) => (
                      <td key={cellIndex}>{cell}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}

export default SpecificationExtractorPanel;