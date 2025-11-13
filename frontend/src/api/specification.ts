import { resolveApiUrl } from "./client";

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

export interface SpecificationFileResponse {
  specification: SpecificationResponse;
  cropped_file_name: string;
  cropped_file_base64: string;
}

export async function uploadSpecificationDocument(file: File): Promise<SpecificationResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(resolveApiUrl("/api/specification"), {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.detail ?? payload?.error
    throw new Error(message);
  }

  return (await response.json()) as SpecificationResponse;

}