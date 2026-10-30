// typed client for the fastapi backend via openapi-fetch + generated api-schema.ts
// nothing here is secret: NEXT_PUBLIC_* ships in the bundle, review keys are typed in at runtime

import createClient from "openapi-fetch";
import type {components, paths} from "./api-schema";

export const API_URL =
    process.env.NEXT_PUBLIC_API_URL ??
    (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");

// ---- review key ----
// sent as X-Review-Key on mutations when PAPER_TRAIL_REVIEW_KEY is set

const LS_REVIEW_KEY = "pt-review-key";

export function getReviewKey(): string {
    if (typeof window === "undefined") return "";
    return localStorage.getItem(LS_REVIEW_KEY) ?? "";
}

export function setReviewKey(key: string) {
    if (key) localStorage.setItem(LS_REVIEW_KEY, key);
    else localStorage.removeItem(LS_REVIEW_KEY);
}

// ---- types: generated from the openapi schema, never hand-written ----
// after a backend model change:
//   uv run python scripts/ops/export_openapi.py && (cd web && npm run gen:api)

type Schemas = components["schemas"];
// stored records always have an id, python only defaults it for new rows
type Stored<T extends { id: number | null }> = Omit<T, "id"> & { id: number };

export type CandidateType = Schemas["CandidateType"];
export type ReviewStatus = Schemas["ReviewStatus"];
export type RelationshipType = Schemas["RelationshipType"];
export type Status = Schemas["Status"];
export type BudgetKind = Schemas["BudgetKind"];
export type EvidencePolarity = Schemas["EvidencePolarity"];
export type EvidenceFlag = Schemas["EvidenceFlag"];
export type Jurisdiction = Schemas["Jurisdiction"];

export type SourceDocument = Stored<Schemas["SourceDocument"]>;
// the api sends candidates with their plain-english note attached
export type PolicyCandidate = Stored<Schemas["CandidateView"]>;
export type Note = Schemas["Note"];
export type Commitment = Stored<Schemas["Commitment"]>;
export type EvidenceItem = Stored<Schemas["EvidenceItem"]>;
export type MatchFeatures = Schemas["MatchFeatures"];
export type EvidenceLink = Stored<Schemas["EvidenceLink"]>;
export type BudgetRecord = Stored<Schemas["BudgetRecord"]>;

export type LinkView = Omit<Schemas["LinkView"], "link" | "evidence" | "budgets"> & {
    link: EvidenceLink;
    evidence: EvidenceItem | null;
    budgets: BudgetRecord[];
};

export type TrailRow = Omit<Schemas["TrailRowView"], "commitment" | "evidence" | "budgets"> & {
    commitment: Commitment;
    evidence: EvidenceItem[];
    budgets: BudgetRecord[];
};

// backend types these loosely (str / object), we narrow what we read
export type JobStatus = "queued" | "running" | "done" | "failed";

export type Job = Omit<Schemas["JobOut"], "status" | "result"> & {
    status: JobStatus;
    // per-kind payload, e.g. {links, warnings} for find_evidence
    result: { links?: number; warnings?: string[] } | null;
};

export type Meta = Schemas["MetaOut"];

// ---- client ----

// readable text for anything thrown, toasts used to say "[object Object]" lol
export function errorMessage(e: unknown): string {
    return e instanceof Error ? e.message : String(e);
}

// fastapi sends 422 details as a list of {loc, msg}, flatten it
export function formatDetail(detail: unknown): string {
    if (Array.isArray(detail)) {
        return detail
            .map((d) => {
                const where = Array.isArray(d?.loc) ? d.loc.slice(1).join(".") : "";
                return where ? `${where}: ${d?.msg ?? "invalid"}` : String(d?.msg ?? d);
            })
            .join("; ");
    }
    return typeof detail === "string" ? detail : JSON.stringify(detail);
}

export class ApiError extends Error {
    constructor(
        public status: number,
        message: string,
    ) {
        super(message);
        this.name = "ApiError";
    }
}

const ORIGIN_PLACEHOLDER = "http://_pt_same_origin_";

export const client = createClient<paths>({
    baseUrl: API_URL || ORIGIN_PLACEHOLDER,
    fetch: async (request: Request) => {
        const url = request.url.startsWith(ORIGIN_PLACEHOLDER)
            ? request.url.slice(ORIGIN_PLACEHOLDER.length)
            : request.url;
        const headers = Object.fromEntries(request.headers.entries());
        const reviewKey = getReviewKey();
        if (reviewKey && request.method !== "GET") {
            headers["x-review-key"] = reviewKey;
        }
        const body = request.method !== "GET" && request.method !== "HEAD"
            ? await request.text()
            : undefined;
        try {
            return await globalThis.fetch(url, {
                method: request.method,
                headers,
                ...(body ? {body} : {}),
                // react-query cancels through request.signal, the timeout caps slow answers
                signal: AbortSignal.any([request.signal, AbortSignal.timeout(90_000)]),
            });
        } catch (e) {
            if (e instanceof DOMException && e.name === "TimeoutError") {
                throw new ApiError(
                    0,
                    "The API took too long to answer — it may be waking up. Try again in a few seconds.",
                );
            }
            if (e instanceof TypeError) {
                throw new ApiError(
                    0,
                    "Cannot reach the API — it may be down or still waking up. Try again.",
                );
            }
            throw e;
        }
    },
});

async function unwrap<T>(
    p: Promise<{ data?: unknown; error?: unknown; response: Response }>,
): Promise<T> {
    const {data, error, response} = await p;
    if (!response.ok) {
        const errObj = error as { detail?: unknown } | null | undefined;
        const detail =
            errObj && typeof errObj === "object" && "detail" in errObj && errObj.detail !== undefined
                ? formatDetail(errObj.detail)
                : response.statusText;
        throw new ApiError(response.status, detail);
    }
    return data as T;
}

export const api = {
    meta: () => unwrap<Meta>(client.GET("/api/meta")),
    healthz: () => unwrap<{ ok: boolean }>(client.GET("/healthz")),

    documents: () => unwrap<SourceDocument[]>(client.GET("/api/documents")),
    availableDocuments: () => unwrap<string[]>(client.GET("/api/documents/available")),
    ingest: (payload: {
        name: string;
        title: string;
        publisher?: string;
        url?: string;
    }) =>
        unwrap<Job>(
            client.POST("/api/documents/ingest", {
                body: {
                    name: payload.name,
                    title: payload.title,
                    publisher: payload.publisher ?? "",
                    url: payload.url ?? "",
                },
            }),
        ),

    candidates: (status?: ReviewStatus) =>
        unwrap<PolicyCandidate[]>(
            client.GET("/api/candidates", status ? {params: {query: {status}}} : {}),
        ),
    acceptCandidate: (
        id: number,
        body?: { kind?: CandidateType; title?: string; parent_id?: number | null },
    ) =>
        unwrap<{ commitment_id: number }>(
            client.POST("/api/candidates/{candidate_id}/accept", {
                params: {path: {candidate_id: id}},
                body: {
                    kind: body?.kind ?? null,
                    title: body?.title ?? null,
                    parent_id: body?.parent_id ?? null,
                },
            }),
        ),
    rejectCandidate: (id: number) =>
        unwrap<{ ok: boolean }>(
            client.POST("/api/candidates/{candidate_id}/reject", {
                params: {path: {candidate_id: id}},
            }),
        ),
    bulkCandidates: (body: {
        accept?: number[];
        reject?: number[];
        reject_rest?: boolean;
    }) =>
        unwrap<{ accepted: number; rejected: number }>(
            client.POST("/api/candidates/bulk", {
                body: {
                    accept: body.accept ?? [],
                    reject: body.reject ?? [],
                    reject_rest: body.reject_rest ?? false,
                },
            }),
        ),

    commitments: () => unwrap<Commitment[]>(client.GET("/api/commitments")),
    findEvidence: (commitmentId: number) =>
        unwrap<Job>(
            client.POST("/api/commitments/{commitment_id}/find-evidence", {
                params: {path: {commitment_id: commitmentId}},
            }),
        ),

    links: (lite = false) =>
        unwrap<LinkView[]>(
            client.GET("/api/links", lite ? {params: {query: {lite: true}}} : {}),
        ),
    link: (id: number) =>
        unwrap<LinkView>(
            client.GET("/api/links/{link_id}", {
                params: {path: {link_id: id}},
            }),
        ),
    setJurisdiction: (id: number, jurisdiction: Jurisdiction) =>
        unwrap<Commitment>(
            client.POST("/api/commitments/{commitment_id}/jurisdiction", {
                params: {path: {commitment_id: id}},
                body: {jurisdiction},
            }),
        ),
    decideLink: (id: number, accept: boolean, relationship?: RelationshipType) =>
        unwrap<{ ok: boolean }>(
            client.POST("/api/links/{link_id}/decide", {
                params: {path: {link_id: id}},
                body: {
                    decision: accept ? "accept" : "reject",
                    relationship: relationship ?? null,
                },
            }),
        ),
    bulkLinks: (body: {
        accept?: number[];
        reject?: number[];
        relationships?: Record<number, RelationshipType>;
    }) =>
        unwrap<{ accepted: number; rejected: number }>(
            client.POST("/api/links/bulk", {
                body: {
                    accept: body.accept ?? [],
                    reject: body.reject ?? [],
                    relationships: body.relationships ?? {},
                },
            }),
        ),

    trail: () => unwrap<TrailRow[]>(client.GET("/api/trail")),
    job: (id: string) =>
        unwrap<Job>(
            client.GET("/api/jobs/{job_id}", {
                params: {path: {job_id: id}},
            }),
        ),
    activeJobs: (kind: string) =>
        unwrap<Job[]>(
            client.GET("/api/jobs", {
                params: {query: {kind}},
            }),
        ),
    translate: (texts: string[]) =>
        unwrap<{ translations: string[]; disclaimer: string }>(
            client.POST("/api/translate", {
                body: {texts},
            }),
        ),
};
