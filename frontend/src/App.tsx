import ChatPanel from "./components/ChatPanel";
import SpecificationExtractorPanel from "./components/SpecificationExtractorPanel";
import "./App.css";

function App() {
  return (
    <div className="layout">
      <header className="layout__header">
        <h1>Contract Parser</h1>
        <p>Извлечение спецификаций из договоров и чат с моделью</p>
      </header>
      <main className="layout__content">
        <section className="layout__column">
          <SpecificationExtractorPanel />
        </section>
        <section className="layout__column">
          <ChatPanel />
        </section>
      </main>
    </div>
  );
}

export default App;