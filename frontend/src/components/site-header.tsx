import type { Ref } from "react"
import { Loader2Icon } from "lucide-react"

import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import { SidebarTrigger } from "@/components/ui/sidebar"

type Props = {
  title: string
  q: string
  onQ: (q: string) => void
  searchRef: Ref<HTMLInputElement>
  /** What running jobs are doing, shown while there are any. */
  progress: string | null
}

/** The top bar: the current stage, search and background-job progress. */
export function SiteHeader({ title, q, onQ, searchRef, progress }: Props) {
  return (
    <header className="flex h-(--header-height) shrink-0 items-center gap-2 border-b px-4">
      <SidebarTrigger className="-ml-1" />
      <Separator orientation="vertical" className="mx-1 h-4 data-vertical:self-auto" />
      <h1 className="text-base font-medium whitespace-nowrap">{title}</h1>

      <div className="ml-auto flex min-w-0 items-center gap-2">
        {progress && (
          <p role="status" className="hidden items-center gap-1.5 text-sm text-muted-foreground md:flex">
            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
            {progress}
          </p>
        )}
        <Input
          ref={searchRef}
          type="search"
          aria-label="Search commitments"
          placeholder="Search commitments"
          className="min-w-0 flex-1 md:w-64 md:flex-none"
          value={q}
          onChange={(e) => onQ(e.target.value)}
        />
      </div>
    </header>
  )
}
