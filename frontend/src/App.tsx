import { type ChangeEvent, useEffect, useState } from "react";
import { fetchModels, selectModel, type ModelListResponse } from "./api/models";
import SimpleChatPanel from "./components/SimpleChatPanel";
import SpecificationPanel from "./components/SpecificationPanel";

function App() {
  const [activeView, setActiveView] = useState<"chat" | "specification">("chat");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [currentModel, setCurrentModel] = useState<string>("");
  const [isModelLoading, setIsModelLoading] = useState(false);
  const [modelError, setModelError] = useState<string | null>(null);

  const updateModels = async () => {
    setIsModelLoading(true);
    try {
      const payload = await fetchModels();
      setCurrentModel(payload.current);
      setAvailableModels(payload.available);
      setModelError(null);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Не удалось загрузить модели";
      setModelError(description);
    } finally {
      setIsModelLoading(false);
    }
  };

  useEffect(() => {
    void updateModels();
  }, []);

  const handleModelChange = async (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value;
    setCurrentModel(value);
    setIsModelLoading(true);

    const applyPayload = (payload: ModelListResponse) => {
      setCurrentModel(payload.current);
      setAvailableModels(payload.available);
      setModelError(null);
    };

    try {
      const payload = await selectModel(value);
      applyPayload(payload);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Не удалось выбрать модель";
      setModelError(description);
      await updateModels();
    } finally {
      setIsModelLoading(false);
    }
  };
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Contract Parser</h1>
        <p>
          Эта демо-страница отправляет ваши вопросы на Ollama. Выберите модель ниже,
          задайте вопрос или загрузите документ, чтобы получить структурированную спецификацию.
        </p>
        <div className="app-model-picker">
          <label className="app-model-picker__label" htmlFor="ollama-model">
            Модель Ollama
          </label>
          <select
            id="ollama-model"
            className="app-select"
            value={currentModel}
            onChange={handleModelChange}
            disabled={isModelLoading || availableModels.length === 0}
          >
            {availableModels.length === 0 ? (
              <option value="">Модели не найдены</option>
            ) : (
              availableModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))
            )}
          </select>
          <button
            className="app-model-picker__refresh"
            type="button"
            onClick={() => void updateModels()}
            disabled={isModelLoading}
            aria-label="Обновить список моделей"
          >
            ↻
          </button>
        </div>
        {modelError && <p className="app-model-picker__error">{modelError}</p>}
      </header>
      <nav className="app-nav">
        <button
          type="button"
          className={`app-nav__button${activeView === "chat" ? " app-nav__button--active" : ""}`}
          onClick={() => setActiveView("chat")}
        >
          Простой чат
        </button>
        <button
          type="button"
          className={`app-nav__button${activeView === "specification" ? " app-nav__button--active" : ""}`}
          onClick={() => setActiveView("specification")}
        >
          Спецификация
        </button>
      </nav>
      <main className="app-main">
        {activeView === "chat" ? <SimpleChatPanel /> : <SpecificationPanel />}
      </main>
    </div>
  );
}

export default App;