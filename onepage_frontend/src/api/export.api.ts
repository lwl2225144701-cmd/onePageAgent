import { apiClient, unwrap } from "@/api/client";

export type ExportTaskResponse = {
  task_id: string;
  status: string;
  created_at?: string | null;
};

export function createExport(pageId: string, format: "png" | "pdf" = "png") {
  return unwrap<ExportTaskResponse>(apiClient.post("/export", { page_id: pageId, format }));
}
