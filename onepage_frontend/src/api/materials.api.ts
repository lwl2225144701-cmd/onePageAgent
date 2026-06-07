import { apiClient, unwrap } from "@/api/client";
import type {
  MaterialGroup,
  MaterialResponse,
  MaterialUploadSessionCreateInput,
  MaterialUploadSessionCreateResponse,
  PaginatedResponse
} from "@/types/backend";

type MaterialListParams = { type?: string; style?: string; emotion?: string; scene?: string };

async function listPaginatedMaterials(
  path: string,
  params: MaterialListParams = {},
  page = 1,
  size = 200
) {
  return unwrap<PaginatedResponse<MaterialResponse>>(apiClient.get(path, { params: { ...params, page, size } }));
}

async function listAllFromPath(path: string, params: MaterialListParams = {}) {
  const firstPage = await listPaginatedMaterials(path, params, 1);
  const totalPages = firstPage.pagination.total_pages;
  if (totalPages <= 1) {
    return firstPage;
  }

  const remainingPages = await Promise.all(
    Array.from({ length: totalPages - 1 }, (_, index) => listPaginatedMaterials(path, params, index + 2))
  );

  return {
    data: [firstPage.data, ...remainingPages.map((pageData) => pageData.data)].flat(),
    pagination: firstPage.pagination
  };
}

export function listMaterials(params: MaterialListParams = {}) {
  return listAllFromPath("/materials", params);
}

export function recommendMaterials(params: { style?: string; emotion?: string; scene?: string; weather?: string } = {}) {
  return unwrap<MaterialGroup[]>(apiClient.get("/materials/recommend", { params }));
}

export function listFavoriteMaterials(params: { type?: string } = {}) {
  return listAllFromPath("/materials/favorites", params);
}

export function listRecentMaterials(params: { type?: string } = {}) {
  return listAllFromPath("/materials/recent", params);
}

export function createMaterialUploadSession(input: MaterialUploadSessionCreateInput) {
  return unwrap<MaterialUploadSessionCreateResponse>(apiClient.post("/materials/upload/sessions", input));
}

export async function uploadMaterialParts(partUrls: string[], file: File, chunkSize: number) {
  const uploads = partUrls.map(async (url, index) => {
    const start = index * chunkSize;
    const end = Math.min(file.size, start + chunkSize);
    const chunk = file.slice(start, end);
    const response = await fetch(url, {
      method: "PUT",
      body: chunk,
      headers: {
        "Content-Type": file.type || "application/octet-stream"
      }
    });
    if (!response.ok) {
      throw new Error(`Part upload failed: ${index + 1}`);
    }
  });
  await Promise.all(uploads);
}

export function completeMaterialUploadSession(sessionId: string) {
  return unwrap<MaterialResponse>(apiClient.post("/materials/upload/sessions/complete", { session_id: sessionId }));
}

export function cancelMaterialUploadSession(sessionId: string) {
  return unwrap<{ ok: boolean }>(apiClient.delete(`/materials/upload/sessions/${sessionId}`));
}

export function setMaterialFavorite(materialId: string, isFavorite: boolean) {
  return unwrap<MaterialResponse>(apiClient.post(`/materials/${materialId}/favorite`, { is_favorite: isFavorite }));
}

export function markMaterialUsed(materialId: string) {
  return unwrap<MaterialResponse>(apiClient.post(`/materials/${materialId}/use`));
}
