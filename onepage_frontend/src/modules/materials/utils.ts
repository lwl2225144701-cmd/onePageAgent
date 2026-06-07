import type { MaterialResponse } from "@/types/backend";

export function getMaterialPreviewUrl(item: MaterialResponse) {
  return item.preview_url || item.file_url || item.raw_file_url || "";
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
  const tags = Array.isArray(item.meta_info?.tags) ? (item.meta_info?.tags as unknown[]).map(String) : [];
  const styleTags = Array.isArray(item.style_tags) ? item.style_tags.map(String) : [];
  const emotionTags = Array.isArray(item.emotion_tags) ? item.emotion_tags.map(String) : [];
  const sceneTags = Array.isArray(item.scene_tags) ? item.scene_tags.map(String) : [];
  const query = (filters.query ?? "").trim().toLowerCase();
  const selectedTag = filters.tag;

  if (filters.category && filters.category !== "全部" && category !== filters.category) {
    return false;
  }

  if (
    selectedTag &&
    selectedTag !== "全部" &&
    ![...tags, ...styleTags, ...emotionTags, ...sceneTags].some((tag) => tag.toLowerCase().includes(selectedTag.toLowerCase()))
  ) {
    return false;
  }

  if (!query) {
    return true;
  }

  return [category, item.material_type, String(item.meta_info?.display_name ?? ""), ...tags, ...styleTags, ...emotionTags, ...sceneTags].some((value) =>
    value.toLowerCase().includes(query)
  );
}
