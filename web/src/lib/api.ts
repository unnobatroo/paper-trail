/** Typed client for the Paper Trail FastAPI backend.
 *
 * Mirrors src/paper_trail/api/schemas.py + domain/enums.py.
 * The backend speaks from NEXT_PUBLIC_API_URL (browser-visible only —
 * never put secrets here).
 */

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---- enums (string values match Python exactly) ------------------------------

export type CandidateType =
  | "objective"
  | "measure"
  | "target"
  | "indicator"
  | "background"
  | "unclear";

export type ReviewStatus = "unreviewed" | "accepted" | "rejected";

export type RelationshipType =
  | "direct_implementation"
  | "supporting"
  | "budget"
  | "related_but_indirect"
  | "probably_unrelated";

export type Status =
  | "announced"
  | "planned"
  | "in_preparation"
  | "in_implementation"
  | "completed"
  | "budget_evidence"
  | "background_only"
  | "unknown";

export type BudgetKind =
  | "estimated_cost"
  | "approved_allocation"
  | "reported_expenditure";

// ---- models ------------------------------------------------------------------

export interface SourceDocument {
  id: number;
  title: string;
  publisher: string | null;
  url: string | null;
  blob_path?: string | null;
}

export interface PolicyCandidate {
  id: number;
  document_id: number;
  suggested_type: CandidateType;
  text: string;
  normalized_title: string;
  source_page: number;
  source_excerpt: string;
  code: string | null;
  excerpt_on_page: boolean | null;
  responsible_org: string | null;
  timeframe: string | null;
  deadline_year: number | null;
  unit: string | null;
  target_value: number | null;
  review_status: ReviewStatus;
}

export interface Commitment {
  id: number;
  candidate_id: number | null;
  parent_id: number | null;
  kind: CandidateType;
  title: string;
  summary: string;
  code: string | null;
  responsible_org: string | null;
  timeframe: string | null;
  deadline_year: number | null;
  unit: string | null;
  target_value: number | null;
  source_page: number | null;
  is_measurable?: boolean;
}

export interface EvidenceItem {
  id: number;
  commitment_id: number;
  url: string;
  title: string;
  publisher: string | null;
  published_on: string | null;
  snippet: string;
  organisations: string[];
  locations: string[];
  dates_mentioned: string[];
  status_hint: Status;
  status_excerpt: string | null;
}

export interface EvidenceLink {
  id: number;
  commitment_id: number;
  evidence_id: number;
  features: Record<string, number>;
  score: number;
  suggested_relationship: RelationshipType;
  reasons: string[];
  relationship: RelationshipType | null;
  review_status: ReviewStatus;
}

export interface BudgetRecord {
  id: number;
  evidence_id: number;
  kind: BudgetKind;
  amount_huf: number | null;
  amount_raw: string | null;
  fiscal_year: number | null;
  description: string;
  source_url: string;
}

export interface LinkView {
  link: EvidenceLink;
  evidence: EvidenceItem | null;
  budgets: BudgetRecord[];
}

export interface TrailRow {
  commitment: Commitment;
  evidence: EvidenceItem[];
  relationships: RelationshipType[];
  budgets: BudgetRecord[];
  status: Status;
  status_excerpt: string | null;
  gaps: string[];
}

export type JobStatus = "queued" | "running" | "done" | "failed";

export interface Job {
  id: string;
  kind: string;
  status: JobStatus;
  /** Latest progress line (overwritten as the job advances). */
  progress: string;
  /** Kind-specific payload, e.g. {links, warnings} for find_evidence. */
  result: { links?: number; warnings?: string[] } | null;
  error: string | null;
  created_at: string;
}

export interface Meta {
  storage: "supabase" | "sqlite";
  embed_model: string;
  reranker: string;
  search_provider: string;
  llm_extraction: boolean;
  translation: boolean;
}

// ---- client ------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** The review key, entered once in the UI and kept for the tab session.
 *  The API only requires it when PAPER_TRAIL_API_KEY is configured —
 *  mutating endpoints answer 401 without it, reads stay open. */
