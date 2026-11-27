import createClient from "openapi-fetch"

import type { components, paths } from "./schema"

export type Schemas = components["schemas"]
export type WorkspaceRow = Schemas["WorkspaceRow"]
export type WorkspaceOut = Schemas["WorkspaceOut"]
export type Candidate = Schemas["CandidateView"]
export type Commitment = Schemas["Commitment"]
export type LinkView = Schemas["LinkView"]
export type TrailRow = Schemas["TrailRow"]
export type Meta = Schemas["MetaOut"]
export type Job = Schemas["JobOut"]

export const REVIEW_KEY = "paper-trail.review-key"

/** A typed client for the REST API, generated from its OpenAPI schema. */
export const api = createClient<paths>({
  baseUrl: window.location.origin,
  // Look fetch up on each call, not once at import, so tests can stub it.
  fetch: (request) => globalThis.fetch(request),
})

// Writes need the shared review key when the deployment sets one.
api.use({
  onRequest({ request }) {
    const key = localStorage.getItem(REVIEW_KEY)
    if (key) request.headers.set("x-review-key", key)
    return request
  },
})

/** Turn an API error body into a readable message. */
export function errorMessage(error: unknown): string {
  const detail = (error as { detail?: unknown } | undefined)?.detail
  if (typeof detail === "string") return detail
  if (Array.isArray(detail)) return detail.map((d) => d?.msg ?? String(d)).join("; ")
  return "Something went wrong"
}

/** Unwrap an openapi-fetch result: return the data or throw the API's message. */
export function unwrap<T>(result: { data?: T; error?: unknown }): T {
  if (result.error !== undefined || result.data === undefined) throw new Error(errorMessage(result.error))
  return result.data
}
