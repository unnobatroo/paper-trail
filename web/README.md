# Paper Trail — the frontend

This is the interface reviewers actually use. It's a Next.js app (App
Router, TypeScript, Tailwind) built on open-source pieces, and it talks
to the FastAPI backend in `../src/paper_trail` over plain REST — it
never touches Supabase directly, so no service keys ever reach the
browser. The only credential a browser may hold is the review key a
reviewer types in themselves, on deployments that enable the write gate.

## What it's built with

| What for | Library |
|---|---|
| Fetching, caching, job polling | TanStack Query |
| Forms and validation | react-hook-form + zod |
| Filters and search state | nuqs (keeps them in the URL, so views are shareable) |
| Tables | TanStack Table v9 |
| Components and app shell | shadcn/ui (Base UI + Tailwind) |
| Toasts, icons, dark mode | sonner · lucide · next-themes |

## The workspace

There is one screen. Each row is a commitment and shows where it is in
the pipeline: **to confirm** (check the promise against the strategy),
**to search** (find official sources), **to review** (confirm or reject
suggested matches), **done** or **rejected**. The filter pills above the
table carry live counts, and rows are grouped by type (objectives,
targets, measures) in collapsible sections.

The detail panel shows the quote, the suggested matches as cards you can
decide on in place, and the confirmed trail. It docks to the right from
1280 px, opens as a slide-over below that and fills the screen on phones.
Table columns drop out as the screen narrows. The old `/commitments`,
`/evidence` and `/trail` routes redirect to the matching filter.

Keyboard: `j`/`k` move, `x` selects, `c`/`r` confirm or reject, `s`
starts an evidence search, `enter` opens the panel, `/` focuses search,
⌘K opens the command palette. Bulk actions follow the stages of what you
selected.

The data side lives in `src/lib/workspace.ts` (joins candidates,
commitments, links and trail into rows) and `src/lib/use-search-jobs.ts`
(starts searches and follows them, also after a reload).

## Run it

```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL to the API
npm install
npm run dev                        # http://localhost:3000
```

The API needs to know this origin: `PAPER_TRAIL_API_ORIGINS` on the
backend should include `http://localhost:3000` (it's the default).

## Deploy it

It's a standard Vercel project — root directory `web/`, one required
environment variable (`NEXT_PUBLIC_API_URL` pointing at the hosted API),
and the Vercel domain added to `PAPER_TRAIL_API_ORIGINS` on the API side.
The long-running evidence jobs happen on the API host, so Vercel's
serverless timeouts are never a problem; the browser just polls the job
endpoint.

When the API sets `PAPER_TRAIL_REVIEW_KEY`, the top bar shows a "Review
key" dialog and reviewers enter it once per browser. Set
`NEXT_PUBLIC_REVIEW_KEY` instead only when the deployed UI itself is
private — it lands in the JS bundle where anyone can read it.

The deployed instance lives at
[paper-trail.vercel.app](https://paper-trail.vercel.app).
