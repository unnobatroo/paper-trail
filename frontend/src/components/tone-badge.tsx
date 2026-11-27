import type { ComponentProps } from "react"

import { Badge } from "@/components/ui/badge"
import { cn } from "@/lib/utils"
import type { Tone } from "@/lib/labels"

// Three looks, not seven colours: green for what is good or done, rose for what is wrong, plain for the rest.
const LOOKS = {
  good: "border-emerald-600/30 text-emerald-700 dark:text-emerald-300",
  rose: "border-destructive/40 text-destructive",
  plain: "border-border text-muted-foreground",
}
const TONES: Record<Tone, string> = {
  green: LOOKS.good,
  teal: LOOKS.good,
  red: LOOKS.rose,
  grey: LOOKS.plain,
  blue: LOOKS.plain,
  amber: LOOKS.plain,
  purple: LOOKS.plain,
}

/** A small outlined label; `title` shows as a native tooltip. */
export function ToneBadge({ tone = "grey", className, ...props }: { tone?: Tone } & ComponentProps<typeof Badge>) {
  return <Badge variant="outline" className={cn("bg-transparent", TONES[tone], className)} {...props} />
}
