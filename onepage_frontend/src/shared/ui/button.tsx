import { cn } from "@/shared/utils/cn";

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "ghost" | "soft";
};

export function Button({ className, variant = "primary", ...props }: ButtonProps) {
  return (
    <button
      className={cn(
        "min-h-11 rounded-full px-6 transition disabled:cursor-not-allowed disabled:opacity-60",
        variant === "primary" && "bg-gradient-to-b from-[#7c735e] to-[#585341] text-paper shadow-[0_8px_18px_rgba(76,66,52,0.2)]",
        variant === "ghost" && "border border-line bg-white/70 text-ink hover:bg-white",
        variant === "soft" && "rounded-lg border border-line bg-[#f4eadc] text-ink hover:bg-[#eadcc9]",
        className
      )}
      {...props}
    />
  );
}
