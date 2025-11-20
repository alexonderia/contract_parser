import { type ChangeEvent, type KeyboardEventHandler, useState } from "react";
import { sendSimpleChatMessage, type ChatRole } from "../api/chat";
import type { LlmDebugInfo } from "../api/specification";
import DebugDetails from "./DebugDetails";

interface ChatTextMessage {
  kind: "text";
  role: ChatRole;
  content: string;
  attachments?: string[];
  debug?: LlmDebugInfo | null;
}

interface ChatResponsePart {
  label: string;
  content: string;
  debug?: LlmDebugInfo | null;
}

interface ChatDualMessage {
  kind: "dual";
  role: "assistant";
  primary: ChatResponsePart;
  secondary: ChatResponsePart;
}

type ChatMessage = ChatTextMessage | ChatDualMessage;

const welcomeMessage: ChatMessage = {
  kind: "text",
  role: "assistant",
  content: "Здравствуйте! Это простое окно чата для вопросов к модели Qwen2.5.",
};

export default function SimpleChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([welcomeMessage]);
  const [input, setInput] = useState("");
  const [primaryAttachment, setPrimaryAttachment] = useState<File | null>(null);
  const [secondaryAttachment, setSecondaryAttachment] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileChange = (
    event: ChangeEvent<HTMLInputElement>,
    setAttachment: (file: File | null) => void,
  ) => {
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

    const attachments = [primaryAttachment?.name, secondaryAttachment?.name].filter(Boolean) as string[];
    const userMessage: ChatMessage = {
      kind: "text",
      role: "user",
      content: trimmed,
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);
    setError(null);

    try {
      const primaryReply = await sendSimpleChatMessage(
        trimmed,
        primaryAttachment ? { file: primaryAttachment } : undefined,
      );
      let secondaryReplyContent: ChatResponsePart | null = null;

      if (secondaryAttachment) {
        try {
          const secondaryReply = await sendSimpleChatMessage(trimmed, { file: secondaryAttachment });
          secondaryReplyContent = {
            label: secondaryAttachment.name,
            content: secondaryReply.reply || "(пустой ответ)",
            debug: secondaryReply.debug ?? null,
          };
        } catch (secondaryError) {
          const description =
            secondaryError instanceof Error
              ? secondaryError.message
              : "Не удалось получить ответ для второго файла";
          secondaryReplyContent = {
            label: secondaryAttachment.name,
            content: `⚠️ Ошибка при обработке второго файла: ${description}`,
            debug: null,
          };
          setError(description);
        }
      }

      const combinedMessage: ChatDualMessage = {
        kind: "dual",
        role: "assistant",
        primary: {
          label: primaryAttachment?.name ?? "Промт без файла",
          content: primaryReply.reply || "(пустой ответ)",
          debug: primaryReply.debug ?? null,
        },
        secondary:
          secondaryReplyContent ?? {
            label: secondaryAttachment?.name ?? "Второй файл",
            content: secondaryAttachment
              ? "Ответ для второго файла не получен"
              : "Второй файл не был выбран",
            debug: null,
          },
      };

      setMessages((prev) => [...prev, combinedMessage]);
      setPrimaryAttachment(null);
      setSecondaryAttachment(null);
    } catch (err) {
      const description = err instanceof Error ? err.message : "Произошла неизвестная ошибка";
      setError(description);
      setMessages((prev) => [
        ...prev,
        {
          kind: "text",
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
        {messages.map((message, index) => {
          if (message.kind === "dual") {
            return (
              <div key={`${message.role}-${index}`} className="chat-message chat-message--assistant">
                <strong>Модель</strong>
                <div className="chat-dual-response">
                  {[message.primary, message.secondary].map((part, partIndex) => (
                    <div key={part.label + partIndex} className="chat-dual-response__column">
                      <div className="chat-dual-response__header">{part.label}</div>
                      <p>{part.content}</p>
                      <DebugDetails debug={part.debug} />
                    </div>
                  ))}
                </div>
              </div>
            );
          }

          return (
            <div key={`${message.role}-${index}`} className={`chat-message chat-message--${message.role}`}>
              <strong>{message.role === "user" ? "Вы" : "Модель"}</strong>
              <div className="chat-message__content">
                <p>{message.content}</p>
                {message.attachments && message.attachments.length > 0 && (
                  <div className="chat-attachments">
                    <span>Файлы:</span>
                    <ul>
                      {message.attachments.map((name) => (
                        <li key={name}>{name}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <DebugDetails debug={message.debug} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="chat-panel__inputs">
        <div className="chat-panel__uploaders">
          <label className={`file-uploader${isLoading ? " file-uploader--disabled" : ""}`}>
            <input
              type="file"
              onChange={(event) => handleFileChange(event, setPrimaryAttachment)}
              disabled={isLoading}
            />
            <span>
              {isLoading
                ? "Загрузка..."
                : primaryAttachment
                ? `📎 Файл 1: ${primaryAttachment.name}`
                : "📎 Прикрепить файл 1"}
            </span>
          </label>
          <label className={`file-uploader${isLoading ? " file-uploader--disabled" : ""}`}>
            <input
              type="file"
              onChange={(event) => handleFileChange(event, setSecondaryAttachment)}
              disabled={isLoading}
            />
            <span>
              {isLoading
                ? "Загрузка..."
                : secondaryAttachment
                ? `📎 Файл 2: ${secondaryAttachment.name}`
                : "📎 Прикрепить файл 2"}
            </span>
          </label>
        </div>
        <textarea
          className="chat-panel__input"
          placeholder="Введите сообщение и нажмите Enter"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
        />
        <div className="chat-panel__actions">
          <button className="button" type="button" onClick={sendMessage} disabled={isLoading}>
            {isLoading ? "Отправка..." : "Отправить"}
          </button>
        </div>
      </div>
      {error && <p className="panel__error">{error}</p>}
    </div>
  );
}