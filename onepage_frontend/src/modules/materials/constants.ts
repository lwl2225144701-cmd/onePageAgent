import type { MaterialType, TagOption } from "./types";

export const stickerEmotionTags: TagOption[] = [
  "全部",
  "人物角色",
  "生活物件",
  "食物饮品",
  "动物生物",
  "交通建筑",
  "文化历史",
  "文字符号",
  "数码科技",
  "自然天气",
  "运动娱乐",
  "医疗健康",
  "植物花草",
  "学习办公",
  "节日纪念"
].map((item) => ({
  label: item,
  value: item
}));

export const stickerStyleTags: TagOption[] = ["全部", "日系", "可爱", "装饰", "线稿", "水彩", "复古", "极简"].map((item) => ({
  label: item,
  value: item
}));

export const backgroundTags: TagOption[] = ["全部", "通用背景", "场景背景", "自然风景", "季节氛围"].map((item) => ({
  label: item,
  value: item
}));

export const collageTags: TagOption[] = ["全部", "边框框架", "标签便签", "其他拼贴", "图标符号"].map((item) => ({
  label: item,
  value: item
}));

export const categoryMap: Record<MaterialType, string[]> = {
  sticker: [
    "人物角色",
    "生活物件",
    "食物饮品",
    "动物生物",
    "交通建筑",
    "文化历史",
    "文字符号",
    "数码科技",
    "自然天气",
    "运动娱乐",
    "医疗健康",
    "植物花草",
    "学习办公",
    "节日纪念"
  ],
  background: ["通用背景", "场景背景", "自然风景", "季节氛围"],
  decoration: ["边框框架", "标签便签", "其他拼贴", "图标符号"]
};

export const typeLabels: Record<MaterialType, string> = {
  sticker: "贴图 Sticker",
  background: "背景 Background",
  decoration: "拼贴元素 Collage"
};
