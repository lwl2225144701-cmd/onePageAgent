import type { LucideIcon } from "lucide-react";

type TopTabProps = {
  icon: LucideIcon;
  label: string;
  shortLabel?: string;
  active: boolean;
  onClick: () => void;
};

export function TopTab({ icon: Icon, label, shortLabel, active, onClick }: TopTabProps) {
  return (
    <button
      className={`flex h-10 min-w-0 items-center justify-center gap-2 rounded-full px-2 transition ${
        active ? "bg-[#e6cfad] text-[#4f3d2c] shadow-[0_6px_12px_rgba(116,82,45,0.12),inset_0_1px_0_rgba(255,255,255,0.62)]" : "text-[#7f7164] hover:bg-[#fffaf3]/58"
      }`}
      onClick={onClick}
    >
      <Icon size={16} className="shrink-0" />
      <span className="hidden whitespace-nowrap md:inline">{label}</span>
      <span className="whitespace-nowrap md:hidden">{shortLabel ?? label}</span>
    </button>
  );
}
