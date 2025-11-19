import { type ChangeEvent, type KeyboardEventHandler, useState } from "react";
import { sendSimpleChatMessage, type ChatRole } from "../api/chat";
import type { LlmDebugInfo } from "../api/specification";
import DebugDetails from "./DebugDetails";

interface ChatMessage {
  role: ChatRole;
  content: string;
  debug?: LlmDebugInfo | null;
}

const welcomeMessage: ChatMessage = {
  role: "assistant",
  content: "Здравствуйте! Это простое окно чата для вопросов к модели Qwen2.5.",
};

export default function SimpleChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [attachment, setAttachment] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    event.target.value = "";
    setAttachment(file);
  };

  const handleKeyDown: KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  const sendMessage = async () => {
    const trimmed = input.trim();
    if (!trimmed || isLoading) {
      return;
    }

    const userMessage: ChatMessage = { role: "user", content: trimmed };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const reply = await sendSimpleChatMessage(
        trimmed,
        attachment ? { file: attachment } : undefined,
      );
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: reply.reply || "(пустой ответ)", debug: reply.debug },
      ]);
      setAttachment(null);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Произошла неизвестная ошибка";
      setError(description);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `⚠️ Не удалось получить ответ: ${description}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="panel chat-panel">
      <h2>Простой чат</h2>
      <div className="chat-panel__messages">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`chat-message chat-message--${message.role}`}>
            <strong>{message.role === "user" ? "Вы" : "Модель"}</strong>
            <div>
              <p>{message.content}</p>
              <DebugDetails debug={message.debug} />
            </div>
          </div>
        ))}
      </div>
      <label className={`file-uploader${isLoading ? " file-uploader--disabled" : ""}`}>
        <input type="file" onChange={handleFileChange} disabled={isLoading} />
        <span>
          {isLoading
            ? "Загрузка..."
            : attachment
            ? `📎 Файл для сообщения: ${attachment.name}`
            : "📎 Прикрепить файл к сообщению"}
        </span>
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