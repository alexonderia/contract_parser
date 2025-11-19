import type { LlmDebugInfo } from "../api/specification";

interface Props {
  debug?: LlmDebugInfo | null;
}

export default function DebugDetails({ debug }: Props) {
  if (!debug) {
    return null;
  }

  return (
    <details className="debug-details">
      <summary>Показать промпт и ответ</summary>
      <div className="debug-details__content">
        <section>
          <h4>Промпт (JSON)</h4>
          <pre>{JSON.stringify(debug.prompt, null, 2)}</pre>
        </section>
        <section>
          <h4>Ответ (JSON)</h4>
          <pre>{JSON.stringify(debug.response, null, 2)}</pre>
        </section>
      </div>
    </details>
  );
}