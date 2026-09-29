# Paper Trail — web frontend

The product UI for Paper Trail. Next.js (App Router) + TypeScript +
Tailwind + shadcn/ui on top of the FastAPI backend in `../src/paper_trail`.

Open-source stack:

| Concern | Library |
|---|---|
| Data fetching, caching, job polling | TanStack Query |
| Forms + validation | react-hook-form + zod |
| Filter/search state | nuqs (URL-synced) |
| UI primitives | shadcn/ui (Base UI + Tailwind) |
| Toasts / icons / theme | sonner · lucide · next-themes |

## Run

```bash
cp .env.local.example .env.local   # NEXT_PUBLIC_API_URL — the FastAPI URL
npm install
npm run dev                        # http://localhost:3000
```

The backend must allow this origin via `PAPER_TRAIL_API_ORIGINS`
(default `http://localhost:3000`).

## Deploy

Vercel: root directory `web/`, env var `NEXT_PUBLIC_API_URL` pointing at
the hosted API; add the Vercel origin to `PAPER_TRAIL_API_ORIGINS` on the
API side. The long-running evidence jobs run on the API host, not on
Vercel — see the Deployment wiki page.
