import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { WorkspaceTable } from "@/components/workspace-table"
import { PrefsProvider } from "@/lib/prefs"
import { candidate, row } from "@/test/fixtures"

function renderTable(over: Partial<React.ComponentProps<typeof WorkspaceTable>> = {}) {
  const props = {
    rows: [
      row({ kind: "measure", group: [candidate({ id: 1, normalized_title: "Fák ültetése", source_page: 6 })] }),
      row({ kind: "objective", group: [candidate({ id: 2, suggested_type: "objective", normalized_title: "Zöld város", source_page: 8 })] }),
    ],
    cursor: null,
    selected: new Set<number>(),
    onOpen: vi.fn(),
    onSelectMany: vi.fn(),
    ...over,
  }
  render(
    <PrefsProvider>
      <WorkspaceTable {...props} />
    </PrefsProvider>,
  )
  return props
}

describe("WorkspaceTable", () => {
  it("groups rows under one header, a collapsible group per kind in the usual order", async () => {
    renderTable()
    expect(screen.getAllByRole("table")).toHaveLength(1)
    expect(screen.getAllByRole("columnheader", { name: "Commitment" })).toHaveLength(1)
    const groups = screen.getAllByRole("button", { expanded: true }).map((b) => b.textContent)
    expect(groups).toEqual(["Objectives1", "Measures1"])

    await userEvent.click(screen.getByRole("button", { name: /Objectives/ }))
    expect(screen.queryByRole("button", { name: "Zöld város" })).not.toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Fák ültetése" })).toBeInTheDocument()
  })

  it("opens a row from its title button, which a keyboard user can reach", async () => {
    const { onOpen } = renderTable()
    await userEvent.click(screen.getByRole("button", { name: "Fák ültetése" }))
    expect(onOpen).toHaveBeenCalledWith(1)
  })

  it("marks the cursor row for assistive technology", () => {
    renderTable({ cursor: 2 })
    expect(screen.getByRole("button", { name: "Zöld város" })).toHaveAttribute("aria-current", "true")
    expect(screen.getByRole("button", { name: "Fák ültetése" })).not.toHaveAttribute("aria-current")
  })

  it("selects a row, and a whole section from its header checkbox", async () => {
    const { onSelectMany } = renderTable()
    await userEvent.click(screen.getByRole("checkbox", { name: "Select Fák ültetése" }))
    expect(onSelectMany).toHaveBeenCalledWith([1], true)
    await userEvent.click(screen.getByRole("checkbox", { name: "Select all objectives" }))
    expect(onSelectMany).toHaveBeenLastCalledWith([2], true)
  })

  it("shows stage, page and a dash for a missing goal", () => {
    renderTable()
    const cells = within(screen.getByRole("button", { name: "Zöld város" }).closest("tr")!).getAllByRole("cell")
    expect(cells.map((c) => c.textContent)).toContain("To confirm")
    expect(cells.map((c) => c.textContent)).toContain("8")
    expect(cells.at(-1)).toHaveTextContent("–")
  })

  it("says so when nothing matches", () => {
    renderTable({ rows: [] })
    expect(screen.getByText("Nothing matches these filters.")).toBeInTheDocument()
  })
})
