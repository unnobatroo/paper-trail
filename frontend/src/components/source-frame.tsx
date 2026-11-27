/** The strategy's own page, from the source PDF, so a quote can be checked where it was written. */
export function SourceFrame({ url, page }: { url: string; page: number }) {
  const src = `${url}#page=${page}&view=FitH&navpanes=0&toolbar=0`
  return (
    <section aria-label={`Source page ${page}`} className="flex min-h-0 flex-1 flex-col">
      <iframe
        title={`The strategy PDF, page ${page}`}
        src={src}
        loading="lazy"
        referrerPolicy="no-referrer"
        className="min-h-96 w-full flex-1 rounded-xl bg-surface ring-1 ring-border"
      />
    </section>
  )
}
