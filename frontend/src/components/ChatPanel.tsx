import {
  type ChangeEvent,
  type KeyboardEventHandler,
  useMemo,
  useState,
} from "react";
import {
  uploadSpecificationDocument,
  type SpecificationResponse,
} from "../api/specification";
import SpecificationPreview from "./SpecificationPreview";
import {
  type ChatHistoryMessage,
  type ChatReply,
  type ChatRole,
  sendChatMessage,
  sendSimpleChatMessage,
} from "../api/chat";


interface BaseChatMessage {
  role: ChatRole;
  content: string;
}

type TextChatMessage = BaseChatMessage & {
  kind: "text";
};

type SpecificationChatMessage = BaseChatMessage & {
  kind: "specification";
  filename: string;
  specification: SpecificationResponse;
  
};

type ChatMessage = TextChatMessage | SpecificationChatMessage;

const welcomeMessage: ChatMessage = {
  role: "assistant",
  kind: "text",
  content: "Здравствуйте! Задайте вопрос, и я отвечу, используя модель Qwen2.5.",
};

const historyLimit = 8;


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
    
    const userMessage: ChatMessage = { role: "user", kind: "text", content: trimmed };
    const payloadHistory = messages.slice(-(historyLimit - 1));
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const historyPayload: ChatHistoryMessage[] = payloadHistory.map((item) => ({
        role: item.role,
        content: item.content,
      }));
      const hasUserHistory = historyPayload.some((item) => item.role === "user");

      let reply: ChatReply;
      if (!hasUserHistory) {
        reply = await sendSimpleChatMessage(trimmed);
      } else {
        reply = await sendChatMessage(trimmed, historyPayload);
      }
      setMessages((prev) => [
        ...prev,
        { role: "assistant", kind: "text", content: reply.reply || "(пустой ответ)" },
      ]);
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
  const parts = [
    `🔍 Найдена спецификация в документе «${filename}».`,
    `Таблиц: ${result.tables.length}.`,
  ];

  const firstAnchor = result.tables[0]?.start_anchor ?? result.start_anchor;
  parts.push(
    `Начало: блок #${firstAnchor.index + 1} (${firstAnchor.type}). ` +
      `Конец: блок #${result.end_anchor.index + 1} (${result.end_anchor.type}).`,
  );

  return parts.join(" ");
}

function ChatPanel() {
  const initial = useMemo(() => [welcomeMessage], []);
  const {
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
  } = useChatState(initial);

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || isLoading) {
      return;
    }

    setMessages((prev) => [
      ...prev,
      { role: "user", kind: "text", content: `📄 Загрузил файл «${file.name}»` },
    ]);
    setIsLoading(true);
    setError(null);

    try {
      const result = await uploadSpecificationDocument(file);
      const summary = formatSpecificationReply(result.specification, file.name);
      
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          kind: "specification",
          content: summary,
          filename: file.name,
          specification: result,
        },
      ]);

    } catch (err) {
      const description = err instanceof Error ? err.message : "Не удалось обработать документ";
      setError(description);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          kind: "text",
          content: `⚠️ Не удалось проанализировать документ: ${description}`,
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="panel chat-panel">
      <h2>Чат</h2>
      <div className="chat-panel__messages">
        {messages.map((message, index) => (
          <div
            key={`${message.kind}-${index}`}
            className={`chat-message chat-message--${message.role}`}
          >
            <strong>{message.role === "user" ? "Вы" : "Модель"}</strong>
            {message.kind === "specification" ? (
              <div className="chat-message__specification">
                <p className="chat-message__summary">{message.content}</p>
                <SpecificationPreview
                  filename={message.filename}
                  specification={message.specification}
                />
              </div>
            ) : (
              <p>{message.content}</p>
            )}
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