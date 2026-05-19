import type { LayoutJSON } from "@/types/backend";

export const fallbackLayout: LayoutJSON = {
  page: { width: 1080, height: 1920, background: "#fffaf4" },
  style: { theme: "healing", font: "handwriting" },
  elements: [
    {
      type: "text",
      props: { id: "title", content: "海边的\n治愈时光", x: 320, y: 120, w: 430, size: 86, align: "center", color: "#332b22" },
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
        content: "今天去了海边，阳光很温柔，海风微咸。和朋友一起散步、拍照，度过了一个轻松治愈的周末～",
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
