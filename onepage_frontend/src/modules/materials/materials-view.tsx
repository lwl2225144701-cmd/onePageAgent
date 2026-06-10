"use client";

import { useCallback, useEffect, useState } from "react";
import { Clock3, Heart, ImageIcon, LayoutGrid, Search, Shapes, Upload } from "lucide-react";
import {
  cancelMaterialUploadSession,
  completeMaterialUploadSession,
  createMaterialUploadSession,
  listFavoriteMaterials,
  listMaterials,
  listRecentMaterials,
  markMaterialUsed,
  recommendMaterials,
  setMaterialFavorite,
  uploadMaterialParts
} from "@/api/materials.api";
import type { MaterialGroup, MaterialResponse } from "@/types/backend";
import { AssetGrid } from "@/modules/materials/components/asset-grid";
import { MaterialPanel } from "@/modules/materials/components/material-panel";
import { TagLine } from "@/modules/materials/components/tag-line";
import { TopTab } from "@/modules/materials/components/top-tab";
import { UploadModal } from "@/modules/materials/components/upload-modal";
import { backgroundTags, categoryMap, collageTags, stickerEmotionTags, stickerStyleTags } from "@/modules/materials/constants";
import type { MaterialType } from "@/modules/materials/types";
import { matchesMaterial } from "@/modules/materials/utils";

function hasActiveFilters(filters: { query: string; category?: string; tag?: string }) {
  return Boolean(
    filters.query.trim() ||
    (filters.category && filters.category !== "全部") ||
    (filters.tag && filters.tag !== "全部")
  );
}

const materialPageStyle = {
  background:
    "radial-gradient(circle at 58% 12%, rgba(255,255,255,0.88), transparent 34%), radial-gradient(circle at 18% 78%, rgba(238,214,184,0.24), transparent 30%), linear-gradient(180deg, rgba(255,250,244,0.95), rgba(246,235,221,0.82))",
} satisfies React.CSSProperties;

