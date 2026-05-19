import { apiClient, unwrap } from "@/api/client";
import type { JournalResponse, PaginatedResponse } from "@/types/backend";

export function listJournals(page = 1, size = 20) {
  return unwrap<PaginatedResponse<JournalResponse>>(apiClient.get("/journals", { params: { page, size } }));
}

export function createJournal(name: string, settings?: Record<string, unknown>) {
  return unwrap<JournalResponse>(apiClient.post("/journals", { name, settings }));
}

export function getJournal(journalId: string) {
  return unwrap<JournalResponse & { pages?: Array<Record<string, unknown>> }>(apiClient.get(`/journals/${journalId}`));
}

export function deleteJournal(journalId: string) {
  return unwrap<{ message: string }>(apiClient.delete(`/journals/${journalId}`));
}
