import { resolveApiUrl } from "./client";

export interface ModelListResponse {
  current: string;
  available: string[];
}

async function handleResponse(response: Response): Promise<ModelListResponse> {
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const message = data?.detail ?? data?.error ?? "Не удалось получить список моделей";
    throw new Error(message);
  }

  return (await response.json()) as ModelListResponse;
}

export async function fetchModels(): Promise<ModelListResponse> {
  const response = await fetch(resolveApiUrl("/api/models"));
  return handleResponse(response);
}

export async function selectModel(model: string): Promise<ModelListResponse> {
  const response = await fetch(resolveApiUrl("/api/models/select"), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ model }),
  });

  return handleResponse(response);
}