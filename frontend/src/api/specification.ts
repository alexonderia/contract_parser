import { resolveApiUrl } from "./client";

export type SpecificationMode = "ai" | "internal";

export interface LlmDebugInfo {
  prompt: Array<{ role: string; content: string }>;
  prompt_formatted: string;
  response: Record<string, unknown>;
  response_formatted: string;
}

export interface SpecificationAnchor {
  index: number;
  type: "paragraph" | "table";
  preview: string;
}

export interface SpecificationTable {
  index: number;
  row_count: number;
  column_count: number;
  preview: string;
  start_anchor: SpecificationAnchor;
  end_anchor: SpecificationAnchor;
  rows: string[][];
}

export interface SpecificationResponse {
  heading: string;
  start_anchor: SpecificationAnchor;
  end_anchor: SpecificationAnchor;
  tables: SpecificationTable[];
}

export interface SpecificationExtractionResponse {
  specification: SpecificationResponse;
  debug?: LlmDebugInfo | null;
}

export interface SpecificationFileResponse {
  specification: SpecificationResponse;
  cropped_file_name: string;
  cropped_file_base64: string;
}

export async function uploadSpecificationDocument(
  file: File,
  mode: SpecificationMode,
): Promise<SpecificationExtractionResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const endpoint = mode === "ai" ? "/api/specification/ai" : "/api/specification/internal";

  const response = await fetch(resolveApiUrl(endpoint), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? payload?.error ?? "Не удалось обработать документ";
    throw new Error(message);
  }

  return (await response.json()) as SpecificationExtractionResponse;
}