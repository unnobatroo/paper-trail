import { ExternalLinkIcon } from "lucide-react"

/** The strategy's own page, from the source PDF, so a quote can be checked where it was written. */
export function SourceFrame({ url, page }: { url: string; page: number }) {
  const link = `${url}#page=${page}`
  const src = `${link}&view=FitH&navpanes=0&toolbar=0`
  return (
    <section aria-label={`Source page ${page}`} className="flex min-h-0 flex-1 flex-col gap-1.5">
      <div className="flex items-baseline justify-between text-[0.7rem] font-medium tracking-wide text-muted-foreground uppercase">
        <span>Source · page {page}</span>
        <a href={link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 underline-offset-4 hover:underline">
          Open in a new tab<span className="sr-only"> (opens in a new tab)</span>
          <ExternalLinkIcon className="size-3" aria-hidden="true" />
        </a>
      </div>
      <iframe
        title={`The strategy PDF, page ${page}`}
        src={src}
        loading="lazy"
        referrerPolicy="no-referrer"
        className="min-h-96 w-full flex-1 border bg-muted"
      />
    </section>
  )
}