const KEY_STORAGE = "pt_review_key";

export function getReviewKey(): string {
  if (typeof window === "undefined") return "";
  return sessionStorage.getItem(KEY_STORAGE) ?? "";
}

export function setReviewKey(key: string) {
  sessionStorage.setItem(KEY_STORAGE, key);
}

export function clearReviewKey() {
  sessionStorage.removeItem(KEY_STORAGE);
}

async function req<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const key = getReviewKey();
  // The free-tier API idles out; a hung request should become a visible,
  // retryable error rather than an infinite spinner. 90s covers the worst
  // observed cold start (~60s) with headroom.
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      signal: AbortSignal.timeout(90_000),
      headers: {
        "content-type": "application/json",
        ...(key ? { authorization: `Bearer ${key}` } : {}),
        ...init?.headers,
      },
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "TimeoutError") {
      throw new ApiError(
        0,
        "The API took too long to answer — it may be waking up. Try again in a few seconds.",
      );
    }
    if (e instanceof TypeError) {
      // fetch() throws TypeError on network failure — unreadable as-is
      throw new ApiError(0, "Cannot reach the API — it may be down or still waking up. Try again.");
    }
    throw e;
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      /* non-JSON error body */
    }
    if (res.status === 401) {
      detail =
        "Review key required — unlock via the lock icon in the sidebar.";
    }
    throw new ApiError(res.status, String(detail));
  }
  return (await res.json()) as T;
}

export const api = {
  meta: () => req<Meta>("/api/meta"),
  healthz: () => req<{ ok: boolean }>("/healthz"),

  documents: () => req<SourceDocument[]>("/api/documents"),
  availableDocuments: () => req<string[]>("/api/documents/available"),
  ingest: (payload: {
    name: string;
    title: string;
    publisher?: string;
    url?: string;
  }) =>
    req<Job>("/api/documents/ingest", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  candidates: (status?: ReviewStatus) =>
    req<PolicyCandidate[]>(
      `/api/candidates${status ? `?status=${status}` : ""}`,
    ),
  acceptCandidate: (
    id: number,
    body?: { kind?: CandidateType; title?: string; parent_id?: number | null },
  ) =>
    req<{ commitment_id: number }>(`/api/candidates/${id}/accept`, {
      method: "POST",
      body: JSON.stringify(body ?? {}),
    }),
  rejectCandidate: (id: number) =>
    req<{ ok: boolean }>(`/api/candidates/${id}/reject`, { method: "POST" }),
  bulkCandidates: (body: {
    accept?: number[];
    reject?: number[];
    reject_rest?: boolean;
  }) =>
    req<{ accepted: number; rejected: number }>("/api/candidates/bulk", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  commitments: () => req<Commitment[]>("/api/commitments"),
  findEvidence: (commitmentId: number) =>
    req<Job>(`/api/commitments/${commitmentId}/find-evidence`, {
      method: "POST",
    }),

  links: (lite = false) =>
    req<LinkView[]>(`/api/links${lite ? "?lite=1" : ""}`),
  link: (id: number) => req<LinkView>(`/api/links/${id}`),
  decideLink: (id: number, accept: boolean, relationship?: RelationshipType) =>
    req<{ ok: boolean }>(`/api/links/${id}/decide`, {
      method: "POST",
      body: JSON.stringify({
        decision: accept ? "accept" : "reject",
        relationship,
      }),
    }),
  bulkLinks: (body: {
    accept?: number[];
    reject?: number[];
    relationships?: Record<number, RelationshipType>;
  }) =>
    req<{ accepted: number; rejected: number }>("/api/links/bulk", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  trail: () => req<TrailRow[]>("/api/trail"),
  job: (id: string) => req<Job>(`/api/jobs/${id}`),
  translate: (texts: string[]) =>
    req<{ translations: string[]; disclaimer: string }>("/api/translate", {
      method: "POST",
      body: JSON.stringify({ texts }),
    }),
};
