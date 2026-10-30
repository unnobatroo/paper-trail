# Security Policy

## Reporting a problem

Please don't open a public issue for security problems — use GitHub's
private reporting instead:

<https://github.com/unnobatroo/paper-trail/security/advisories/new>

Tell us what you found, how to trigger it, and what you think it could
lead to. We'll acknowledge it within a few days, and you'll be credited
in the advisory when the fix ships.

`main` is the only supported branch — the project is pre-1.0 and fixes
land there.

## What we care about most

- **Leaked secrets.** Database passwords, the review key and model or API
  tokens must never end up in the browser, in logs, or in git. If you find a path
  where they could, that's a reportable bug.
- **Escaped fetching.** The app only ever fetches domains in its official
  source registry. Anything that lets untrusted input widen that list or
  send requests elsewhere (including private addresses) is reportable.
- **Untrusted content.** Fetched pages and PDF text flow into the UI
  and the database — XSS or injection through crafted content is
  reportable.
- **Skipped review.** Any route that lets pipeline output become part
  of the record without a human approving it breaks the project's core
  promise, and we want to know immediately.
- **Write-gate bypass.** When `REVIEW_KEY` is set, every
  mutating endpoint must require the `X-Review-Key` header — a route
  that skips the check is reportable. The key is a shared secret, not
  authentication; treat it accordingly. With the variable unset, open
  review is the documented default, not a bug.

## What's probably not a security issue

- Vulnerabilities in dependencies without a demonstrated exploit path
  through Paper Trail — a regular issue asking us to bump the dep is
  fine.
- Disagreement with a status hint or a suggested relationship. Those are
  review decisions, and a human always has the final say anyway.
