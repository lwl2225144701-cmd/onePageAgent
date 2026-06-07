import type { TagOption } from "../types";

type TagLineProps = {
  label?: string;
  tags: TagOption[];
  activeTag: string;
  onSelect: (value: string) => void;
  className?: string;
};

export function TagLine({ label, tags, activeTag, onSelect, className = "" }: TagLineProps) {
  return (
    <div className={`flex items-center gap-4 ${className}`}>
      {label ? <div className="shrink-0 whitespace-nowrap text-[13px] font-medium text-[#4f4238]">{label}</div> : null}
      <div className="relative min-w-0 flex-1 overflow-hidden">
        <div className="flex snap-x gap-2 overflow-x-auto pb-1 [overscroll-behavior-x:contain] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {tags.map((tag) => (
            <button
              key={tag.value}
              className={`min-h-8 shrink-0 snap-start rounded-full border px-3.5 text-xs transition ${
                activeTag === tag.value ? "border-[#d0ad7f] bg-[#e7d0ae] text-[#4f3d2c] shadow-[0_5px_10px_rgba(111,82,51,0.10)]" : "border-[#eadcc9] bg-[#fffaf3]/70 text-[#6f6257]"
              }`}
              onClick={() => onSelect(tag.value)}
            >
              {tag.label}
            </button>
          ))}
        </div>
        <div className="pointer-events-none absolute bottom-1 right-0 top-0 w-5 bg-gradient-to-l from-[#fff8ee]/70 via-[#fff8ee]/28 to-transparent" />
      </div>
    </div>
  );
}
