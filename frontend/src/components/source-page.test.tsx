import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"

import { SourcePage } from "@/components/source-page"

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } })

function renderPage(reply: () => Response, pdfUrl: string | null = "https://city.example/plan.pdf") {
  vi.stubGlobal("fetch", async () => reply())
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <SourcePage candidateId={7} pdfUrl={pdfUrl ?? undefined} page={6} />
    </QueryClientProvider>,
  )
}

describe("SourcePage", () => {
  it("shows the page the API drew, with one marker per rectangle", async () => {
    const { container } = renderPage(() =>
      json({
        page: 6,
        found: true,
        image_url: "/api/documents/1/pages/6/image",
        boxes: [
          { x: 0.1, y: 0.2, w: 0.8, h: 0.02 },
          { x: 0.1, y: 0.22, w: 0.4, h: 0.02 },
        ],
      }),
    )
    const image = await screen.findByRole("img", { name: "Page 6 of the strategy" })
    expect(image).toHaveAttribute("src", "/api/documents/1/pages/6/image")
    const markers = container.querySelectorAll("[data-slot=highlight]")
    expect(markers).toHaveLength(2)
    expect(markers[0]).toHaveStyle({ left: "10%", top: "20%", width: "80%" })
    expect(screen.queryByRole("note")).not.toBeInTheDocument()
  })

  it("says so when the quote's words are not in the page text, instead of marking a guess", async () => {
    const { container } = renderPage(() => json({ page: 6, found: false, boxes: [], image_url: "/x" }))
    expect(await screen.findByRole("note")).toHaveTextContent("none are marked")
    expect(container.querySelectorAll("[data-slot=highlight]")).toHaveLength(0)
  })

  it("falls back to the strategy's own viewer when the page can't be drawn", async () => {
    renderPage(() => json({ detail: "could not read the source page" }, 502))
    expect(await screen.findByTitle("The strategy PDF, page 6")).toHaveAttribute(
      "src",
      expect.stringContaining("https://city.example/plan.pdf#page=6"),
    )
  })

  it("shows nothing at all when it can't be drawn and the strategy has no address", async () => {
    const { container } = renderPage(() => json({ detail: "no address" }, 404), null)
    await vi.waitFor(() => expect(container).toBeEmptyDOMElement())
  })
})
