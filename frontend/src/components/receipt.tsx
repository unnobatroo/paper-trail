import type { ReactNode } from "react"

import { cn } from "@/lib/utils"

/** A verbatim quote from a source, set apart in serif with a rule: the product's proof, so it should look like one. */
export function Receipt({ caption, children, className }: { caption?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <figure className={cn("flex flex-col gap-1.5 rounded-r-md border-l-2 border-primary bg-muted/50 py-2 pr-3 pl-3", className)}>
      {caption && (
        <figcaption className="text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase">{caption}</figcaption>
      )}
      <blockquote className="font-serif leading-relaxed">“{children}”</blockquote>
    </figure>
  )
}
