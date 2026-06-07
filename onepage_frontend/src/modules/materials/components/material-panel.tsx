import type { ReactNode } from "react";

type MaterialPanelProps = {
  title: string;
  subtitle: string;
  count: number;
  children: ReactNode;
};

export function MaterialPanel({ title, subtitle, count, children }: MaterialPanelProps) {
  const countLabel = title.includes("背景") ? `${count} 张背景` : title.includes("拼贴") ? `${count} 个元素` : `${count} 个素材`;

  return (
    <section className="mb-3 rounded-[18px] border border-[#eadcc9]/20 bg-[#fffaf3]/22 px-3.5 py-4 shadow-[0_4px_12px_rgba(111,82,51,0.018),inset_0_1px_0_rgba(255,255,255,0.34)]">
      <div className="mb-4 flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-song text-[22px] font-semibold leading-none text-[#4f3d2c]">{title}</h2>
          <p className="mt-2 text-[12px] leading-5 text-[#8a7a68]">{subtitle}</p>
        </div>
        <span className="shrink-0 rounded-full bg-transparent px-1 text-[11px] text-[#a39483]">{countLabel}</span>
      </div>
      {children}
    </section>
  );
}
