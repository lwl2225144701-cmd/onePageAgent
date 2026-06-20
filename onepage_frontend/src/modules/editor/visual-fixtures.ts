import type { LayoutElement, LayoutJSON } from "@/types/backend";

export const visualFixtureIds = [
  "watermark-center-tape",
  "watermark-center-clean",
  "short-note-focal-center",
  "text-forward-long",
  "minimal-text-only",
] as const;

export type VisualFixtureId = (typeof visualFixtureIds)[number];

const page = { width: 1080, height: 1920, background: "#FAF6F0" };

function tagElements(): LayoutElement[] {
  return [
    {
      type: "date_tag",
      props: { id: "date", role: "date", text: "2026.06.20 周六", date: "2026.06.20 周六", x: 73, y: 89, w: 367, h: 67, size: 28, font: "handwriting", color: "#7D6D5D" },
      z_index: 40,
    },
    {
      type: "mood_tag",
      props: { id: "mood", role: "mood", text: "开心", mood: "开心", icon: "😊", x: 73, y: 171, w: 205, h: 86, size: 30, font: "handwriting", color: "#BF6F81", fill: "rgba(232,180,184,0.18)", stroke: "rgba(232,180,184,0.40)", strokeWidth: 2, borderRadius: 28, paddingX: 18, paddingY: 8, iconGap: 8 },
      z_index: 40,
    },
    {
      type: "weather_tag",
      props: { id: "weather", role: "weather", text: "多云", weather: "多云", icon: "⛅", x: 300, y: 171, w: 238, h: 86, size: 30, font: "handwriting", color: "#4F7C8B", fill: "rgba(74,124,139,0.12)", stroke: "rgba(74,124,139,0.28)", strokeWidth: 2, borderRadius: 28, paddingX: 18, paddingY: 8, iconGap: 8 },
      z_index: 40,
    },
  ];
}

function textElements(long = false): LayoutElement[] {
  return [
    {
      type: "text",
      props: { id: "title", role: "title", content: long ? "慢慢整理今天写下的片段" : "被猫治愈的一天", x: 73, y: 342, w: 934, h: 230, size: 64, lineHeight: 1.4, maxLines: 2, font: "handwriting", color: "#5C4A3A", align: "left", shadow: { color: "#FFFAF2", blur: 4, opacity: 0.32, offset_x: 0, offset_y: 0 } },
      z_index: 35,
    },
    {
      type: "text",
      props: { id: "body", role: "body", content: long ? "今天写下了很多关于生活的片段。那些看似普通的小事，在认真回想的时候，也有自己的温度。想把这些细小的感受慢慢整理好，留给以后再翻开这一页的自己。" : "今天猫猫一直趴在键盘上不让我工作，最后只好抱着它一起看电影。\n虽然是很平凡的一天，但感觉被治愈了。", x: 73, y: long ? 576 : 1220, w: 934, h: long ? 998 : 442, size: long ? 34 : 42, lineHeight: 1.85, maxLines: long ? 18 : 8, font: long ? "serif" : "handwriting", color: "#5C4A3A", align: "left", shadow: { color: "#FFFAF2", blur: 3, opacity: 0.22, offset_x: 0, offset_y: 0 } },
      z_index: 35,
    },
  ];
}

function background(): LayoutElement {
  return {
    type: "image",
    props: { id: "background:bg", role: "background", material_id: "bg", url: "/visual-fixtures/background-home.svg", mimeType: "image/svg+xml", x: 0, y: 0, w: 1080, h: 1920, opacity: 0.09, fit: "watermark", objectPosition: "center", visualBBox: { x: 0, y: 0, w: 1, h: 1 }, cornerRadius: 0 },
    z_index: 1,
  };
}

function focal(): LayoutElement {
  return {
    type: "sticker",
    props: { id: "focal:cat", role: "focal_sticker", material_id: "cat", url: "/visual-fixtures/cat-focal.svg", mimeType: "image/svg+xml", x: 296, y: 618, w: 487, h: 488, opacity: 1, fit: "contain", objectPosition: "center", visualBBox: { x: 0.1, y: 0.08, w: 0.8, h: 0.84 }, cornerRadius: 24 },
    z_index: 22,
  };
}

function tape(): LayoutElement {
  return {
    type: "decoration",
    props: { id: "tape:flower", role: "tape", material_id: "tape", url: "/visual-fixtures/flower-tape.svg", mimeType: "image/svg+xml", x: 49, y: 610, w: 983, h: 37, rotation: -1, opacity: 1, fit: "contain", objectPosition: "center", visualBBox: { x: 0, y: 0, w: 1, h: 1 }, cornerRadius: 8 },
    z_index: 18,
  };
}

export function getVisualFixture(id: VisualFixtureId): LayoutJSON {
  const common = [...tagElements()];
  let elements: LayoutElement[];
  let templateId: string;
  if (id === "watermark-center-tape") {
    templateId = "watermark_center_tape";
    elements = [background(), tape(), focal(), ...textElements(), ...common];
  } else if (id === "watermark-center-clean") {
    templateId = "watermark_center_clean";
    elements = [background(), focal(), ...textElements(), ...common];
  } else if (id === "short-note-focal-center") {
    templateId = "short_note_focal_center";
    elements = [focal(), ...textElements(), ...common];
  } else if (id === "text-forward-long") {
    templateId = "text_forward_background";
    elements = [background(), ...textElements(true), ...common];
  } else {
    templateId = "minimal_text_only";
    elements = [...textElements(), ...common];
  }
  return {
    meta: { layout_engine: "v2", engine_version: "2.0.0", template_id: templateId, template_locked: true, task_id: `visual-${id}`, build_commit: "visual-fixture" },
    page: { ...page },
    elements,
    style: { font: "handwriting", page_border: "#E5D8C7", page_border_width: 3, page_border_inset: 24, template_id: templateId },
  };
}
