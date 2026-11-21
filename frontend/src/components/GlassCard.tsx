import type { HTMLAttributes, ReactNode } from "react";
import { cn } from "../lib/cn";

type Props = HTMLAttributes<HTMLDivElement> & {
  tone?: "dark" | "light";
  padding?: "none" | "sm" | "md" | "lg";
  as?: "div" | "section" | "article" | "aside";
  children: ReactNode;
};

const PAD = { none: "", sm: "p-4", md: "p-6", lg: "p-8" } as const;

export function GlassCard({ tone = "dark", padding = "md", as: Tag = "div", className, children, ...rest }: Props) {
  return (
    <Tag className={cn(tone === "light" ? "glass-light" : "glass", PAD[padding], className)} {...rest}>
      {children}
    </Tag>
  );
}
