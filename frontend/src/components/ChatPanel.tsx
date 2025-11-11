import {
  type ChangeEvent,
  type KeyboardEventHandler,
  useMemo,
  useState,
} from "react";
import { resolveApiUrl } from "../api/client";
import { uploadSpecificationDocument, type SpecificationResponse } from "../api/specification";

type ChatRole = "user" | "assistant";

interface ChatMessage {
  role: ChatRole;
  content: string;
}

const welcomeMessage: ChatMessage = {
  role: "assistant",
  content: "Здравствуйте! Задайте вопрос, и я отвечу, используя модель Qwen2.5.",
};

const historyLimit = 6;

async function requestModelReply(payload: { message: string; history: ChatMessage[] }): Promise<string> {
  const response = await fetch(resolveApiUrl("/api/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new Error(data?.detail ?? data?.error ?? "Не удалось получить ответ от сервера");
  }

  const data = await response.json();
  return data.reply ?? "";
}

function useChatState(initialMessages: ChatMessage[]) {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) {
      return;
    }
    
    const userMessage: ChatMessage = { role: "user", content: trimmed };
    const payloadHistory = messages.slice(-(historyLimit - 1));
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const reply = await requestModelReply({
        message: trimmed,
        history: payloadHistory,
      });
      setMessages((prev) => [...prev, { role: "assistant", content: reply || "(пустой ответ)" }]);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Произошла неизвестная ошибка";
      setError(description);
    } finally {
      setIsLoading(false);
    }
  };
  const handleKeyDown: KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  return {
    messages,
    input,
    isLoading,
    error,
    setInput,
    sendMessage,
    handleKeyDown,
    setMessages,
    setError,
    setIsLoading,
  } as const;
}

function formatSpecificationReply(result: SpecificationResponse, filename: string): string {
  const lines = [
    `📎 Документ «${filename}»`,
    "🔍 Найден раздел «Спецификация»:",
    `• Заголовок: ${result.heading}`,
    `• Начало (#${result.start_anchor.index + 1}, ${result.start_anchor.type === "table" ? "таблица" : "параграф"}): ${result.start_anchor.preview}`,
    `• Конец (#${result.end_anchor.index + 1}, ${result.end_anchor.type === "table" ? "таблица" : "параграф"}): ${result.end_anchor.preview}`,
    `• Таблиц в разделе: ${result.tables.length}`,
  ];

  if (result.tables.length > 0) {
    lines.push("", "Таблицы:");
    result.tables.forEach((table, idx) => {
      lines.push(
        `  ${idx + 1}. #${table.index + 1} — ${table.row_count}×${table.column_count} строк/столбцов`,
        `     ↳ начало (#${table.start_anchor.index + 1}, ${table.start_anchor.type}): ${table.start_anchor.preview}`,
        `     ↳ конец (#${table.end_anchor.index + 1}, ${table.end_anchor.type}): ${table.end_anchor.preview}`,
        `     Предпросмотр: ${table.preview}`,
      );

      if (table.rows.length > 0) {
        const rowPreview = table.rows.slice(0, 5);
        rowPreview.forEach((row, rowIndex) => {
          lines.push(`     [${rowIndex + 1}] ${row.join(" | ")}`);
        });
        if (table.rows.length > rowPreview.length) {
          lines.push(`     … ещё ${table.rows.length - rowPreview.length} строк(и)`);
        }
      }
    });
  }

  return lines.join("\n");
}

function ChatPanel() {
  const initial = useMemo(() => [welcomeMessage], []);
  const { messages, input, isLoading, error, setInput, sendMessage, handleKeyDown, setMessages, setError, setIsLoading } =
    useChatState(initial);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || isLoading) {
      return;
    }

    setMessages((prev) => [...prev, { role: "user", content: `📄 Загрузил файл «${file.name}»` }]);
    setIsLoading(true);
    setError(null);

    try {
      const result = await uploadSpecificationDocument(file);
      const formatted = formatSpecificationReply(result, file.name);
      setMessages((prev) => [...prev, { role: "assistant", content: formatted }]);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Не удалось обработать документ";
      setError(description);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠️ Не удалось проанализировать документ: ${description}` },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="panel chat-panel">
      <h2>Чат с Qwen2.5</h2>
      <div className="chat-panel__messages">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`chat-message chat-message--${message.role}`}>
            <strong>{message.role === "user" ? "Вы" : "Модель"}</strong>
            <p>{message.content}</p>
          </div>
        ))}
      </div>
      <label className={`file-uploader${isLoading ? " file-uploader--disabled" : ""}`}>
        <input
          type="file"
          accept=".docx,.txt,.md,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
          onChange={handleFileChange}
          disabled={isLoading}
        />
        <span>{isLoading ? "Обработка файла..." : "📎 Прикрепить документ"}</span>
      </label>
      <textarea
        className="chat-panel__input"
        placeholder="Введите сообщение и нажмите Enter"
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
      />
      <button className="button" type="button" onClick={sendMessage} disabled={isLoading}>
        {isLoading ? "Отправка..." : "Отправить"}
      </button>
      {error && <p className="panel__error">{error}</p>}
    </div>
  );
}
export default ChatPanel;