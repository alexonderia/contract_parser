import { useState } from "react";
import SimpleChatPanel from "./components/SimpleChatPanel";
import SpecificationPanel from "./components/SpecificationPanel";

function App() {
  const [activeView, setActiveView] = useState<"chat" | "specification">("chat");
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Contract Parser</h1>
        <p>
          Эта демо-страница отправляет ваши вопросы на Ollama, где запущена модель
          <code> qwen2.5:1.5b</code>. Задайте вопрос или загрузите документ, чтобы
          получить структурированную спецификацию.
        </p>
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