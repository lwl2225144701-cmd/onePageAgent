import type { MaterialType, TagOption } from "./types";

export const stickerEmotionTags: TagOption[] = [
  { label: "全部", value: "全部" },
  { label: "动物", value: "动物" },
  { label: "花草", value: "花草" },
  { label: "天气自然", value: "天气自然" },
  { label: "爱心星星", value: "爱心星星" },
  { label: "人物场景", value: "人物场景" },
  { label: "小物件", value: "小物件" },
  { label: "节日符号", value: "节日符号" }
];

export const stickerStyleTags: TagOption[] = ["全部", "线稿", "手绘", "插画", "装饰", "复古", "可爱", "极简"].map((item) => ({
  label: item,
  value: item
}));

export const backgroundTags: TagOption[] = ["全部", "纸张纹理", "网格线条", "牛皮纸", "水彩", "留白底", "森系", "海边", "雨天"].map((item) => ({
  label: item,
  value: item
}));

export const collageTags: TagOption[] = ["全部", "边框", "标签", "丝带", "框架", "分隔线", "角标", "装饰花纹"].map((item) => ({
  label: item,
  value: item
}));

export const categoryMap: Record<MaterialType, string[]> = {
  sticker: ["动物", "花草", "天气自然", "爱心星星", "人物场景", "小物件", "节日符号"],
  background: ["纸张纹理", "网格线条", "牛皮纸", "水彩", "留白底", "森系", "海边", "雨天"],
  decoration: ["边框", "标签", "丝带", "框架", "分隔线", "角标", "装饰花纹"]
};

export const typeLabels: Record<MaterialType, string> = {
  sticker: "贴图 Sticker",
  background: "背景 Background",
  decoration: "拼贴元素 Collage"
};
