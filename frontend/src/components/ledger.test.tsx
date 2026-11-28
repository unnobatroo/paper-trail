import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { beforeEach, describe, expect, it, vi } from "vitest"

import { Ledger, folio } from "@/components/ledger"
import { PrefsProvider } from "@/lib/prefs"
import { candidate, row } from "@/test/fixtures"

function renderLedger(over: Partial<React.ComponentProps<typeof Ledger>> = {}) {
  const props = {
    rows: [
      row({ id: 1, kind: "objective", group: [candidate({ id: 1, suggested_type: "objective", normalized_title: "Zöld város", source_page: 8, source_excerpt: "Stratégiai cél: zöld város" })] }),
      row({ id: 2, kind: "measure", group: [candidate({ id: 2, normalized_title: "Fák ültetése", source_page: 6 }), candidate({ id: 3, normalized_title: "Fák ültetése", source_page: 138 })] }),
    ],
    showStage: false,
    cursor: null,
    selected: new Set<number>(),
    onOpen: vi.fn(),
    onSelectMany: vi.fn(),
    ...over,
  }
  render(
    <PrefsProvider>
      <Ledger {...props} />
    </PrefsProvider>,
  )
  return props
}

describe("Ledger", () => {
  beforeEach(() => localStorage.clear())

  it("is one table with one header, listing rows in the order given", () => {
    renderLedger()
    expect(screen.getAllByRole("table")).toHaveLength(1)
    expect(screen.getAllByRole("columnheader", { name: "Commitment" })).toHaveLength(1)
    const titles = screen.getAllByRole("button", { name: /ültetése|város/ }).map((b) => b.textContent)
    expect(titles).toEqual(["Zöld város", "Fák ültetése"])
  })

  it("cites the page of each row, and every page of a repeated passage", () => {
    renderLedger()
    expect(folio(renderedRow(1))).toBe("p. 8")
    expect(folio(renderedRow(2))).toBe("p. 6, 138")
  })

  it("shows the quote under the title", () => {
    renderLedger()
    expect(screen.getByText("Stratégiai cél: zöld város")).toBeInTheDocument()
  })

  it("opens a row from its title, which a keyboard user can reach", async () => {
    const { onOpen } = renderLedger()
    await userEvent.click(screen.getByRole("button", { name: "Fák ültetése" }))
    expect(onOpen).toHaveBeenCalledWith(2)
  })

  it("marks the cursor row for assistive technology", () => {
    renderLedger({ cursor: 1 })
    expect(screen.getByRole("button", { name: "Zöld város" })).toHaveAttribute("aria-current", "true")
    expect(screen.getByRole("button", { name: "Fák ültetése" })).not.toHaveAttribute("aria-current")
  })

  it("selects a row, and every shown row from the header box", async () => {
    const { onSelectMany } = renderLedger()
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Fák ültetése" }))
    expect(onSelectMany).toHaveBeenCalledWith([2], true)
    await userEvent.click(screen.getByRole("checkbox", { name: "Select all shown" }))
    expect(onSelectMany).toHaveBeenLastCalledWith([1, 2], true)
  })

  it("treats a click on the cell around a checkbox as a click on the box, a bigger target", async () => {
    const { onSelectMany, onOpen } = renderLedger()
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Fák ültetése" }).closest("td")!)
    expect(onSelectMany).toHaveBeenCalledWith([2], true)
    expect(onOpen).not.toHaveBeenCalled()
  })

  it("names the stage on each row only when stages are mixed", () => {
    renderLedger({ showStage: true })
    const cells = within(screen.getByRole("button", { name: "Zöld város" }).closest("tr")!).getAllByRole("cell")
    expect(cells.map((c) => c.textContent)).toContain("To confirm")
  })

  it("says so when nothing matches", () => {
    renderLedger({ rows: [] })
    expect(screen.getByText("Nothing matches these filters.")).toBeInTheDocument()
  })

  it("does not repeat a quote that is only the title again", () => {
    renderLedger({
      rows: [row({ id: 5, title: "Zöld város", group: [candidate({ id: 5, normalized_title: "Zöld város", source_excerpt: "Zöld város" })] })],
    })
    expect(screen.getAllByText("Zöld város")).toHaveLength(1)
  })

  it("starts the evidence search from a 'to search' row without opening it", async () => {
    const onSearch = vi.fn()
    const onOpen = vi.fn()
    renderLedger({
      rows: [row({ id: 7, stage: "search", group: [candidate({ id: 7, normalized_title: "Napelemek" })] })],
      onSearch,
      onOpen,
    })
    await userEvent.click(screen.getByRole("button", { name: "Find evidence" }))
    expect(onSearch).toHaveBeenCalledOnce()
    expect(onOpen).not.toHaveBeenCalled()
  })
})

function renderedRow(id: number) {
  return row({
    id,
    group:
      id === 1
        ? [candidate({ id: 1, source_page: 8 })]
        : [candidate({ id: 2, source_page: 6 }), candidate({ id: 3, source_page: 138 })],
  })
}
