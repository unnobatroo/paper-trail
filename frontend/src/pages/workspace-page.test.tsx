import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { ThemeProvider } from "next-themes"
import { MemoryRouter } from "react-router"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { TooltipProvider } from "@/components/ui/tooltip"
import { PrefsProvider } from "@/lib/prefs"
import { WorkspacePage } from "@/pages/workspace-page"
import { candidate, row, workspace } from "@/test/fixtures"

const META = {
  deployment: "test", storage: "postgres", embed_model: "hashing", reranker: "none", search_provider: "fixture",
  llm_extraction: false, review_required: false, translation: false, language_profile_loaded: true,
  language_name: "Hungarian", glossary: [{ term: "M", meaning: "measure" }],
}

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })

/** Stub fetch like the API: returns the rows for each stage and records every write. */
function stubApi(meta: object = META) {
  const rows = [
    row({ kind: "measure", group: [candidate({ id: 1, normalized_title: "Fák ültetése" })] }),
    row({ kind: "measure", stage: "search", group: [candidate({ id: 2, normalized_title: "Napelemek", review_status: "accepted" })] }),
  ]
  const calls: { method: string; path: string; query: string }[] = []
  vi.stubGlobal("fetch", async (input: Request) => {
    const url = new URL(input.url)
    calls.push({ method: input.method, path: url.pathname, query: url.search })
    if (url.pathname === "/api/meta") return json(meta)
    if (url.pathname === "/api/jobs") return json([])
    if (url.pathname === "/api/workspace") {
      const stage = url.searchParams.get("stage") ?? "all"
      const shownRows = rows.filter((r) => stage === "all" || r.stage === stage)
      return json({ ...workspace(rows), rows: shownRows })
    }
    if (url.pathname.endsWith("/accept")) return json({ commitment_id: 10 })
    return json({ detail: "not stubbed" }, 404)
  })
  return calls
}

function renderPage(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem>
      <QueryClientProvider client={client}>
        <PrefsProvider>
          <TooltipProvider>
            <MemoryRouter initialEntries={[path]}>
              <WorkspacePage />
            </MemoryRouter>
          </TooltipProvider>
        </PrefsProvider>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

describe("WorkspacePage", () => {
  beforeEach(() => localStorage.clear())

  it("shows the stage counts and the commitments the API returns", async () => {
    stubApi()
    renderPage()
    expect(await screen.findByRole("button", { name: "Fák ültetése" })).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Napelemek" })).toBeInTheDocument()
    // the stages run along the top, each with its count
    expect(screen.getByRole("tab", { name: "To confirm 1" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "To search 1" })).toBeInTheDocument()
  })

  it("asks the server for the stage you pick, because filtering lives on the server", async () => {
    const calls = stubApi()
    renderPage()
    await screen.findByRole("button", { name: "Fák ültetése" })
    await userEvent.click(screen.getByRole("tab", { name: /^To search/ }))
    await waitFor(() => expect(screen.queryByRole("button", { name: "Fák ültetése" })).not.toBeInTheDocument())
    expect(calls.some((c) => c.path === "/api/workspace" && c.query.includes("stage=search"))).toBe(true)
  })

  it("opens the first row by itself, so the detail pane is never empty", async () => {
    stubApi()
    renderPage()
    expect(await screen.findByRole("heading", { name: /Fák ültetése/ })).toBeInTheDocument()
  })

  it("confirms with c, posting to the accept endpoint, then moves on to the next row", async () => {
    const calls = stubApi()
    renderPage()
    expect(await screen.findByRole("heading", { name: /Fák ültetése/ })).toBeInTheDocument()
    await userEvent.keyboard("c")
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/api/candidates/1/accept")).toBe(true))
    expect(await screen.findByRole("heading", { name: /Napelemek/ })).toBeInTheDocument()
  })

  it("moves down with j", async () => {
    stubApi()
    renderPage()
    await screen.findByRole("heading", { name: /Fák ültetése/ })
    await userEvent.keyboard("j")
    expect(await screen.findByRole("heading", { name: /Napelemek/ })).toBeInTheDocument()
  })

  it("asks the server for every kind, and offers no kind choice when there is only one", async () => {
    const calls = stubApi()
    renderPage()
    await screen.findByRole("button", { name: "Fák ültetése" })
    // both rows are measures: "All" plus one kind is no choice, so there is no kind filter
    expect(screen.queryByRole("tablist", { name: "Filter by type" })).not.toBeInTheDocument()
    // the kind filter lives in the client, so the server is always asked for all kinds
    expect(calls.filter((c) => c.path === "/api/workspace").every((c) => c.query.includes("type=all"))).toBe(true)
  })

  it("ignores shortcuts while typing in the search box", async () => {
    const calls = stubApi()
    renderPage()
    await screen.findByRole("button", { name: "Fák ültetése" })
    const box = screen.getByRole("searchbox", { name: "Search commitments" })
    box.focus()
    await userEvent.keyboard("jc")
    expect(box).toHaveValue("jc")
    expect(calls.filter((c) => c.method === "POST")).toEqual([])
  })

  it("is read-only until the review key is saved, when the deployment asks for one", async () => {
    const calls = stubApi({ ...META, review_required: true })
    renderPage()
    expect(await screen.findByText(/Read-only\. You can browse everything/)).toBeInTheDocument()
    // the first row opens by itself, with its decision buttons switched off
    expect(await screen.findByRole("button", { name: "Confirm" })).toBeDisabled()
    expect(screen.getByRole("button", { name: "Reject" })).toBeDisabled()
    await userEvent.keyboard("c")
    expect(calls.filter((c) => c.method === "POST")).toEqual([])
  })
})
