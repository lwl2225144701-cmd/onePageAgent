"use client";

import { useEffect, useRef, useState } from "react";
import { Heart, Plus } from "lucide-react";

import { getMaterialPreviewUrl } from "@/modules/materials/utils";
import type { MaterialResponse } from "@/types/backend";

type AssetGridProps = {
  items: MaterialResponse[];
  columns: string;
  emptyText?: string;
  variant?: "asset" | "background";
  lowCountHint?: string;
  onToggleFavorite?: (item: MaterialResponse) => void;
  onUse?: (item: MaterialResponse) => void;
};

const INITIAL_BATCH_SIZE = 120;
const BATCH_SIZE = 80;

export function AssetGrid({ items, columns, emptyText, variant = "asset", lowCountHint, onToggleFavorite, onUse }: AssetGridProps) {
  const [visibleCount, setVisibleCount] = useState(INITIAL_BATCH_SIZE);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const hasMore = visibleCount < items.length;
  const visibleItems = items.slice(0, visibleCount);

  useEffect(() => {
    setVisibleCount(INITIAL_BATCH_SIZE);
  }, [items]);

  useEffect(() => {
    if (!hasMore || !sentinelRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries[0]?.isIntersecting) return;
        setVisibleCount((current) => Math.min(current + BATCH_SIZE, items.length));
      },
      {
        rootMargin: "320px 0px"
      }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [hasMore, items.length]);

  return (
    <>
      <div className={`mt-5 grid gap-3.5 ${columns}`}>
        {items.length > 0 ? visibleItems.map((item) => <AssetCard key={item.id} item={item} variant={variant} onToggleFavorite={onToggleFavorite} onUse={onUse} />) : <EmptyState text={emptyText} />}
      </div>
      {lowCountHint && items.length > 0 && items.length <= 1 ? <LowCountHint text={lowCountHint} /> : null}
      <div ref={sentinelRef} className="h-12 w-full" aria-hidden />
    </>
  );
}

function AssetCard({
  item,
  variant,
  onToggleFavorite,
  onUse
}: {
  item: MaterialResponse;
  variant: "asset" | "background";
  onToggleFavorite?: (item: MaterialResponse) => void;
  onUse?: (item: MaterialResponse) => void;
}) {
  const category = String(item.meta_info?.category ?? "");
  const visibility = String(item.meta_info?.visibility ?? "public");
  const tags = Array.isArray(item.meta_info?.tags) ? (item.meta_info?.tags as unknown[]).map(String) : [];
  const previewUrl = getMaterialPreviewUrl(item);
  const mimeType = String(item.mime_type ?? item.meta_info?.mime_type ?? "");
  const isSvg = mimeType === "image/svg+xml" || previewUrl.endsWith(".svg");
  const formatLabel = isSvg ? "SVG" : mimeType.includes("png") ? "PNG" : mimeType.includes("jpeg") || mimeType.includes("jpg") ? "JPG" : "";
  const typeLabel = item.material_type === "background" ? "背景" : item.material_type === "decoration" ? "拼贴" : "贴图";
  const metaText = [typeLabel, formatLabel].filter(Boolean).join(" · ");
  const isBackground = variant === "background";

  return (
    <div
      role="button"
      tabIndex={0}
      className={`group relative overflow-hidden rounded-[16px] border border-[#eadcc9]/90 bg-[#fffaf3]/78 shadow-[0_9px_18px_rgba(111,82,51,0.08),inset_0_1px_0_rgba(255,255,255,0.72)] transition hover:-translate-y-0.5 hover:shadow-[0_12px_22px_rgba(111,82,51,0.12)] ${
        isBackground ? "p-4" : "p-2.5"
      }`}
      onClick={() => onUse?.(item)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onUse?.(item);
        }
      }}
    >
      <div
        className={`rounded-[12px] bg-[radial-gradient(circle_at_50%_28%,rgba(255,255,255,0.76),transparent_36%),linear-gradient(180deg,#fff8ee,#f3e3ca)] shadow-[inset_0_0_18px_rgba(255,255,255,0.48),inset_0_-8px_16px_rgba(139,98,54,0.08)] ${
          isBackground ? "aspect-[16/9] p-4" : "aspect-square p-3"
        }`}
      >
        <img
          src={previewUrl}
          alt={category || item.material_type}
          loading="lazy"
          decoding="async"
          className={`h-full w-full [content-visibility:auto] ${isBackground ? "rounded-[8px] object-cover shadow-[0_4px_10px_rgba(111,82,51,0.08)]" : "rounded-[9px] object-contain"}`}
        />
      </div>
      <div className={`mt-2 text-left text-[#6f6257] ${isBackground ? "min-h-[34px] px-1 text-[11px] leading-4" : "min-h-[32px] text-[10px] leading-4"}`}>
        <div className="truncate font-medium text-[#4f4238]">{category || item.material_type}</div>
        <div className="truncate text-[#9a8a78]">{metaText}</div>
      </div>
      {visibility === "private" ? (
        <span className="absolute left-3 top-3 rounded-full bg-[#7d6a55]/78 px-1.5 py-0.5 text-[10px] text-white">仅自己</span>
      ) : null}
      <button
        type="button"
        className={`absolute right-3 top-3 grid h-7 w-7 place-items-center rounded-full border border-white/70 shadow-[0_4px_10px_rgba(80,55,34,0.10)] ${
          item.is_favorite ? "bg-[#c9879a] text-white" : "bg-[#fffdf8]/76 text-[#8b7a68]"
        }`}
        onClick={(event) => {
          event.stopPropagation();
          onToggleFavorite?.(item);
        }}
      >
        <Heart size={14} fill={item.is_favorite ? "currentColor" : "none"} />
      </button>
      <AddBadge />
    </div>
  );
}

function LowCountHint({ text }: { text: string }) {
  return <p className="mt-3 px-1 text-center text-[12px] leading-5 text-[#a39483]">{text}</p>;
}

function EmptyState({ text }: { text?: string }) {
  return (
    <div className="col-span-full rounded-[16px] border border-dashed border-[#d8c7b2] bg-[#fffaf3]/58 px-4 py-8 text-center text-sm text-muted">
      {text || "当前无素材"}
    </div>
  );
}

function AddBadge() {
  return (
    <span className="absolute bottom-2.5 right-2.5 grid h-5 w-5 place-items-center rounded-full bg-[#caa06b] text-white shadow-[0_4px_8px_rgba(111,82,51,0.14)]">
      <Plus size={13} strokeWidth={2.5} />
    </span>
  );
}
