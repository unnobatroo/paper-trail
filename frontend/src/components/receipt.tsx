import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** A verbatim quote from a source, with a caption saying where it comes from. */
export function Receipt({ caption, children, className }: { caption?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <figure className={cn("flex flex-col gap-1", className)}>
      {caption && <figcaption className="text-xs text-muted-foreground">{caption}</figcaption>}
      <blockquote className="border-l-2 pl-3">“{typeof children === "string" ? children.replace(/\s+/g, " ").trim() : children}”</blockquote>
    </figure>
  )
}
