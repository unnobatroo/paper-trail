# Paper Trail

**Did they actually do what they promised?**

Paper Trail started with a simple frustration: councils publish big,
ambitious climate strategies, and a few years later nobody can say which
of those promises turned into anything real. The evidence is out there —
in annual reports, procurement notices, budget resolutions — but it's
scattered across official websites in PDFs and news posts that nobody has
time to cross-reference by hand.

So Paper Trail does the tedious part for you. It reads the Józsefváros
(Budapest District VIII) climate strategy, pulls out every commitment it
finds, then searches the district's official websites for pages and
documents that look like follow-through — the municipality's own site
(jozsefvaros.hu, including the participatory-budget votes), the district
developer RÉV8 (rev8.hu), and Budapest's city portal (budapest.hu). It
ranks the best candidates, quotes the passages it thinks matter, and lays
it all out for review.

And here's the part we care about most: **the software only ever
suggests.** Nothing enters the public record until a person clicks
Confirm. Every suggestion comes with its receipts — the page number, the
verbatim quote, the source URL — so you can always check where a claim
came from. If nothing was found, the tool shows a gap instead of
pretending otherwise.

See it live at [paper-trail.vercel.app](https://paper-trail.vercel.app).

## Run it yourself

```bash
git clone https://github.com/unnobatroo/paper-trail
cd paper-trail
uv sync                                                # install the backend
uv run uvicorn paper_trail.api.app:app --app-dir src   # API on :8000

cd web
npm install && npm run dev                             # interface on :3000
```

Open http://localhost:3000 and walk the three steps in the sidebar:
check the extracted commitments, find evidence for them, then read the
resulting trail. Everything works offline with stub providers — the
first real search downloads a ~220 MB open-source embedding model, and
that's the only heavyweight thing the app ever does.

## Where things stand

The production stack is boring on purpose: a Next.js frontend on Vercel,
a FastAPI service on Azure, and Supabase holding Postgres, pgvector
embeddings, and the source PDFs. Evidence searches run as durable
background jobs, so a busy or restarted server never loses your work.

## Read more

The [project wiki](https://github.com/unnobatroo/paper-trail/wiki) is
where the detail lives — how the pieces fit together, how evidence is
actually ranked, what the database looks like, and how to deploy your
own:

- [Architecture](https://github.com/unnobatroo/paper-trail/wiki/Architecture) — the moving parts and why they look this way
- [Ranking Pipeline](https://github.com/unnobatroo/paper-trail/wiki/Ranking-Pipeline) — how a commitment becomes evidence suggestions
- [Machine Learning](https://github.com/unnobatroo/paper-trail/wiki/Machine-Learning) — the models involved, and how to swap them
- [Data Layer](https://github.com/unnobatroo/paper-trail/wiki/Data-Layer) — what's stored where
- [API Reference](https://github.com/unnobatroo/paper-trail/wiki/API-Reference) — every endpoint
- [Development](https://github.com/unnobatroo/paper-trail/wiki/Development) and [Deployment](https://github.com/unnobatroo/paper-trail/wiki/Deployment) — working on it and shipping it

## Contributing

Bug reports and pull requests are welcome — [CONTRIBUTING.md](CONTRIBUTING.md)
has the ground rules (the short version: nothing may bypass human
review, and every claim needs a quotable source). Security issues go to
[SECURITY.md](SECURITY.md), and everyone is covered by the
[Code of Conduct](CODE_OF_CONDUCT.md).

## License

[GPL-3.0](LICENSE) — free to use, study, share and improve; derivatives
stay open. Copyright © 2026 Paper Trail contributors.
