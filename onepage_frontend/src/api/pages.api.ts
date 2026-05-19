import { apiClient, unwrap } from "@/api/client";
import type { ElementDTO, LayoutJSON, PageResponse } from "@/types/backend";

export type SavePagePayload = {
  journal_id: string;
  title?: string;
  content_text?: string;
  layout_json?: LayoutJSON;
  elements?: ElementDTO[];
  weather?: Record<string, unknown>;
  mood?: string;
  page_date?: string;
};

export function createPage(payload: SavePagePayload) {
  return unwrap<PageResponse>(apiClient.post("/pages", payload));
}

export function updatePage(pageId: string, payload: Partial<SavePagePayload>) {
  return unwrap<PageResponse>(apiClient.put(`/pages/${pageId}`, payload));
}

export function getPage(pageId: string) {
  return unwrap<PageResponse & { elements?: ElementDTO[] }>(apiClient.get(`/pages/${pageId}`));
}

export function deletePage(pageId: string) {
  return unwrap<{ message: string }>(apiClient.delete(`/pages/${pageId}`));
}
