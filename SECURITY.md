# Security Policy

## Supported versions

The `main` branch is supported. The project is pre-1.0; security fixes
land on `main` and are noted in the release notes.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately via GitHub's private vulnerability reporting:

- <https://github.com/unnobatroo/paper-trail/security/advisories/new>

Include: what you found, how to reproduce it, and the impact you see.
You will get an acknowledgement within a few days and a credited advisory
when the fix ships.

## Scope notes

Things that matter most for this project:

- **Secrets handling.** The Supabase service key, Jina and HF tokens must
  never reach the browser, logs, or git. If you find a path where they
  could leak, that is a reportable bug.
- **Outbound fetching.** The app fetches URLs from an allowlist
  (jozsefvaros.hu, rev8.hu, budapest.hu). A bug that lets untrusted input
  widen the allowlist or smuggle requests elsewhere (SSRF) is reportable.
- **Untrusted content.** Fetched HTML/PDF text and LLM output flow into
  the UI and database — injection paths (XSS in rendered pages, SQL via
  crafted text) are reportable.
- **Data integrity.** Routes that bypass human review of
  `review_status` would violate the project's core guarantee.

## Out of scope

- Vulnerabilities in upstream dependencies without a demonstrated exploit
  path through Paper Trail (do open a regular issue to bump the dep).
- Content disagreements (e.g. a commitment's status hint) — those are
  domain decisions for reviewers, not security bugs.
