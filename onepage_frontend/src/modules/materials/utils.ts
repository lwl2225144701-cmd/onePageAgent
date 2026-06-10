import type { MaterialResponse } from "@/types/backend";

function stringValue(value: unknown) {
  return typeof value === "string" ? value.trim() : "";
}

function apiBaseUrl() {
  return (process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api").replace(/\/+$/, "");
}

function apiOrigin() {
  try {
    return new URL(apiBaseUrl()).origin;
  } catch {
    return "";
  }
}

function isLocalFilePath(value: string) {
  return (
    value.startsWith("file:") ||
    value.startsWith("/Users/") ||
    value.startsWith("/private/") ||
    value.startsWith("/var/") ||
    value.startsWith("/tmp/") ||
    value.startsWith("/home/") ||
    /^[A-Za-z]:[\\/]/.test(value)
  );
}

function normalizeMaterialImageUrl(value: unknown) {
  const url = stringValue(value);
  if (!url || isLocalFilePath(url)) return null;
  if (/^https?:\/\//i.test(url) || url.startsWith("data:image/") || url.startsWith("blob:")) return url;
  if (url.startsWith("/api/")) {
    const origin = apiOrigin();
    return origin ? `${origin}${url}` : null;
  }
  if (url.startsWith("/materials/")) return `${apiBaseUrl()}${url}`;
  return null;
}

export function getMaterialImageUrlCandidates(item: MaterialResponse) {
  const material = item as MaterialResponse & { url?: unknown };
  const meta = (item.meta_info ?? {}) as Record<string, unknown>;
  const fallbackPreviewUrl = item.id ? `${apiBaseUrl()}/materials/${item.id}/preview` : "";
  const fallbackAssetUrl = item.id ? `${apiBaseUrl()}/materials/${item.id}/asset` : "";
  const candidates = [
    material.file_url,
    material.preview_url,
    material.raw_file_url,
    material.url,
    meta.preview_url,
    meta.raw_file_url,
    meta.file_url,
    meta.image_url,
    fallbackPreviewUrl,
    fallbackAssetUrl
  ];
  const result: string[] = [];
  for (const candidate of candidates) {
    const normalized = normalizeMaterialImageUrl(candidate);
    if (normalized && !result.includes(normalized)) {
      result.push(normalized);
    }
  }
  return result;
}

export function getMaterialImageUrl(item: MaterialResponse) {
  return getMaterialImageUrlCandidates(item)[0] ?? null;
}

export function getMaterialPreviewUrl(item: MaterialResponse) {
  return getMaterialImageUrl(item) ?? "";
}

function stringList(value: unknown) {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

export function matchesMaterial(
  item: MaterialResponse,
  filters: {
    category?: string;
    tag?: string;
    query?: string;
  }
) {
  const category = String(item.meta_info?.category ?? "");
  const tags = stringList(item.meta_info?.tags);
  const semanticTags = stringList(item.meta_info?.semantic_tags);
  const styleTags = stringList(item.style_tags);
  const emotionTags = stringList(item.emotion_tags);
  const sceneTags = stringList(item.scene_tags);
  const searchableMeta = [
    String(item.meta_info?.display_name ?? ""),
    String(item.meta_info?.filename ?? ""),
    String(item.meta_info?.sub_category ?? ""),
    String(item.meta_info?.usage_type ?? ""),
    String(item.meta_info?.target_path ?? "")
  ];
  const query = (filters.query ?? "").trim().toLowerCase();
  const selectedTag = filters.tag;

  if (filters.category && filters.category !== "全部" && category !== filters.category) {
    return false;
  }

  if (
    selectedTag &&
    selectedTag !== "全部" &&
    ![...tags, ...semanticTags, ...styleTags, ...emotionTags, ...sceneTags, ...searchableMeta].some((tag) => tag.toLowerCase().includes(selectedTag.toLowerCase()))
  ) {
    return false;
  }

  if (!query) {
    return true;
  }

  return [category, item.material_type, ...searchableMeta, ...tags, ...semanticTags, ...styleTags, ...emotionTags, ...sceneTags].some((value) =>
    value.toLowerCase().includes(query)
  );
}
