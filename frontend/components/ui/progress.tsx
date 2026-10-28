import * as React from "react";

import { cn } from "@/lib/utils";

export function Progress({
  value = 0,
  className,
  barClassName,
}: {
  value?: number;
  className?: string;
  barClassName?: string;
}) {
  const clamped = Math.min(100, Math.max(0, value));
  return (
    <div className={cn("h-1.5 w-full overflow-hidden rounded-full bg-white/10", className)}>
      <div
        className={cn(
          "h-full rounded-full bg-gradient-to-r from-twitch to-[#e879ff] transition-[width] duration-500",
          barClassName,
        )}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
