import type { LayoutJSON } from "@/types/backend";

export const fallbackLayout: LayoutJSON = {
  page: { width: 1080, height: 1920, background: "#fbf4e8" },
  style: { theme: "healing", font: "handwriting" },
  elements: [
    {
      type: "text",
      props: { id: "title", content: "今天的一页", x: 160, y: 150, w: 760, size: 76, align: "center", color: "#4f3d2c" },
      z_index: 40
    },
    {
      type: "date_tag",
      props: { id: "date", date: "2024.06.01 周六", x: 170, y: 285, w: 310, size: 30, color: "#8a7a68" },
      z_index: 42
    },
    {
      type: "mood_tag",
      props: { id: "mood", icon: "♡", mood: "平静", x: 710, y: 285, w: 190, size: 30, color: "#8a7a68" },
      z_index: 42
    },
    {
      type: "image",
      props: { id: "photoA", x: 160, y: 440, w: 330, h: 430, rotation: -3, opacity: 0.96 },
      z_index: 20
    },
    {
      type: "image",
      props: { id: "photoB", x: 580, y: 420, w: 330, h: 440, rotation: 5, opacity: 0.94 },
      z_index: 21
    },
    {
      type: "text",
      props: {
        id: "note",
        content: "把今天的小片段慢慢收好：天气、心情、路上的光，还有想记住的一句话。",
        x: 165,
        y: 1010,
        w: 750,
        size: 48,
        color: "#5f5146"
      },
      z_index: 30
    },
    {
      type: "text",
      props: {
        id: "quote",
        content: "愿这一页，替你留住当下的温度。",
        x: 210,
        y: 1375,
        w: 660,
        size: 38,
        align: "center",
        color: "#9a7b5f"
      },
      z_index: 31
    },
    {
      type: "sticker",
      props: { id: "stickerA", content: "✿", x: 875, y: 330, size: 66, color: "#c99566" },
      z_index: 50
    },
    {
      type: "decoration",
      props: { id: "tapeA", content: "—", x: 200, y: 390, size: 92, color: "#d8b994" },
      z_index: 49
    },
    {
      type: "decoration",
      props: { id: "sparkA", content: "✦", x: 145, y: 1235, size: 46, color: "#b7bea3" },
      z_index: 49
    },
    {
      type: "decoration",
      props: { id: "sparkB", content: "✧", x: 850, y: 1500, size: 56, color: "#d6ad8f" },
      z_index: 49
    }
  ]
};
