import { resolveApiUrl } from "./client";

export type ChatRole = "user" | "assistant" | "system";

export interface ChatHistoryMessage {
  role: ChatRole;
  content: string;
}

export interface ChatReply {
  reply: string;
  raw: Record<string, unknown>;
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

export async function sendSimpleChatMessage(message: string, systemPrompt?: string): Promise<ChatReply> {
  const payload: { message: string; system_prompt?: string } = { message };
  if (systemPrompt && systemPrompt.trim()) {
    payload.system_prompt = systemPrompt.trim();
  }

  const response = await fetch(resolveApiUrl("/api/chat/simple"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  return handleResponse(response);
}