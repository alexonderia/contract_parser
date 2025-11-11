import { useState } from "react";
import axios from "axios";
import { resolveApiUrl } from "../api/client";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

const initialMessages: ChatMessage[] = [
  {
    role: "assistant",
    content: "Здравствуйте! Я помогу вам извлечь спецификацию из договора или ответить на вопросы.",
  },
];

function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const sendMessage = async () => {
    if (!input.trim()) {
      return;
    }
    const nextMessages = [...messages, { role: "user" as const, content: input }];
    setMessages(nextMessages);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const response = await axios.post(resolveApiUrl("/api/chat"), {
        message: input,
        history: nextMessages.slice(-5).map((message) => ({
          role: message.role,
          content: message.content,
        })),
      });
      const reply: ChatMessage = {
        role: "assistant",
        content: response.data.reply ?? "",
      };
      setMessages((prev) => [...prev, reply]);
    } catch (err) {
      console.error(err);
      setError("Не удалось получить ответ. Проверьте подключение к серверу.");
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown: React.KeyboardEventHandler<HTMLTextAreaElement> = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage();
    }
  };

  return (
    <div className="panel">
      <h2>Чат с моделью</h2>
      <div className="chat-panel__messages">
        {messages.map((message, index) => (
          <div key={index} className={`chat-message chat-message--${message.role}`}>
            <strong>{message.role === "user" ? "Вы" : "Модель"}</strong>
            <p>{message.content}</p>
          </div>
        ))}
      </div>
      <textarea
        className="chat-panel__input"
        placeholder="Напишите сообщение..."
        value={input}
        onChange={(event) => setInput(event.target.value)}
        onKeyDown={handleKeyDown}
        rows={3}
      />
      <button className="button" onClick={sendMessage} disabled={loading}>
        {loading ? "Отправка..." : "Отправить"}
      </button>
      {error && <p className="panel__error">{error}</p>}
    </div>
  );
}

export default ChatPanel;