export function MaterialsView() {
  const [groups, setGroups] = useState<MaterialGroup[]>([]);
  const [stickerMaterials, setStickerMaterials] = useState<MaterialResponse[]>([]);
  const [backgroundMaterials, setBackgroundMaterials] = useState<MaterialResponse[]>([]);
  const [decorationMaterials, setDecorationMaterials] = useState<MaterialResponse[]>([]);
  const [materialCounts, setMaterialCounts] = useState<Record<MaterialType, number>>({ sticker: 0, background: 0, decoration: 0 });
  const [activeType, setActiveType] = useState<MaterialType>("sticker");
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedStickerCategory, setSelectedStickerCategory] = useState("全部");
  const [selectedStickerStyle, setSelectedStickerStyle] = useState("全部");
  const [selectedBackgroundCategory, setSelectedBackgroundCategory] = useState("全部");
  const [selectedDecorationCategory, setSelectedDecorationCategory] = useState("全部");
  const [viewMode, setViewMode] = useState<"all" | "recent" | "favorites">("all");
  const [showUpload, setShowUpload] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadDone, setUploadDone] = useState("");
  const [materialType, setMaterialType] = useState<MaterialType>("sticker");
  const [category, setCategory] = useState(categoryMap.sticker[0]);
  const [tagsInput, setTagsInput] = useState("");
  const [visibility, setVisibility] = useState<"private" | "public">("private");
  const [file, setFile] = useState<File | null>(null);

  const loadData = useCallback(async () => {
    try {
      const query = searchQuery.trim() || undefined;
      const [stickers, backgrounds, decorations] = await Promise.all([
        listMaterials({
          type: "sticker",
          category: selectedStickerCategory === "全部" ? undefined : selectedStickerCategory,
          tag: selectedStickerStyle === "全部" ? undefined : selectedStickerStyle,
          query
        }),
        listMaterials({
          type: "background",
          category: selectedBackgroundCategory === "全部" ? undefined : selectedBackgroundCategory,
          query
        }),
        listMaterials({
          type: "decoration",
          category: selectedDecorationCategory === "全部" ? undefined : selectedDecorationCategory,
          query
        })
      ]);
      setStickerMaterials(stickers.data);
      setBackgroundMaterials(backgrounds.data);
      setDecorationMaterials(decorations.data);
      setMaterialCounts({
        sticker: stickers.pagination.total,
        background: backgrounds.pagination.total,
        decoration: decorations.pagination.total
      });
    } catch {
      setStickerMaterials([]);
      setBackgroundMaterials([]);
      setDecorationMaterials([]);
      setMaterialCounts({ sticker: 0, background: 0, decoration: 0 });
    }

    recommendMaterials({ style: "插画", emotion: "治愈", scene: "旅行" })
      .then(setGroups)
      .catch(() => setGroups([]));
  }, [
    searchQuery,
    selectedBackgroundCategory,
    selectedDecorationCategory,
    selectedStickerCategory,
    selectedStickerStyle
  ]);

  const loadSpecialData = useCallback(async (mode: "recent" | "favorites") => {
    try {
      const loader = mode === "recent" ? listRecentMaterials : listFavoriteMaterials;
      const [stickers, backgrounds, decorations] = await Promise.all([
        loader({ type: "sticker" }),
        loader({ type: "background" }),
        loader({ type: "decoration" })
      ]);
      setStickerMaterials(stickers.data);
      setBackgroundMaterials(backgrounds.data);
      setDecorationMaterials(decorations.data);
      setMaterialCounts({
        sticker: stickers.pagination.total,
        background: backgrounds.pagination.total,
        decoration: decorations.pagination.total
      });
    } catch {
      setStickerMaterials([]);
      setBackgroundMaterials([]);
      setDecorationMaterials([]);
      setMaterialCounts({ sticker: 0, background: 0, decoration: 0 });
    }
  }, []);

  useEffect(() => {
    if (viewMode === "all") {
      void loadData();
      return;
    }
    void loadSpecialData(viewMode);
  }, [viewMode, loadData, loadSpecialData]);

  useEffect(() => {
    setCategory(categoryMap[materialType][0]);
  }, [materialType]);

  const recommendedCounts = groups.reduce<Record<string, number>>((acc, group) => {
    acc[group.material_type] = group.items.length;
    return acc;
  }, {});

  const hasStickerFilters = hasActiveFilters({
    category: selectedStickerCategory,
    tag: selectedStickerStyle,
    query: searchQuery
  });
  const hasBackgroundFilters = hasActiveFilters({
    category: selectedBackgroundCategory,
    query: searchQuery
  });
  const hasDecorationFilters = hasActiveFilters({
    category: selectedDecorationCategory,
    query: searchQuery
  });

  const stickerVisible = viewMode === "all" ? stickerMaterials : stickerMaterials.filter((item) =>
    matchesMaterial(item, {
      category: selectedStickerCategory,
      tag: selectedStickerStyle,
      query: searchQuery
    })
  );
  const backgroundVisible = viewMode === "all" ? backgroundMaterials : backgroundMaterials.filter((item) =>
    matchesMaterial(item, {
      category: selectedBackgroundCategory,
      query: searchQuery
    })
  );
  const decorationVisible = viewMode === "all" ? decorationMaterials : decorationMaterials.filter((item) =>
    matchesMaterial(item, {
      category: selectedDecorationCategory,
      query: searchQuery
    })
  );

  async function handleToggleFavorite(item: MaterialResponse) {
    const updated = await setMaterialFavorite(item.id, !item.is_favorite);
    const sync = (items: MaterialResponse[]) => items.map((current) => (current.id === updated.id ? updated : current));
    setStickerMaterials(sync);
    setBackgroundMaterials(sync);
    setDecorationMaterials(sync);
    if (viewMode === "favorites" && !updated.is_favorite) {
      void loadSpecialData("favorites");
    }
  }

  async function handleUseMaterial(item: MaterialResponse) {
    const updated = await markMaterialUsed(item.id);
    const sync = (items: MaterialResponse[]) => items.map((current) => (current.id === updated.id ? updated : current));
    setStickerMaterials(sync);
    setBackgroundMaterials(sync);
    setDecorationMaterials(sync);
  }

  return (
    <section className="grid min-h-[calc(100dvh-112px)] place-items-center max-md:h-[calc(100dvh-120px-env(safe-area-inset-bottom))] max-md:min-h-0 max-md:items-stretch">
      <div className="material-page relative flex min-h-[690px] w-full max-w-[860px] flex-col overflow-hidden rounded-[20px] border border-line shadow-journal max-md:h-full max-md:min-h-0 max-md:max-w-none" style={materialPageStyle}>
      <div className="pointer-events-none absolute inset-0 opacity-35 [background-image:radial-gradient(rgba(118,83,52,0.13)_0.55px,transparent_0.7px),radial-gradient(rgba(255,255,255,0.62)_0.55px,transparent_0.8px)] [background-position:0_0,8px_7px] [background-size:18px_18px,22px_22px] [mix-blend-mode:multiply]" />
      <div className="relative z-10 shrink-0 bg-[#fffaf3]/74 shadow-[0_8px_18px_rgba(111,82,51,0.025)] backdrop-blur">
        <div className="flex items-start justify-between gap-4 px-5 pb-3.5 pt-5 max-lg:flex-col max-md:px-4 max-md:pt-4">
          <div className="flex items-start gap-3.5">
            <div>
              <h1 className="font-song text-[34px] font-semibold leading-none tracking-[0.03em] text-[#4F3D2C] max-md:text-[30px]">素材库</h1>
              <p className="mt-2.5 max-w-[390px] text-[13px] leading-6 text-[#6f6257]">收藏贴图、背景和拼贴元素，让每一页更有温度。</p>
            </div>
            <div className="relative mt-0.5 h-11 w-12 text-[#b7895e]/60" aria-hidden>
              <span className="absolute left-4 top-5 h-7 w-px -rotate-12 bg-current" />
              <span className="absolute left-7 top-1 h-9 w-px rotate-12 bg-current" />
              <span className="absolute left-2 top-0 text-base">✿</span>
              <span className="absolute right-2 top-4 text-base">✿</span>
            </div>
          </div>

          <div className="flex items-center gap-2.5 max-sm:w-full max-sm:flex-wrap">
            <label className="flex h-10 w-[248px] items-center gap-3 rounded-full border border-[#eadcc9] bg-[#fffdf8]/72 px-4 text-[13px] text-muted shadow-[inset_0_1px_0_rgba(255,255,255,0.76),0_6px_14px_rgba(111,82,51,0.06)] max-sm:w-full">
              <span className="sr-only">搜索素材</span>
              <input
                className="min-w-0 flex-1 bg-transparent outline-none placeholder:text-[#a79b8f]"
                placeholder="搜索贴图、背景、胶带、花朵..."
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
              />
              <Search size={17} className="text-[#6f6257]" />
            </label>
            <button
              className={`flex h-10 items-center gap-2 rounded-full border px-4 text-[13px] shadow-[0_5px_12px_rgba(111,82,51,0.05)] ${
                viewMode === "recent" ? "border-[#d0ad7f] bg-[#ead4b5] text-[#4f4238]" : "border-[#eadcc9] bg-[#fffdf8]/60 text-[#6f6257]"
              }`}
              onClick={() => setViewMode("recent")}
            >
              <Clock3 size={16} />
              最近使用
            </button>
            <button
              className={`flex h-10 items-center gap-2 rounded-full border px-4 text-[13px] shadow-[0_5px_12px_rgba(111,82,51,0.05)] ${
                viewMode === "favorites" ? "border-[#d0ad7f] bg-[#ead4b5] text-[#4f4238]" : "border-[#eadcc9] bg-[#fffdf8]/60 text-[#6f6257]"
              }`}
              onClick={() => setViewMode("favorites")}
            >
              <Heart size={16} />
              收藏夹
            </button>
            <button
              className="flex h-10 items-center gap-2 rounded-full border border-[#eadcc9] bg-[#fffdf8]/60 px-4 text-[13px] text-[#6f6257] shadow-[0_5px_12px_rgba(111,82,51,0.05)]"
              onClick={() => {
                setUploadError("");
                setUploadDone("");
                setShowUpload(true);
              }}
            >
              <Upload size={16} />
              上传素材
            </button>
            {viewMode !== "all" ? (
              <button className="flex h-10 items-center gap-2 rounded-full border border-[#eadcc9] bg-[#fffdf8]/60 px-4 text-[13px] text-[#6f6257]" onClick={() => setViewMode("all")}>
                全部素材
              </button>
            ) : null}
          </div>
        </div>

        <div className="mx-5 grid grid-cols-3 gap-1 rounded-full border border-[#eadcc9]/80 bg-[#f8eddd]/70 p-1 text-center text-sm font-semibold shadow-[inset_0_1px_0_rgba(255,255,255,0.7)] max-md:mx-4 max-md:text-[11px]">
          <TopTab icon={Shapes} label="贴图 Sticker" shortLabel="贴图" active={activeType === "sticker"} onClick={() => setActiveType("sticker")} />
          <TopTab icon={ImageIcon} label="背景 Background" shortLabel="背景" active={activeType === "background"} onClick={() => setActiveType("background")} />
          <TopTab icon={LayoutGrid} label="拼贴元素 Collage" shortLabel="拼贴" active={activeType === "decoration"} onClick={() => setActiveType("decoration")} />
        </div>
      </div>

      <div className="relative z-10 min-h-0 flex-1 overflow-y-auto overscroll-contain px-3 pb-5 pt-1.5 [scrollbar-width:none] [-webkit-overflow-scrolling:touch] [&::-webkit-scrollbar]:hidden max-md:pb-[clamp(32px,7dvh,64px)] max-md:scroll-pb-[clamp(32px,7dvh,64px)]">
        {activeType === "sticker" ? (
          <MaterialPanel
            title="贴图 Sticker"
            subtitle="小小贴纸，点亮今天的心情。"
            count={materialCounts.sticker || (hasStickerFilters ? stickerVisible.length : stickerMaterials.length || recommendedCounts.sticker || 0)}
          >
            <TagLine label="内容分类" tags={stickerEmotionTags} activeTag={selectedStickerCategory} onSelect={setSelectedStickerCategory} />
            <TagLine label="风格标签" tags={stickerStyleTags} activeTag={selectedStickerStyle} onSelect={setSelectedStickerStyle} className="mt-4" />
            <AssetGrid
              items={stickerVisible}
              columns="grid-cols-4 max-lg:grid-cols-3 max-sm:grid-cols-2"
              emptyText="当前贴图分类下还没有素材"
              onToggleFavorite={handleToggleFavorite}
              onUse={handleUseMaterial}
            />
          </MaterialPanel>
        ) : null}

        {activeType === "background" ? (
          <MaterialPanel
            title="背景 Background"
            subtitle="纸纹、网格、水彩底色，铺好这一页的氛围。"
            count={materialCounts.background || (hasBackgroundFilters ? backgroundVisible.length : backgroundMaterials.length || recommendedCounts.background || 0)}
          >
            <TagLine tags={backgroundTags} activeTag={selectedBackgroundCategory} onSelect={setSelectedBackgroundCategory} />
            <AssetGrid
              items={backgroundVisible}
              columns="grid-cols-1"
              emptyText="当前背景分类下还没有素材"
              variant="background"
              lowCountHint="继续上传更多背景纸样，让 AI 有更多氛围可选。"
              onToggleFavorite={handleToggleFavorite}
              onUse={handleUseMaterial}
            />
          </MaterialPanel>
        ) : null}

        {activeType === "decoration" ? (
          <MaterialPanel
            title="拼贴元素 Collage"
            subtitle="胶带、标签、撕纸和边框，让页面更有层次。"
            count={materialCounts.decoration || (hasDecorationFilters ? decorationVisible.length : decorationMaterials.length || recommendedCounts.decoration || 0)}
          >
            <TagLine tags={collageTags} activeTag={selectedDecorationCategory} onSelect={setSelectedDecorationCategory} />
            <AssetGrid
              items={decorationVisible}
              columns="grid-cols-4 max-lg:grid-cols-3 max-sm:grid-cols-2"
              emptyText="当前装饰分类下还没有素材"
              onToggleFavorite={handleToggleFavorite}
              onUse={handleUseMaterial}
            />
          </MaterialPanel>
        ) : null}
      </div>

      <UploadModal
        open={showUpload}
        uploading={uploading}
        uploadError={uploadError}
        uploadDone={uploadDone}
        materialType={materialType}
        category={category}
        categories={categoryMap[materialType]}
        tagsInput={tagsInput}
        visibility={visibility}
        file={file}
        onClose={() => {
          if (!uploading) setShowUpload(false);
        }}
        onMaterialTypeChange={setMaterialType}
        onCategoryChange={setCategory}
        onTagsInputChange={setTagsInput}
        onVisibilityChange={setVisibility}
        onFileChange={setFile}
        onSubmit={async () => {
          if (!file) return;
          setUploading(true);
          setUploadError("");
          setUploadDone("");
          let sessionId = "";
          try {
            const tags = tagsInput
              .split(",")
              .map((tag) => tag.trim())
              .filter(Boolean);
            const session = await createMaterialUploadSession({
              file_name: file.name,
              file_size: file.size,
              mime_type: file.type || "application/octet-stream",
              material_type: materialType,
              category,
              tags,
              visibility
            });
            sessionId = session.session_id;
            await uploadMaterialParts(session.part_urls, file, session.chunk_size);
            await completeMaterialUploadSession(session.session_id);
            await loadData();
            setActiveType(materialType);
            if (materialType === "sticker") setSelectedStickerCategory(category);
            if (materialType === "background") setSelectedBackgroundCategory(category);
            if (materialType === "decoration") setSelectedDecorationCategory(category);
            setTagsInput("");
            setFile(null);
            setUploadDone("上传成功，素材已加入素材库。");
            setShowUpload(false);
          } catch (error) {
            if (sessionId) {
              await cancelMaterialUploadSession(sessionId).catch(() => undefined);
            }
            setUploadError(error instanceof Error ? error.message : "上传失败，请重试");
          } finally {
            setUploading(false);
          }
        }}
      />
      <div className="pointer-events-none fixed inset-x-0 bottom-0 z-20 hidden h-[calc(112px+env(safe-area-inset-bottom))] bg-[linear-gradient(180deg,rgba(251,245,236,0)_0%,rgba(251,245,236,0.88)_42%,rgba(255,250,244,0.96)_100%)] max-md:block" />
      </div>
    </section>
  );
}
