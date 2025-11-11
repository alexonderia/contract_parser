import ChatPanel from "./components/ChatPanel";

function App() {
  return (
    <div className="app-container">
      <header className="app-header">
        <h1>Contract Parser</h1>
        <p>
          Эта демо-страница отправляет ваши вопросы на Ollama, где запущена модель
          <code> qwen2.5:1.5b</code>.
        </p>
      </header>
      <main className="app-main">
        <ChatPanel />
      </main>
    </div>
  );
}

export default App;