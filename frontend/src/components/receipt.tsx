import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** A verbatim quote from a source, set on its own inset surface. */
export function Receipt({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <blockquote className={cn("layer-surface type-body px-4 py-3", className)}>
      “{typeof children === "string" ? children.replace(/\s+/g, " ").trim() : children}”
    </blockquote>
  )
}
