import { type KeyboardEventHandler, useMemo, useState } from "react";
import { resolveApiUrl } from "../api/client";

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
  } as const;
}

function ChatPanel() {
  const initial = useMemo(() => [welcomeMessage], []);
  const { messages, input, isLoading, error, setInput, sendMessage, handleKeyDown } = useChatState(initial);

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