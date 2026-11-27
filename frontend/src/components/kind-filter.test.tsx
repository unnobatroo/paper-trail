import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"

import { KindFilter } from "@/components/kind-filter"

describe("KindFilter", () => {
  it("offers each kind that has rows, with its count, and the total", () => {
    render(<KindFilter counts={{ objective: 3, measure: 2 }} kind="all" onKind={vi.fn()} />)
    expect(screen.getByRole("tab", { name: "All 5" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Objectives 3" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Measures 2" })).toBeInTheDocument()
    expect(screen.queryByRole("tab", { name: /Targets/ })).not.toBeInTheDocument()
  })

  it("reports the kind that was clicked", async () => {
    const onKind = vi.fn()
    render(<KindFilter counts={{ objective: 3, measure: 2 }} kind="all" onKind={onKind} />)
    await userEvent.click(screen.getByRole("tab", { name: "Measures 2" }))
    expect(onKind).toHaveBeenLastCalledWith("measure")
  })

  it("says nothing when there is only one kind to choose from, but still shows what is passed in", () => {
    const { container } = render(<KindFilter counts={{ measure: 4 }} kind="all" onKind={vi.fn()} />)
    expect(container).toBeEmptyDOMElement()
    render(
      <KindFilter counts={{ measure: 4 }} kind="all" onKind={vi.fn()}>
        <span>2 selected</span>
      </KindFilter>,
    )
    expect(screen.getByText("2 selected")).toBeInTheDocument()
    expect(screen.queryByRole("tablist")).not.toBeInTheDocument()
  })
})

describe("KindFilter with a kind already chosen", () => {
  it("stays, even if only one kind is left, so the choice can be undone", () => {
    render(<KindFilter counts={{ objective: 4 }} kind="measure" onKind={vi.fn()} />)
    expect(screen.getByRole("tab", { name: "All 4" })).toBeInTheDocument()
  })
})
