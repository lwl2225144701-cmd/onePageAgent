"use client";

import type { MaterialType } from "@/modules/materials/types";

type UploadVisibility = "private" | "public";

type UploadModalProps = {
  open: boolean;
  uploading: boolean;
  uploadError: string;
  uploadDone: string;
  materialType: MaterialType;
  category: string;
  categories: string[];
  tagsInput: string;
  visibility: UploadVisibility;
  file: File | null;
  onClose: () => void;
  onMaterialTypeChange: (value: MaterialType) => void;
  onCategoryChange: (value: string) => void;
  onTagsInputChange: (value: string) => void;
  onVisibilityChange: (value: UploadVisibility) => void;
  onFileChange: (file: File | null) => void;
  onSubmit: () => void;
};

export function UploadModal({
  open,
  uploading,
  uploadError,
  uploadDone,
  materialType,
  category,
  categories,
  tagsInput,
  visibility,
  file,
  onClose,
  onMaterialTypeChange,
  onCategoryChange,
  onTagsInputChange,
  onVisibilityChange,
  onFileChange,
  onSubmit
}: UploadModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="absolute inset-0 z-30 grid place-items-center bg-black/20 p-4">
      <div className="w-full max-w-[520px] rounded-xl border border-line bg-[#fff9ef] p-5 shadow-journal">
        <h3 className="text-lg font-semibold">上传素材</h3>
        <p className="mt-1 text-xs text-muted">上传后会进入新的内容分类体系，默认仅自己可见。</p>

        <div className="mt-4 grid gap-3">
          <label className="grid gap-1 text-sm">
            素材类型
            <select className="h-10 rounded-lg border border-line bg-white/80 px-3" value={materialType} onChange={(event) => onMaterialTypeChange(event.target.value as MaterialType)}>
              <option value="sticker">Sticker</option>
              <option value="background">Background</option>
              <option value="decoration">Collage</option>
            </select>
          </label>

          <label className="grid gap-1 text-sm">
            分类
            <select className="h-10 rounded-lg border border-line bg-white/80 px-3" value={category} onChange={(event) => onCategoryChange(event.target.value)}>
              {categories.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </label>

          <label className="grid gap-1 text-sm">
            标签（用英文逗号分隔）
            <input
              className="h-10 rounded-lg border border-line bg-white/80 px-3"
              placeholder="例如：插画, 旅行, 阅读"
              value={tagsInput}
              onChange={(event) => onTagsInputChange(event.target.value)}
            />
          </label>

          <label className="grid gap-1 text-sm">
            可见性
            <select className="h-10 rounded-lg border border-line bg-white/80 px-3" value={visibility} onChange={(event) => onVisibilityChange(event.target.value as UploadVisibility)}>
              <option value="private">仅自己可见</option>
              <option value="public">全体可见</option>
            </select>
          </label>

          <label className="grid gap-1 text-sm">
            选择文件
            <input
              className="h-10 rounded-lg border border-line bg-white/80 px-3 py-2"
              type="file"
              accept="image/*,.svg,image/svg+xml"
              onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>

        {uploadError ? <p className="mt-3 text-sm text-[#b64545]">{uploadError}</p> : null}
        {uploadDone ? <p className="mt-3 text-sm text-[#3f7a53]">{uploadDone}</p> : null}

        <div className="mt-5 flex justify-end gap-2">
          <button className="min-h-10 rounded-lg border border-line bg-white/75 px-4 text-sm" onClick={onClose} disabled={uploading}>
            取消
          </button>
          <button className="min-h-10 rounded-lg bg-[#7b6a54] px-4 text-sm text-white disabled:opacity-60" disabled={uploading || !file} onClick={onSubmit}>
            {uploading ? "上传中..." : "开始上传"}
          </button>
        </div>
      </div>
    </div>
  );
}
