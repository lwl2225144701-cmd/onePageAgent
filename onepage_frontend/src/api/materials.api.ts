import { apiClient, unwrap } from "@/api/client";
import type { MaterialGroup, MaterialResponse, PaginatedResponse } from "@/types/backend";

export function listMaterials(params: { type?: string; style?: string; emotion?: string; scene?: string } = {}) {
  return unwrap<PaginatedResponse<MaterialResponse>>(apiClient.get("/materials", { params }));
}

export function recommendMaterials(params: { style?: string; emotion?: string; scene?: string; weather?: string } = {}) {
  return unwrap<MaterialGroup[]>(apiClient.get("/materials/recommend", { params }));
}
