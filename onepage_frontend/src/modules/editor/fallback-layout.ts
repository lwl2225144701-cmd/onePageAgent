import type { LayoutJSON } from "@/types/backend";

export const fallbackLayout: LayoutJSON = {
  page: { width: 1080, height: 1920, background: "#fffaf4" },
  style: { theme: "healing", font: "handwriting" },
  elements: [
    {
      type: "text",
      props: { id: "title", content: "生成中的标题", x: 320, y: 120, w: 430, size: 72, align: "center", color: "#332b22" },
      z_index: 40
    },
    {
      type: "image",
      props: { id: "photoA", x: 150, y: 440, w: 320, h: 430, rotation: -2 },
      z_index: 20
    },
    {
      type: "image",
      props: { id: "photoB", x: 560, y: 420, w: 330, h: 450, rotation: 9 },
      z_index: 21
    },
    {
      type: "text",
      props: {
        id: "note",
        content: "这里会显示你的生成结果",
        x: 150,
        y: 1080,
        w: 780,
        size: 48,
        color: "#4b4035"
      },
      z_index: 30
    },
    {
      type: "sticker",
      props: { id: "stickerA", content: "✿", x: 890, y: 330, size: 72, color: "#c99566" },
      z_index: 50
    }
  ]
};
