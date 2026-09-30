# Paper Trail — the frontend

This is the interface reviewers actually use. It's a Next.js app (App
Router, TypeScript, Tailwind) built on open-source pieces, and it talks
to the FastAPI backend in `../src/paper_trail` over plain REST — it
never touches Supabase directly, so no keys ever reach the browser.

## What it's built with

| What for | Library |
|---|---|
| Fetching, caching, job polling | TanStack Query |
| Forms and validation | react-hook-form + zod |
| Filters and search state | nuqs (keeps them in the URL, so views are shareable) |
| Components and app shell | shadcn/ui (Base UI + Tailwind) |
| Toasts, icons, dark mode | sonner · lucide · next-themes |

The design language is a triage inbox: lists on the left, an inspector
on the right, keyboard shortcuts (`j`/`k` to move, `x` to select, `c`/`r`
to confirm/reject), and a command palette on ⌘K. Same interaction model
on both review screens, so once you've learned one queue you've learned
them all.

## Run it

```bash
cp .env.local.example .env.local   # set NEXT_PUBLIC_API_URL to the API
npm install
npm run dev                        # http://localhost:3000
```

The API needs to know this origin: `PAPER_TRAIL_API_ORIGINS` on the
backend should include `http://localhost:3000` (it's the default).

## Deploy it

It's a standard Vercel project — root directory `web/`, one environment
variable (`NEXT_PUBLIC_API_URL` pointing at the hosted API), and the
Vercel domain added to `PAPER_TRAIL_API_ORIGINS` on the API side. The
long-running evidence jobs happen on the API host, so Vercel's
serverless timeouts are never a problem; the browser just polls the job
endpoint.

The deployed instance lives at
[paper-trail.vercel.app](https://paper-trail.vercel.app).
