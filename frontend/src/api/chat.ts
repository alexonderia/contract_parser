import { resolveApiUrl } from "./client";
import type { LlmDebugInfo } from "./specification";

export type ChatRole = "user" | "assistant" | "system";

export interface ChatHistoryMessage {
  role: ChatRole;
  content: string;
}

export interface ChatReply {
  reply: string;
  raw: Record<string, unknown>;
  debug?: LlmDebugInfo | null;
}

async function handleResponse(response: Response): Promise<ChatReply> {
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const message = data?.detail ?? data?.error ?? "Не удалось получить ответ от сервера";
    throw new Error(message);
  }

  return (await response.json()) as ChatReply;
}

export async function sendChatMessage(message: string, history: ChatHistoryMessage[]): Promise<ChatReply> {
  const payload = {
    message,
    history,
  };

  const response = await fetch(resolveApiUrl("/api/chat"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response);
}

interface SimpleChatOptions {
  systemPrompt?: string;
  file?: File | null;
}

export async function sendSimpleChatMessage(
  message: string,
  options?: SimpleChatOptions,
): Promise<ChatReply> {

  const trimmedPrompt = options?.systemPrompt?.trim() || "";
  const file = options?.file ?? null;

  const formData = new FormData();

  // backend всегда ждёт message_form
  formData.append("message_form", message);

  if (trimmedPrompt.length > 0) {
    formData.append("system_prompt_form", trimmedPrompt);
  }

  // файл необязателен
  if (file) {
    formData.append("file", file);
  }

  const response = await fetch(resolveApiUrl("/api/chat/simple"), {
    method: "POST",
    body: formData,
  });

  return handleResponse(response);
}
