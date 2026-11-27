import type { ComponentProps } from "react"

import { cn } from "@/lib/utils"

/** A keyboard key, as in "press c to confirm". */
export function Kbd({ className, ...props }: ComponentProps<"kbd">) {
  return (
    <kbd
      className={cn("rounded border bg-muted px-1 font-mono text-[0.65rem] leading-4 font-medium text-muted-foreground", className)}
      {...props}
    />
  )
}
