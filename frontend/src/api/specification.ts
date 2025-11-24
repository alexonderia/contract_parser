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

export interface DocumentSection {
  number: number | null;
  title: string;
  content: string;
  filename?: string | null;
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
  exported_json_name?: string | null;
  exported_json_base64?: string | null;
  sections?: DocumentSection[];
  combined_sections_name?: string | null;
  combined_sections_base64?: string | null;
  combined_sections_text?: string | null;
}

export interface SpecificationFileResponse {
  specification: SpecificationResponse;
  cropped_file_name: string;
  cropped_file_base64: string;
}

export interface SectionReview {
  title: string;
  resume: string;
  risks: string;
  score: string;
}

export interface SectionReviewResponse {
  reviews: SectionReview[];
  overall_score?: number | null;
  red_flags?: string | null;
  html: string;
  debug?: LlmDebugInfo | null;
}

export interface FullProcessingResponse {
  specification_text?: string | null;
  docx_text?: string | null;
  overall_score?: number | null;
  inaccuracy?: string | null;
  red_flags?: string | null;
  html: string;
  debug?: LlmDebugInfo | null;
}

export async function uploadSpecificationDocument(
  file: File,
  mode: SpecificationMode,
  prompt?: string,
): Promise<SpecificationExtractionResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (prompt && prompt.trim()) {
    formData.append("prompt", prompt.trim());
  }

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

export async function uploadInstructionFile(
  file: File,
): Promise<SectionReviewResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(resolveApiUrl("/api/sections/review"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? payload?.error ?? "Не удалось обработать файл";
    throw new Error(message);
  }

  return (await response.json()) as SectionReviewResponse;
}

export async function processFullContract(
  file: File,
): Promise<FullProcessingResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(resolveApiUrl("/api/sections/full"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? payload?.error ?? "Не удалось обработать договор";
    throw new Error(message);
  }

  return (await response.json()) as FullProcessingResponse;
}